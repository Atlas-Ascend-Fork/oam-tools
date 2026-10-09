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

from fault_trace_core import build_trace, render_html, validate_trace  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


class BoundedContextTest(unittest.TestCase):
    def write_window_fixture(self, root: Path) -> None:
        root.joinpath("fault.log").write_text(
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:10.000000 "
            "[runtime.cc:1]Dispatch stream_id=3, task_id=19.\n"
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:10.999999 "
            "[runtime.cc:2]Outside before.\n"
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:11.000000 "
            "[runtime.cc:3]Exact before boundary.\n"
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:11.999900 "
            "[runtime.cc:4]Nearest context.\n"
            "[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000000 "
            "[runtime.cc:5]Abort stream_id=3, task_id=19.\n"
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:12.100000 "
            "[runtime.cc:6]Exact after boundary.\n"
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:12.100001 "
            "[runtime.cc:7]Outside after.\n"
            "[INFO] RUNTIME(7,app):2026-09-08-10:11:13.500000 "
            "[runtime.cc:8]Return stream_id=3, task_id=19.\n",
            encoding="utf-8",
        )

    def selected_view(self, trace: dict) -> dict:
        return next(
            view
            for view in trace["views"]
            if view["anchor_id"] == trace["selected_anchor_id"]
        )

    def messages_for(self, trace: dict, event_ids: list[str]) -> set[str]:
        event_by_id = {event["id"]: event for event in trace["events"]}
        return {event_by_id[event_id]["message"] for event_id in event_ids}

    def test_default_window_is_inclusive_and_preserves_proven_chain_outside_it(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.write_window_fixture(root)

            trace = build_trace(root)
            view = self.selected_view(trace)
            window = view["context_window"]
            messages = self.messages_for(trace, view["context_event_ids"])

            self.assertEqual(
                window["requested"],
                {
                    "before_us": 1_000_000,
                    "after_us": 100_000,
                    "non_chain_event_limit": 20_000,
                },
            )
            self.assertEqual(window["requested_start_offset_us"], 1_000_000)
            self.assertEqual(window["requested_end_offset_us"], 2_100_000)
            self.assertEqual(window["effective_start_offset_us"], 1_000_000)
            self.assertEqual(window["effective_end_offset_us"], 2_100_000)
            self.assertEqual(window["scope_event_count"], 8)
            self.assertEqual(window["included_non_chain_event_count"], 3)
            self.assertEqual(window["excluded_outside_window_count"], 2)
            self.assertEqual(window["excluded_by_limit_count"], 0)
            self.assertEqual(window["preserved_chain_event_count"], 3)
            self.assertTrue(window["truncated"])
            self.assertEqual(trace["diagnostics"]["context_window"], window)
            self.assertIn("context_truncated", trace["diagnostics"]["gaps"])
            self.assertIn("Exact before boundary.", messages)
            self.assertIn("Exact after boundary.", messages)
            self.assertNotIn("Outside before.", messages)
            self.assertNotIn("Outside after.", messages)
            self.assertIn("Dispatch stream_id=3, task_id=19.", messages)
            self.assertIn("Return stream_id=3, task_id=19.", messages)

    def test_non_chain_limit_keeps_nearest_event_without_removing_chain(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.write_window_fixture(root)

            trace = build_trace(root, context_event_limit=1)
            view = self.selected_view(trace)
            window = view["context_window"]
            messages = self.messages_for(trace, view["context_event_ids"])

            self.assertEqual(window["included_non_chain_event_count"], 1)
            self.assertEqual(window["excluded_outside_window_count"], 2)
            self.assertEqual(window["excluded_by_limit_count"], 2)
            self.assertEqual(window["effective_start_offset_us"], 1_999_900)
            self.assertEqual(window["effective_end_offset_us"], 1_999_900)
            self.assertIn("Nearest context.", messages)
            self.assertEqual(len(view["context_event_ids"]), 4)
            self.assertTrue(set(view["highlighted_event_ids"]).issubset(view["context_event_ids"]))

    def test_cli_overrides_window_values_independently_and_rejects_negative_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_root = root / "input"
            input_root.mkdir()
            self.write_window_fixture(input_root)
            output = root / "output"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    str(input_root),
                    "--output-dir",
                    str(output),
                    "--context-before-us",
                    "0",
                    "--context-after-us",
                    "0",
                    "--context-event-limit",
                    "0",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((output / "fault-trace.json").read_text(encoding="utf-8"))
            view = self.selected_view(trace)
            self.assertEqual(
                view["context_window"]["requested"],
                {"before_us": 0, "after_us": 0, "non_chain_event_limit": 0},
            )
            self.assertEqual(
                set(view["context_event_ids"]), set(view["highlighted_event_ids"])
            )

            invalid = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    str(input_root),
                    "--output-dir",
                    str(root / "invalid-output"),
                    "--context-before-us",
                    "-1",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("non-negative", invalid.stderr)

    def test_runtime_validator_rejects_inconsistent_context_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.write_window_fixture(root)
            trace = build_trace(root)

            wrong_count = copy.deepcopy(trace)
            self.selected_view(wrong_count)["context_window"][
                "included_non_chain_event_count"
            ] += 1

            wrong_global = copy.deepcopy(trace)
            wrong_global["diagnostics"]["context_window"]["truncated"] = False

            for invalid in (wrong_count, wrong_global):
                with self.subTest(trace=invalid):
                    with self.assertRaises(TraceValidationError):
                        validate_trace(invalid)

    def test_schema_and_viewer_publish_context_window_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.write_window_fixture(root)
            trace = build_trace(root, context_event_limit=1)

            schema = json.loads(
                (SKILL_ROOT / "schemas" / "fault-trace-v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                schema["$defs"]["view"]["properties"]["context_window"]["$ref"],
                "#/$defs/contextWindow",
            )
            self.assertEqual(
                schema["properties"]["diagnostics"]["properties"]["context_window"][
                    "$ref"
                ],
                "#/$defs/contextWindow",
            )
            context_window = schema["$defs"]["contextWindow"]
            self.assertIn("requested", context_window["required"])
            self.assertIn("excluded_by_limit_count", context_window["required"])

            html = render_html(trace)
            self.assertIn("window -1000000/+100000 us", html)
            self.assertIn("2 outside window", html)
            self.assertIn("2 over event limit", html)


if __name__ == "__main__":
    unittest.main()
