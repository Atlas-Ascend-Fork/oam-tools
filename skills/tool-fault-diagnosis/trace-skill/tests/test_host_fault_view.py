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

import json
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "build_fault_trace.py"
FIXTURES = SKILL_ROOT / "tests" / "fixtures" / "host-real-redacted"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, validate_trace  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


class HostFaultViewTest(unittest.TestCase):
    def run_cli(self, input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(CLI),
                str(input_path),
                "--output-dir",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_real_host_formats_build_a_process_scoped_fault_view(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"

            completed = self.run_cli(FIXTURES / "fault-scope", output)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads(output.joinpath("fault-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["metadata"]["generator_version"], "0.6.0")
            self.assertEqual(
                trace["metadata"]["parser_versions"],
                {
                    "device-common-slog": "1.1.0",
                    "host-common-plog": "2.1.0",
                    "host-kernel": "1.1.0",
                },
            )
            self.assertEqual(len(trace["events"]), 6)
            device_inventory = next(
                item for item in trace["input"]["inventory"]
                if item["source_path"].endswith("device.log")
            )
            self.assertEqual(device_inventory["status"], "parsed")
            self.assertEqual(device_inventory["parser"], "device-common-slog-v1")

            anchor = next(event for event in trace["events"] if event["id"] == trace["selected_anchor_id"])
            self.assertEqual(anchor["timestamp"]["raw"], "2026-08-30-14:24:22.940.584")
            self.assertEqual(anchor["timestamp"]["offset_us"], 84)
            self.assertEqual(anchor["execution"]["pid"], "77034")
            self.assertEqual(anchor["execution"]["tid"], "77034")
            self.assertEqual(anchor["raw_component"], "RUNTIME")
            self.assertEqual(anchor["component"], "Runtime")
            self.assertEqual(anchor["component_mapping_rule"], "builtin-host-v1:RUNTIME")
            self.assertEqual(anchor["fault_rule_id"], "level-fatal")

            kernel = next(event for event in trace["events"] if event["raw_component"] == "hdcdrv")
            self.assertEqual(kernel["component"], "Driver")
            self.assertEqual(kernel["execution"]["pid"], "77034")
            self.assertEqual(kernel["execution"]["tid"], "77036")
            self.assertEqual(kernel["timestamp"]["monotonic_raw"], "439.288679")
            self.assertEqual(kernel["timestamp"]["offset_us"], 90)

            selected_view = trace["views"][0]
            context = set(selected_view["context_event_ids"])
            scoped_events = [event for event in trace["events"] if event["id"] in context]
            self.assertEqual({event["execution"]["pid"] for event in scoped_events}, {"77034"})
            self.assertEqual(selected_view["scope"]["kind"], "process")
            self.assertEqual(selected_view["scope"]["pid"], "77034")
            self.assertEqual(len(selected_view["excluded_event_ids"]), 3)
            self.assertEqual(trace["diagnostics"]["excluded_event_count"], 3)

            visible_html = output.joinpath("fault-trace.html").read_text(encoding="utf-8").split(
                '<script id="fault-trace-data"', 1
            )[0]
            self.assertEqual(
                visible_html.count('<button class="event event-point'),
                len(selected_view["highlighted_event_ids"]),
            )
            unrelated = next(
                event for event in trace["events"] if "Unrelated" in event["message"]
            )
            self.assertNotIn(f'data-event-id="{unrelated["id"]}"', visible_html)

    def test_real_error_level_records_do_not_become_fault_anchor_by_level_alone(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"

            completed = self.run_cli(FIXTURES / "error-only", output)

            self.assertEqual(completed.returncode, 3, completed.stderr)
            self.assertIn("no eligible fault anchor", completed.stderr)
            audit = json.loads(
                output.joinpath("fault-trace-inventory.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit["input"]["inventory"][0]["parsed_records"], 3)
            self.assertEqual(audit["input"]["inventory"][0]["parser"], "host-common-plog-v2")

    def test_adapter_detection_uses_source_role_and_scans_past_preamble(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            host_plog = root / "dfx" / "log" / "host" / "cann" / "debug" / "plog.log"
            host_plog.parent.mkdir(parents=True)
            host_plog.write_text(
                "\n".join(["collector preamble"] * 51)
                + "\n[FATAL] RUNTIME(7,app):2026-08-30-14:24:22.940.584 "
                "[runtime.cc:10][tid:7] Process abort.\n",
                encoding="utf-8",
            )
            host_named_device = root / "dfx" / "log" / "host" / "device-tools" / "plog.log"
            host_named_device.parent.mkdir(parents=True)
            host_named_device.write_text(
                "[INFO] GE(7,app):2026-08-30-14:24:22.940.590 "
                "[graph.cc:20][tid:8] Host-side work.\n",
                encoding="utf-8",
            )
            device_log = root / "dfx" / "log" / "device" / "run" / "device.log"
            device_log.parent.mkdir(parents=True)
            device_log.write_text(
                "[FATAL] RUNTIME(7,device-app):2026-08-30-14:24:22.940.592 "
                "[device.cc:11][tid:44] Device panic.\n",
                encoding="utf-8",
            )
            root_device_log = root / "device.log"
            root_device_log.write_text(
                "[FATAL] RUNTIME(7,device-app):2026-08-30-14:24:22.940.593 "
                "[device.cc:12][tid:44] Device panic.\n",
                encoding="utf-8",
            )
            collected_host_plog = root / "host-plog" / "plog-1.log"
            collected_host_plog.parent.mkdir(parents=True)
            collected_host_plog.write_text(
                "[FATAL] GE(7,app):2026-08-30-14:24:22.940.594 "
                "[graph.cc:21][tid:9] Process abort.\n",
                encoding="utf-8",
            )
            collected_host_run_plog = root / "host-run-plog" / "plog-2.log"
            collected_host_run_plog.parent.mkdir(parents=True)
            collected_host_run_plog.write_text(
                "[INFO] RUNTIME(7,app):2026-08-30-14:24:22.940.595 "
                "[runtime.cc:22][tid:10] Host runtime work.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertEqual(len(trace["events"]), 6)
            collected_items = [
                item for item in trace["input"]["inventory"]
                if item["source_path"].startswith(("host-plog/", "host-run-plog/"))
            ]
            self.assertEqual(len(collected_items), 2)
            self.assertTrue(all(item["status"] == "parsed" for item in collected_items))
            self.assertTrue(
                all(item["parser"] == "host-common-plog-v2" for item in collected_items)
            )
            device_items = [
                item for item in trace["input"]["inventory"]
                if item["source_path"].endswith("device.log")
            ]
            self.assertEqual(len(device_items), 2)
            self.assertTrue(all(item["status"] == "parsed" for item in device_items))
            self.assertTrue(
                all(item["parser"] == "device-common-slog-v1" for item in device_items)
            )
            device_events = [event for event in trace["events"] if event["location"] == "device"]
            self.assertEqual(len(device_events), 2)
            self.assertTrue(
                all(event["id"] in trace["views"][0]["excluded_event_ids"] for event in device_events)
            )

    def test_unknown_kernel_module_stays_unclassified(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            kernel_log = root / "slog" / "host" / "host_kernel.log"
            kernel_log.parent.mkdir(parents=True)
            kernel_log.write_text(
                "[2026-08-30-14:24:22.940590] [439.288679] [ascend] [hdcdrv] "
                "[FATAL] [notify.c 42] <app:7:8> Process abort.\n"
                "[2026-08-30-14:24:22.940600] [439.288689] [linux] [filesystem] "
                "[INFO] [fs.c 9] <app:7:8> Flush complete.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            unknown = next(event for event in trace["events"] if event["raw_component"] == "filesystem")
            self.assertEqual(unknown["component"], "Unclassified")
            self.assertEqual(unknown["component_mapping_rule"], "unclassified-host-kernel-v1")

    def test_unknown_pid_anchor_does_not_join_other_unknown_pid_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            kernel_log = root / "slog" / "host" / "host_kernel.log"
            kernel_log.parent.mkdir(parents=True)
            kernel_log.write_text(
                "[2026-08-30-14:24:22.940590] [439.288679] [ascend] [hdcdrv] "
                "[FATAL] [notify.c 42] <app> Process abort.\n"
                "[2026-08-30-14:24:22.940600] [439.288689] [ascend] [hdcdrv] "
                "[INFO] [notify.c 43] <other> Unrelated work.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            anchor = next(event for event in trace["events"] if event["id"] == trace["selected_anchor_id"])
            view = trace["views"][0]
            self.assertNotIn("pid", anchor["execution"])
            self.assertEqual(view["context_event_ids"], [anchor["id"]])
            self.assertEqual(view["scope"]["kind"], "anchor-only")
            self.assertEqual(view["scope"]["anchor_event_id"], anchor["id"])
            self.assertIn("scope_ambiguity", trace["diagnostics"]["gaps"])

    def test_runtime_validator_rejects_invalid_host_scope_extensions(self):
        trace = build_trace(FIXTURES / "fault-scope")
        invalid_traces = []

        bad_mapping = copy.deepcopy(trace)
        bad_mapping["events"][0]["component_mapping_rule"] = 1
        invalid_traces.append(bad_mapping)

        bad_monotonic = copy.deepcopy(trace)
        kernel = next(event for event in bad_monotonic["events"] if event["raw_component"] == "hdcdrv")
        kernel["timestamp"]["monotonic_raw"] = 1
        invalid_traces.append(bad_monotonic)

        bad_scope = copy.deepcopy(trace)
        bad_scope["views"][0]["scope"]["pid"] = 77034
        invalid_traces.append(bad_scope)

        bad_exclusion = copy.deepcopy(trace)
        bad_exclusion["views"][0]["excluded_event_ids"] = ["event-unknown"]
        invalid_traces.append(bad_exclusion)

        bad_count = copy.deepcopy(trace)
        bad_count["diagnostics"]["excluded_event_count"] = 99
        invalid_traces.append(bad_count)

        mismatched_scope = copy.deepcopy(trace)
        mismatched_scope["views"][0]["scope"]["pid"] = "88000"
        invalid_traces.append(mismatched_scope)

        wrong_pid_context = copy.deepcopy(trace)
        excluded_id = wrong_pid_context["views"][0]["excluded_event_ids"].pop()
        wrong_pid_context["views"][0]["context_event_ids"].append(excluded_id)
        invalid_traces.append(wrong_pid_context)

        incomplete_partition = copy.deepcopy(trace)
        incomplete_partition["views"][0]["excluded_event_ids"].pop()
        incomplete_partition["diagnostics"]["excluded_event_count"] -= 1
        invalid_traces.append(incomplete_partition)

        duplicate_scope_evidence = copy.deepcopy(trace)
        scope_evidence = duplicate_scope_evidence["views"][0]["scope"]["evidence_ids"]
        scope_evidence.append(scope_evidence[0])
        invalid_traces.append(duplicate_scope_evidence)

        unrelated_scope_evidence = copy.deepcopy(trace)
        unrelated_scope_evidence["views"][0]["scope"]["evidence_ids"] = [
            unrelated_scope_evidence["events"][0]["evidence_ids"][0]
        ]
        invalid_traces.append(unrelated_scope_evidence)

        highlighted_outside_context = copy.deepcopy(trace)
        unrelated_id = highlighted_outside_context["views"][0]["excluded_event_ids"][0]
        highlighted_outside_context["relationships"] = [
            {
                "id": "relationship-1",
                "source_event_id": highlighted_outside_context["selected_anchor_id"],
                "target_event_id": unrelated_id,
                "strength": "proven",
                "evidence_ids": highlighted_outside_context["events"][0]["evidence_ids"],
            }
        ]
        highlighted_outside_context["views"][0]["highlighted_event_ids"].append(unrelated_id)
        invalid_traces.append(highlighted_outside_context)

        for invalid in invalid_traces:
            with self.subTest(trace=invalid):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid)


if __name__ == "__main__":
    unittest.main()
