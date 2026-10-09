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
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "build_fault_trace.py"
VIEWER_HARNESS = SKILL_ROOT / "tests" / "run_viewer_behavior.mjs"
FIXTURE = SKILL_ROOT / "tests" / "fixtures" / "device-trace-redacted"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, render_html, validate_trace  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


class DeviceTraceDomainsTest(unittest.TestCase):
    def test_device_and_stackcore_records_preserve_explicit_domains_and_identity(self):
        trace = build_trace(FIXTURE)

        self.assertEqual(
            trace["metadata"]["parser_versions"],
            {
                "cann-stackcore-trace": "1.0.0",
                "device-common-slog": "1.1.0",
                "host-common-plog": "2.1.0",
            },
        )
        self.assertEqual(len(trace["events"]), 5)
        domains = {domain["id"]: domain for domain in trace["clock_domains"]}
        self.assertEqual(
            set(domains),
            {
                "clock-host-wall-unknown-zone",
                "clock-device-wall-unknown-zone-physical-5",
                "clock-device-boot-relative-physical-5",
            },
        )
        self.assertTrue(all(domain["aligned_to"] is None for domain in domains.values()))
        self.assertNotIn("missing_device_logs", trace["diagnostics"]["gaps"])
        self.assertIn("unaligned_host_device_clocks", trace["diagnostics"]["gaps"])

        mapped = next(event for event in trace["events"] if "local device id" in event["message"])
        self.assertEqual(mapped["location"], "device")
        self.assertEqual(mapped["component"], "Trace")
        self.assertEqual(
            mapped["execution"]["device"],
            {
                "logical_id": "0",
                "physical_id": "5",
                "mapping_strength": "proven",
                "mapping_evidence_ids": mapped["evidence_ids"],
            },
        )

        unmapped = next(event for event in trace["events"] if "Accept failed" in event["message"])
        self.assertEqual(unmapped["execution"]["device"], {"physical_id": "5"})

        boot = next(event for event in trace["events"] if "event_id=0x8c2fa009" in event["message"])
        self.assertEqual(boot["timestamp"]["raw"], "1970-01-01-00:00:10.560.325")
        self.assertEqual(boot["timestamp"]["monotonic_raw"], "9.621873")
        self.assertEqual(
            boot["timestamp"]["clock_domain_id"],
            "clock-device-boot-relative-physical-5",
        )

        anchor = next(event for event in trace["events"] if event["id"] == trace["selected_anchor_id"])
        self.assertEqual(anchor["component"], "Trace")
        self.assertEqual(anchor["location"], "host")
        self.assertEqual(anchor["fault_rule_id"], "trace-signal-6")
        self.assertEqual(anchor["timestamp"]["raw"], "20260907173012438697")
        self.assertEqual(anchor["execution"]["pid"], "5127")
        self.assertEqual(anchor["execution"]["tid"], "5127")
        self.assertEqual(len(anchor["evidence_ids"]), 4)
        source_lines = (
            FIXTURE
            .joinpath("atrace", "stackcore_tracer_6_5127_python3_20260907173012438697.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        reason_evidence = next(
            trace["evidence"][evidence_id]
            for evidence_id in anchor["evidence_ids"]
            if trace["evidence"][evidence_id]["line"] == 5
        )
        self.assertEqual(reason_evidence["excerpt"], source_lines[4])
        self.assertEqual(
            reason_evidence["record_sha256"],
            hashlib.sha256(source_lines[4].encode("utf-8")).hexdigest(),
        )
        stack_orphan = next(
            orphan for orphan in trace["orphan_evidence"] if orphan["line"] == 7
        )
        self.assertIn("gsignal", stack_orphan["excerpt"])
        stackcore_inventory = next(
            item for item in trace["input"]["inventory"]
            if "stackcore_tracer_" in item["source_path"]
        )
        self.assertEqual(stackcore_inventory["unparsed_records"], 1)

    def test_unaligned_domain_candidates_are_local_and_explicitly_ambiguous(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            host = root / "host" / "fault.log"
            host.parent.mkdir()
            host.write_text(
                "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000.001 "
                "[runtime.cc:3]Host abort.\n",
                encoding="utf-8",
            )
            device = root / "slog" / "dev-os-5" / "run" / "event" / "event.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[INFO] DRV(8,device):1970-01-01-00:00:10.560.300 "
                "[event.c:3][9.621800] Device preparing.\n"
                "[FATAL] DRV(8,device):1970-01-01-00:00:10.560.325 "
                "[event.c:4][9.621873] Device panic.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertEqual(trace["events"][0]["location"], "host")
            selection = trace["diagnostics"]["anchor_selection"]
            self.assertEqual(selection["status"], "ambiguous")
            self.assertEqual(selection["reason"], "unaligned_clock_domains")
            self.assertEqual(set(selection["domain_candidate_ids"]), set(trace["fault_candidates"]))
            self.assertEqual(
                {view["anchor_id"] for view in trace["views"]},
                set(trace["fault_candidates"]),
            )
            self.assertIn("ambiguous_fault_anchor", trace["diagnostics"]["gaps"])

            with tempfile.TemporaryDirectory() as output_directory:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(CLI),
                        str(root),
                        "--output-dir",
                        output_directory,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                html = Path(output_directory, "fault-trace.html").read_text(encoding="utf-8")
                self.assertIn('id="fault-candidate-select"', html)
                candidate_select = html.split('id="fault-candidate-select"', 1)[1].split("</select>", 1)[0]
                self.assertEqual(candidate_select.count("<option value="), 2)
                generated_trace = json.loads(
                    Path(output_directory, "fault-trace.json").read_text(encoding="utf-8")
                )
                target = generated_trace["fault_candidates"][1]
                target_view = next(
                    view for view in generated_trace["views"] if view["anchor_id"] == target
                )
                self.assertEqual(target_view["scope"]["kind"], "process")
                partition_id = target_view["context_partition_id"]
                expected_context = generated_trace["context_partitions"][partition_id]["event_ids"]
                behavior = subprocess.run(
                    ["node", str(VIEWER_HARNESS), str(Path(output_directory, "fault-trace.html")), target],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(behavior.returncode, 0, behavior.stderr)
                state = json.loads(behavior.stdout)
                self.assertEqual(state["switched"]["activeAnchorId"], target)
                # Fault-chain mode keeps proven-reachable neighbours of the
                # anchor visible; the anchor itself plus its proven graph.
                self.assertIn(target, state["switched"]["visibleEventIds"])
                self.assertTrue(len(state["switched"]["visibleEventIds"]) >= 1)
                self.assertEqual(state["context"]["visibleEventIds"], expected_context)
                self.assertEqual(state["switched"]["highlightedIds"], [target])
                self.assertEqual(state["switched"]["selectedEventIds"], [target])
                self.assertEqual(state["switched"]["eventCoordinates"][target], 0)

    def test_all_same_domain_candidates_have_views_but_only_earliest_is_domain_default(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:3]First abort.\n"
                "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:4]Second abort.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertEqual(len(trace["fault_candidates"]), 2)
            self.assertEqual(
                {view["anchor_id"] for view in trace["views"]},
                set(trace["fault_candidates"]),
            )
            self.assertEqual(
                trace["diagnostics"]["anchor_selection"]["domain_candidate_ids"],
                [trace["fault_candidates"][0]],
            )

    def test_many_candidates_do_not_duplicate_full_event_partitions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            records = "".join(
                f"[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.{index:06d} "
                f"[runtime.cc:{index}]Abort {index}.\n"
                for index in range(1, 51)
            )
            root.joinpath("fault.log").write_text(records, encoding="utf-8")

            trace = build_trace(root)

            materialized_ids = sum(
                len(view["context_event_ids"])
                + len(view.get("excluded_event_ids", []))
                for view in trace["views"]
                if "context_event_ids" in view
            ) + sum(
                len(partition["event_ids"])
                for partition in trace["context_partitions"].values()
            )
            self.assertLessEqual(materialized_ids, len(trace["events"]) * 2)
            compact_views = [
                view for view in trace["views"]
                if view["anchor_id"] != trace["selected_anchor_id"]
            ]
            self.assertTrue(all(view["scope"]["kind"] == "process" for view in compact_views))
            self.assertEqual(
                len({view["context_partition_id"] for view in compact_views}),
                1,
            )
            self.assertTrue(all(view["excluded_event_count"] == 0 for view in compact_views))
            self.assertTrue(all("excluded_event_ids" not in view for view in compact_views))

            class CountingList(list):
                def __init__(self, values):
                    super().__init__(values)
                    self.iterations = 0

                def __iter__(self):
                    self.iterations += 1
                    return super().__iter__()

            measured_events = CountingList(trace["events"])
            partition = next(iter(trace["context_partitions"].values()))
            measured_partition = CountingList(partition["event_ids"])
            trace["events"] = measured_events
            partition["event_ids"] = measured_partition

            validate_trace(trace)
            self.assertLessEqual(measured_events.iterations, 10)
            self.assertLessEqual(measured_partition.iterations, 10)

            measured_events.iterations = 0
            measured_partition.iterations = 0
            render_html(trace)
            self.assertLessEqual(measured_events.iterations, 12)
            self.assertLessEqual(measured_partition.iterations, 12)

    def test_validator_rejects_invalid_shared_context_partitions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(7,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:2]Preparing.\n"
                "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:3]First abort.\n"
                "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000003 "
                "[runtime.cc:4]Second abort.\n",
                encoding="utf-8",
            )
            trace = build_trace(root)
            compact_view = trace["views"][1]
            partition_id = compact_view["context_partition_id"]

            missing_context = copy.deepcopy(trace)
            del missing_context["views"][1]["context_partition_id"]

            unknown_partition = copy.deepcopy(trace)
            unknown_partition["views"][1]["context_partition_id"] = "context-missing"

            mismatched_materialization = copy.deepcopy(trace)
            mismatched_materialization["views"][1]["context_event_ids"] = [
                compact_view["anchor_id"]
            ]

            wrong_partition_pid = copy.deepcopy(trace)
            wrong_partition_pid["context_partitions"][partition_id]["pid"] = "8"

            wrong_partition_location = copy.deepcopy(trace)
            wrong_partition_location["context_partitions"][partition_id]["location"] = "device"

            wrong_partition_domain = copy.deepcopy(trace)
            wrong_partition_domain["context_partitions"][partition_id][
                "clock_domain_id"
            ] = "clock-missing"

            incomplete_partition = copy.deepcopy(trace)
            removed_event_id = incomplete_partition["context_partitions"][partition_id][
                "event_ids"
            ].pop(0)
            incomplete_partition["views"][0]["excluded_event_ids"].append(
                removed_event_id
            )
            for view in incomplete_partition["views"]:
                view["excluded_event_count"] += 1
            incomplete_partition["diagnostics"]["excluded_event_count"] += 1

            for invalid in (
                missing_context,
                unknown_partition,
                mismatched_materialization,
                wrong_partition_pid,
                wrong_partition_location,
                wrong_partition_domain,
                incomplete_partition,
            ):
                with self.subTest(trace=invalid):
                    with self.assertRaises(TraceValidationError):
                        validate_trace(invalid)

    def test_unknown_device_sources_remain_in_separate_clock_domains(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for source, timestamp in (
                ("device-alpha", "2026-09-08-10:11:12.000001"),
                ("device-beta", "2026-09-08-10:11:12.000002"),
            ):
                path = root / "slog" / source / "run" / "device-os" / "device.log"
                path.parent.mkdir(parents=True)
                path.write_text(
                    f"[FATAL] DRV(8,device):{timestamp} [event.c:4]Device panic.\n",
                    encoding="utf-8",
                )

            trace = build_trace(root)
            device_events = [event for event in trace["events"] if event["location"] == "device"]

            self.assertEqual(len(device_events), 2)
            self.assertEqual(
                len({event["timestamp"]["clock_domain_id"] for event in device_events}),
                2,
            )
            self.assertTrue(
                all(
                    event["timestamp"]["clock_domain_id"].startswith(
                        "clock-device-wall-unknown-zone-physical-unknown-source-"
                    )
                    for event in device_events
                )
            )

    def test_device_path_cannot_be_claimed_by_host_stackcore_adapter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stackcore = (
                root / "slog" / "dev-os-5" / "run" / "atrace"
                / "stackcore_tracer_6_5127_python3_20260907173012438697.txt"
            )
            stackcore.parent.mkdir(parents=True)
            stackcore.write_text(
                "[process]\ncrash task:python3\ncrash pid:5127\ncrash tid:5127\n"
                "crash reason:SIGNAL 6\n[stack]\n#00 gsignal\n",
                encoding="utf-8",
            )
            output = root / "output"

            completed = subprocess.run(
                [sys.executable, "-B", str(CLI), str(root / "slog"), "--output-dir", str(output)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 3)
            audit = json.loads(output.joinpath("fault-trace-inventory.json").read_text(encoding="utf-8"))
            item = next(entry for entry in audit["input"]["inventory"] if "stackcore_tracer" in entry["source_path"])
            self.assertNotEqual(item.get("parser"), "cann-stackcore-trace-v1")

    def test_conflicting_path_and_record_physical_ids_are_not_mapped(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            device = root / "slog" / "dev-os-5" / "run" / "device-os" / "device.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[FATAL] ATRACE(8,slogd):2026-09-08-10:11:12.000.001 "
                "[trace.c:3] local device id = 0, physical device id = 7.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            event = trace["events"][0]
            identity = event["execution"]["device"]
            self.assertEqual(identity["logical_id"], "0")
            self.assertEqual(identity["path_physical_id"], "5")
            self.assertEqual(identity["reported_physical_id"], "7")
            self.assertEqual(identity["identity_status"], "conflict")
            self.assertEqual(identity["conflict_evidence_ids"], event["evidence_ids"])
            self.assertNotIn("physical_id", identity)
            self.assertNotIn("mapping_strength", identity)
            self.assertEqual(
                event["timestamp"]["clock_domain_id"],
                "clock-device-wall-unknown-zone-physical-conflict-5-7",
            )

    def test_offline_html_has_one_unaligned_axis_per_clock_domain(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"

            completed = subprocess.run(
                [sys.executable, "-B", str(CLI), str(FIXTURE), "--output-dir", str(output)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            html = output.joinpath("fault-trace.html").read_text(encoding="utf-8")
            initial_markup = html.split('<script id="fault-trace-data"', 1)[0]
            self.assertEqual(initial_markup.count('class="clock-panel"'), 3)
            self.assertEqual(initial_markup.count("unaligned; independent axis"), 3)
            self.assertIn('data-location="host"', initial_markup)
            self.assertEqual(initial_markup.count('data-location="device"'), 2)
            self.assertNotIn("https://", html)
            self.assertNotIn("http://", html)

    def test_validator_rejects_unproven_or_malformed_device_identity(self):
        trace = build_trace(FIXTURE)
        mapped = next(event for event in trace["events"] if "local device id" in event["message"])
        invalid_traces = []

        numeric_logical = copy.deepcopy(trace)
        next(event for event in numeric_logical["events"] if event["id"] == mapped["id"])[
            "execution"
        ]["device"]["logical_id"] = 0
        invalid_traces.append(numeric_logical)

        inferred_mapping = copy.deepcopy(trace)
        next(event for event in inferred_mapping["events"] if event["id"] == mapped["id"])[
            "execution"
        ]["device"]["mapping_strength"] = "inferred"
        invalid_traces.append(inferred_mapping)

        unrelated_mapping_evidence = copy.deepcopy(trace)
        other_evidence = next(
            event["evidence_ids"][0]
            for event in unrelated_mapping_evidence["events"]
            if event["id"] != mapped["id"]
        )
        next(
            event for event in unrelated_mapping_evidence["events"] if event["id"] == mapped["id"]
        )["execution"]["device"]["mapping_evidence_ids"] = [other_evidence]
        invalid_traces.append(unrelated_mapping_evidence)

        unproven_pair = copy.deepcopy(trace)
        unproven_pair_device = next(
            event for event in unproven_pair["events"] if event["id"] == mapped["id"]
        )["execution"]["device"]
        del unproven_pair_device["mapping_strength"]
        del unproven_pair_device["mapping_evidence_ids"]
        invalid_traces.append(unproven_pair)

        incomplete_conflict = copy.deepcopy(trace)
        next(
            event for event in incomplete_conflict["events"] if event["id"] == mapped["id"]
        )["execution"]["device"]["path_physical_id"] = "5"
        invalid_traces.append(incomplete_conflict)

        for invalid in invalid_traces:
            with self.subTest(trace=invalid):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid)

    def test_v1_runtime_validator_accepts_absent_optional_anchor_selection(self):
        trace = build_trace(FIXTURE)
        legacy_candidate = next(
            event["id"] for event in trace["events"]
            if event["id"] not in trace["fault_candidates"]
        )
        trace["fault_candidates"].append(legacy_candidate)
        trace["diagnostics"]["fault_candidate_count"] = len(trace["fault_candidates"])
        del trace["diagnostics"]["anchor_selection"]

        validate_trace(trace)


if __name__ == "__main__":
    unittest.main()
