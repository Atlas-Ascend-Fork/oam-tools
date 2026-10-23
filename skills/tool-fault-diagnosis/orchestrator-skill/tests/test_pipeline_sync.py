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
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from artifact_contract import read_artifact  # noqa: E402


class PipelineSyncTest(unittest.TestCase):
    def test_pipeline_preserves_logs_and_keeps_trace_link_next_to_report(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "logs"
            input_dir.mkdir()
            original = (
                b"[DEBUG] RUNTIME(7,app):2026-09-08-10:11:12.000001 [runtime.cc:1]start\n"
                b"\n"
                b"[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000002 [runtime.cc:2]Process abort\n"
                b"[FATAL] RUNTIME(7,app):2026-09-08-10:11:12.000002 [runtime.cc:2]Process abort\n"
            )
            source = input_dir / "fault.log"
            source.write_bytes(original)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps({"input": {"path": str(input_dir)},
                                             "stages": {"diagnose": {"execution": "evidence_only"}}}), encoding="utf-8")
            state_dir = root / "state"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "run_pipeline.py"),
                    "--plan",
                    str(plan_path),
                    "--state-dir",
                    str(state_dir),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            clean, _ = read_artifact(state_dir / "artifacts" / "clean-result.md")
            self.assertEqual(clean["result"]["input_lines"], 4)
            self.assertEqual(clean["result"]["kept_lines"], 4)
            self.assertEqual(clean["result"]["collapsed_lines"], 0)
            self.assertEqual(len(clean["result"]["files"]), 1)
            self.assertEqual(Path(clean["result"]["files"][0]["output"]).read_bytes(), original)
            self.assertTrue(Path(clean["result"]["audit_path"]).is_file())

            report, _ = read_artifact(state_dir / "artifacts" / "report.md")
            report_html = next(
                Path(output["path"])
                for output in report["outputs"]
                if output["kind"] == "diagnostic_html"
            )
            self.assertTrue((report_html.parent / "tracing-report.html").is_file())
            self.assertIn("tracing-report.html?", report_html.read_text(encoding="utf-8"))
