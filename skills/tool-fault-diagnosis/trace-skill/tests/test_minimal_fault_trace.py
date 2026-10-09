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
import json
from pathlib import Path
import copy
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "build_fault_trace.py"
FIXTURE = SKILL_ROOT / "tests" / "fixtures" / "minimal-plog"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, validate_trace  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


class MinimalFaultTraceTest(unittest.TestCase):
    def test_cli_builds_auditable_microsecond_fault_anchor_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    str(FIXTURE),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace_path = output_dir / "fault-trace.json"
            html_path = output_dir / "fault-trace.html"
            tracing_path = output_dir / "tracing-report.html"
            self.assertTrue(trace_path.is_file())
            self.assertTrue(html_path.is_file())
            self.assertTrue(tracing_path.is_file())
            self.assertEqual(html_path.read_bytes(), tracing_path.read_bytes())
            self.assertIn("tracing-report.html", completed.stdout)

            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["schema_version"], "1.0.0")
            self.assertEqual(trace["status"], "partial")
            self.assertEqual(trace["metadata"]["generator_version"], "0.6.0")
            self.assertEqual(trace["metadata"]["severity_rules_version"], "1.1.0")

            self.assertEqual(len(trace["events"]), 2)
            anchor = trace["events"][1]
            self.assertEqual(anchor["level"], "FATAL")
            self.assertEqual(anchor["component"], "Runtime")
            self.assertEqual(anchor["timestamp"]["raw"], "2026-09-08-10:11:12.123456")
            self.assertEqual(anchor["timestamp"]["clock_domain_id"], "clock-host-wall-unknown-zone")
            self.assertEqual(anchor["timestamp"]["offset_us"], 6)
            self.assertIsInstance(anchor["timestamp"]["offset_us"], int)

            source_record = FIXTURE.joinpath("fault.log").read_text(encoding="utf-8").splitlines()[1]
            evidence = trace["evidence"][anchor["evidence_ids"][0]]
            self.assertEqual(evidence["source_path"], "fault.log")
            self.assertEqual(evidence["line"], 2)
            self.assertEqual(
                evidence["record_sha256"],
                hashlib.sha256(source_record.encode("utf-8")).hexdigest(),
            )
            self.assertIn("Process abort", evidence["excerpt"])

            self.assertEqual(trace["fault_candidates"], [anchor["id"]])
            self.assertEqual(trace["selected_anchor_id"], anchor["id"])
            self.assertEqual(trace["views"][0]["highlighted_event_ids"], [anchor["id"]])
            self.assertEqual(trace["relationships"], [])
            self.assertIn("missing_device_logs", trace["diagnostics"]["gaps"])

            html = html_path.read_text(encoding="utf-8")
            self.assertIn("CANN Fault Trace", html)
            self.assertIn("data-offset-us=\"6\"", html)
            self.assertIn("2026-09-08-10:11:12.123456", html)
            self.assertIn("Fault anchor", html)
            self.assertIn(evidence["record_sha256"], html)
            self.assertIn("fault-trace-data", html)
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)

    def test_cli_returns_invalid_input_exit_for_a_missing_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "output"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    str(root / "missing"),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("input path is not readable", completed.stderr)
            self.assertFalse(output_dir.exists())

    def test_invalid_calendar_timestamp_is_reported_as_no_usable_trace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            input_dir.joinpath("invalid.log").write_text(
                "[FATAL] RUNTIME(7,app):2026-99-08-10:11:12.000001 "
                "[runtime.cc:3]Process abort\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-B", str(CLI), str(input_dir), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 3)
            self.assertIn("no usable timestamped", completed.stderr)
            self.assertTrue(output_dir.joinpath("fault-trace-inventory.json").is_file())
            self.assertFalse(output_dir.joinpath("fault-trace.json").exists())

    def test_sensitive_identifiers_are_stably_pseudonymized_in_both_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            input_dir.joinpath("private.log").write_text(
                "[FATAL] RUNTIME(9,C:\\Users\\alice\\secret\\app.exe):"
                "2026-09-08-10:11:12.000001 [runtime.cc:3]Process abort "
                "user=alice host=worker-node ip=10.1.2.3 "
                "path=C:\\Users\\alice\\secret\\model.om\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-B", str(CLI), str(input_dir), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            json_text = output_dir.joinpath("fault-trace.json").read_text(encoding="utf-8")
            html_text = output_dir.joinpath("fault-trace.html").read_text(encoding="utf-8")
            for secret in ("alice", "worker-node", "10.1.2.3", "C:\\Users"):
                self.assertNotIn(secret, json_text)
                self.assertNotIn(secret, html_text)
            for alias in ("USER-001", "HOST-001", "IP-001", "PATH-001"):
                self.assertIn(alias, json_text)
                self.assertIn(alias, html_text)

    def test_runtime_validator_rejects_dangling_and_unproven_references(self):
        valid_trace = build_trace(FIXTURE)
        invalid_mutations = []

        dangling_candidate = copy.deepcopy(valid_trace)
        dangling_candidate["fault_candidates"].append("event-missing")
        invalid_mutations.append(dangling_candidate)

        unrelated_highlight = copy.deepcopy(valid_trace)
        unrelated_highlight["views"][0]["highlighted_event_ids"].append("event-000001")
        invalid_mutations.append(unrelated_highlight)

        duplicate_event = copy.deepcopy(valid_trace)
        duplicate_event["events"][1]["id"] = duplicate_event["events"][0]["id"]
        invalid_mutations.append(duplicate_event)

        inconsistent_evidence = copy.deepcopy(valid_trace)
        inconsistent_evidence["evidence"]["evidence-000001"]["id"] = "evidence-other"
        invalid_mutations.append(inconsistent_evidence)

        for invalid_trace in invalid_mutations:
            with self.subTest(trace=invalid_trace):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid_trace)

    def test_runtime_validator_rejects_missing_or_wrongly_typed_nested_fields(self):
        valid_trace = build_trace(FIXTURE)
        invalid_mutations = []

        missing_raw_timestamp = copy.deepcopy(valid_trace)
        del missing_raw_timestamp["events"][0]["timestamp"]["raw"]
        invalid_mutations.append(missing_raw_timestamp)

        non_integer_evidence_line = copy.deepcopy(valid_trace)
        non_integer_evidence_line["evidence"]["evidence-000001"]["line"] = "1"
        invalid_mutations.append(non_integer_evidence_line)

        non_string_generator_version = copy.deepcopy(valid_trace)
        non_string_generator_version["metadata"]["generator_version"] = 1
        invalid_mutations.append(non_string_generator_version)

        missing_view_context = copy.deepcopy(valid_trace)
        del missing_view_context["views"][0]["context_event_ids"]
        del missing_view_context["views"][0]["context_partition_id"]
        invalid_mutations.append(missing_view_context)

        for invalid_trace in invalid_mutations:
            with self.subTest(trace=invalid_trace):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid_trace)

    def test_candidate_rules_accept_sigabrt_but_reject_negated_crash_text(self):
        cases = (
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]No crash detected\n", 3),
            ("[ERROR] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]Caught SIGABRT\n", 0),
            ("[ERROR] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]OOM while allocating\n", 0),
            ("[ERROR] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]panic: runtime failed\n", 0),
            ("[ERROR] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]Abort due to unrecoverable error\n", 0),
            ("[WARNING] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]Caught SIGABRT\n", 0),
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]No OOM was observed\n", 3),
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]Trace path /tmp/sigabrt/output\n", 3),
            ("[INFO] TDT(7,app):2026-09-08-10:11:12.000001 [tdt.cc:3]Need to check oom reserved mem\n", 3),
            ("[ERROR] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]SIGABRT\n", 0),
            ("[ERROR] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]signal: SIGABRT\n", 0),
            ("[ERROR] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]OOM\n", 0),
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]SIGABRT handler installed\n", 3),
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]OOM monitor enabled\n", 3),
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]OOM killer disabled\n", 3),
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]OOM killer initialized\n", 3),
            ("[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:3]out of memory check passed\n", 3),
        )
        for record, expected_exit in cases:
            with self.subTest(record=record), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                input_dir = root / "input"
                input_dir.mkdir()
                input_dir.joinpath("candidate.log").write_text(record, encoding="utf-8")

                completed = subprocess.run(
                    [sys.executable, "-B", str(CLI), str(input_dir), "--output-dir", str(root / "output")],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )

                self.assertEqual(completed.returncode, expected_exit, completed.stderr)

    def test_submicrosecond_grammar_rejects_short_fractional_timestamp(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            input_dir.mkdir()
            input_dir.joinpath("millisecond.log").write_text(
                "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.123 "
                "[runtime.cc:3]Process abort\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-B", str(CLI), str(input_dir), "--output-dir", str(root / "output")],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 3)

    def test_cli_rejects_output_file_and_output_nested_below_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            input_dir.mkdir()
            input_dir.joinpath("fault.log").write_text(
                FIXTURE.joinpath("fault.log").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            output_file = root / "existing-file"
            output_file.write_text("occupied", encoding="utf-8")
            cases = (output_file, input_dir / "generated-output")

            for output_path in cases:
                with self.subTest(output_path=output_path):
                    completed = subprocess.run(
                        [sys.executable, "-B", str(CLI), str(input_dir), "--output-dir", str(output_path)],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                    )

                    self.assertEqual(completed.returncode, 2)
                    self.assertIn("invalid output directory", completed.stderr)

    def test_cli_rejects_output_nested_below_symlinked_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            input_dir.mkdir()
            input_dir.joinpath("fault.log").write_text(
                FIXTURE.joinpath("fault.log").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            root_link = root.parent / f"{root.name}-link"
            try:
                root_link.symlink_to(root, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlinks unavailable: {error}")
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(CLI),
                        str(root_link / "input"),
                        "--output-dir",
                        str(input_dir / "output"),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )

                self.assertEqual(completed.returncode, 2)
                self.assertIn("invalid output directory", completed.stderr)
            finally:
                root_link.unlink()

    def test_redaction_handles_unquoted_labels_ipv6_and_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            input_dir.joinpath("adversarial.log").write_text(
                "[FATAL] RUNTIME(9,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:3]Abort host worker-node user alice "
                "ip 2001:db8::1 path=C:\\Program Files\\Secret Team\\model.om "
                "data=/srv/team-secret/model.om\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-B", str(CLI), str(input_dir), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            rendered = (
                output_dir.joinpath("fault-trace.json").read_text(encoding="utf-8")
                + output_dir.joinpath("fault-trace.html").read_text(encoding="utf-8")
            )
            for secret in (
                "worker-node",
                "alice",
                "2001:db8::1",
                "Program Files",
                "Secret Team",
                "/srv/team-secret/model.om",
            ):
                self.assertNotIn(secret, rendered)
            for alias in ("HOST-001", "USER-001", "IP-001", "PATH-001"):
                self.assertIn(alias, rendered)

    def test_runtime_validator_covers_every_published_nested_reference(self):
        valid_trace = build_trace(FIXTURE)
        invalid_mutations = []

        non_object_event = copy.deepcopy(valid_trace)
        non_object_event["events"][0] = "event"
        invalid_mutations.append(non_object_event)

        non_object_domain = copy.deepcopy(valid_trace)
        non_object_domain["clock_domains"][0] = "domain"
        invalid_mutations.append(non_object_domain)

        invalid_hash = copy.deepcopy(valid_trace)
        invalid_hash["evidence"]["evidence-000001"]["record_sha256"] = "not-a-hash"
        invalid_mutations.append(invalid_hash)

        missing_relationship_evidence = copy.deepcopy(valid_trace)
        missing_relationship_evidence["relationships"] = [{
            "id": "relationship-1",
            "source_event_id": "event-000001",
            "target_event_id": "event-000002",
            "strength": "proven",
            "evidence_ids": ["evidence-missing"],
        }]
        invalid_mutations.append(missing_relationship_evidence)

        dangling_span = copy.deepcopy(valid_trace)
        dangling_span["spans"] = [{
            "id": "span-1",
            "start_event_id": "event-000001",
            "end_event_id": "event-missing",
            "duration_us": 6,
            "evidence_ids": ["evidence-000001", "evidence-000002"],
        }]
        invalid_mutations.append(dangling_span)

        invalid_input = copy.deepcopy(valid_trace)
        invalid_input["input"]["inventory"][0]["parsed_records"] = -1
        invalid_mutations.append(invalid_input)

        invalid_diagnostics = copy.deepcopy(valid_trace)
        invalid_diagnostics["diagnostics"]["event_count"] = "2"
        invalid_mutations.append(invalid_diagnostics)

        duplicate_context = copy.deepcopy(valid_trace)
        duplicate_context["views"][0]["context_event_ids"].append("event-000001")
        invalid_mutations.append(duplicate_context)

        for invalid_trace in invalid_mutations:
            with self.subTest(trace=invalid_trace):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid_trace)

    def test_runtime_validator_enforces_selected_view_and_identifier_types(self):
        valid_trace = build_trace(FIXTURE)
        invalid_mutations = []

        mismatched_selected_view = copy.deepcopy(valid_trace)
        mismatched_selected_view["fault_candidates"].append("event-000001")
        mismatched_selected_view["diagnostics"]["fault_candidate_count"] = 2
        mismatched_selected_view["views"][0]["anchor_id"] = "event-000001"
        mismatched_selected_view["views"][0]["highlighted_event_ids"] = ["event-000001"]
        invalid_mutations.append(mismatched_selected_view)

        list_event_id = copy.deepcopy(valid_trace)
        list_event_id["events"][0]["id"] = ["event-000001"]
        invalid_mutations.append(list_event_id)

        null_relationship_id = copy.deepcopy(valid_trace)
        null_relationship_id["relationships"] = [{
            "id": None,
            "source_event_id": "event-000001",
            "target_event_id": "event-000002",
            "strength": "inferred",
            "evidence_ids": ["evidence-000001"],
        }]
        invalid_mutations.append(null_relationship_id)

        duplicate_relationship_id = copy.deepcopy(valid_trace)
        relationship = {
            "id": "relationship-1",
            "source_event_id": "event-000001",
            "target_event_id": "event-000002",
            "strength": "inferred",
            "evidence_ids": ["evidence-000001"],
        }
        duplicate_relationship_id["relationships"] = [relationship, copy.deepcopy(relationship)]
        invalid_mutations.append(duplicate_relationship_id)

        integer_span_id = copy.deepcopy(valid_trace)
        integer_span_id["spans"] = [{
            "id": 1,
            "start_event_id": "event-000001",
            "end_event_id": "event-000002",
            "duration_us": 6,
            "evidence_ids": ["evidence-000001", "evidence-000002"],
        }]
        invalid_mutations.append(integer_span_id)

        list_event_evidence_id = copy.deepcopy(valid_trace)
        list_event_evidence_id["events"][0]["evidence_ids"] = [["evidence-000001"]]
        invalid_mutations.append(list_event_evidence_id)

        list_clock_domain_reference = copy.deepcopy(valid_trace)
        list_clock_domain_reference["events"][0]["timestamp"]["clock_domain_id"] = ["clock-host-wall-unknown-zone"]
        invalid_mutations.append(list_clock_domain_reference)

        list_relationship_source = copy.deepcopy(valid_trace)
        list_relationship_source["relationships"] = [{
            "id": "relationship-1",
            "source_event_id": ["event-000001"],
            "target_event_id": "event-000002",
            "strength": "inferred",
            "evidence_ids": ["evidence-000001"],
        }]
        invalid_mutations.append(list_relationship_source)

        list_span_evidence = copy.deepcopy(valid_trace)
        list_span_evidence["spans"] = [{
            "id": "span-1",
            "start_event_id": "event-000001",
            "end_event_id": "event-000002",
            "duration_us": 6,
            "evidence_ids": [["evidence-000001"], "evidence-000002"],
        }]
        invalid_mutations.append(list_span_evidence)

        for invalid_trace in invalid_mutations:
            with self.subTest(trace=invalid_trace):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid_trace)

    def test_cli_returns_no_trace_exit_when_no_fault_anchor_exists(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            input_dir.joinpath("healthy.log").write_text(
                "[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:3]Task completed successfully\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    str(input_dir),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 3)
            self.assertIn("no eligible fault anchor", completed.stderr)
            self.assertTrue(output_dir.joinpath("fault-trace-inventory.json").is_file())
            self.assertFalse(output_dir.joinpath("fault-trace.json").exists())


if __name__ == "__main__":
    unittest.main()
