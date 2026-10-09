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
VIEWER_HARNESS = SKILL_ROOT / "tests" / "run_viewer_behavior.mjs"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, render_html, validate_trace  # noqa: E402
from fault_trace_core.correlation import build_clock_alignments  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


class FaultCorrelationTest(unittest.TestCase):
    def test_supported_records_preserve_explicit_correlation_and_interaction_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plog = root / "host" / "log" / "debug" / "plog" / "plog.log"
            plog.parent.mkdir(parents=True)
            plog.write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:2]Dispatch stream_id=3, task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:3]Process abort.\n",
                encoding="utf-8",
            )
            device = root / "slog" / "dev-os-0" / "run" / "event" / "event.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[EVENT] DRV(686,dms_poll_task):1970-01-01-00:00:13.648.402 "
                "[dms_event_device.c:171][fault_manager][14.016678] "
                "Event sent to the host successfully. (dev_id=0; event_id=0x8c2fa009; "
                "node_id=1; assertion=2; alarm_raised_time=13648)\n",
                encoding="utf-8",
            )
            kernel = root / "slog" / "host" / "host_kernel.log"
            kernel.parent.mkdir(parents=True)
            kernel.write_text(
                "[2026-09-08-10:11:12.000003] [26.177144] [ascend] [dms_module] "
                "[INFO] [dms_event_distribute_to_process 395] <kworker:766:766> "
                "Receive an event. (dev_id=0; event_id=0x8c2fa009; node_id=1; "
                "assertion=2; alarm_raised_time=13648)\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            dispatch = next(event for event in trace["events"] if "Dispatch" in event["message"])
            sent = next(event for event in trace["events"] if "sent to the host" in event["message"])
            received = next(event for event in trace["events"] if "Receive an event" in event["message"])
            self.assertEqual(dispatch["correlation"], {"stream_id": "3", "task_id": "19"})
            self.assertEqual(dispatch["interaction"], "dispatch")
            expected_event_identity = {
                "device_id": "0",
                "event_id": "0x8c2fa009",
                "node_id": "1",
                "assertion": "2",
                "alarm_raised_time": "13648",
            }
            self.assertEqual(sent["correlation"], expected_event_identity)
            self.assertEqual(received["correlation"], expected_event_identity)
            self.assertEqual(sent["interaction"], "notify-host")
            self.assertEqual(received["interaction"], "receive-device-event")

    def test_validator_rejects_malformed_correlation_and_interaction_fields(self):
        trace = build_trace(SKILL_ROOT / "tests" / "fixtures" / "minimal-plog")
        invalid_traces = []

        numeric_identity = copy.deepcopy(trace)
        numeric_identity["events"][0]["correlation"] = {"stream_id": 3}
        invalid_traces.append(numeric_identity)

        unknown_identity = copy.deepcopy(trace)
        unknown_identity["events"][0]["correlation"] = {"request": "3"}
        invalid_traces.append(unknown_identity)

        empty_identity = copy.deepcopy(trace)
        empty_identity["events"][0]["correlation"] = {}
        invalid_traces.append(empty_identity)

        unknown_interaction = copy.deepcopy(trace)
        unknown_interaction["events"][0]["interaction"] = "probably-called"
        invalid_traces.append(unknown_interaction)

        for invalid in invalid_traces:
            with self.subTest(trace=invalid):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid)

    def test_negated_or_failed_interactions_do_not_create_proven_relationships(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            device = root / "slog" / "dev-os-0" / "run" / "event" / "event.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[EVENT] DRV(8,device):1970-01-01-00:00:13.648.401 "
                "[event.c:1]Event was not sent to the host. (dev_id=0; "
                "event_id=0x8c2fa009; node_id=1; assertion=2; "
                "alarm_raised_time=13648)\n",
                encoding="utf-8",
            )
            host = root / "host" / "fault.log"
            host.parent.mkdir(parents=True)
            host.write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Failed to dispatch task stream_id=3, task_id=19.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:2]Task was not completed stream_id=3, task_id=19.\n"
                "[INFO] DRV(42,app):2026-09-08-10:11:12.000003 "
                "[event.c:2]Failed to receive an event. (dev_id=0; "
                "event_id=0x8c2fa009; node_id=1; assertion=2; "
                "alarm_raised_time=13648)\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:3]Process abort.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            negative_events = [
                event
                for event in trace["events"]
                if "not sent" in event["message"]
                or "Failed to" in event["message"]
                or "not completed" in event["message"]
            ]
            self.assertTrue(negative_events)
            self.assertTrue(all("interaction" not in event for event in negative_events))
            self.assertFalse(
                any(
                    relationship["strength"] == "proven"
                    for relationship in trace["relationships"]
                )
            )

    def test_conflicting_device_identity_blocks_stream_task_proof(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Dispatch device_id=0, stream_id=3, task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:2]Process abort device_id=1, stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertFalse(
                any(
                    relationship["strength"] == "proven"
                    for relationship in trace["relationships"]
                )
            )

    def test_conflicting_aliases_in_one_record_drop_its_correlation_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Dispatch device_id=0, dev_id=1, stream_id=3, "
                "task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:2]Process abort device_id=0, stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)
            dispatch = next(
                event for event in trace["events"] if event.get("interaction") == "dispatch"
            )

            self.assertNotIn("correlation", dispatch)
            self.assertFalse(
                any(
                    relationship["strength"] == "proven"
                    for relationship in trace["relationships"]
                )
            )

    def test_validator_rejects_invalid_relationship_kind_and_rule_id(self):
        trace = build_trace(SKILL_ROOT / "tests" / "fixtures" / "minimal-plog")
        source, target = trace["events"]
        relationship = {
            "id": "relationship-000001",
            "source_event_id": source["id"],
            "target_event_id": target["id"],
            "kind": "hypothesis",
            "strength": "inferred",
            "rule_id": "test-hypothesis-v1",
            "evidence_ids": source["evidence_ids"] + target["evidence_ids"],
        }

        invalid_kind = copy.deepcopy(trace)
        invalid_kind["relationships"] = [relationship | {"kind": "temporal-guess"}]

        invalid_rule_id = copy.deepcopy(trace)
        invalid_rule_id["relationships"] = [relationship | {"rule_id": 1}]

        for invalid in (invalid_kind, invalid_rule_id):
            with self.subTest(trace=invalid):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid)

    def test_validator_rejects_relationships_not_derived_from_endpoint_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] GE(42,app):2026-09-08-10:11:12.000001 "
                "[ge.cc:2]Dispatch stream_id=3, task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:3]Process abort stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )
            trace = build_trace(root)
            source = trace["events"][0]
            relationship = trace["relationships"][0]

            wrong_strength_for_kind = copy.deepcopy(trace)
            wrong_strength_for_kind["relationships"][0].update(
                {
                    "kind": "hypothesis",
                    "strength": "proven",
                    "rule_id": "temporal-component-adjacency-v1",
                }
            )

            invented_rule = copy.deepcopy(trace)
            invented_rule["relationships"][0]["rule_id"] = "invented-proof-v1"

            incomplete_evidence = copy.deepcopy(trace)
            incomplete_evidence["relationships"][0]["evidence_ids"] = source[
                "evidence_ids"
            ]

            self_loop = copy.deepcopy(trace)
            self_loop["relationships"][0]["target_event_id"] = source["id"]
            self_loop["relationships"][0]["evidence_ids"] = source["evidence_ids"]
            self_loop["views"][0]["highlighted_event_ids"] = [
                self_loop["selected_anchor_id"]
            ]

            for invalid in (
                wrong_strength_for_kind,
                invented_rule,
                incomplete_evidence,
                self_loop,
            ):
                with self.subTest(relationship=relationship, trace=invalid):
                    with self.assertRaises(TraceValidationError):
                        validate_trace(invalid)

    def test_explicit_device_notification_proves_only_the_exact_host_receipt(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            device = root / "slog" / "dev-os-0" / "run" / "event" / "event.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[EVENT] DRV(686,dms_poll_task):1970-01-01-00:00:13.648.402 "
                "[dms_event_device.c:171][fault_manager][14.016678] "
                "Event sent to the host successfully. (dev_id=0; event_id=0x8c2fa009; "
                "node_id=1; assertion=2; alarm_raised_time=13648)\n"
                "[EVENT] DRV(686,dms_poll_task):1970-01-01-00:00:13.648.403 "
                "[dms_event_device.c:171][fault_manager][14.016679] "
                "Event sent to the host successfully. (dev_id=0; event_id=0x8c2fa010; "
                "node_id=1; assertion=2; alarm_raised_time=13648)\n",
                encoding="utf-8",
            )
            kernel = root / "slog" / "host" / "host_kernel.log"
            kernel.parent.mkdir(parents=True)
            kernel.write_text(
                "[2026-09-08-10:11:12.000003] [26.177144] [ascend] [dms_module] "
                "[FATAL] [dms_event_distribute_to_process 395] <kworker:766:766> "
                "Receive an event; process abort. (dev_id=0; event_id=0x8c2fa009; "
                "node_id=1; assertion=2; alarm_raised_time=13648)\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            anchor_id = trace["selected_anchor_id"]
            matching_sender = next(
                event for event in trace["events"] if event.get("correlation", {}).get("event_id") == "0x8c2fa009" and event["location"] == "device"
            )
            unrelated_sender = next(
                event for event in trace["events"] if event.get("correlation", {}).get("event_id") == "0x8c2fa010"
            )
            self.assertEqual(
                trace["relationships"],
                [
                    {
                        "id": "relationship-000001",
                        "source_event_id": matching_sender["id"],
                        "target_event_id": anchor_id,
                        "kind": "notification",
                        "strength": "proven",
                        "rule_id": "explicit-device-event-notification-v1",
                        "evidence_ids": matching_sender["evidence_ids"]
                        + next(event for event in trace["events"] if event["id"] == anchor_id)["evidence_ids"],
                    }
                ],
            )
            view = next(view for view in trace["views"] if view["anchor_id"] == anchor_id)
            self.assertEqual(set(view["highlighted_event_ids"]), {matching_sender["id"], anchor_id})
            self.assertIn(matching_sender["id"], view["context_event_ids"])
            self.assertNotIn(unrelated_sender["id"], view["context_event_ids"])
            self.assertNotIn(matching_sender["id"], trace["fault_candidates"])

            html_path = root / "fault-trace.html"
            html_path.write_text(render_html(trace), encoding="utf-8")
            behavior = subprocess.run(
                ["node", str(VIEWER_HARNESS), str(html_path), anchor_id],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(behavior.returncode, 0, behavior.stderr)
            switched = json.loads(behavior.stdout)["switched"]
            self.assertEqual(
                set(switched["highlightedIds"]), {matching_sender["id"], anchor_id}
            )
            self.assertIn(anchor_id, switched["visibleEventIds"])

    def test_stream_and_task_identity_with_same_execution_subject_is_proven(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] GE(42,app):2026-09-08-10:11:12.000001 "
                "[ge.cc:2]Dispatch stream_id=3, task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:3]Process abort stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertEqual(len(trace["relationships"]), 1)
            relationship = trace["relationships"][0]
            self.assertEqual(relationship["strength"], "proven")
            self.assertEqual(relationship["kind"], "same-execution")
            self.assertEqual(relationship["rule_id"], "stream-task-execution-v1")
            self.assertEqual(
                set(trace["views"][0]["highlighted_event_ids"]),
                {event["id"] for event in trace["events"]},
            )
            self.assertIn('class="relationship proven"', render_html(trace))

    def test_reused_stream_and_task_identity_is_segmented_by_dispatch_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000000 "
                "[runtime.cc:1]Observed stream_id=3, task_id=19 before dispatch.\n"
                "[INFO] GE(42,app):2026-09-08-10:11:12.000001 "
                "[ge.cc:2]Dispatch stream_id=3, task_id=19.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:3]Executing stream_id=3, task_id=19.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000003 "
                "[runtime.cc:4]Recycle task stream_id=3, task_id=19.\n"
                "[INFO] GE(42,app):2026-09-08-10:11:12.000004 "
                "[ge.cc:5]Send AI Core Task, stream_id=3, task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000005 "
                "[runtime.cc:6]Process abort stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)
            events_by_message = {event["message"]: event for event in trace["events"]}

            first_dispatch = events_by_message["Dispatch stream_id=3, task_id=19."]
            first_progress = events_by_message["Executing stream_id=3, task_id=19."]
            first_return = events_by_message["Recycle task stream_id=3, task_id=19."]
            second_dispatch = events_by_message[
                "Send AI Core Task, stream_id=3, task_id=19."
            ]
            second_failure = events_by_message[
                "Process abort stream_id=3, task_id=19."
            ]
            self.assertEqual(first_return.get("interaction"), "return")
            self.assertEqual(second_dispatch.get("interaction"), "dispatch")
            proven_pairs = {
                (relationship["source_event_id"], relationship["target_event_id"])
                for relationship in trace["relationships"]
                if relationship["strength"] == "proven"
            }
            self.assertEqual(
                proven_pairs,
                {
                    (first_dispatch["id"], first_progress["id"]),
                    (first_progress["id"], first_return["id"]),
                    (second_dispatch["id"], second_failure["id"]),
                },
            )

    def test_known_cann_task_lifecycle_messages_have_explicit_interactions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]StreamLaunchKernelV2: kernel info: device_id=0, "
                "stream_id=47, task_id=0.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:2]AllocTaskAndSendStars: device_id=0, stream_id=47, "
                "task_id=0, task_type=66.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000003 "
                "[runtime.cc:3]ConstructSqeForStarsVersionTask: Send "
                "GetStarsVersionTask success, stream_id=48, task_id=0.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:4]RecycleTaskProcessForSeparatedStm: device_id=0, "
                "stream_id=48, recycle task_id=0.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000005 "
                "[runtime.cc:5]Process abort.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)
            interactions = {
                event["message"].split(":", 1)[0]: event.get("interaction")
                for event in trace["events"]
            }

            self.assertEqual(interactions["StreamLaunchKernelV2"], "dispatch")
            self.assertEqual(interactions["AllocTaskAndSendStars"], "dispatch")
            self.assertEqual(
                interactions["ConstructSqeForStarsVersionTask"], "dispatch"
            )
            self.assertEqual(
                interactions["RecycleTaskProcessForSeparatedStm"], "return"
            )

    def test_timing_and_component_adjacency_is_inferred_and_not_highlighted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] GE(42,app):2026-09-08-10:11:12.000001 "
                "[ge.cc:2]Preparing work.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:3]Process abort.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertEqual(len(trace["relationships"]), 1)
            relationship = trace["relationships"][0]
            self.assertEqual(relationship["strength"], "inferred")
            self.assertEqual(relationship["rule_id"], "temporal-component-adjacency-v1")
            self.assertEqual(trace["views"][0]["highlighted_event_ids"], [trace["selected_anchor_id"]])
            rendered = render_html(trace)
            self.assertIn('class="relationship inferred"', rendered)
            self.assertIn("temporal-component-adjacency-v1", rendered)

    def test_explicit_clock_alignment_is_auditable_and_other_domains_remain_unaligned(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:3]Process abort.\n",
                encoding="utf-8",
            )
            aligned_device = root / "slog" / "dev-os-0" / "run" / "device-os" / "device.log"
            aligned_device.parent.mkdir(parents=True)
            aligned_device.write_text(
                "[INFO] DRV(8,device):2026-09-08-10:11:12.000001 "
                "[clock.c:2]clock_alignment target=clock-host-wall-unknown-zone "
                "offset_us=17 uncertainty_us=5 method=hardware-sync\n",
                encoding="utf-8",
            )
            unaligned_device = root / "slog" / "dev-os-1" / "run" / "device-os" / "device.log"
            unaligned_device.parent.mkdir(parents=True)
            unaligned_device.write_text(
                "[INFO] DRV(9,device):2026-09-08-10:11:12.000002 "
                "[clock.c:3]No synchronization evidence.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            alignment_event = next(
                event for event in trace["events"] if "clock_alignment" in event["message"]
            )
            source_domain = alignment_event["timestamp"]["clock_domain_id"]
            self.assertEqual(
                trace["clock_alignments"],
                [
                    {
                        "id": "alignment-000001",
                        "source_clock_domain_id": source_domain,
                        "target_clock_domain_id": "clock-host-wall-unknown-zone",
                        "method": "hardware-sync",
                        "offset_us": 17,
                        "uncertainty_us": 5,
                        "evidence_ids": alignment_event["evidence_ids"],
                    }
                ],
            )
            domains = {domain["id"]: domain for domain in trace["clock_domains"]}
            self.assertEqual(domains[source_domain]["aligned_to"], "clock-host-wall-unknown-zone")
            self.assertIsNone(
                domains["clock-device-wall-unknown-zone-physical-1"]["aligned_to"]
            )
            html = render_html(trace)
            self.assertIn("hardware-sync", html)
            self.assertIn("uncertainty 5 us", html)

    def test_clock_alignment_orders_candidates_and_drives_shared_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            host = root / "host" / "fault.log"
            host.parent.mkdir(parents=True)
            host.write_text(
                "[FATAL] RUNTIME(42,host-app):2026-09-08-10:11:12.000100 "
                "[runtime.cc:1]Host abort.\n",
                encoding="utf-8",
            )
            device = root / "slog" / "dev-os-0" / "run" / "event" / "event.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[INFO] DRV(8,device):1970-01-01-00:00:10.000000 "
                "[clock.c:1]clock_alignment target=clock-host-wall-unknown-zone "
                "offset_us=-100 uncertainty_us=5 method=hardware-sync\n"
                "[FATAL] DRV(8,device):1970-01-01-00:00:10.000020 "
                "[event.c:2]Device panic.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)
            host_fault = next(
                event
                for event in trace["events"]
                if event["location"] == "host" and event["level"] == "FATAL"
            )
            device_fault = next(
                event
                for event in trace["events"]
                if event["location"] == "device" and event["level"] == "FATAL"
            )

            self.assertEqual(trace["selected_anchor_id"], device_fault["id"])
            self.assertEqual(
                trace["diagnostics"]["anchor_selection"],
                {
                    "status": "selected",
                    "reason": "aligned_clock_domains",
                    "domain_candidate_ids": [device_fault["id"]],
                },
            )
            self.assertNotIn(
                "unaligned_host_device_clocks", trace["diagnostics"]["gaps"]
            )
            self.assertNotIn("ambiguous_fault_anchor", trace["diagnostics"]["gaps"])
            self.assertEqual(host_fault["timestamp"]["aligned_offset_us"], 0)
            self.assertEqual(device_fault["timestamp"]["aligned_offset_us"], -80)
            self.assertEqual(
                device_fault["timestamp"]["aligned_clock_domain_id"],
                "clock-host-wall-unknown-zone",
            )
            self.assertEqual(
                device_fault["timestamp"]["alignment_uncertainty_us"], 5
            )
            rendered = render_html(trace)
            self.assertIn("offset -100 us", rendered)
            initial_markup = rendered.split('<script id="fault-trace-data"', 1)[0]
            self.assertIn(
                f'data-event-id="{device_fault["id"]}" data-offset-us="20"', initial_markup
            )
            self.assertNotIn(f'data-event-id="{host_fault["id"]}"', initial_markup)
            self.assertIn('data-location="device host" data-aligned="true"', initial_markup)

    def test_identical_clock_alignment_declarations_merge_their_evidence(self):
        events = [
            {
                "timestamp": {"clock_domain_id": "clock-device", "offset_us": 0},
                "clock_alignment": {
                    "target_clock_domain_id": "clock-host",
                    "offset_us": 17,
                    "uncertainty_us": 5,
                    "method": "hardware-sync",
                },
                "evidence_ids": ["evidence-1"],
            },
            {
                "timestamp": {"clock_domain_id": "clock-device", "offset_us": 10},
                "clock_alignment": {
                    "target_clock_domain_id": "clock-host",
                    "offset_us": 17,
                    "uncertainty_us": 5,
                    "method": "hardware-sync",
                },
                "evidence_ids": ["evidence-2"],
            },
        ]

        self.assertEqual(
            build_clock_alignments(events),
            [
                {
                    "id": "alignment-000001",
                    "source_clock_domain_id": "clock-device",
                    "target_clock_domain_id": "clock-host",
                    "method": "hardware-sync",
                    "offset_us": 17,
                    "uncertainty_us": 5,
                    "evidence_ids": ["evidence-1", "evidence-2"],
                }
            ],
        )

    def test_conflicting_clock_alignment_declarations_remain_unaligned(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[FATAL] RUNTIME(42,host-app):2026-09-08-10:11:12.000100 "
                "[runtime.cc:1]Host abort.\n",
                encoding="utf-8",
            )
            device = root / "slog" / "dev-os-0" / "run" / "event" / "event.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[INFO] DRV(8,device):1970-01-01-00:00:10.000000 "
                "[clock.c:1]clock_alignment target=clock-host-wall-unknown-zone "
                "offset_us=17 uncertainty_us=5 method=hardware-sync\n"
                "[INFO] DRV(8,device):1970-01-01-00:00:10.000001 "
                "[clock.c:2]clock_alignment target=clock-host-wall-unknown-zone "
                "offset_us=18 uncertainty_us=5 method=hardware-sync\n",
                encoding="utf-8",
            )

            try:
                trace = build_trace(root)
            except TraceValidationError as error:
                self.fail(f"conflicting declarations must produce a partial trace: {error}")

            self.assertEqual(trace["clock_alignments"], [])
            self.assertTrue(
                all(domain["aligned_to"] is None for domain in trace["clock_domains"])
            )
            self.assertIn("clock_alignment_conflict", trace["diagnostics"]["gaps"])
            self.assertIn(
                "unaligned_host_device_clocks", trace["diagnostics"]["gaps"]
            )

    def test_validator_rejects_invalid_clock_alignment_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:3]Process abort.\n",
                encoding="utf-8",
            )
            device = root / "slog" / "dev-os-0" / "run" / "device-os" / "device.log"
            device.parent.mkdir(parents=True)
            device.write_text(
                "[INFO] DRV(8,device):2026-09-08-10:11:12.000001 "
                "[clock.c:2]clock_alignment target=clock-host-wall-unknown-zone "
                "offset_us=-17 uncertainty_us=5 method=hardware-sync\n",
                encoding="utf-8",
            )
            trace = build_trace(root)
            alignment = trace["clock_alignments"][0]
            source_domain = alignment["source_clock_domain_id"]

            dangling_domain = copy.deepcopy(trace)
            dangling_domain["clock_alignments"][0]["target_clock_domain_id"] = "clock-missing"

            missing_evidence = copy.deepcopy(trace)
            missing_evidence["clock_alignments"][0]["evidence_ids"] = ["evidence-missing"]

            negative_uncertainty = copy.deepcopy(trace)
            negative_uncertainty["clock_alignments"][0]["uncertainty_us"] = -1

            unbound_offset = copy.deepcopy(trace)
            unbound_offset["clock_alignments"][0]["offset_us"] = 999

            cycle = copy.deepcopy(trace)
            host_domain = "clock-host-wall-unknown-zone"
            next(domain for domain in cycle["clock_domains"] if domain["id"] == host_domain)[
                "aligned_to"
            ] = source_domain
            cycle["clock_alignments"].append(
                {
                    "id": "alignment-000002",
                    "source_clock_domain_id": host_domain,
                    "target_clock_domain_id": source_domain,
                    "method": "hardware-sync",
                    "offset_us": 17,
                    "uncertainty_us": 5,
                    "evidence_ids": cycle["events"][0]["evidence_ids"],
                }
            )

            for invalid in (
                dangling_domain,
                missing_evidence,
                negative_uncertainty,
                unbound_offset,
                cycle,
            ):
                with self.subTest(trace=invalid):
                    with self.assertRaises(TraceValidationError):
                        validate_trace(invalid)

    def test_legacy_trace_aligned_to_must_reference_another_existing_domain(self):
        trace = build_trace(SKILL_ROOT / "tests" / "fixtures" / "minimal-plog")
        trace.pop("clock_alignments", None)
        domain_id = trace["clock_domains"][0]["id"]

        dangling = copy.deepcopy(trace)
        dangling["clock_domains"][0]["aligned_to"] = "clock-missing"

        self_aligned = copy.deepcopy(trace)
        self_aligned["clock_domains"][0]["aligned_to"] = domain_id

        for invalid in (dangling, self_aligned):
            with self.subTest(trace=invalid):
                with self.assertRaises(TraceValidationError):
                    validate_trace(invalid)


if __name__ == "__main__":
    unittest.main()
