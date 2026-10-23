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
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from artifact_contract import read_artifact, write_artifact


class DiagnosisHandoffTests(unittest.TestCase):
    def test_evidence_draft_requires_analysis_before_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fault.log"
            source.write_text("[ERROR] RUNTIME(7,app):2026-10-18-10:00:00.000001 "
                              "device_id=0 HBM allocation failed requested=8GB available=2GB\n")
            plan = root / "plan.json"
            plan.write_text(json.dumps({"input": {"path": str(source)}}))
            state_dir = root / "state"
            command = [sys.executable, str(SCRIPTS / "run_pipeline.py"),
                       "--plan", str(plan), "--state-dir", str(state_dir)]
            result = subprocess.run(command, capture_output=True, text=True)
            state = json.loads((state_dir / "state.json").read_text())
            self.assertEqual(state["stages"]["diagnose"]["status"], "blocked", result.stdout)
            self.assertEqual(state["stages"]["confidence"]["status"], "pending")
            artifact_path = state_dir / "artifacts" / "diagnosis.md"
            artifact, body = read_artifact(artifact_path)
            self.assertEqual(artifact["result"]["analysis_status"], "draft")
            self.assertTrue(artifact["result"]["first_error"])

            # An agent can finish a bounded conclusion without inventing a cause.
            artifact["status"] = "success"
            artifact["result"]["analysis_status"] = "reviewed"
            artifact["result"]["root_cause"]["description"] = (
                "The 8GB allocation exceeds the reported 2GB available; "
                "the memory consumer is not identified in this log.")
            artifact["result"]["root_cause"]["status"] = "hypothesis"
            artifact["result"]["recommendations"] = [{
                "action": "Reduce the allocation below the available capacity and verify the same workload.",
                "status": "recommended", "expected_impact": "Avoid allocation failure",
                "evidence": ["fault.log:1"],
            }]
            write_artifact(artifact_path, artifact, body)
            resumed = subprocess.run(command + ["--resume"], capture_output=True, text=True)
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            state = json.loads((state_dir / "state.json").read_text())
            self.assertEqual(state["stages"]["report"]["status"], "success")
            report, _ = read_artifact(state_dir / "artifacts" / "report.md")
            self.assertEqual(report["result"]["recommendations"][0]["action"],
                             artifact["result"]["recommendations"][0]["action"])
            data_path = next(Path(item["path"]) for item in report["outputs"]
                             if item["kind"] == "report_data")
            data = json.loads(data_path.read_text())
            self.assertIn("hypothesis", data["notices"]["caution"]["detail"])


if __name__ == "__main__":
    unittest.main()
