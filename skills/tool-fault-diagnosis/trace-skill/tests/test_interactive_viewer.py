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
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
VIEWER_HARNESS = SKILL_ROOT / "tests" / "run_interactive_viewer_behavior.mjs"
DEEP_LINK_HARNESS = SKILL_ROOT / "tests" / "run_deep_link_viewer_behavior.mjs"
DEVICE_FIXTURE = SKILL_ROOT / "tests" / "fixtures" / "device-trace-redacted"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, render_html  # noqa: E402


class InteractiveViewerTest(unittest.TestCase):
    def build_viewer(self, root: Path) -> tuple[dict, Path, str]:
        root.joinpath("fault.log").write_text(
            "[INFO] RUNTIME(42,worker-a):2026-09-08-10:11:12.000001 "
            "[runtime.cc:1]Dispatch stream_id=3, task_id=19.\n"
            "[INFO] RUNTIME(42,worker-a):2026-09-08-10:11:12.000009 "
            "[runtime.cc:2]Recycle task stream_id=3, task_id=19.\n"
            "[FATAL] RUNTIME(42,worker-a):2026-09-08-10:11:12.000010 "
            "[runtime.cc:3]Worker-a abort.\n"
            "[INFO] GE(99,worker-b):2026-09-08-10:11:12.000020 "
            "[ge.cc:4]Routine worker-b activity.\n"
            "[FATAL] GE(99,worker-b):2026-09-08-10:11:17.000030 "
            "[ge.cc:5]Worker-b abort.\n",
            encoding="utf-8",
        )
        trace = build_trace(root)
        html = render_html(trace)
        html_path = root / "fault-trace.html"
        html_path.write_text(html, encoding="utf-8")
        return trace, html_path, html

    def test_viewer_is_self_contained_and_exposes_overview_detail_controls(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            trace, _, html = self.build_viewer(Path(temporary_directory))

            self.assertIn('id="timeline-overview"', html)
            self.assertIn('id="detail-viewport"', html)
            self.assertIn('class="overview-anchor"', html)
            self.assertIn('id="timeline-zoom"', html)
            self.assertIn('id="zoom-scale-label"', html)
            self.assertIn('id="full-context-toggle"', html)
            self.assertIn('id="inferred-toggle"', html)
            self.assertIn('id="evidence-filter"', html)
            self.assertIn('id="event-details"', html)
            self.assertIn('lang="zh-CN"', html)
            self.assertIn('id="locale-select"', html)
            self.assertIn('id="theme-toggle"', html)
            self.assertIn('data-theme="light"', html)
            self.assertIn('已证明链路事件', html)
            self.assertIn('option value="en"', html)
            self.assertIn('id="evidence-page-status"', html)
            self.assertIn('class="component-chain-card"', html)
            self.assertIn('class="component-chain-stage"', html)
            self.assertIn('data-component-chain-source', html)
            self.assertIn('class="event event-point', html)
            self.assertIn('class="span"', html)
            self.assertIn('class="overview-bin', html)
            self.assertNotIn('class="overview-event', html)
            for forbidden in (
                "http://",
                "https://",
                "fetch(",
                "XMLHttpRequest",
                "WebSocket",
            ):
                self.assertNotIn(forbidden, html)

    def test_deep_link_prefers_event_and_falls_back_to_default_anchor(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            trace, html_path, _ = self.build_viewer(Path(temporary_directory))
            ge_anchor = next(
                event["id"]
                for event in trace["events"]
                if event["component"] == "GE" and event["level"] == "FATAL"
            )
            selected = subprocess.run(
                [
                    "node",
                    str(DEEP_LINK_HARNESS),
                    str(html_path),
                    f"?view=fault&anchor={ge_anchor}&component=GE&event={ge_anchor}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            selected_state = json.loads(selected.stdout)
            self.assertEqual(selected_state["activeAnchorId"], ge_anchor)
            self.assertEqual(selected_state["viewMode"], "fault")
            self.assertEqual(selected_state["detailsEventId"], ge_anchor)
            self.assertEqual(selected_state["deepLinkFallbacks"], [])

            invalid = subprocess.run(
                [
                    "node",
                    str(DEEP_LINK_HARNESS),
                    str(html_path),
                    "?view=fault&anchor=missing&component=missing&event=missing",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            invalid_state = json.loads(invalid.stdout)
            self.assertEqual(invalid_state["activeAnchorId"], trace["selected_anchor_id"])
            self.assertEqual(invalid_state["detailsEventId"], trace["selected_anchor_id"])
            self.assertEqual(
                invalid_state["deepLinkFallbacks"],
                ["anchor", "event", "component"],
            )

    def test_initial_markup_contains_only_the_selected_proven_chain(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            trace, _, html = self.build_viewer(Path(temporary_directory))
            selected_view = next(
                view
                for view in trace["views"]
                if view["anchor_id"] == trace["selected_anchor_id"]
            )
            rendered_ids = set(
                re.findall(
                    r'<button class="[^"]*\bevent-point\b[^"]*"[^>]*data-event-id="([^"]+)"',
                    html,
                )
            )

            self.assertEqual(rendered_ids, set(selected_view["highlighted_event_ids"]))
            self.assertLess(len(rendered_ids), len(selected_view["context_event_ids"]))

    def test_component_process_lanes_and_unaligned_clock_panels_are_explicit(self):
        trace = build_trace(DEVICE_FIXTURE)
        html = render_html(trace)
        initial_markup = html.split('<script id="fault-trace-data"', 1)[0]

        roots = {
            event["timestamp"].get(
                "aligned_clock_domain_id", event["timestamp"]["clock_domain_id"]
            )
            for event in trace["events"]
        }
        self.assertEqual(initial_markup.count('class="clock-panel"'), len(roots))
        self.assertIn('data-location="host"', initial_markup)
        self.assertIn('data-location="device"', initial_markup)
        self.assertRegex(initial_markup, r'class="trace-lane"[^>]+data-component="[^"]+"')
        self.assertRegex(initial_markup, r'class="trace-lane"[^>]+data-process="[^"]+"')
        self.assertIn('class="time-axis"', initial_markup)
        self.assertRegex(initial_markup, r'class="time-tick"[^>]+data-relative-us="-?\d+"')
        self.assertRegex(initial_markup, r'class="tick-label">[+-]?\d+(?:\.\d+)? (?:us|ms)<')

    def test_device_evidence_state_and_clock_identity_are_explicit(self):
        trace = build_trace(DEVICE_FIXTURE)
        html = render_html(trace)
        initial_markup = html.split('<script id="fault-trace-data"', 1)[0]

        device_labels = re.findall(
            r'<span class="overview-label">([^<]*Device[^<]*)</span>', initial_markup
        )
        self.assertGreaterEqual(len(device_labels), 2)
        self.assertEqual(len(device_labels), len(set(device_labels)))
        self.assertTrue(all("·" in label or "clock-" in label for label in device_labels))
        self.assertIn('data-evidence-state="device-records-unaligned"', initial_markup)
        self.assertIn("Device records", initial_markup)
        self.assertIn("no proven relation", initial_markup)
        self.assertIn("independent clocks", initial_markup)

    def test_no_device_records_have_a_distinct_summary_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("host-only.log").write_text(
                "[FATAL] RUNTIME(42,worker-a):2026-09-08-10:11:12.000010 "
                "[runtime.cc:3]Worker-a abort.\n",
                encoding="utf-8",
            )
            html = render_html(build_trace(root))

            self.assertIn('data-evidence-state="no-device-records"', html)
            self.assertIn("No Device records", html)

    def test_fault_anchor_has_a_prominent_marker(self):
        html = render_html(build_trace(DEVICE_FIXTURE))

        self.assertRegex(
            html,
            r"\.event\.anchor\s*\{[^}]*z-index:\s*[6789]",
        )
        self.assertRegex(
            html,
            r"\.event\.anchor \.event-glyph[^}]*width:\s*1[6-9]px",
        )

    def test_inferred_relationships_are_disabled_independently_by_default(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("inferred.log").write_text(
                "[INFO] RUNTIME(42,worker-a):2026-09-08-10:11:12.000001 "
                "[runtime.cc:1]Runtime step.\n"
                "[INFO] GE(42,worker-a):2026-09-08-10:11:12.000002 "
                "[ge.cc:2]GE step.\n"
                "[FATAL] RUNTIME(42,worker-a):2026-09-08-10:11:12.000003 "
                "[runtime.cc:3]Worker abort.\n",
                encoding="utf-8",
            )
            trace = build_trace(root)
            self.assertTrue(
                any(item["strength"] == "inferred" for item in trace["relationships"])
            )
            html = render_html(trace)

            self.assertRegex(
                html,
                r'class="connector inferred"[^>]+data-strength="inferred"[^>]+hidden',
            )
            self.assertRegex(
                html,
                r'class="relationship inferred"[^>]+data-strength="inferred"[^>]+hidden',
            )

    def test_overview_and_tables_have_bounded_initial_dom(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            records = [
                f"[INFO] RUNTIME(42,worker-a):2026-09-08-10:11:12.{index:06d} "
                f"[runtime.cc:{index + 1}]Routine activity {index}.\n"
                for index in range(300)
            ]
            records.append(
                "[FATAL] RUNTIME(42,worker-a):2026-09-08-10:11:13.000001 "
                "[runtime.cc:301]Worker abort.\n"
            )
            root.joinpath("large.log").write_text("".join(records), encoding="utf-8")
            trace = build_trace(root)
            html = render_html(trace)

            self.assertGreater(len(trace["events"]), 250)
            self.assertLessEqual(html.count('class="overview-bin'), 120)
            self.assertLessEqual(html.count('class="evidence-row"'), 25)
            self.assertLessEqual(html.count('class="relationship '), 25)
            self.assertIn('data-page-size="25"', html)
            self.assertIn('id="relationship-page-status"', html)

    def test_viewer_interactions_share_one_state_without_changing_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            trace, html_path, _ = self.build_viewer(Path(temporary_directory))
            target_anchor = trace["fault_candidates"][1]
            selected_event = next(
                event
                for event in trace["events"]
                if "Routine worker-b" in event["message"]
            )["id"]

            completed = subprocess.run(
                [
                    "node",
                    str(VIEWER_HARNESS),
                    str(html_path),
                    target_anchor,
                    selected_event,
                    "Routine",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            behavior = json.loads(completed.stdout)
            self.assertEqual(behavior["switched"]["activeAnchorId"], target_anchor)
            self.assertEqual(
                behavior["switched"]["overviewHighlightedIds"], [target_anchor]
            )
            target_view = next(view for view in trace["views"] if view["anchor_id"] == target_anchor)
            self.assertEqual(
                set(behavior["context"]["visibleEventIds"]),
                set(target_view["context_event_ids"]),
            )
            self.assertEqual(
                set(behavior["filtered"]["visibleEventIds"]),
                {target_anchor, selected_event},
            )
            self.assertEqual(behavior["selected"]["selectedEventIds"], [selected_event])
            self.assertEqual(behavior["selected"]["selectedEvidenceIds"], [selected_event])
            self.assertEqual(behavior["selected"]["detailsEventId"], selected_event)
            self.assertEqual(behavior["sortedEvidenceLines"], [5, 4])
            self.assertFalse(behavior["initial"]["showInferred"])
            self.assertGreater(behavior["zoomed"]["pixelsPerUs"], behavior["initial"]["pixelsPerUs"])
            self.assertEqual(
                behavior["zoomed"]["eventCoordinates"],
                behavior["beforeZoom"]["eventCoordinates"],
            )


if __name__ == "__main__":
    unittest.main()
