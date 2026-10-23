#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
"""Run isolated diagnosis arms and the unchanged upstream benchmark judge."""
from __future__ import annotations

import argparse
import copy
import contextlib
import fcntl
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


SKILLS = ("orchestrator-skill", "collect-skill", "eval-skill", "trace-skill", "metric-skill")
SOURCES = ("benchmark-yeswecann", "benchmark-DTS", "benchmark-ISSUE", "benchmark-wiki")


@contextlib.contextmanager
def diagnosis_lock(output):
    """Serialize runners that share one output directory and its workspaces."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    path = output / ".diagnosis.lock"
    stream = path.open("a+")
    try:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another diagnosis process is active for this output") from exc
        yield stream
    finally:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class ArchiveParts(io.RawIOBase):
    def __init__(self, paths):
        self.paths = iter(paths)
        self.current = None

    def readable(self):
        return True

    def readinto(self, target):
        while True:
            if self.current is None:
                path = next(self.paths, None)
                if path is None:
                    return 0
                self.current = path.open("rb")
            size = self.current.readinto(target)
            if size:
                return size
            self.current.close()
            self.current = None

    def close(self):
        if self.current:
            self.current.close()
        super().close()


def prepare_case(source, destination):
    """Copy only input.json and raw logs; never expose gold or previous reports."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError("Case workspace already exists: " + str(destination))
    destination.mkdir(parents=True)
    if (source / "input.json").is_symlink():
        raise ValueError("Symlink input is not supported")
    shutil.copy2(source / "input.json", destination / "input.json")
    logs = source / "log"
    if logs.is_dir():
        if logs.is_symlink() or any(path.is_symlink() for path in logs.rglob("*")):
            raise ValueError("Symlink logs are not supported")
        shutil.copytree(logs, destination / "log")
    else:
        parts = [source / "log.tar.gz"] if (source / "log.tar.gz").is_file() else sorted(source.glob("log.tar.gz.part*"))
        if not parts or any(path.is_symlink() for path in parts):
            raise ValueError("Missing or unsafe log archive: " + source.name)
        if len(parts) > 1 and [path.name for path in parts] != ["log.tar.gz.part%02d" % n for n in range(len(parts))]:
            raise ValueError("Non-contiguous log archive parts: " + source.name)
        with io.BufferedReader(ArchiveParts(parts)) as stream, tarfile.open(fileobj=stream, mode="r|gz") as archive:
            for member in archive:
                target = (destination / member.name).resolve()
                if not target.is_relative_to(destination.resolve()) or not (member.isfile() or member.isdir()):
                    raise ValueError("Unsafe log archive member: " + member.name)
                if not target.is_relative_to((destination / "log").resolve()):
                    raise ValueError("Archive member outside log/: " + member.name)
                archive.extract(member, destination, filter="data")


def fingerprint(root):
    checksum = hashlib.sha256()
    for skill in SKILLS:
        for path in sorted((root / skill).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and "tests" not in path.parts:
                checksum.update(path.relative_to(root).as_posix().encode())
                checksum.update(path.read_bytes())
    return checksum.hexdigest()


def copy_skills(source, destination):
    for name in SKILLS:
        shutil.copytree(source / name, destination / name,
                        ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))


def discard_workspace(workspace, output):
    workspace, output = Path(workspace).absolute(), Path(output).absolute()
    if not workspace.is_relative_to(output):
        raise ValueError("Workspace is outside the experiment output")
    relative = workspace.relative_to(output)
    if (len(relative.parts) != 4 or relative.parts[0] not in ("base", "original", "fixed") or
            relative.parts[1] not in SOURCES or relative.parts[2] != "workspaces"):
        raise ValueError("Refusing to remove a non-workspace directory")
    for candidate in (workspace, *workspace.parents):
        if candidate == output:
            break
        if candidate.is_symlink():
            raise ValueError("Refusing to remove a symlinked workspace path")
    if workspace.exists():
        shutil.rmtree(workspace)


def summarize(rows, expected):
    scored = [row for row in rows if row.get("status") == "judged"]
    score_sum = sum(row["score"] for row in scored)
    mean = score_sum / expected if expected else 0
    return {"expected": expected, "scored": len(scored),
            "coverage": len(scored) / expected if expected else 0,
            "mean_all_cases": round(mean, 4),
            "mean_scored_cases": round(score_sum / len(scored), 4) if scored else 0,
            "accepted": len(scored) == expected and mean > 85}


def select_audited(items, audit, policy):
    decisions = {}
    for row in audit["cases"]:
        key = (row.get("source", audit.get("dataset")), row["case_id"])
        if key in decisions or row.get("decision") not in ("include", "exclude", "review"):
            raise ValueError("Duplicate or invalid audit decision: " + str(key))
        if not row.get("reason", "").strip():
            raise ValueError("Audit decision needs an explicit reason: " + str(key))
        decisions[key] = dict(row, source=key[0])
    selected, records = [], []
    for source, path in items:
        key = (source, path.name)
        if key not in decisions:
            raise ValueError("Audit is missing case: " + str(key))
        row = decisions[key]
        records.append(row)
        if (policy == "include-only" and row["decision"] == "include" or
                policy == "review-only" and row["decision"] == "review" or
                policy == "all-nonexcluded" and row["decision"] != "exclude"):
            selected.append((source, path))
    return selected, records


def score_case(case_path, result_dir, judge, run_id=None):
    """Score only this run's successful result; upstream legacy fallback is forbidden."""
    case_result = result_dir / case_path.name
    run_path, md_path = case_result / "run.json", case_result / "result.md"
    missing = {"case_id": case_path.name, "status": "no_result", "score": 0}
    if not run_path.is_file() or not md_path.is_file():
        return missing
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run.get("status") != "done" or (run_id is not None and run.get("run_id") != run_id):
        return missing
    md_hash = hashlib.sha256(md_path.read_bytes()).hexdigest()
    if run.get("result_sha256") != md_hash:
        return dict(missing, status="result_changed")
    provenance = {"result_sha256": md_hash,
                  "gold_sha256": hashlib.sha256((case_path / "gold.json").read_bytes()).hexdigest(),
                  "judge_model": judge.DEFAULT_JUDGE_MODEL}
    if getattr(judge, "__file__", None):
        provenance["judge_script_sha256"] = hashlib.sha256(Path(judge.__file__).read_bytes()).hexdigest()
    score_path = case_result / "judge.json"
    if score_path.is_file():
        cached = json.loads(score_path.read_text(encoding="utf-8"))
        if cached.get("provenance") == provenance and cached.get("status") == "judged":
            cached.setdefault("judge_case_id", cached.get("case_id"))
            cached["case_id"] = case_path.name
            return cached
    row = judge.evaluate_one(case_path, result_dir)
    row["judge_case_id"] = row.get("case_id")
    row["case_id"] = case_path.name
    row["provenance"] = provenance
    save_json(score_path, row)
    return row


def load_provider(model, source="opencode"):
    if source == "codex":
        provider_id, separator, model_id = model.partition("/")
        if provider_id != "openai" or not separator or not model_id or "/" in model_id:
            raise ValueError("Codex provider models must use openai/<model-id>")
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
        provider = config.get("model_providers", {}).get(config.get("model_provider"), {})
        if provider.get("wire_api") != "responses" or not provider.get("base_url"):
            raise ValueError("Codex provider needs an explicit Responses endpoint")
        auth = json.loads((home / "auth.json").read_text(encoding="utf-8"))
        key = auth.get("OPENAI_API_KEY")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Codex provider needs API-key authentication")
        model_config = {"name": model_id, "reasoning": True}
        if effort := config.get("model_reasoning_effort"):
            model_config["options"] = {"reasoningEffort": effort}
        return provider_id, {
            "npm": "@ai-sdk/openai", "name": provider.get("name", "Configured Responses provider"),
            "options": {"baseURL": provider["base_url"], "apiKey": key},
            "models": {model_id: model_config}}
    if source != "opencode":
        raise ValueError("Unknown provider source")
    result = subprocess.run(["opencode", "debug", "config", "--pure"],
                            capture_output=True, text=True, check=True)
    config = json.loads(result.stdout)
    provider_id = model.split("/", 1)[0]
    provider = config.get("provider", {}).get(provider_id)
    if not provider or not provider.get("options", {}).get("apiKey"):
        raise ValueError("Selected provider needs a configured API key")
    return provider_id, provider


class ModelProxy:
    """Expose only the configured model endpoint to the sandboxed process."""

    def __init__(self, base_url, api_key, api_path="/chat/completions"):
        if api_path not in ("/chat/completions", "/responses"):
            raise ValueError("Unsupported model protocol")
        endpoint = base_url.rstrip("/") + api_path
        class RejectRedirects(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        opener = build_opener(ProxyHandler({}), RejectRedirects())
        transport_errors = self.transport_errors = []
        self._identity_lock = identity_lock = threading.Lock()
        self._requested_models = requested_models = set()
        self._reported_models = reported_models = set()
        self._requests = requests = {}
        self._oversized_identity_lines = 0
        self._oversized_identity_json_responses = 0
        proxy = self

        def parse_event(data):
            if data.startswith(b"data:"):
                data = data[5:].strip()
            try:
                event = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                return {}
            return event if isinstance(event, dict) else {}

        def identity_value(value):
            if isinstance(value, str) and 0 < len(value) <= 256:
                return value.replace(api_key, "[REDACTED]")
            return None

        def inspect_identity(data, request_identity):
            event = parse_event(data)
            response = event.get("response")
            value = response.get("model") if isinstance(response, dict) else event.get("model")
            if value := identity_value(value):
                with identity_lock:
                    reported_models.add(value)
                    request_identity["reported_models"].add(value)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_error(403)

            def do_POST(self):
                if self.path != api_path:
                    self.send_error(403)
                    return
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 32 * 1024 * 1024:
                    self.send_error(413)
                    return
                body = self.rfile.read(size)
                event = parse_event(body)
                model = identity_value(event.get("model"))
                reasoning = event.get("reasoning")
                effort = identity_value(reasoning.get("effort")) if isinstance(reasoning, dict) else None
                with identity_lock:
                    if model:
                        requested_models.add(model)
                    request_identity = requests.setdefault((model, effort), {
                        "model": model, "reasoning_effort": effort, "count": 0,
                        "reported_models": set()})
                    request_identity["count"] += 1
                request = Request(endpoint, data=body, headers={
                    "Content-Type": "application/json", "Authorization": "Bearer " + api_key})
                headers_sent = False
                try:
                    with opener.open(request, timeout=300) as response:
                        self.send_response(response.status)
                        content_type = response.headers.get("Content-Type", "application/json")
                        self.send_header("Content-Type", content_type)
                        self.send_header("Connection", "close")
                        self.end_headers()
                        headers_sent = True
                        line, skipping = b"", False
                        is_stream = content_type.split(";", 1)[0].strip().lower() == "text/event-stream"
                        while chunk := response.read1(65536):
                            segments = chunk.split(b"\n") if is_stream else [chunk]
                            for index, segment in enumerate(segments):
                                if not skipping:
                                    if len(line) + len(segment) <= 1024 * 1024:
                                        line += segment
                                    else:
                                        line, skipping = b"", True
                                        with identity_lock:
                                            if is_stream:
                                                proxy._oversized_identity_lines += 1
                                            else:
                                                proxy._oversized_identity_json_responses += 1
                                if index < len(segments) - 1:
                                    if not skipping and line.strip():
                                        inspect_identity(line, request_identity)
                                    line, skipping = b"", False
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        if not skipping and line.strip():
                            inspect_identity(line, request_identity)
                except (OSError, ValueError, HTTPException) as exc:
                    if isinstance(exc, HTTPError):
                        exc.close()
                    # Do not expose upstream credentials or response bodies to artifacts.
                    transport_errors.append({
                        "phase": "stream" if headers_sent else "request",
                        "error_type": type(exc).__name__})
                    self.close_connection = True
                    if not headers_sent and not self.wfile.closed:
                        try:
                            self.send_error(502, "Model transport failed")
                        except OSError:
                            pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_port
        self.base_url = "http://127.0.0.1:" + str(self.port)

    def model_identity(self):
        with self._identity_lock:
            return {"requested_models": sorted(self._requested_models),
                    "reported_models": sorted(self._reported_models),
                    "oversized_identity_lines": self._oversized_identity_lines,
                    "oversized_identity_json_responses": self._oversized_identity_json_responses,
                    "requests": [dict(row, reported_models=sorted(row["reported_models"]))
                                 for _, row in sorted(self._requests.items(),
                                                      key=lambda item: tuple(value or "" for value in item[0]))]}

    def __enter__(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def sandbox_profile(workspace, benchmark, output, model_port):
    """Keep gold and other arms unreadable to the agent and all its subprocesses."""
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    readable = [workspace.resolve(), Path(shutil.which("opencode")).resolve().parent]
    readable += [Path(path) for path in ("/usr", "/System", "/Library", "/bin", "/sbin",
                                        "/dev", "/private/etc", "/private/var/db", "/opt/homebrew")]
    allow_reads = " ".join("(subpath " + quote(path) + ")" for path in readable)
    return "\n".join([
        "(version 1)", "(allow default)",
        "(deny file-read-data (require-all (require-not (vnode-type DIRECTORY)) "
        "(require-not (require-any " + allow_reads + "))))",
        "(deny file-write* (require-all (require-not (subpath " + quote(workspace.resolve()) +
        ')) (require-not (subpath "/dev"))))',
        "(deny file-read* file-write* (subpath " + quote(benchmark.resolve()) + "))",
        "(deny file-read* file-write* (require-all (subpath " + quote(output.resolve()) +
        ") (require-not (subpath " + quote(workspace.resolve()) + "))))",
        "(deny network-outbound)",
        '(allow network-outbound (remote tcp "localhost:' + str(model_port) + '"))',
    ])


def completed_answer(raw):
    """Accept only the final OpenCode message with an explicit normal finish."""
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not events or any(not isinstance(event, dict) for event in events):
        raise ValueError("Missing or malformed model events")
    if any(event.get("type") == "error" for event in events):
        raise ValueError("Model reported an execution error")
    for event in events:
        if event.get("type") not in ("text", "step_finish"):
            continue
        part = event.get("part", {})
        if not isinstance(part, dict):
            raise ValueError("Malformed model event fields")
        if event["type"] == "text":
            if not isinstance(part.get("text", ""), str):
                raise ValueError("Malformed model text")
            continue
        tokens = part.get("tokens", {})
        if not isinstance(tokens, dict):
            raise ValueError("Malformed model token counts")
        for field in ("input", "output", "total"):
            count = tokens.get(field, 0)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("Malformed model token counts")
    final = events[-1]
    part = final.get("part", {})
    if not isinstance(part, dict):
        raise ValueError("Missing final model completion")
    message_id = part.get("messageID")
    if (final.get("type") != "step_finish" or part.get("reason") != "stop" or
            not isinstance(message_id, str) or not message_id):
        raise ValueError("Missing final model completion")
    parts = [event.get("part", {}) for event in events if event.get("type") == "text"]
    md = "\n".join(part["text"] for part in parts
                   if isinstance(part, dict) and part.get("messageID") == message_id
                   and isinstance(part.get("text"), str))
    if not md.strip():
        raise ValueError("Completed model message has no answer")
    return md


def run_diagnosis(item, arm, snapshot, output, model, provider_id, provider, timeout, upstream, run_id,
                  discard_workspaces=False):
    source_name, case_path = item
    case_id = case_path.name
    arm_dir = output / arm / source_name
    result_dir = arm_dir / "results" / case_id
    record_path = result_dir / "run.json"
    if record_path.exists():
        cached = json.loads(record_path.read_text(encoding="utf-8"))
        if cached.get("run_id") != run_id:
            raise ValueError("Run provenance mismatch; use a new output directory")
        return cached
    result_dir.mkdir(parents=True, exist_ok=True)
    workspace = arm_dir / "workspaces" / case_id
    started = time.monotonic()
    record = {"source": source_name, "case_id": case_id, "arm": arm, "status": "error", "run_id": run_id}
    try:
        case_workspace = workspace / case_id
        prepare_case(case_path, case_workspace)
        if snapshot:
            copy_skills(snapshot, workspace / ".opencode" / "skills")
        prompt = upstream.build_prompt(case_workspace)
        if snapshot:
            prompt += ("\n使用本工作目录 .opencode/skills/orchestrator-skill/SKILL.md 和"
                       " eval-skill/SKILL.md 的故障诊断能力；按需要读取其参考资料。")
        prompt += ("\n最终回复直接给出完整诊断正文及关键日志引用，不能只返回报告路径。"
                   "仅分析当前 case 的 input.json 与 log/，技能文档作为辅助资源；"
                   "不访问其他案例、历史评测输出或标金，不修改原始输入，不访问网络，不派生其他 Agent。")
        (result_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        local_provider = copy.deepcopy(provider)
        config = {"provider": {provider_id: local_provider}, "model": model, "plugin": [],
                  "permission": {"*": "allow", "task": "deny", "webfetch": "deny", "websearch": "deny"}}
        env = {key: value for key, value in os.environ.items()
               if key in ("PATH", "HOME", "SHELL", "LANG", "LC_ALL", "TERM")}
        env.update(OPENCODE_CONFIG_CONTENT=json.dumps(config),
                   OPENCODE_TEST_HOME=str(workspace / ".isolated-home"),
                   OPENCODE_CONFIG_DIR=str(workspace / ".isolated-config"),
                   OPENCODE_DISABLE_EXTERNAL_SKILLS="1", OPENCODE_DISABLE_CLAUDE_CODE="1",
                   OPENCODE_DISABLE_AUTOUPDATE="1", OPENCODE_DISABLE_DEFAULT_PLUGINS="1",
                   OPENCODE_DISABLE_MODELS_FETCH="1",
                   XDG_DATA_HOME=str(workspace / ".data"),
                   XDG_CACHE_HOME=str(workspace / ".cache"),
                   XDG_CONFIG_HOME=str(workspace / ".config"),
                   TMPDIR=str(workspace / ".tmp"))
        (workspace / ".tmp").mkdir()
        sandbox = shutil.which("sandbox-exec")
        if not sandbox:
            raise ValueError("This adapter requires macOS sandbox-exec for gold isolation")
        api_path = "/responses" if provider.get("npm") == "@ai-sdk/openai" else "/chat/completions"
        with ModelProxy(provider["options"]["baseURL"], provider["options"]["apiKey"], api_path) as proxy:
            local_provider["options"].update(baseURL=proxy.base_url, apiKey="isolated-model-proxy")
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
            profile = sandbox_profile(workspace, case_path.parents[2], output, proxy.port)
            try:
                completed = subprocess.run([sandbox, "-p", profile, shutil.which("opencode"),
                                            "run", "--pure", "--auto", "--format", "json",
                                            "--model", model, prompt], cwd=workspace, env=env,
                                           capture_output=True, text=True, timeout=timeout)
            finally:
                if getattr(proxy, "transport_errors", []):
                    record["model_transport_errors"] = list(proxy.transport_errors)
                if callable(getattr(proxy, "model_identity", None)):
                    record["model_transport_identity"] = proxy.model_identity()
        key = provider["options"]["apiKey"]
        raw = completed.stdout.replace(key, "[REDACTED]")
        stderr = completed.stderr.replace(key, "[REDACTED]")
        (result_dir / "events.jsonl").write_text(raw, encoding="utf-8")
        (result_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        if completed.returncode:
            record["error"] = "Model execution failed; inspect events.jsonl and stderr.txt"
        else:
            md = completed_answer(raw)
            _, inputs, outputs, total = upstream.parse_jsonl_output(raw)
            index = md.find("## 评估结论")
            if index > 0:
                md = md[index:]
            (result_dir / "result.md").write_text(md, encoding="utf-8")
            record.update(status="done", input_tokens=inputs, output_tokens=outputs, total_tokens=total,
                          result_sha256=hashlib.sha256(md.encode("utf-8")).hexdigest())
    except subprocess.TimeoutExpired as exc:
        record.update(timed_out=True,
                      error=f"TimeoutExpired: diagnosis exceeded {timeout}s; inspect events.jsonl and stderr.txt")
        for filename, partial in (("events.jsonl", exc.stdout), ("stderr.txt", exc.stderr)):
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            text = (partial or "").replace(provider["options"]["apiKey"], "[REDACTED]")
            try:
                (result_dir / filename).write_text(text, encoding="utf-8")
            except OSError as log_error:
                message = str(log_error).replace(provider["options"]["apiKey"], "[REDACTED]")
                record.setdefault("log_retention_errors", []).append({
                    "file": filename, "error": type(log_error).__name__ + ": " + message[:300]})
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)[:300]
    record["elapsed"] = round(time.monotonic() - started, 1)
    save_json(record_path, record)
    if discard_workspaces:
        try:
            discard_workspace(workspace, output)
            record["workspace_retained"] = False
        except (OSError, ValueError) as exc:
            record["workspace_retained"] = True
            record["workspace_cleanup_error"] = type(exc).__name__ + ": " + str(exc)[:300]
        save_json(record_path, record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--original-skill", type=Path)
    parser.add_argument("--fixed-skill", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--arms", default="base,original,fixed")
    parser.add_argument("--sources", default=",".join(SOURCES))
    parser.add_argument("--sample-per-source", type=int)
    parser.add_argument("--case-audit", type=Path, nargs="+")
    parser.add_argument("--audit-policy", choices=("all-nonexcluded", "include-only", "review-only"),
                        default="all-nonexcluded")
    parser.add_argument("--model", default="api.cannbot.com/glm-5.3-flash")
    parser.add_argument("--provider-source", choices=("opencode", "codex"), default="opencode")
    parser.add_argument("--judge-provider-model",
                        help="Use this configured OpenCode provider for the Judge independently of diagnosis")
    parser.add_argument("--judge-model", default="glm-5.3-flash")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--discard-workspaces", action="store_true",
                        help="Remove each generated case workspace after preserving run artifacts")
    parser.add_argument("--diagnose-only", action="store_true")
    parser.add_argument("--judge-only", action="store_true")
    args = parser.parse_args(argv)
    if args.provider_source == "codex" and not args.judge_provider_model:
        parser.error("--provider-source codex requires an explicit --judge-provider-model")
    lock = contextlib.nullcontext() if args.judge_only else diagnosis_lock(args.output)
    with lock:
        return execute_benchmark(args, parser)


def execute_benchmark(args, parser):
    benchmark, output = args.benchmark.resolve(), args.output.resolve()
    sys.path.insert(0, str(benchmark / "scripts"))
    import run_diagnosis as upstream
    import eval_benchmark as judge

    arms = args.arms.split(",")
    adapter_bytes = Path(__file__).read_bytes()
    skill_hashes = {}
    for arm in arms:
        if arm not in ("base", "original", "fixed"):
            parser.error("Unknown arm: " + arm)
        root = args.original_skill if arm == "original" else args.fixed_skill
        if arm != "base" and not root:
            parser.error("--original-skill is required for the original arm")
        skill_hashes[arm] = fingerprint(root.resolve()) if arm != "base" else None
    items = []
    for source_name in args.sources.split(","):
        if source_name not in SOURCES:
            parser.error("Unknown source: " + source_name)
        candidates = upstream.discover_cases(benchmark / source_name)
        items.extend((source_name, path) for path in candidates)
    selection = {"available": len(items), "policy": "all", "decisions": []}
    if args.case_audit:
        audit = {"cases": []}
        checksums = {}
        for audit_path in args.case_audit:
            document = json.loads(audit_path.read_text(encoding="utf-8"))
            dataset = document.get("dataset", document.get("source", ""))
            if not dataset or "/" in dataset:
                parser.error("Audit needs a dataset name: " + str(audit_path))
            source = dataset if dataset.startswith("benchmark-") else "benchmark-" + dataset
            audit["cases"].extend(dict(row, source=source) for row in document["cases"])
            checksums[audit_path.name] = hashlib.sha256(audit_path.read_bytes()).hexdigest()
        items, decisions = select_audited(items, audit, args.audit_policy)
        selection.update(policy=args.audit_policy, decisions=decisions,
                         audit_sha256=checksums)
    if args.sample_per_source:
        if args.sample_per_source < 1:
            parser.error("--sample-per-source must be positive")
        items = [item for source in args.sources.split(",")
                 for item in sorted((item for item in items if item[0] == source),
                                    key=lambda item: hashlib.sha256(item[1].name.encode()).hexdigest())[:args.sample_per_source]]
        selection["sample_per_source"] = args.sample_per_source
    if not items or args.workers < 1:
        parser.error("Select cases and a positive worker count")
    revision = subprocess.check_output(["git", "-C", str(benchmark), "rev-parse", "HEAD"], text=True).strip()
    manifest = {"benchmark_revision": revision, "model": args.model, "judge_model": args.judge_model,
                "cases": [{"source": source, "case_id": path.name} for source, path in items], "arms": arms,
                "selection": selection, "skill_fingerprints": skill_hashes,
                "adapter_sha256": hashlib.sha256(adapter_bytes).hexdigest(), "timeout": args.timeout}
    manifest["discard_workspaces"] = args.discard_workspaces
    provider_id, provider = load_provider(args.model, args.provider_source)
    if args.provider_source != "opencode" or args.judge_provider_model:
        manifest.update(provider_source=args.provider_source,
                        diagnosis_protocol="responses" if provider.get("npm") == "@ai-sdk/openai"
                        else "chat/completions", judge_provider_model=args.judge_provider_model,
                        diagnosis_model_config=provider.get("models", {}).get(args.model.split("/", 1)[1], {}))
    manifest_path = output / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        parser.error("Manifest differs from the saved run; use another output directory")
    save_json(manifest_path, manifest)
    (output / "benchmark-adapter.py").write_bytes(adapter_bytes)
    run_id = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    snapshots = {}
    for arm in arms:
        if arm not in ("base", "original", "fixed"):
            parser.error("Unknown arm: " + arm)
        snapshots[arm] = None
        if arm != "base":
            source = args.original_skill if arm == "original" else args.fixed_skill
            if not source:
                parser.error("--original-skill is required for the original arm")
            snapshot = output / "snapshots" / arm
            if not snapshot.exists():
                copy_skills(source.resolve(), snapshot)
            if fingerprint(snapshot) != skill_hashes[arm]:
                parser.error("Skill snapshot changed; use a new output directory")
            snapshots[arm] = snapshot
    save_json(output / "skill-fingerprints.json", {arm: fingerprint(path) if path else None
                                                  for arm, path in snapshots.items()})
    if not args.judge_only:
        for arm in arms:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(run_diagnosis, item, arm, snapshots[arm], output,
                                       args.model, provider_id, provider, args.timeout, upstream, run_id,
                                       args.discard_workspaces) for item in items]
                for index, future in enumerate(as_completed(futures), 1):
                    record = future.result()
                    print(f"[{arm} {index}/{len(items)}] {record['source']}/{record['case_id']} {record['status']} {record['elapsed']}s", flush=True)
    if args.diagnose_only:
        return 0
    judge_provider = load_provider(args.judge_provider_model)[1] if args.judge_provider_model else provider
    judge.DEFAULT_BASE_URL = judge_provider["options"]["baseURL"].rstrip("/")
    judge.DEFAULT_JUDGE_MODEL = args.judge_model
    judge.JUDGE_API_KEY = judge_provider["options"]["apiKey"]
    judge.JUDGE_VK_KEY = ""
    judge.JUDGE_TIMEOUT = 300
    summary = {"manifest": manifest, "arms": {}}
    for arm in arms:
        def score(item):
            source_name, case_path = item
            result_dir = output / arm / source_name / "results"
            row = score_case(case_path, result_dir, judge, run_id)
            row["source_name"] = source_name
            return row
        rows = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(score, item) for item in items]
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                print(f"[judge {arm} {len(rows)}/{len(items)}] {row['case_id']} {row['status']} {row.get('score', 0)}", flush=True)
        aggregate = summarize(rows, len(items))
        if selection["decisions"]:
            eligible = {(row["source"], row["case_id"]) for row in selection["decisions"]
                        if row["decision"] == "include"}
            audited_rows = [row for row in rows if (row["source_name"], row["case_id"]) in eligible]
            aggregate["audited_included"] = summarize(audited_rows, sum(item in eligible for item in
                                                      ((source, path.name) for source, path in items)))
        aggregate["results"] = rows
        summary["arms"][arm] = aggregate
        save_json(output / "summary.json", summary)
        print(f"{arm}: {aggregate['mean_all_cases']}/100; {aggregate['scored']}/{len(items)} judged", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
