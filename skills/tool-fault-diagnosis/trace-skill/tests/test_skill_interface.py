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

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "build_fault_trace.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, validate_trace  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


class SkillInterfaceTest(unittest.TestCase):
    def write_fixture(self, root: Path) -> None:
        root.joinpath("fault.log").write_text(
            "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000001 "
            "[runtime.cc:1]First abort token=TOP-SECRET.\n"
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000002 "
            "[runtime.cc:2]Caller selected event token=SECOND-SECRET.\n"
            "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000003 "
            "[runtime.cc:3]Later abort token=THIRD-SECRET.\n",
            encoding="utf-8",
        )

    def run_cli(
        self, input_root: Path, output: Path, *arguments: str
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(CLI),
                str(input_root),
                "--output-dir",
                str(output),
                *arguments,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_caller_anchor_takes_precedence_over_eval_anchor(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_root = root / "input"
            input_root.mkdir()
            self.write_fixture(input_root)
            eval_anchor = root / "eval-anchor.json"
            eval_anchor.write_text(
                json.dumps({"fault_anchor": {"event_id": "event-000001"}}),
                encoding="utf-8",
            )

            completed = self.run_cli(
                input_root,
                root / "output",
                "--anchor-id",
                "event-000002",
                "--eval-anchor-json",
                str(eval_anchor),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["selected_anchor_id"], "event-000002")
            self.assertIn("event-000002", trace["fault_candidates"])
            self.assertEqual(
                trace["metadata"]["anchor_request"],
                {
                    "source": "caller",
                    "selector": {"kind": "event_id", "value": "event-000002"},
                },
            )
            self.assertEqual(trace["diagnostics"]["anchor_selection"]["reason"], "explicit_event_id")
            self.assertEqual(
                trace["diagnostics"]["anchor_selection"]["domain_candidate_ids"],
                ["event-000001"],
            )

    def test_eval_anchor_can_select_a_source_location(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_root = root / "input"
            input_root.mkdir()
            self.write_fixture(input_root)
            eval_anchor = root / "eval-anchor.json"
            eval_anchor.write_text(
                json.dumps(
                    {
                        "analysis_id": "eval-42",
                        "fault_anchor": {"source_path": "fault.log", "line": 3},
                    }
                ),
                encoding="utf-8",
            )

            completed = self.run_cli(
                input_root,
                root / "output",
                "--eval-anchor-json",
                str(eval_anchor),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["selected_anchor_id"], "event-000003")
            self.assertEqual(
                trace["metadata"]["anchor_request"]["source"], "eval-skill"
            )
            self.assertEqual(trace["diagnostics"]["anchor_selection"]["reason"], "explicit_source_location")

    def test_caller_metadata_and_timezone_add_epoch_microseconds(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_root = root / "input"
            input_root.mkdir()
            self.write_fixture(input_root)

            completed = self.run_cli(
                input_root,
                root / "output",
                "--cann-version",
                "8.5.0",
                "--source-timezone",
                "+08:00",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(
                trace["metadata"]["cann_version"],
                {"value": "8.5.0", "source": "caller"},
            )
            self.assertEqual(
                trace["metadata"]["source_timezone"],
                {"value": "+08:00", "source": "caller"},
            )
            self.assertEqual(trace["events"][0]["timestamp"]["epoch_us"], "1788833472000001")
            self.assertEqual(trace["clock_domains"][0]["kind"], "host-wall-source-zone")

    def test_source_timezone_preserves_explicit_clock_alignment_targets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            host = root / "host" / "log" / "debug" / "plog"
            device = root / "slog" / "dev-os-0" / "run" / "device-os"
            host.mkdir(parents=True)
            device.mkdir(parents=True)
            host.joinpath("fault.log").write_text(
                "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Abort.\n",
                encoding="utf-8",
            )
            device.joinpath("device.log").write_text(
                "[INFO] RUNTIME(9,device):1970-01-01-00:00:00.000002 "
                "[runtime.cc:2][0.000002]clock_alignment target=clock-host-wall-unknown-zone "
                "offset_us=0 uncertainty_us=5 method=sync.\n",
                encoding="utf-8",
            )

            trace = build_trace(root, source_timezone="+08:00")

            self.assertEqual(
                trace["clock_alignments"][0]["target_clock_domain_id"],
                "clock-host-wall-source-zone",
            )

    def test_additional_redaction_extends_builtins_and_records_rule_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_root = root / "input"
            input_root.mkdir()
            self.write_fixture(input_root)
            config = root / "redaction.json"
            config.write_text(
                json.dumps({"additional_patterns": {"TOKEN": r"(?:TOP|SECOND|THIRD)-SECRET"}}),
                encoding="utf-8",
            )

            completed = self.run_cli(
                input_root,
                root / "output",
                "--redaction-config",
                str(config),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            json_text = (root / "output" / "fault-trace.json").read_text(encoding="utf-8")
            html_text = (root / "output" / "fault-trace.html").read_text(encoding="utf-8")
            for secret in ("TOP-SECRET", "SECOND-SECRET", "THIRD-SECRET"):
                self.assertNotIn(secret, json_text)
                self.assertNotIn(secret, html_text)
            self.assertIn("TOKEN-001", json_text)
            trace = json.loads(json_text)
            self.assertEqual(
                trace["metadata"]["redaction_rules"],
                {
                    "builtin_profile": "cann-trace-default-v1",
                    "additional_pattern_names": ["TOKEN"],
                    "source": "caller",
                },
            )

    def test_invalid_configuration_returns_2_and_missing_anchor_returns_3(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_root = root / "input"
            input_root.mkdir()
            self.write_fixture(input_root)
            invalid_config = root / "invalid.json"
            invalid_config.write_text(
                json.dumps({"additional_patterns": {"TOKEN": "("}}),
                encoding="utf-8",
            )

            invalid = self.run_cli(
                input_root,
                root / "invalid-output",
                "--redaction-config",
                str(invalid_config),
            )
            missing = self.run_cli(
                input_root,
                root / "missing-output",
                "--anchor-id",
                "event-999999",
            )

            self.assertEqual(invalid.returncode, 2)
            self.assertIn("invalid redaction configuration", invalid.stderr)
            self.assertEqual(missing.returncode, 3)
            self.assertIn("requested fault anchor was not found", missing.stderr)

    def test_empty_anchor_is_invalid_and_artifact_write_failure_returns_4(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_root = root / "input"
            input_root.mkdir()
            self.write_fixture(input_root)

            invalid = self.run_cli(
                input_root,
                root / "invalid-output",
                "--anchor-id",
                "",
            )
            blocked_output = root / "blocked-output"
            blocked_output.mkdir()
            blocked_output.joinpath("fault-trace.json").mkdir()
            failed = self.run_cli(input_root, blocked_output)

            self.assertEqual(invalid.returncode, 2)
            self.assertIn("invalid anchor ID", invalid.stderr)
            self.assertEqual(failed.returncode, 4)
            self.assertIn("generation failed", failed.stderr)

    def test_runtime_validator_rejects_invalid_interface_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.write_fixture(root)
            trace = build_trace(root, cann_version="8.5.0", source_timezone="+08:00")

            invalid_epoch = copy.deepcopy(trace)
            invalid_epoch["events"][0]["timestamp"]["epoch_us"] = 123
            invalid_source = copy.deepcopy(trace)
            invalid_source["metadata"]["cann_version"]["source"] = "guessed"
            invalid_timezone = copy.deepcopy(trace)
            invalid_timezone["metadata"]["source_timezone"]["value"] = "Not/AZone"

            for invalid in (invalid_epoch, invalid_source, invalid_timezone):
                with self.subTest(trace=invalid):
                    with self.assertRaises(TraceValidationError):
                        validate_trace(invalid)

    def test_schema_publishes_optional_interface_metadata(self):
        schema = json.loads(
            (SKILL_ROOT / "schemas" / "fault-trace-v1.schema.json").read_text(encoding="utf-8")
        )
        metadata = schema["properties"]["metadata"]["properties"]
        timestamp = schema["$defs"]["timestamp"]["properties"]

        self.assertEqual(metadata["cann_version"]["$ref"], "#/$defs/callerValue")
        self.assertEqual(metadata["source_timezone"]["$ref"], "#/$defs/callerValue")
        self.assertEqual(timestamp["epoch_us"]["pattern"], "^-?[0-9]+$")


if __name__ == "__main__":
    unittest.main()
