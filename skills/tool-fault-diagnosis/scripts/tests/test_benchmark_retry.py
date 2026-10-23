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
import hashlib
import fcntl
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "retry_agent_benchmark.py"


class BenchmarkRetryTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "The bounded recovery tool is missing")
        spec = importlib.util.spec_from_file_location("benchmark_retry", SCRIPT)
        self.retry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.retry)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = {
            "arms": ["fixed"],
            "cases": [
                {"source": "benchmark-DTS", "case_id": "CASE-A"},
                {"source": "benchmark-DTS", "case_id": "CASE-B"},
                {"source": "benchmark-DTS", "case_id": "CASE-C"},
            ],
        }
        self.run_id = self.retry.manifest_id(self.manifest)

    def record(self, case, status, **extra):
        folder = self.root / "fixed" / "benchmark-DTS" / "results" / case
        folder.mkdir(parents=True, exist_ok=True)
        row = {"run_id": self.run_id, "arm": "fixed", "source": "benchmark-DTS",
               "case_id": case, "status": status, **extra}
        (folder / "run.json").write_text(json.dumps(row), encoding="utf-8")
        return folder

    def test_selects_only_errors_in_manifest_order(self):
        self.record("CASE-A", "done")
        self.record("CASE-B", "error")
        self.record("CASE-C", "error")
        selected = self.retry.select_failures(self.root, self.manifest, limit=1)
        self.assertEqual([row["case_id"] for row in selected], ["CASE-B"])

    def test_foreign_record_and_unsafe_case_fail_before_retry(self):
        folder = self.record("CASE-A", "error")
        row = json.loads((folder / "run.json").read_text())
        row["run_id"] = "another-run"
        (folder / "run.json").write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.retry.select_failures(self.root, self.manifest)
        self.manifest["cases"][0]["case_id"] = "../escape"
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            self.retry.select_failures(self.root, self.manifest)

    def test_cannot_archive_success_or_valid_judgment(self):
        success = self.record("CASE-A", "done")
        with self.assertRaisesRegex(ValueError, "error"):
            self.retry.archive_failure(success, self.root / "archive-a", self.run_id)
        failed = self.record("CASE-B", "error")
        (failed / "judge.json").write_text('{"status":"judged","score":52}')
        with self.assertRaisesRegex(ValueError, "judgment"):
            self.retry.archive_failure(failed, self.root / "archive-b", self.run_id)
        self.assertTrue((success / "run.json").exists())
        self.assertTrue((failed / "judge.json").exists())

    def test_archives_all_failure_bytes_and_refuses_overwrite(self):
        failed = self.record("CASE-A", "error")
        (failed / "events.jsonl").write_bytes(b"failed-event\n")
        (failed / "stderr.txt").write_bytes(b"failure\x00\n")
        (failed / "judge.json.tmp").write_bytes(b"failed judge partial bytes")
        expected = self.retry.file_hashes(failed)
        archive = self.root / "attempts" / "CASE-A"
        actual = self.retry.archive_failure(failed, archive, self.run_id)
        self.assertEqual(expected, actual)
        self.assertEqual(expected, self.retry.file_hashes(archive))
        self.assertFalse(failed.exists())
        self.record("CASE-A", "error")
        with self.assertRaises(FileExistsError):
            self.retry.archive_failure(failed, archive, self.run_id)

    def test_two_failures_stop_before_third_and_preserve_success(self):
        protected = self.record("CASE-A", "done")
        (protected / "result.md").write_bytes(b"valid answer")
        (protected / "judge.json").write_bytes(b'{"status":"judged","score":61}')
        self.record("CASE-B", "error")
        self.record("CASE-C", "error")
        self.manifest["cases"].append({"source": "benchmark-DTS", "case_id": "CASE-D"})
        self.run_id = self.retry.manifest_id(self.manifest)
        for case in ("CASE-A", "CASE-B", "CASE-C"):
            p = self.root / "fixed/benchmark-DTS/results" / case / "run.json"
            row = json.loads(p.read_text())
            row["run_id"] = self.run_id
            p.write_text(json.dumps(row))
        self.record("CASE-D", "error")
        before = self.retry.file_hashes(protected)
        pending = self.retry.select_failures(self.root, self.manifest)
        calls = []

        def diagnose(item):
            calls.append(item["case_id"])
            self.record(item["case_id"], "error")
            return {"status": "error"}

        report = self.retry.retry_cases(
            self.root, self.manifest, pending, self.root / "batch", diagnose, stop_after=2)
        self.assertEqual(calls, ["CASE-B", "CASE-C"])
        self.assertEqual(report["status"], "stopped_after_failures")
        self.assertEqual(report["remaining"], 1)
        self.assertEqual(before, self.retry.file_hashes(protected))
        self.assertTrue((self.root / "fixed/benchmark-DTS/results/CASE-D/run.json").exists())

    def test_success_resets_consecutive_failure_count(self):
        for case in ("CASE-A", "CASE-B", "CASE-C"):
            self.record(case, "error")
        pending = self.retry.select_failures(self.root, self.manifest)
        outcomes = iter(("error", "done", "error"))

        def diagnose(item):
            status = next(outcomes)
            self.record(item["case_id"], status)
            return {"status": status}

        report = self.retry.retry_cases(
            self.root, self.manifest, pending, self.root / "batch", diagnose, stop_after=2)
        self.assertEqual(report["status"], "finished")
        self.assertEqual(report["attempted"], 3)
        self.assertEqual(report["done"], 1)

    def test_tampered_frozen_adapter_is_rejected_before_import(self):
        adapter = self.root / "benchmark-adapter.py"
        original = b"IMPORTED = True\n"
        adapter.write_bytes(original)
        self.manifest["adapter_sha256"] = hashlib.sha256(original).hexdigest()
        self.assertTrue(self.retry.load_frozen_adapter(self.root, self.manifest).IMPORTED)
        adapter.write_bytes(b"raise AssertionError('must not execute')\n")
        with self.assertRaisesRegex(ValueError, "adapter provenance"):
            self.retry.load_frozen_adapter(self.root, self.manifest)

    def test_model_configuration_drift_is_rejected(self):
        self.manifest.update(
            benchmark_revision="revision", skill_fingerprints={"fixed": "snapshot"},
            model="openai/example", provider_source="codex", diagnosis_protocol="responses",
            diagnosis_model_config={"name": "example", "options": {"reasoningEffort": "xhigh"}})
        provider = {"npm": "@ai-sdk/openai", "models": {
            "example": {"name": "example", "options": {"reasoningEffort": "low"}}}}
        adapter = SimpleNamespace(fingerprint=lambda _: "snapshot",
                                  load_provider=lambda *_: ("openai", provider))
        with patch.object(self.retry.subprocess, "check_output", side_effect=["revision\n", "", ""]):
            with self.assertRaisesRegex(ValueError, "model configuration"):
                self.retry.validate_environment(self.root, self.root, self.manifest, adapter)

    def test_symlink_results_are_rejected(self):
        failed = self.record("CASE-A", "error")
        (failed / "linked-events").symlink_to(failed / "run.json")
        with self.assertRaisesRegex(ValueError, "Unsafe symlink"):
            self.retry.archive_failure(failed, self.root / "archive", self.run_id)
        self.assertTrue(failed.exists())

    def test_active_original_runner_blocks_recovery(self):
        command = f"123 python3 /tmp/benchmark-adapter.py --output {self.root}\n"
        with patch.object(self.retry.subprocess, "check_output", return_value=command):
            with self.assertRaisesRegex(ValueError, "active"):
                self.retry.assert_inactive(self.root)

    def test_diagnosis_lock_blocks_recovery_before_loading_run(self):
        with (self.root / ".diagnosis.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(self.retry, "assert_inactive", return_value=False), \
                    patch.object(self.retry, "read_json") as read:
                with self.assertRaises((BlockingIOError, ValueError)):
                    self.retry.main(["--output", str(self.root), "--benchmark", str(self.root)])
                read.assert_not_called()

    def test_runner_flags_and_equal_output_argument_are_detected(self):
        commands = (
            f"123 python3 /tmp/benchmark-adapter.py --output={self.root}\n",
            f"123 python3 -B -u /tmp/benchmark-adapter.py --output {self.root}\n",
        )
        for command in commands:
            with self.subTest(command=command), patch.object(
                    self.retry.subprocess, "check_output", return_value=command):
                with self.assertRaisesRegex(ValueError, "active"):
                    self.retry.assert_inactive(self.root)

    def test_added_ignored_and_untracked_logs_fail_frozen_input_validation(self):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

        git("init", "-q")
        case = self.root / "benchmark-DTS/cases/CASE-A"
        case.mkdir(parents=True)
        (case / "input.json").write_text("{}")
        (self.root / ".gitignore").write_text("*.ignored\n")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-qm", "fixture")
        self.manifest.update(benchmark_revision=git("rev-parse", "HEAD"),
                             skill_fingerprints={"fixed": "snapshot"}, model="openai/example")
        adapter = SimpleNamespace(fingerprint=lambda _: "snapshot", load_provider=lambda *_: (
            "openai", {"models": {"example": {}}}))
        for name in ("extra.txt", "extra.ignored"):
            path = case / name
            path.write_text("new evidence that was not in the original input")
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "contents changed"):
                self.retry.validate_environment(self.root, self.root, self.manifest, adapter)
            path.unlink()

    def test_relative_output_of_other_process_is_not_resolved_against_our_cwd(self):
        command = "123 python3 /tmp/benchmark-adapter.py --output output\n"
        with patch.object(self.retry.subprocess, "check_output", return_value=command):
            with self.assertRaisesRegex(ValueError, "relative output"):
                self.retry.assert_inactive(self.root / "output")

    def test_pending_success_cannot_be_replaced(self):
        folder = self.record("CASE-A", "done")
        before = self.retry.file_hashes(folder)
        item = {"arm": "fixed", **self.manifest["cases"][0]}
        called = []
        with self.assertRaisesRegex(ValueError, "existing errors"):
            self.retry.retry_cases(self.root, self.manifest, [item], self.root / "batch", called.append)
        self.assertEqual(called, [])
        self.assertEqual(before, self.retry.file_hashes(folder))

    def test_first_judgments_may_be_added_while_retry_preserves_existing_bytes(self):
        valid = self.record("CASE-A", "done")
        (valid / "result.md").write_text("valid answer")
        self.record("CASE-B", "error")
        pending = self.retry.select_failures(self.root, self.manifest)

        def diagnose(item):
            (valid / "judge.json").write_text('{"status":"judged","score":73}')
            self.record(item["case_id"], "done")
            return {"status": "done"}

        report = self.retry.retry_cases(
            self.root, self.manifest, pending, self.root / "batch", diagnose)
        self.assertEqual(report["done"], 1)
        self.assertEqual((valid / "result.md").read_text(), "valid answer")

    def test_retry_detects_overwrite_of_existing_valid_judgment(self):
        valid = self.record("CASE-A", "done")
        (valid / "judge.json").write_text('{"status":"judged","score":73}')
        self.record("CASE-B", "error")
        pending = self.retry.select_failures(self.root, self.manifest)

        def diagnose(item):
            (valid / "judge.json").write_text('{"status":"judged","score":99}')
            self.record(item["case_id"], "done")
            return {"status": "done"}

        with self.assertRaisesRegex(ValueError, "Protected successful result changed"):
            self.retry.retry_cases(self.root, self.manifest, pending, self.root / "batch", diagnose)

    def test_judge_only_process_does_not_block_error_recovery(self):
        command = f"123 python3 /tmp/benchmark-adapter.py --output {self.root} --judge-only\n"
        with patch.object(self.retry.subprocess, "check_output", return_value=command):
            self.retry.assert_inactive(self.root)

    def test_first_judge_atomic_publish_does_not_protect_temporary_file(self):
        valid = self.record("CASE-A", "done")
        temporary = valid / "judge.json.tmp"
        temporary.write_text('{"status":"judged","score":73}')
        self.record("CASE-B", "error")
        pending = self.retry.select_failures(self.root, self.manifest)

        def diagnose(item):
            temporary.replace(valid / "judge.json")
            self.record(item["case_id"], "done")
            return {"status": "done"}

        report = self.retry.retry_cases(
            self.root, self.manifest, pending, self.root / "batch", diagnose)
        protected = json.loads((self.root / "batch/protected.json").read_text())
        self.assertNotIn("judge.json.tmp", next(iter(protected.values())))
        self.assertEqual(report["done"], 1)

    def test_partial_answers_are_not_archived_during_active_judging(self):
        failed = self.record("CASE-A", "error")
        (failed / "result.md").write_text("partial answer")
        pending = self.retry.select_failures(self.root, self.manifest)
        before = self.retry.file_hashes(failed)
        with self.assertRaisesRegex(ValueError, "partial answer"):
            self.retry.validate_parallel_recovery(self.root, pending)
        self.assertEqual(before, self.retry.file_hashes(failed))


if __name__ == "__main__":
    unittest.main()
