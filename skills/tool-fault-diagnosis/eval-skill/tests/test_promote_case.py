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
"""Safety checks for case promotion and read-only scanning."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "promote_case.py"


class PromoteCaseTests(unittest.TestCase):
    def test_check_and_promote_cannot_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pending = root / "cases-pending.md"
            pending.write_text("## PCASE-001：候选\n- 验证状态：待验证\n", encoding="utf-8")
            sample = root / "sample.txt"
            sample.write_text("public sample\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--check", "--files", str(sample),
                 "--promote", "PCASE-001", "--cases-dir", str(root)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "cases.md").exists())
            self.assertIn("PCASE-001", pending.read_text(encoding="utf-8"))

    def test_sensitive_candidate_is_not_promoted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pending = root / "cases-pending.md"
            pending.write_text(
                "## PCASE-001：候选\n- 验证状态：待验证\n"
                "- 关键日志：token=private-value\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--promote", "PCASE-001",
                 "--cases-dir", str(root)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "cases.md").exists())
            self.assertIn("PCASE-001", pending.read_text(encoding="utf-8"))

    def test_migration_inline_case_gets_next_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pending = root / "cases-pending.md"
            pending.write_text("## PCASE-001：Public candidate\n- 验证状态：待验证\n", encoding="utf-8")
            main = root / "cases.md"
            main.write_text("## CASE-HANG-001：inline legacy case\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--promote", "PCASE-001", "--cases-dir", str(root), "--dry-run"],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CASE-HANG-002", result.stdout)

    def test_promote_non_dry_run_moves_candidate_and_syncs_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pending = root / "cases-pending.md"
            pending.write_text(
                "## PCASE-001：Public candidate\n- 验证状态：待验证\n\n---\n\n"
                "## PCASE-002：Retained candidate\n- 验证状态：待验证\n",
                encoding="utf-8")
            index = root / "cases.md"
            index.write_text("# 常见问题案例库\n\n| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--promote", "PCASE-001", "--cases-dir", str(root)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            category = root / "cases-hang.md"
            self.assertIn("## CASE-HANG-001", category.read_text(encoding="utf-8"))
            self.assertIn("| CASE-HANG-001 |", index.read_text(encoding="utf-8"))
            self.assertIn("## PCASE-002", pending.read_text(encoding="utf-8"))
            self.assertNotIn("## PCASE-001", pending.read_text(encoding="utf-8"))
            self.assertFalse((root / "pipeline.lock").exists())

    def test_concurrent_accepts_get_unique_ids_and_consistent_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases_dir = root / "cases"
            cases_dir.mkdir()
            index = cases_dir / "cases.md"
            category = cases_dir / "cases-hang.md"
            index.write_text(
                "# 常见问题案例库\n\n| 分类 | 案例文件 | 编号 |\n| --- | --- | --- |\n",
                encoding="utf-8",
            )
            category.write_text("# 进程卡住 案例集\n", encoding="utf-8")
            jobs = []
            for number in (1, 2):
                report = root / f"report-{number}.md"
                report.write_text(
                    f"# 故障 {number}\n\n## 问题摘要\n\n独立故障 {number}\n\n"
                    "## 关键日志\n\n```\nERROR timeout\n```\n\n"
                    "## 根因分析\n\nhang\n\n## 修复建议\n\nfix\n",
                    encoding="utf-8",
                )
                confidence = root / f"confidence-{number}.json"
                confidence.write_text(
                    json.dumps({"case_gate": "accept", "final_score": 90, "level": "HIGH"}),
                    encoding="utf-8",
                )
                jobs.append((report, confidence))
            processes = [
                subprocess.Popen(
                    [sys.executable, str(SCRIPT), "--report", str(report),
                     "--confidence", str(confidence), "--cases-dir", str(cases_dir)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                for report, confidence in jobs
            ]
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=30)
                results.append((process.returncode, stdout, stderr))
            self.assertTrue(all(code == 0 for code, _, _ in results), results)
            category_text = category.read_text(encoding="utf-8")
            index_text = index.read_text(encoding="utf-8")
            self.assertIn("## CASE-HANG-001", category_text)
            self.assertIn("## CASE-HANG-002", category_text)
            self.assertEqual(category_text.count("独立故障"), 2)
            self.assertIn("| CASE-HANG-001 |", index_text)
            self.assertIn("| CASE-HANG-002 |", index_text)
            self.assertFalse((cases_dir / "pipeline.lock").exists())

    def test_stale_library_lock_can_be_forced_unlocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cases-pending.md").write_text(
                "## PCASE-001：Public candidate\n- 验证状态：待验证\n", encoding="utf-8")
            (root / "pipeline.lock").write_text(
                '{"pid": 99999999, "token": "stale", "host": "same", "at": "2026-01-01"}',
                encoding="utf-8")
            env = dict(os.environ, COMPUTERNAME="same")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--promote", "PCASE-001", "--cases-dir", str(root),
                 "--force-unlock"],
                capture_output=True, text=True, encoding="utf-8", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "pipeline.lock").exists())
            self.assertIn("CASE-HANG-001", (root / "cases-hang.md").read_text(encoding="utf-8"))

    def test_pending_write_requires_library_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = root / "pipeline.lock"
            lock.write_text(
                json.dumps({"pid": os.getpid(), "token": "other", "host": "other", "at": "now"}),
                encoding="utf-8")
            report = root / "report.md"
            report.write_text(
                "# Diagnosis\n\n## 问题摘要\n\nPublic pending case\n\n## 关键日志\n\n"
                "```\nERROR timeout\n```\n\n## 根因分析\n\nhang\n\n## 修复建议\n\nfix\n",
                encoding="utf-8")
            confidence = root / "confidence.json"
            confidence.write_text(
                json.dumps({"case_gate": "pending", "final_score": 75, "level": "MEDIUM"}),
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--report", str(report), "--confidence", str(confidence),
                 "--cases-dir", str(root)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("案例库锁已存在", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((root / "cases-pending.md").exists())

    def test_dry_run_promote_preserves_case_libraries(self):
        for has_main in (False, True):
            with self.subTest(has_main=has_main):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    pending = root / "cases-pending.md"
                    pending.write_text(
                        "## PCASE-001：Public candidate\n"
                        "- 验证状态：待验证\n\n---\n\n"
                        "## PCASE-002：Retained candidate\n"
                        "- 验证状态：待验证\n",
                        encoding="utf-8",
                    )
                    main = root / "cases.md"
                    if has_main:
                        main.write_text(
                            "# Retained cases\n\n## CASE-007：Retained reference\n",
                            encoding="utf-8",
                        )
                    before_pending = pending.read_bytes()
                    before_main = main.read_bytes() if has_main else None
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--promote",
                            "PCASE-001",
                            "--cases-dir",
                            str(root),
                            "--dry-run",
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(pending.read_bytes(), before_pending)
                    if has_main:
                        self.assertEqual(main.read_bytes(), before_main)
                    else:
                        self.assertFalse(main.exists())
                    self.assertIn("[DRY-RUN]", result.stdout)
                    self.assertIn("CASE-HANG-001", result.stdout)
                    self.assertIn("验证状态：已验证修复有效", result.stdout)
                    self.assertIn("转正日期：", result.stdout)


if __name__ == "__main__":
    unittest.main()
