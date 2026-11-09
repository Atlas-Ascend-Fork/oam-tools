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
                    self.assertIn("CASE-008" if has_main else "CASE-001", result.stdout)
                    self.assertIn("验证状态：已验证修复有效", result.stdout)
                    self.assertIn("转正日期：", result.stdout)


if __name__ == "__main__":
    unittest.main()
