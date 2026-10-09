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
from pathlib import Path
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, render_html, validate_trace  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


class SpansAndDeduplicationTest(unittest.TestCase):
    def test_exact_semantic_duplicates_merge_all_source_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "host" / "log" / "debug" / "plog" / "first.log"
            second = root / "host" / "log" / "run" / "plog" / "second.log"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            duplicate = (
                "[INFO] GE(42,app):2026-09-08-10:11:12.000001 "
                "[ge.cc:1]Dispatch device_id=0, stream_id=3, task_id=19.\n"
            )
            first.write_text(
                duplicate
                + "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:2]Process abort device_id=0, stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )
            second.write_text(duplicate, encoding="utf-8")

            trace = build_trace(root)

            self.assertEqual(len(trace["events"]), 2)
            dispatch = next(
                event for event in trace["events"] if event.get("interaction") == "dispatch"
            )
            self.assertEqual(len(dispatch["evidence_ids"]), 2)
            self.assertEqual(
                {
                    trace["evidence"][evidence_id]["source_path"]
                    for evidence_id in dispatch["evidence_ids"]
                },
                {
                    "host/log/debug/plog/first.log",
                    "host/log/run/plog/second.log",
                },
            )
            self.assertEqual(
                len(
                    [
                        relationship
                        for relationship in trace["relationships"]
                        if relationship["strength"] == "proven"
                    ]
                ),
                1,
            )

    def test_conflicting_observations_remain_visible_and_block_proof(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "host" / "log" / "debug" / "plog" / "first.log"
            second = root / "host" / "log" / "run" / "plog" / "second.log"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text(
                "[INFO] GE(42,app):2026-09-08-10:11:12.000001 "
                "[ge.cc:1]Dispatch device_id=0, stream_id=3, task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000004 "
                "[runtime.cc:2]Process abort device_id=0, stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )
            second.write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:9]Launch task device_id=0, stream_id=3, task_id=19.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            conflict = next(
                relationship
                for relationship in trace["relationships"]
                if relationship["strength"] == "conflict"
            )
            self.assertEqual(conflict["kind"], "evidence-conflict")
            conflict_ids = {conflict["source_event_id"], conflict["target_event_id"]}
            self.assertTrue(
                all(
                    event_id not in conflict_ids
                    for relationship in trace["relationships"]
                    if relationship["strength"] == "proven"
                    for event_id in (
                        relationship["source_event_id"],
                        relationship["target_event_id"],
                    )
                )
            )
            self.assertIn("evidence_conflicts", trace["diagnostics"]["gaps"])
            self.assertIn('class="relationship conflict"', render_html(trace))

    def test_matched_dispatch_and_return_create_one_auditable_span(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Dispatch device_id=0, stream_id=3, task_id=19.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000009 "
                "[runtime.cc:2]Recycle task device_id=0, stream_id=3, task_id=19.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000010 "
                "[runtime.cc:3]Process abort.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)
            dispatch = next(
                event for event in trace["events"] if event.get("interaction") == "dispatch"
            )
            returned = next(
                event for event in trace["events"] if event.get("interaction") == "return"
            )

            self.assertEqual(
                trace["spans"],
                [
                    {
                        "id": "span-000001",
                        "start_event_id": dispatch["id"],
                        "end_event_id": returned["id"],
                        "duration_us": 8,
                        "evidence_ids": dispatch["evidence_ids"] + returned["evidence_ids"],
                    }
                ],
            )
            self.assertNotIn("no_call_spans", trace["diagnostics"]["gaps"])
            self.assertNotIn("unmatched_span_endpoints", trace["diagnostics"]["gaps"])
            rendered = render_html(trace)
            self.assertIn('class="span"', rendered)
            self.assertIn('data-duration-us="8"', rendered)

            invalid = copy.deepcopy(trace)
            invalid["spans"][0]["duration_us"] = 9
            with self.assertRaises(TraceValidationError):
                validate_trace(invalid)

    def test_equal_time_and_unmatched_endpoints_remain_points(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Dispatch device_id=0, stream_id=3, task_id=19.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000001 "
                "[runtime.cc:2]Recycle task device_id=0, stream_id=3, task_id=19.\n"
                "[INFO] RUNTIME(42,app):2026-09-08-10:11:12.000002 "
                "[runtime.cc:3]Recycle task device_id=0, stream_id=4, task_id=20.\n"
                "[FATAL] RUNTIME(42,app):2026-09-08-10:11:12.000003 "
                "[runtime.cc:4]Process abort.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertEqual(trace["spans"], [])
            self.assertIn("no_call_spans", trace["diagnostics"]["gaps"])
            self.assertIn("unmatched_span_endpoints", trace["diagnostics"]["gaps"])
            same_time = [
                event
                for event in trace["events"]
                if event["timestamp"]["offset_us"] == 0
            ]
            self.assertEqual(len(same_time), 2)
            self.assertFalse(
                any(
                    relationship["strength"] == "proven"
                    and {
                        relationship["source_event_id"],
                        relationship["target_event_id"],
                    }
                    == {event["id"] for event in same_time}
                    for relationship in trace["relationships"]
                )
            )

    def test_span_requires_all_correlation_fields_and_execution_subject_to_match(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(
                "[INFO] RUNTIME(42,app-a):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Dispatch stream_id=3, task_id=19, node_id=1.\n"
                "[INFO] RUNTIME(42,app-a):2026-09-08-10:11:12.000002 "
                "[runtime.cc:2]Recycle task stream_id=3, task_id=19, node_id=2.\n"
                "[INFO] RUNTIME(42,app-a):2026-09-08-10:11:12.000003 "
                "[runtime.cc:3]Dispatch stream_id=4, task_id=20, node_id=1.\n"
                "[INFO] RUNTIME(42,app-b):2026-09-08-10:11:12.000004 "
                "[runtime.cc:4]Recycle task stream_id=4, task_id=20, node_id=1.\n"
                "[FATAL] RUNTIME(42,app-a):2026-09-08-10:11:12.000005 "
                "[runtime.cc:5]Process abort.\n",
                encoding="utf-8",
            )

            trace = build_trace(root)

            self.assertEqual(trace["spans"], [])
            self.assertIn("unmatched_span_endpoints", trace["diagnostics"]["gaps"])


if __name__ == "__main__":
    unittest.main()
