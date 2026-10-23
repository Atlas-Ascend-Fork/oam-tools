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
"""Recover failed diagnoses with the run's frozen adapter and bounded attempts."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def manifest_id(manifest):
    return hashlib.sha256(json.dumps(
        manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def file_hashes(directory, *, omit=()):
    directory = Path(directory)
    paths = sorted(path for path in directory.rglob("*")
                   if path.relative_to(directory).as_posix() not in omit)
    if directory.is_symlink() or any(path.is_symlink() for path in paths):
        raise ValueError("Unsafe symlink in result directory")
    return {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.is_file()}


def component(value):
    if (not isinstance(value, str) or not value or value in (".", "..") or
            "/" in value or "\\" in value or "\x00" in value):
        raise ValueError("Unsafe manifest path component")
    return value


def result_directory(root, item):
    path = root
    for part in (item["arm"], item["source"], "results", item["case_id"]):
        path /= component(part)
        if path.is_symlink():
            raise ValueError("Unsafe result path symlink")
    return path


def manifest_items(manifest):
    items = [dict(case, arm=arm) for arm in manifest["arms"] for case in manifest["cases"]]
    keys = []
    for item in items:
        keys.append(tuple(component(item[key]) for key in ("arm", "source", "case_id")))
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate manifest case")
    return items


def validate_record(record, item, run_id):
    if (record.get("run_id") != run_id or
            any(record.get(key) != item[key] for key in ("arm", "source", "case_id"))):
        raise ValueError("Run provenance mismatch")


def select_failures(root, manifest, limit=None):
    if limit is not None and limit < 1:
        raise ValueError("Limit must be positive")
    run_id = manifest_id(manifest)
    selected = []
    for item in manifest_items(manifest):
        folder = result_directory(Path(root), item)
        if not (folder / "run.json").exists():
            continue
        record = read_json(folder / "run.json")
        validate_record(record, item, run_id)
        if record.get("status") == "error":
            selected.append(item)
    return selected if limit is None else selected[:limit]


def archive_failure(result_dir, archive_dir, run_id):
    result_dir, archive_dir = Path(result_dir), Path(archive_dir)
    if archive_dir.exists():
        raise FileExistsError(archive_dir)
    record = read_json(result_dir / "run.json")
    if record.get("status") != "error":
        raise ValueError("Only error records can be archived")
    if record.get("run_id") != run_id:
        raise ValueError("Run provenance mismatch")
    judge_path = result_dir / "judge.json"
    if judge_path.exists() and read_json(judge_path).get("status") == "judged":
        raise ValueError("Refusing to move a valid judgment")
    if archive_dir.resolve().is_relative_to(result_dir.resolve()):
        raise ValueError("Unsafe archive inside result directory")
    hashes = file_hashes(result_dir)
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(result_dir), str(archive_dir))
    if file_hashes(archive_dir) != hashes:
        raise ValueError("Archived bytes differ")
    return hashes


def retry_cases(root, manifest, pending, batch_dir, diagnose_callback, stop_after=2):
    root, batch_dir = Path(root), Path(batch_dir)
    if stop_after < 1:
        raise ValueError("Failure threshold must be positive")
    available = select_failures(root, manifest)
    if any(item not in available for item in pending) or len(pending) != len({
            (item["arm"], item["source"], item["case_id"]) for item in pending}):
        raise ValueError("Pending cases must be distinct existing errors")
    protected = {}
    for item in manifest_items(manifest):
        folder = result_directory(root, item)
        if (folder / "run.json").exists() and read_json(folder / "run.json").get("status") == "done":
            protected[folder] = file_hashes(folder, omit=("judge.json.tmp",))
    batch_dir.mkdir(parents=True, exist_ok=False)
    run_id = manifest_id(manifest)
    report = {"run_id": run_id, "status": "running", "attempted": 0, "done": 0,
              "remaining": len(pending), "stop_after": stop_after, "attempts": []}
    save_json(batch_dir / "plan.json", {"run_id": run_id, "cases": pending})
    save_json(batch_dir / "protected.json", {
        str(path.relative_to(root)): hashes for path, hashes in protected.items()})
    save_json(batch_dir / "status.json", report)
    consecutive = 0
    for item in pending:
        folder = result_directory(root, item)
        validate_record(read_json(folder / "run.json"), item, run_id)
        archive = batch_dir / "attempts" / item["arm"] / item["source"] / item["case_id"]
        hashes = archive_failure(folder, archive, run_id)
        attempt = dict(item, archived_sha256=hashes, archive=str(archive), status="running")
        report["attempts"].append(attempt)
        save_json(batch_dir / "status.json", report)
        try:
            returned = diagnose_callback(item)
            record = read_json(folder / "run.json")
            validate_record(record, item, run_id)
            if returned.get("status") != record.get("status"):
                raise ValueError("Callback and saved record differ")
            attempt["status"] = record["status"]
        except Exception as exc:
            # Keep the archive even if a callback exits before it writes run.json.
            attempt.update(status="callback_error", error_type=type(exc).__name__)
            report["status"] = "callback_error"
        report["attempted"] += 1
        report["remaining"] -= 1
        if attempt["status"] == "done":
            report["done"] += 1
            consecutive = 0
        else:
            consecutive += 1
        for path, expected in protected.items():
            if path.is_symlink() or any(
                    not (path / name).is_file() or (path / name).is_symlink() or
                    hashlib.sha256((path / name).read_bytes()).hexdigest() != digest
                    for name, digest in expected.items()):
                raise ValueError("Protected successful result changed: " + str(path))
        if consecutive >= stop_after:
            report["status"] = "stopped_after_failures"
        save_json(batch_dir / "status.json", report)
        print(json.dumps({key: attempt[key] for key in ("arm", "source", "case_id", "status")}), flush=True)
        if report["status"] != "running":
            break
    if report["status"] == "running":
        report["status"] = "finished"
    save_json(batch_dir / "status.json", report)
    return report


def load_frozen_adapter(root, manifest):
    path = root / "benchmark-adapter.py"
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest["adapter_sha256"]:
        raise ValueError("Frozen adapter provenance mismatch")
    spec = importlib.util.spec_from_file_location("frozen_benchmark_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_environment(root, benchmark, manifest, adapter):
    revision = subprocess.check_output(["git", "-C", str(benchmark), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(benchmark), "status", "--porcelain", "--untracked-files=all"], text=True)
    case_roots = sorted({component(case["source"]) + "/cases" for case in manifest["cases"]})
    ignored = subprocess.check_output([
        "git", "-C", str(benchmark), "status", "--porcelain", "--untracked-files=all",
        "--ignored=matching", "--", *case_roots], text=True)
    if revision != manifest["benchmark_revision"] or dirty or ignored:
        raise ValueError("Benchmark revision or tracked contents changed")
    for arm in manifest["arms"]:
        if arm != "base" and adapter.fingerprint(root / "snapshots" / arm) != manifest["skill_fingerprints"][arm]:
            raise ValueError("Skill snapshot provenance mismatch")
    provider_id, provider = adapter.load_provider(manifest["model"], manifest.get("provider_source", "opencode"))
    config = provider.get("models", {}).get(manifest["model"].split("/", 1)[1], {})
    protocol = "responses" if provider.get("npm") == "@ai-sdk/openai" else "chat/completions"
    if (config != manifest.get("diagnosis_model_config", config) or
            protocol != manifest.get("diagnosis_protocol", protocol)):
        raise ValueError("Diagnosis provider model configuration changed")
    return provider_id, provider


def assert_inactive(root):
    root = Path(root).resolve()
    judges_active = False
    processes = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True)
    for line in processes.splitlines():
        pid, _, command = line.strip().partition(" ")
        if not pid or int(pid) == os.getpid():
            continue
        try:
            args = shlex.split(command)
        except ValueError:
            continue
        if not any(Path(arg).name in ("benchmark-adapter.py", "retry_agent_benchmark.py", "run_agent_benchmark.py")
                   for arg in args):
            continue
        for index, arg in enumerate(args):
            value = None
            if arg == "--output" and index + 1 < len(args):
                value = args[index + 1]
            elif arg.startswith("--output="):
                value = arg.split("=", 1)[1]
            if "--judge-only" in args:
                if value and (not Path(value).is_absolute() or Path(value).resolve() == root):
                    judges_active = True
                continue
            if value and not Path(value).is_absolute():
                raise ValueError("Active runner has a relative output; cannot verify its directory")
            if value and Path(value).resolve() == root:
                raise ValueError("Another benchmark process is active for this output")
    return judges_active


def validate_parallel_recovery(root, pending):
    for item in pending:
        if (result_directory(Path(root), item) / "result.md").exists():
            raise ValueError("A failed case has a partial answer; wait for judging to finish before archiving")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--stop-after", type=int, default=2)
    parser.add_argument("--execute", action="store_true", help="Run selected errors; default only validates and lists them")
    args = parser.parse_args(argv)
    root, benchmark = args.output.resolve(), args.benchmark.resolve()
    # Share the diagnosis lock with runners; retain the legacy recovery lock too.
    lock = root / ".retry.lock"
    with lock.open("a") as stream, (root / ".diagnosis.lock").open("a") as diagnosis:
        import fcntl
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(diagnosis, fcntl.LOCK_EX | fcntl.LOCK_NB)
        judges_active = assert_inactive(root)
        manifest = read_json(root / "manifest.json")
        adapter = load_frozen_adapter(root, manifest)
        provider_id, provider = validate_environment(root, benchmark, manifest, adapter)
        pending = select_failures(root, manifest, args.limit)
        print(json.dumps({"run_id": manifest_id(manifest), "selected": pending, "execute": args.execute}), flush=True)
        if not args.execute or not pending:
            return 0
        if judges_active:
            validate_parallel_recovery(root, pending)
        for item in pending:
            workspace = root / item["arm"] / item["source"] / "workspaces" / item["case_id"]
            if workspace.exists():
                raise ValueError("Existing workspace requires explicit recovery before retry")
        sys.path.insert(0, str(benchmark / "scripts"))
        import run_diagnosis as upstream
        batch = root / "retry-batches" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")

        def diagnose(item):
            snapshot = None if item["arm"] == "base" else root / "snapshots" / item["arm"]
            return adapter.run_diagnosis(
                (item["source"], benchmark / item["source"] / "cases" / item["case_id"]),
                item["arm"], snapshot, root, manifest["model"], provider_id, provider,
                manifest["timeout"], upstream, manifest_id(manifest), manifest.get("discard_workspaces", False))

        report = retry_cases(root, manifest, pending, batch, diagnose, args.stop_after)
        print(json.dumps({key: value for key, value in report.items() if key != "attempts"}), flush=True)
        return 0 if report["done"] == report["attempted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
