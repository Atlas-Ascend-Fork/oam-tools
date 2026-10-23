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
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "docs/benchmark/2026-10-18/score_report.py"


@unittest.skipUnless(SCRIPT.is_file(), "Missing reproducible score report")
class BenchmarkReportTests(unittest.TestCase):
    def test_report_output_cannot_overwrite_frozen_inputs(self):
        spec = importlib.util.spec_from_file_location("score_report", SCRIPT)
        report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(report)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, benchmark = root / "run", root / "benchmark"
            run.mkdir()
            benchmark.mkdir()
            selection = root / "selection.json"
            selection.write_text("frozen selection")
            manifest = run / "manifest.json"
            manifest.write_text("frozen manifest")
            self.assertTrue(hasattr(report, "validate_report_output"))
            for path in (manifest, run / "judge.json", benchmark / "input.json", selection):
                with self.assertRaises(ValueError):
                    report.validate_report_output(path, [run, benchmark], [selection])
            report.validate_report_output(root / "report.json", [run, benchmark], [selection])
            self.assertEqual(selection.read_text(), "frozen selection")
            self.assertEqual(manifest.read_text(), "frozen manifest")

    def test_retained_cohort_keeps_failed_cases_in_denominator(self):
        self.assertTrue(SCRIPT.is_file(), "Missing reproducible score report")
        spec = importlib.util.spec_from_file_location("score_report", SCRIPT)
        report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(report)
        rows = [{"source_name": "DTS", "case_id": "A", "status": "judged", "score": 90},
                {"source_name": "DTS", "case_id": "B", "status": "no_result", "score": 0},
                {"source_name": "DTS", "case_id": "C", "status": "judged", "score": 30}]
        summary = report.cohort_summary(rows, {("DTS", "A"), ("DTS", "B")})
        self.assertEqual(summary["expected"], 2)
        self.assertEqual(summary["mean_all_cases"], 45)
        self.assertEqual(summary["scored"], 1)
        self.assertFalse(summary["accepted"])

    def test_missing_selected_case_cannot_disappear_from_report(self):
        self.assertTrue(SCRIPT.is_file(), "Missing reproducible score report")
        spec = importlib.util.spec_from_file_location("score_report", SCRIPT)
        report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(report)
        rows = [{"source_name": "DTS", "case_id": "A", "status": "judged", "score": 90}]
        summary = report.cohort_summary(rows, {("DTS", "A"), ("DTS", "missing")})
        self.assertEqual(summary["expected"], 2)
        self.assertEqual(summary["mean_all_cases"], 45)


if __name__ == "__main__":
    unittest.main()
