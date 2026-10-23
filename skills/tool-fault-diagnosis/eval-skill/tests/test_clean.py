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
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "clean.py"
SPEC = importlib.util.spec_from_file_location("diagnosis_clean", SCRIPT)
clean = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clean)


class EvidenceCleaningTests(unittest.TestCase):
    def test_error_focus_preserves_progress_stack_and_repeated_errors(self):
        lines = ["[INFO] rank=2 entered AllReduce\n", "\n",
                 "[ERROR] allocation failed\n", "  kernel.cc:72\n",
                 "[ERROR] allocation failed\n", "[DEBUG] task submit id=17\n"]
        self.assertEqual(clean.clean_lines(lines, "ERROR"),
                         [line.rstrip("\n") for line in lines])

    def test_file_preserves_crlf_and_missing_final_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "raw.log"
            output = Path(directory) / "clean.log"
            raw = b"[INFO] started\r\n\r\n[ERROR] failed\r\n  stack:72"
            source.write_bytes(raw)
            clean.process_file(source, output, "ERROR")
            self.assertEqual(output.read_bytes(), raw)

    def test_input_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "raw.log"
            raw = b"[INFO] started\n[ERROR] failed\n"
            source.write_bytes(raw)
            with self.assertRaises(ValueError):
                clean.process_file(source, source, "ERROR")
            self.assertEqual(source.read_bytes(), raw)

    def test_decode_failure_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "raw.log"
            output = Path(directory) / "clean.log"
            source.write_bytes(b"[ERROR] \xff\n")
            with self.assertRaises(UnicodeDecodeError):
                clean.process_file(source, output)
            self.assertFalse(output.exists())

    def test_merge_keeps_continuation_with_its_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "logs"
            logs.mkdir()
            first = "[ERROR] 2026-10-18 10:00:02.000 crash\n  stack.cc:72\n"
            second = "[INFO] 2026-10-18 10:00:01.000 other host\n"
            (logs / "a.log").write_text(first)
            (logs / "b.log").write_text(second)
            output = root / "merged.log"
            result = subprocess.run([sys.executable, str(SCRIPT), "--input-dir", str(logs),
                                     "--merge", "--output", str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(), first + second)


if __name__ == "__main__":
    unittest.main()
