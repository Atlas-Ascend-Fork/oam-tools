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
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
BUILDER = SKILL_ROOT / "scripts" / "build_html_report.py"


class ComponentChainReportTest(unittest.TestCase):
    def run_builder(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUILDER), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

    def component_chain(self) -> dict[str, object]:
        return {
            "schema_version": "1.0.0",
            "anchor_id": "event-app",
            "execution_event_ids": ["event-app", "event-hccl"],
            "nodes": [
                {
                    "id": "component-node-001",
                    "component": "Application",
                    "member_event_ids": ["event-app"],
                    "representative_event_id": "event-app",
                    "fault_role": "business-error",
                    "summary": "ERR00100 call failed",
                    "evidence_ids": ["evidence-app"],
                    "deep_link": {
                        "view": "fault",
                        "anchor": "event-app",
                        "component": "Application",
                        "event": "event-app",
                    },
                },
                {
                    "id": "component-node-002",
                    "component": "HCCL",
                    "member_event_ids": ["event-hccl"],
                    "representative_event_id": "event-hccl",
                    "fault_role": "fault-source",
                    "summary": "channel connect timeout hcclRet=9",
                    "evidence_ids": ["evidence-hccl"],
                    "deep_link": {
                        "view": "fault",
                        "anchor": "event-app",
                        "component": "HCCL",
                        "event": "event-hccl",
                    },
                },
            ],
            "edges": [
                {
                    "id": "component-edge-001",
                    "source_component": "Application",
                    "target_component": "HCCL",
                    "kind": "call",
                    "strength": "inferred",
                    "rule_ids": ["observed-error-path-architecture-v1"],
                    "event_relationship_ids": ["relationship-1"],
                    "evidence_ids": ["evidence-app", "evidence-hccl"],
                }
            ],
            "gaps": [],
        }

    def test_builder_renders_clickable_component_chain_below_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            work = root / "work"
            initialized = self.run_builder("--init", str(work))
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            data_path = work / "report-data.json"
            trace_path = root / "fault-trace.json"
            trace_path.write_text(
                json.dumps(
                    {"schema_version": "1.0.0", "component_chain": self.component_chain()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            output = root / "diagnostic-report.html"

            completed = self.run_builder(
                "--input",
                str(work / "index.html"),
                "--data",
                str(data_path),
                "--trace",
                str(trace_path),
                "--output",
                str(output),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = output.read_text(encoding="utf-8")
            self.assertIn('id="component-chain-title"', report)
            self.assertIn('data-component-chain-component="Application"', report)
            self.assertIn('data-component-chain-component="HCCL"', report)
            self.assertIn('data-component-chain-strength="inferred"', report)
            self.assertIn(
                "tracing-report.html?view=fault&amp;anchor=event-app&amp;component=HCCL&amp;event=event-hccl",
                report,
            )
            self.assertLess(
                report.index('id="chain-title"'),
                report.index('id="component-chain-title"'),
            )
            self.assertLess(
                report.index('id="component-chain-title"'),
                report.index('id="remedy-title"'),
            )

    def test_builder_rejects_unknown_component_chain_strength(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            work = root / "work"
            initialized = self.run_builder("--init", str(work))
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            data_path = work / "report-data.json"
            chain = self.component_chain()
            chain["edges"][0]["strength"] = "guessed"
            trace_path = root / "fault-trace.json"
            trace_path.write_text(
                json.dumps(
                    {"schema_version": "1.0.0", "component_chain": chain},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            completed = self.run_builder(
                "--input",
                str(work / "index.html"),
                "--data",
                str(data_path),
                "--trace",
                str(trace_path),
                "--output",
                str(root / "invalid.html"),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("component_chain.edges.0.strength", completed.stderr)

    def test_builder_preserves_multiple_component_to_hardware_edges(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            work = root / "work"
            initialized = self.run_builder("--init", str(work))
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            data_path = work / "report-data.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            architecture = data["architecture"]
            component_layer = next(layer for layer in architecture["layers"] if layer["kind"] == "component")
            hardware_layer = next(layer for layer in architecture["layers"] if layer["kind"] == "hardware")
            component_id = component_layer["nodes"][0]["id"]
            hardware_template = hardware_layer["nodes"][0]
            hardware_layer["nodes"] = []
            edges = []
            for index in range(4):
                hardware_id = f"hardware-{index}"
                hardware_node = dict(hardware_template)
                hardware_node.update({"id": hardware_id, "title": f"Device {index}"})
                hardware_layer["nodes"].append(hardware_node)
                edges.append(
                    {
                        "from": component_id,
                        "to": hardware_id,
                        "kind": "call",
                        "evidence_strength": "proven",
                        "label": "调用/任务下发",
                    }
                )
            architecture["edges"] = edges
            data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            output = root / "diagnostic-report.html"
            completed = self.run_builder(
                "--input",
                str(work / "index.html"),
                "--data",
                str(data_path),
                "--output",
                str(output),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = output.read_text(encoding="utf-8")
            self.assertEqual(report.count(f'data-edge-from="{component_id}"'), 4)
            self.assertIn("const hardwareRouteGroups = new Map();", report)
            self.assertIn("return label;", report)


if __name__ == "__main__":
    unittest.main()
