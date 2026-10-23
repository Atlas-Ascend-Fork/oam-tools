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
import importlib.util
import hashlib
import http.client
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "run_agent_benchmark.py"


class BenchmarkIsolationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "The reproducible benchmark adapter is missing")
        spec = importlib.util.spec_from_file_location("fault_benchmark_adapter", SCRIPT)
        self.adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.adapter)

    def test_diagnosis_lock_rejects_a_competing_process_and_releases_after_failure(self):
        self.assertTrue(hasattr(self.adapter, "diagnosis_lock"),
                        "Concurrent diagnosis processes must not share workspaces")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            child = (
                "import importlib.util,sys\n"
                "from pathlib import Path\n"
                "spec=importlib.util.spec_from_file_location('adapter',sys.argv[1])\n"
                "adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)\n"
                "try:\n"
                " with adapter.diagnosis_lock(Path(sys.argv[2])): pass\n"
                "except ValueError as exc:\n"
                " print(exc);sys.exit(7)\n")
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                with self.adapter.diagnosis_lock(output):
                    process = subprocess.run(
                        [sys.executable, "-c", child, str(SCRIPT), str(output)],
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(process.returncode, 7, process.stderr)
                    self.assertIn("Another diagnosis process", process.stdout)
                    raise RuntimeError("simulated failure")
            with self.adapter.diagnosis_lock(output):
                self.assertTrue((output / ".diagnosis.lock").is_file())

    def test_main_refuses_a_locked_output_before_any_run_setup(self):
        self.assertTrue(hasattr(self.adapter, "diagnosis_lock"),
                        "The CLI must acquire the diagnosis lock before writing run metadata")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with self.adapter.diagnosis_lock(output), \
                    patch.object(self.adapter, "load_provider") as provider:
                with self.assertRaisesRegex(ValueError, "Another diagnosis process"):
                    self.adapter.main(["--benchmark", "/unused", "--output", str(output)])
                provider.assert_not_called()
                self.assertEqual({path.name for path in output.iterdir()}, {".diagnosis.lock"})

    def test_main_releases_lock_when_setup_raises_with_traceback_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            failure = None
            with patch.dict(sys.modules, {"run_diagnosis": SimpleNamespace(),
                                          "eval_benchmark": SimpleNamespace()}), \
                    patch.object(self.adapter, "fingerprint", side_effect=RuntimeError("setup failed")):
                try:
                    self.adapter.main(["--benchmark", "/unused", "--output", str(output),
                                       "--arms", "fixed"])
                except RuntimeError as exc:
                    failure = exc
            self.assertIsNotNone(failure)
            self.assertIsNotNone(failure.__traceback__)
            with self.adapter.diagnosis_lock(output):
                pass

    def test_judge_only_can_read_results_while_diagnosis_is_locked(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with self.adapter.diagnosis_lock(output), \
                    patch.dict(sys.modules, {"run_diagnosis": SimpleNamespace(),
                                              "eval_benchmark": SimpleNamespace()}), \
                    patch.object(self.adapter, "fingerprint", side_effect=RuntimeError("setup reached")):
                with self.assertRaisesRegex(RuntimeError, "setup reached"):
                    self.adapter.main(["--benchmark", "/unused", "--output", str(output),
                                       "--arms", "fixed", "--judge-only"])

    def test_codex_provider_reads_key_on_host_and_preserves_model(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "config.toml").write_text(
                'model_provider = "local"\n[model_providers.local]\n'
                'name = "Local"\nbase_url = "https://example.invalid/v1"\n'
                'wire_api = "responses"\nrequires_openai_auth = true\n')
            (home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "test-private-key"}))
            with patch.dict(self.adapter.os.environ, {"CODEX_HOME": str(home)}):
                provider_id, provider = self.adapter.load_provider("openai/explicit-model", source="codex")
            self.assertEqual(provider_id, "openai")
            self.assertEqual(provider["npm"], "@ai-sdk/openai")
            self.assertEqual(provider["options"], {
                "baseURL": "https://example.invalid/v1", "apiKey": "test-private-key"})
            self.assertEqual(set(provider["models"]), {"explicit-model"})

    def test_codex_provider_fails_closed_for_unsupported_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for auth, wire, model in (({}, "responses", "openai/test"),
                                      ({"OPENAI_API_KEY": "secret"}, "chat", "openai/test"),
                                      ({"OPENAI_API_KEY": "secret"}, "responses", "test"),
                                      ({"OPENAI_API_KEY": "secret"}, "responses", "other/test")):
                with self.subTest(auth=bool(auth), wire=wire, model=model):
                    (home / "config.toml").write_text(
                        'model_provider = "local"\n[model_providers.local]\n'
                        'base_url = "https://example.invalid"\nwire_api = "' + wire + '"\n')
                    (home / "auth.json").write_text(json.dumps(auth))
                    with patch.dict(self.adapter.os.environ, {"CODEX_HOME": str(home)}):
                        with self.assertRaises(ValueError) as raised:
                            self.adapter.load_provider(model, source="codex")
                    self.assertNotIn("secret", str(raised.exception))

    def test_codex_diagnosis_requires_explicit_independent_judge(self):
        with patch.object(self.adapter, "load_provider") as load, \
                patch("sys.stderr", new_callable=io.StringIO) as error:
            with self.assertRaises(SystemExit) as raised:
                self.adapter.main(["--benchmark", "/unused", "--output", "/unused",
                                   "--provider-source", "codex", "--model", "openai/test"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--judge-provider-model", error.getvalue())
        load.assert_not_called()

    def test_responses_proxy_forwards_only_exact_endpoint_with_host_credentials(self):
        received = []

        class Endpoint(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                received.append((self.path, self.headers.get("Authorization"),
                                 self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

        server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = "http://127.0.0.1:" + str(server.server_port) + "/v1"
            with self.adapter.ModelProxy(endpoint, "host-only-key", api_path="/responses") as proxy:
                for path, expected in (("/responses", 200), ("/chat/completions", 403),
                                       ("/responses/extra", 403), ("/responses?url=other", 403)):
                    connection = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=3)
                    connection.request("POST", path, body=b'{}', headers={"Authorization": "Bearer dummy"})
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected)
                    response.read()
                    connection.close()
            self.assertEqual(received, [("/v1/responses", "Bearer host-only-key", b'{}')])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_proxy_retains_reported_model_identity_from_split_stream_without_body(self):
        import urllib.request

        payload = (b'data: {"type":"response.created","response":{"model":"reported-model"}}\n\n'
                   b'data: {"type":"response.output_text.delta","delta":"private-output"}\n\n'
                   b'data: [DONE]\n\n')
        response = MagicMock()
        response.status = 200
        response.headers = {"Content-Type": "text/event-stream"}
        response.read1.side_effect = [payload[i:i + 7] for i in range(0, len(payload), 7)] + [b'']
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        with patch.object(self.adapter, "build_opener", return_value=opener):
            with self.adapter.ModelProxy("https://example.invalid", "secret-key", "/responses") as proxy:
                request = urllib.request.Request(proxy.base_url + "/responses",
                                                 data=b'{"model":"requested-model"}')
                with urllib.request.urlopen(request, timeout=3) as forwarded:
                    self.assertEqual(forwarded.read(), payload)
                self.assertEqual(proxy.model_identity(), {
                    "requested_models": ["requested-model"],
                    "reported_models": ["reported-model"],
                    "oversized_identity_lines": 0,
                    "oversized_identity_json_responses": 0,
                    "requests": [{"model": "requested-model", "reasoning_effort": None,
                                  "count": 1, "reported_models": ["reported-model"]}]})
                self.assertNotIn("private-output", json.dumps(proxy.model_identity()))

    def test_proxy_identity_limits_long_lines_and_recovers_at_next_event(self):
        import urllib.request

        payload = (b'data: ' + b'x' * (1024 * 1024 + 1) + b'\n'
                   b'data: {"model":"recovered-model"}\n\n')
        response = MagicMock()
        response.status = 200
        response.headers = {"Content-Type": "text/event-stream"}
        response.read1.side_effect = [payload[i:i + 65536] for i in range(0, len(payload), 65536)] + [b'']
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        with patch.object(self.adapter, "build_opener", return_value=opener):
            with self.adapter.ModelProxy("https://example.invalid", "secret-key") as proxy:
                with urllib.request.urlopen(urllib.request.Request(
                        proxy.base_url + "/chat/completions", data=b'{}'), timeout=3) as forwarded:
                    self.assertEqual(forwarded.read(), payload)
                self.assertEqual(proxy.model_identity()["reported_models"], ["recovered-model"])
                self.assertEqual(proxy.model_identity()["oversized_identity_lines"], 1)

    def test_proxy_does_not_forward_credentials_on_upstream_redirect(self):
        received = []

        class Endpoint(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:" + str(self.server.server_port) + "/outside")
                self.end_headers()

            def do_GET(self):
                received.append((self.path, self.headers.get("Authorization")))
                self.send_response(200)
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.adapter.ModelProxy("http://127.0.0.1:" + str(server.server_port), "secret-key") as proxy:
                connection = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=3)
                connection.request("POST", "/chat/completions", body=b'{}')
                response = connection.getresponse()
                self.assertEqual(response.status, 502)
                response.read()
                connection.close()
            self.assertEqual(received, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_proxy_identity_associates_each_requested_model_and_effort_with_response(self):
        import urllib.request

        responses = []
        for model in ("reported-primary", "reported-auxiliary"):
            response = MagicMock()
            response.status = 200
            response.headers = {"Content-Type": "application/json; charset=utf-8"}
            response.read1.side_effect = [json.dumps({"model": model, "output": []}, indent=2).encode(), b'']
            responses.append(response)
        opener = MagicMock()
        opener.open.return_value.__enter__.side_effect = responses
        with patch.object(self.adapter, "build_opener", return_value=opener):
            with self.adapter.ModelProxy("https://example.invalid", "secret-key", "/responses") as proxy:
                for model, effort in (("primary", "xhigh"), ("auxiliary", "none")):
                    request = urllib.request.Request(proxy.base_url + "/responses", data=json.dumps({
                        "model": model, "reasoning": {"effort": effort}}).encode())
                    with urllib.request.urlopen(request, timeout=3) as response:
                        response.read()
                identity = proxy.model_identity()
                self.assertEqual(identity["reported_models"], ["reported-auxiliary", "reported-primary"])
                self.assertEqual(identity["requests"], [
                    {"model": "auxiliary", "reasoning_effort": "none", "count": 1,
                     "reported_models": ["reported-auxiliary"]},
                    {"model": "primary", "reasoning_effort": "xhigh", "count": 1,
                     "reported_models": ["reported-primary"]}])

    def test_proxy_closes_upstream_error_response(self):
        from urllib.error import HTTPError

        upstream_body = io.BytesIO(b"private-error-body")
        error = HTTPError("https://example.invalid", 302, "Found", {}, upstream_body)
        opener = MagicMock()
        opener.open.side_effect = error
        with patch.object(self.adapter, "build_opener", return_value=opener):
            with self.adapter.ModelProxy("https://example.invalid", "secret-key") as proxy:
                connection = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=3)
                connection.request("POST", "/chat/completions", body=b'{}')
                response = connection.getresponse()
                self.assertEqual(response.status, 502)
                self.assertNotIn(b"private-error-body", response.read())
                connection.close()
        self.assertTrue(upstream_body.closed)

    def test_prepare_exposes_only_case_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root / "source"
            case.mkdir()
            (case / "input.json").write_text(json.dumps({"case_id": "test"}))
            (case / "gold.json").write_text("SECRET ANSWER")
            (case / "old-result.md").write_text("OLD DIAGNOSIS")
            (case / "log").mkdir()
            (case / "log" / "fault.log").write_text("[ERROR] failure\n")
            dest = root / "isolated"
            self.adapter.prepare_case(case, dest)
            self.assertEqual({path.name for path in dest.iterdir()}, {"input.json", "log"})
            self.assertEqual((dest / "log" / "fault.log").read_text(), "[ERROR] failure\n")

    def test_tar_member_cannot_escape_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root / "source"
            case.mkdir()
            (case / "input.json").write_text("{}")
            with tarfile.open(case / "log.tar.gz", "w:gz") as archive:
                info = tarfile.TarInfo("../outside.log")
                info.size = 3
                archive.addfile(info, io.BytesIO(b"bad"))
            with self.assertRaises(ValueError):
                self.adapter.prepare_case(case, root / "isolated")
            self.assertFalse((root / "outside.log").exists())

    def test_split_archives_are_read_in_order_without_joining_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root / "source"
            case.mkdir()
            (case / "input.json").write_text("{}")
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
                member = tarfile.TarInfo("log/error.txt")
                member.size = 5
                archive.addfile(member, io.BytesIO(b"error"))
            data = buffer.getvalue()
            middle = len(data) // 2
            (case / "log.tar.gz.part00").write_bytes(data[:middle])
            (case / "log.tar.gz.part01").write_bytes(data[middle:])
            self.adapter.prepare_case(case, root / "isolated")
            self.assertEqual((root / "isolated/log/error.txt").read_bytes(), b"error")
            self.assertFalse((case / "log.tar.gz").exists())

    def test_failures_remain_in_acceptance_denominator(self):
        rows = [{"status": "judged", "score": 90},
                {"status": "judge_error", "score": 0}]
        summary = self.adapter.summarize(rows, expected=3)
        self.assertEqual(summary["scored"], 1)
        self.assertEqual(summary["coverage"], 1 / 3)
        self.assertEqual(summary["mean_all_cases"], 30)
        self.assertFalse(summary["accepted"])

    def test_only_a_completed_final_message_can_be_scored(self):
        answer = "## 评估结论\nFinal answer"
        text = {"type": "text", "part": {"messageID": "final", "text": answer}}
        finish = {"type": "step_finish", "part": {"messageID": "final", "reason": "stop"}}
        scenarios = [
            ("partial", [text], False),
            ("tool_calls", [text, {"type": "step_finish", "part": {
                "messageID": "final", "reason": "tool-calls"}}], False),
            ("length", [text, {"type": "step_finish", "part": {
                "messageID": "final", "reason": "length"}}], False),
            ("wrong_message", [text, {"type": "step_finish", "part": {
                "messageID": "other", "reason": "stop"}}], False),
            ("missing_message_id", [{"type": "text", "part": {"text": answer}},
                {"type": "step_finish", "part": {"reason": "stop"}}], False),
            ("later_partial", [text, finish, {"type": "text", "part": {
                "messageID": "later", "text": "partial"}}], False),
            ("reordered_error", [{"error": {"message": "failure"}, "type": "error"},
                text, finish], False),
            ("earlier_null_part", [{"type": "text", "part": None}, text, finish], False),
            ("null_tokens", [text, {"type": "step_finish", "part": {
                "messageID": "final", "reason": "stop", "tokens": None}}], False),
            ("null_token_count", [text, {"type": "step_finish", "part": {
                "messageID": "final", "reason": "stop", "tokens": {"input": None}}}], False),
            ("boolean_token_count", [text, {"type": "step_finish", "part": {
                "messageID": "final", "reason": "stop", "tokens": {"input": True}}}], False),
            ("negative_token_count", [text, {"type": "step_finish", "part": {
                "messageID": "final", "reason": "stop", "tokens": {"input": -1}}}], False),
            ("complete", [{"type": "text", "part": {
                "messageID": "draft", "text": "## 评估结论\nSuperseded draft"}},
                text, finish], True),
        ]
        for label, events, success in scenarios:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                case = root / "benchmark" / "benchmark-DTS" / "cases" / "case"
                case.mkdir(parents=True)
                (case / "input.json").write_text("{}")
                (case / "log").mkdir()
                raw = "\n".join(json.dumps(event) for event in events)
                upstream = SimpleNamespace(
                    build_prompt=lambda _: "diagnose",
                    parse_jsonl_output=lambda _: ("## 评估结论\nSuperseded draft\n" + answer, 1, 2, 3))
                provider = {"options": {"baseURL": "https://example.invalid", "apiKey": "secret-key"}}
                completed = SimpleNamespace(returncode=0, stdout=raw, stderr="")
                with patch.object(self.adapter, "ModelProxy") as proxy, \
                        patch.object(self.adapter.shutil, "which", return_value="/usr/bin/true"), \
                        patch.object(self.adapter.subprocess, "run", return_value=completed):
                    proxy.return_value.__enter__.return_value = SimpleNamespace(
                        base_url="http://localhost:18081", port=18081,
                        transport_errors=[{"phase": "stream", "error_type": "IncompleteRead"}])
                    record = self.adapter.run_diagnosis(
                        ("benchmark-DTS", case), "fixed", None, root / "output", "provider/model",
                        "provider", provider, 1, upstream, "run-id", discard_workspaces=True)
                result = root / "output/fixed/benchmark-DTS/results/case/result.md"
                self.assertEqual(record["status"], "done" if success else "error")
                self.assertEqual(result.exists(), success)
                if success:
                    self.assertEqual(result.read_text(), answer)
                    self.assertEqual(record["total_tokens"], 3)
                    self.assertEqual(record.get("model_transport_errors"), [
                        {"phase": "stream", "error_type": "IncompleteRead"}])

    def test_timeout_keeps_redacted_partial_streams_after_workspace_cleanup(self):
        streams = [
            (b'{"type":"text","part":{"text":"partial secret-key"}}\n',
             b"request failed secret-key\n"),
            ("partial secret-key", "stderr secret-key"),
            (b"partial secret-key\xe4\xb8", b"stderr secret-key\xe4\xb8"),
            (None, None),
        ]
        for stdout, stderr in streams:
            with self.subTest(stdout=stdout), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                case = root / "benchmark" / "benchmark-DTS" / "cases" / "case"
                case.mkdir(parents=True)
                (case / "input.json").write_text("{}")
                (case / "log").mkdir()
                (case / "log" / "error.log").write_text("original evidence")
                output = root / "output"
                upstream = SimpleNamespace(build_prompt=lambda _: "diagnose")
                provider = {"options": {"baseURL": "https://example.invalid", "apiKey": "secret-key"}}
                timeout = subprocess.TimeoutExpired(["opencode", "secret-key"], 1,
                                                    output=stdout, stderr=stderr)
                with patch.object(self.adapter, "ModelProxy") as proxy, \
                        patch.object(self.adapter.shutil, "which", return_value="/usr/bin/true"), \
                        patch.object(self.adapter.subprocess, "run", side_effect=timeout):
                    proxy.return_value.__enter__.return_value = SimpleNamespace(
                        base_url="http://localhost:18081", port=18081)
                    record = self.adapter.run_diagnosis(
                        ("benchmark-DTS", case), "fixed", None, output, "provider/model",
                        "provider", provider, 1, upstream, "run-id", discard_workspaces=True)

                result = output / "fixed" / "benchmark-DTS" / "results" / "case"
                for filename, value in (("events.jsonl", stdout), ("stderr.txt", stderr)):
                    self.assertTrue((result / filename).is_file(), "Timeout must preserve partial streams")
                    expected = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                    self.assertEqual((result / filename).read_text(),
                                     expected.replace("secret-key", "[REDACTED]"))
                self.assertEqual(record["status"], "error")
                self.assertTrue(record["timed_out"])
                self.assertNotIn("secret-key", (result / "run.json").read_text())
                self.assertFalse((result / "result.md").exists())
                self.assertFalse((output / "fixed" / "benchmark-DTS" / "workspaces" / "case").exists())
                self.assertEqual((case / "log" / "error.log").read_text(), "original evidence")

                class Judge:
                    def evaluate_one(self, *args):
                        raise AssertionError("Partial timeout output must not be scored")

                row = self.adapter.score_case(case, result.parent, Judge(), "run-id")
                self.assertEqual((row["status"], row["score"]), ("no_result", 0))

    def test_timeout_log_write_failure_keeps_run_record_and_cleans_workspace(self):
        for failed_file in ("events.jsonl", "stderr.txt"):
            with self.subTest(failed_file=failed_file), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                case = root / "benchmark" / "benchmark-DTS" / "cases" / "case"
                case.mkdir(parents=True)
                (case / "input.json").write_text("{}")
                (case / "log").mkdir()
                (case / "log" / "error.log").write_text("original evidence")
                output = root / "output"
                upstream = SimpleNamespace(build_prompt=lambda _: "diagnose")
                provider = {"options": {"baseURL": "https://example.invalid", "apiKey": "secret-key"}}
                timeout = subprocess.TimeoutExpired(["opencode"], 1,
                                                    output=b"partial", stderr=b"stderr")
                write_text = Path.write_text

                def fail_one_log(path, *args, **kwargs):
                    if path.name == failed_file:
                        raise OSError("log storage unavailable secret-key")
                    return write_text(path, *args, **kwargs)

                with patch.object(self.adapter, "ModelProxy") as proxy, \
                        patch.object(self.adapter.shutil, "which", return_value="/usr/bin/true"), \
                        patch.object(self.adapter.subprocess, "run", side_effect=timeout), \
                        patch.object(Path, "write_text", fail_one_log):
                    proxy.return_value.__enter__.return_value = SimpleNamespace(
                        base_url="http://localhost:18081", port=18081)
                    try:
                        record = self.adapter.run_diagnosis(
                            ("benchmark-DTS", case), "fixed", None, output, "provider/model",
                            "provider", provider, 1, upstream, "run-id", discard_workspaces=True)
                    except OSError as exc:
                        self.fail("A timeout log failure must not abort the batch: " + str(exc))

                result = output / "fixed" / "benchmark-DTS" / "results" / "case"
                saved = json.loads((result / "run.json").read_text())
                self.assertEqual(saved, record)
                self.assertEqual(saved["status"], "error")
                self.assertTrue(saved["timed_out"])
                self.assertIn("TimeoutExpired", saved["error"])
                self.assertEqual(saved["log_retention_errors"], [{
                    "file": failed_file,
                    "error": "OSError: log storage unavailable [REDACTED]"}])
                self.assertNotIn("secret-key", (result / "run.json").read_text())
                other_file = "stderr.txt" if failed_file == "events.jsonl" else "events.jsonl"
                self.assertTrue((result / other_file).is_file())
                self.assertFalse((result / "result.md").exists())
                self.assertFalse((output / "fixed" / "benchmark-DTS" / "workspaces" / "case").exists())
                self.assertEqual((case / "log" / "error.log").read_text(), "original evidence")

    def test_discard_workspace_preserves_results_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "output"
            source.mkdir()
            (source / "input.json").write_text("source evidence")
            workspace = output / "fixed" / "benchmark-DTS" / "workspaces" / "case"
            workspace.mkdir(parents=True)
            shutil.copytree(source, workspace / "case")
            result = output / "fixed" / "results" / "case" / "result.md"
            result.parent.mkdir(parents=True)
            result.write_text("diagnosis")
            self.assertTrue(hasattr(self.adapter, "discard_workspace"),
                            "Full-suite runs need bounded temporary disk use")
            self.adapter.discard_workspace(workspace, output)
            self.assertFalse(workspace.exists())
            self.assertEqual(result.read_text(), "diagnosis")
            self.assertEqual((source / "input.json").read_text(), "source evidence")

    def test_discard_refuses_output_root_and_external_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, external = root / "output", root / "external"
            output.mkdir()
            external.mkdir()
            self.assertTrue(hasattr(self.adapter, "discard_workspace"),
                            "Workspace removal must validate its boundary")
            for path in (output, external):
                with self.assertRaises(ValueError):
                    self.adapter.discard_workspace(path, output)
                self.assertTrue(path.is_dir())

    def test_discard_refuses_parent_symlink_into_results(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            arm = output / "fixed" / "benchmark-DTS"
            result = arm / "results" / "case" / "result.md"
            result.parent.mkdir(parents=True)
            result.write_text("preserve diagnosis")
            (arm / "workspaces").symlink_to(arm / "results", target_is_directory=True)
            with self.assertRaises(ValueError):
                self.adapter.discard_workspace(arm / "workspaces" / "case", output)
            self.assertEqual(result.read_text(), "preserve diagnosis")

    def test_audit_removes_only_explicit_exclusions_by_default(self):
        self.assertTrue(hasattr(self.adapter, "select_audited"), "Missing transparent case selection")
        items = [("source", Path(case)) for case in ("valid", "invalid", "pending")]
        audit = {"cases": [
            {"source": "source", "case_id": "valid", "decision": "include", "reason": "Sufficient logs"},
            {"source": "source", "case_id": "invalid", "decision": "exclude", "reason": "Missing required evidence"},
            {"source": "source", "case_id": "pending", "decision": "review", "reason": "Not verified"}]}
        selected, decisions = self.adapter.select_audited(items, audit, "all-nonexcluded")
        self.assertEqual([path.name for _, path in selected], ["valid", "pending"])
        self.assertEqual(len(decisions), 3)
        selected, _ = self.adapter.select_audited(items, audit, "include-only")
        self.assertEqual([path.name for _, path in selected], ["valid"])
        selected, _ = self.adapter.select_audited(items, audit, "review-only")
        self.assertEqual([path.name for _, path in selected], ["pending"])

    def test_audit_cannot_silently_omit_cases_or_exclusion_reasons(self):
        items = [("source", Path("case"))]
        for cases in ([], [{"source": "source", "case_id": "case", "decision": "exclude"}]):
            with self.assertRaises(ValueError):
                self.adapter.select_audited(items, {"cases": cases}, "all-nonexcluded")

    def test_failed_run_cannot_fall_back_to_historical_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root / "source" / "test"
            case.mkdir(parents=True)
            (case / "result.md").write_text("HISTORICAL DIAGNOSIS")
            result_dir = root / "results"
            result_dir.mkdir()

            class Judge:
                DEFAULT_JUDGE_MODEL = "test-model"

                def evaluate_one(self, *args):
                    raise AssertionError("An unsuccessful run must not reach the judge")

            self.assertTrue(hasattr(self.adapter, "score_case"), "Missing result provenance check")
            row = self.adapter.score_case(case, result_dir, Judge())
            self.assertEqual(row["status"], "no_result")
            self.assertEqual(row["score"], 0)

    def test_success_without_result_hash_is_not_a_current_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, results = root / "case", root / "results"
            case.mkdir()
            (case / "gold.json").write_text("{}")
            result = results / "case"
            result.mkdir(parents=True)
            (result / "result.md").write_text("OLD ANSWER")
            (result / "run.json").write_text(json.dumps({"status": "done"}))

            class Judge:
                DEFAULT_JUDGE_MODEL = "fake"

                def evaluate_one(self, *args):
                    raise AssertionError("Missing result hash must fail closed")

            row = self.adapter.score_case(case, results, Judge())
            self.assertNotEqual(row["status"], "judged")

    def test_judge_alias_does_not_break_selected_case_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, results = root / "CASE-DTS-TEST", root / "results"
            case.mkdir()
            (case / "gold.json").write_text("{}")
            result = results / case.name
            result.mkdir(parents=True)
            (result / "result.md").write_text("diagnosis")
            (result / "run.json").write_text(json.dumps({
                "status": "done", "run_id": "current",
                "result_sha256": hashlib.sha256(b"diagnosis").hexdigest()}))

            class Judge:
                DEFAULT_JUDGE_MODEL = "fake"
                calls = 0

                def evaluate_one(self, *args):
                    self.calls += 1
                    return {"case_id": "TEST", "status": "judged", "score": 90}

            judge = Judge()
            for _ in range(2):
                row = self.adapter.score_case(case, results, judge, "current")
                self.assertEqual(row["case_id"], case.name)
                self.assertEqual(row["judge_case_id"], "TEST")
            self.assertEqual(judge.calls, 1)

    @unittest.skipUnless(shutil.which("sandbox-exec"), "macOS sandbox-exec required")
    def test_os_sandbox_denies_benchmark_and_sibling_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            benchmark, output = root / "benchmark", root / "output"
            workspace = output / "fixed" / "case"
            workspace.mkdir(parents=True)
            benchmark.mkdir()
            denied = benchmark / "answer.txt"
            denied.write_text("secret")
            sibling = output / "original.txt"
            sibling.write_text("old output")
            allowed = workspace / "input.json"
            allowed.write_text("{}")
            self.assertTrue(hasattr(self.adapter, "sandbox_profile"), "Missing OS isolation")
            external = root / "external-answer.txt"
            external.write_text("unrelated history")
            profile = self.adapter.sandbox_profile(workspace, benchmark, output, 18081)
            for path, expected in [(denied, False), (sibling, False), (external, False), (allowed, True)]:
                result = subprocess.run(["sandbox-exec", "-p", profile, "/bin/cat", str(path)],
                                        capture_output=True)
                self.assertEqual(result.returncode == 0, expected, result.stderr)
            moved = workspace / "moved-answer.txt"
            result = subprocess.run(["sandbox-exec", "-p", profile, "/bin/mv", str(external), str(moved)],
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0, "Renaming outside evidence must be denied")
            self.assertTrue(external.is_file())
            result = subprocess.run(["sandbox-exec", "-p", profile, "/usr/bin/touch", str(root / "outside-write")],
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0, "Writes outside the case workspace must be denied")

    def test_proxy_rejects_non_model_routes(self):
        import urllib.error
        import urllib.request

        self.assertTrue(hasattr(self.adapter, "ModelProxy"), "Missing restricted model transport")
        with self.adapter.ModelProxy("https://api.example.invalid", "secret") as proxy:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(proxy.base_url + "/gold.json", timeout=2)
            self.assertEqual(raised.exception.code, 403)
            raised.exception.close()

    def test_proxy_stream_failure_closes_without_appending_an_http_response(self):
        import urllib.request

        prefix = b'data: {"content":"partial"}\n\n'
        for failure in (http.client.IncompleteRead(b"secret-key"),
                        OSError("upstream secret-key")):
            with self.subTest(failure=type(failure).__name__):
                response = MagicMock()
                response.status = 200
                response.headers = {"Content-Type": "text/event-stream"}
                response.read1.side_effect = [prefix, failure]
                opener = MagicMock()
                opener.open.return_value.__enter__.return_value = response
                with patch.object(self.adapter, "build_opener", return_value=opener):
                    with self.adapter.ModelProxy("https://example.invalid", "secret-key") as proxy:
                        with patch.object(proxy.server, "handle_error") as handle_error:
                            request = urllib.request.Request(
                                proxy.base_url + "/chat/completions", data=b"{}")
                            with urllib.request.urlopen(request, timeout=2) as downstream:
                                self.assertEqual(downstream.status, 200)
                                self.assertEqual(downstream.read(), prefix)
                            handle_error.assert_not_called()

    def test_proxy_http_failure_before_headers_returns_generic_502(self):
        import urllib.error
        import urllib.request

        opener = MagicMock()
        opener.open.side_effect = http.client.IncompleteRead(b"secret-key")
        with patch.object(self.adapter, "build_opener", return_value=opener):
            with self.adapter.ModelProxy("https://example.invalid", "secret-key") as proxy:
                with patch.object(proxy.server, "handle_error") as handle_error:
                    request = urllib.request.Request(
                        proxy.base_url + "/chat/completions", data=b"{}")
                    with self.assertRaises(urllib.error.HTTPError) as raised:
                        urllib.request.urlopen(request, timeout=2)
                    with raised.exception as response:
                        self.assertEqual(response.code, 502)
                        self.assertNotIn(b"secret-key", response.read())
                    handle_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
