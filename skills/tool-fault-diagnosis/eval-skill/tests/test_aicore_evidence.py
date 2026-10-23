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
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_aicore_evidence.py"


class AicoreEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Read-only AI Core evidence extractor is missing")
        spec = importlib.util.spec_from_file_location("aicore_evidence", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_exact_hash_and_task_fields_remain_strings(self):
        fields = self.module.extract_fields(
            "[DFX_INFO]AI Core kernel execution failed, device_id=0, stream_id=47, "
            "task_id=0, fault kernel_name=_Z6kernelPf, hash=18446744073709551615.")
        self.assertEqual(fields, {
            "device_id": "0", "stream_id": "47", "task_id": "0",
            "kernel_name": "_Z6kernelPf", "kernel_hash": "18446744073709551615"})

    def test_parameter_block_and_argument_values_are_distinct(self):
        fields = self.module.extract_fields(
            "para base: 0x120000; args(0 to 2) after execute:0x1000, 0x2000, 0x3000.")
        self.assertEqual(fields["parameter_block_address"], "0x120000")
        self.assertEqual(fields["arguments"], {
            "phase": "after", "first_index": "0", "last_index": "2",
            "values": ["0x1000", "0x2000", "0x3000"]})
        self.assertNotIn("valid", fields)
        self.assertNotIn("total_tasks", fields)

    def test_kernel_name_keeps_spaces_and_other_fields_independent(self):
        fields = self.module.extract_fields(
            "device_id=2, stream_id=7, task_id=9, "
            "fault kernel_name=ExampleKernel FP16 FP32 high_performance, "
            "fault kernel info=none, program_id=6, hash=123456789.")
        self.assertEqual(fields, {
            "device_id": "2", "stream_id": "7", "task_id": "9",
            "kernel_name": "ExampleKernel FP16 FP32 high_performance",
            "kernel_hash": "123456789"})

    def test_repeated_kernel_names_keep_each_complete_value(self):
        fields = self.module.extract_fields(
            "fault kernel_name=FirstKernel FP16 FP32, hash=11, "
            "fault kernel_name=SecondKernel BF16, hash=22")
        self.assertEqual(fields["kernel_name"],
                         ["FirstKernel FP16 FP32", "SecondKernel BF16"])
        self.assertEqual(fields["kernel_hash"], ["11", "22"])

    def test_empty_kernel_name_does_not_capture_another_field_or_line(self):
        for text in ("fault kernel_name= , hash=123",
                     "fault kernel_name=\n hash=123"):
            with self.subTest(text=text):
                fields = self.module.extract_fields(text)
                self.assertNotIn("kernel_name", fields)
                self.assertNotIn("kernel_hash", fields)

    def test_scan_keeps_kernel_whitespace_and_raw_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            text = "fault kernel_name=ExampleKernel FP16\tFP32, hash=123"
            path.write_text(text + "\n")
            result = self.module.scan_logs(path)
            self.assertEqual(result["status"], "complete")
            observation = result["observations"][0]
            self.assertEqual(observation["raw"], text)
            self.assertEqual(observation["fields"]["kernel_name"],
                             "ExampleKernel FP16\tFP32")
            self.assertEqual(observation["fields"]["kernel_hash"], "123")

    def test_error_text_does_not_decode_other_registers(self):
        fields = self.module.extract_fields(
            "The extend info: errcode:(0, 0x20, 0) errorStr: scalar internal buffer "
            "out of bounds. fixp_error0 info: 0x18, subErrType:4.")
        self.assertEqual(fields["error_str"], "scalar internal buffer out of bounds.")
        self.assertNotIn("buffer_kind", fields)
        self.assertNotIn("fixp_fault", fields)
        self.assertEqual(self.module.extract_fields("malloc succeeded; task queue closed"), {})

    def test_error_codes_and_info_values_are_separate_literal_fields(self):
        fields = self.module.extract_fields(
            "error code = 0, mte error info: 0x123456789abcdef0, "
            "vec error info: 0, fixp_error0 info: 0x1234, "
            "MTE errorCode=0, cube error info: 0x20")
        self.assertEqual(fields["error_code"], "0")
        self.assertEqual(fields["mte_error_info"], "0x123456789abcdef0")
        self.assertEqual(fields["mte_error_code"], "0")
        self.assertEqual(fields["vec_error_info"], "0")
        self.assertEqual(fields["fixp_error0_info"], "0x1234")
        self.assertEqual(fields["cube_error_info"], "0x20")
        self.assertNotIn("fault_unit", fields)
        self.assertNotIn("hardware_excluded", fields)

    def test_compound_header_error_code_is_not_reduced_to_first_number(self):
        for value in ("11, 19", "0x2, 0x8", "11,19, 23"):
            with self.subTest(value=value):
                fields = self.module.extract_fields(
                    "error code = " + value + ", dump info: pc start: 0x1000")
                self.assertEqual(fields["error_code"], value)
        self.assertEqual(self.module.extract_fields(
            "error code = 11, dump info: pc start: 0x1000")["error_code"], "11")

    def test_unsupported_numeric_suffix_does_not_publish_a_shortened_signature(self):
        for value in ("11, -19", "11, +19", "11, + 19", "11, -0x2",
                      "11, 0xGG", "11, 19oops", "11, 19.5"):
            with self.subTest(value=value):
                fields = self.module.extract_fields(
                    "error code = " + value + ", dump info: pc start: 0x1000")
                self.assertNotIn("error_code", fields)

    def test_summary_scans_past_observation_cap_and_preserves_full_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            first = "The extend info: errcode:(11) errorStr: first failure."
            last = ("The extend info: errcode:(11, 19) errorStr: second failure. "
                    "Additional constraint. subErrType:4.")
            path.write_text(first + "\n" + "normal progress\n" * 20 + last + "\n")
            result = self.module.scan_logs(path, max_observations=1, summary=True)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["files"][0]["bytes_read"], path.stat().st_size)
            self.assertEqual(result["summary"]["matching_lines"], 2)
            groups = result["summary"]["groups"]
            self.assertEqual(len(groups), 2)
            self.assertEqual(groups[1]["fields"]["errcode"], "(11, 19)")
            self.assertEqual(groups[1]["fields"]["error_str"],
                             "second failure. Additional constraint. subErrType:4.")
            self.assertEqual(groups[1]["first"]["line"], 22)
            self.assertEqual(groups[1]["first"]["raw"], last)
            self.assertNotIn("observations", result)

    def test_summary_counts_printed_lines_per_source_without_joining_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lines = ("task_id=2, error code = 11, pc start: 0x1000, current: 0x1010\n"
                     "progress\n"
                     "task_id=9, error code = 11, pc start: 0x2000, current: 0x2020\n")
            (root / "a.log").write_text(lines)
            (root / "b.log").write_text(lines)
            result = self.module.scan_logs(root, summary=True)
            groups = result["summary"]["groups"]
            self.assertEqual(result["summary"]["matching_lines"], 4)
            self.assertEqual(len(groups), 2)
            for group, source in zip(groups, ("a.log", "b.log")):
                self.assertEqual(group["source"], source)
                self.assertEqual(group["count"], 2)
                self.assertEqual(group["fields"], {"error_code": "11"})
                self.assertEqual(group["first"]["line"], 1)
                self.assertEqual(group["last"]["line"], 3)
                self.assertEqual(group["first"]["fields"]["task_id"], "2")
                self.assertEqual(group["last"]["fields"]["task_id"], "9")
                self.assertEqual(group["first"]["calculations"]["pc_offset_bytes"][
                    "value_hex"], "0x10")
                self.assertEqual(group["last"]["calculations"]["pc_offset_bytes"][
                    "value_hex"], "0x20")
                self.assertNotIn("task_count", group)

    def test_summary_group_overflow_keeps_scanning_and_reports_omissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            path.write_text("error code = 11\nerror code = 19\nerror code = 11\n")
            result = self.module.scan_logs(path, summary=True, max_summary_groups=1)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["files"][0]["status"], "complete")
            self.assertEqual(result["files"][0]["bytes_read"], path.stat().st_size)
            self.assertEqual(result["summary"]["matching_lines"], 3)
            self.assertEqual(result["summary"]["omitted_observations"], 1)
            self.assertEqual(result["summary"]["groups"][0]["count"], 2)
            self.assertEqual(result["summary"]["groups"][0]["last"]["line"], 3)

    def test_summary_byte_limit_is_not_mistaken_for_complete_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            first = "errcode:(11) errorStr: first.\n"
            path.write_text(first + "errcode:(19) errorStr: second.\n")
            result = self.module.scan_logs(path, summary=True,
                                           max_file_bytes=len(first.encode()))
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["files"][0]["status"], "truncated")
            self.assertEqual(result["summary"]["matching_lines"], 1)

    def test_summary_cli_emits_valid_json_and_rejects_nonpositive_group_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            path.write_text("error code = 11, 19\n")
            command = ["python3", str(SCRIPT), "--input", str(path), "--summary"]
            result = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["summary"]["groups"][0][
                "fields"]["error_code"], "11, 19")
            invalid = subprocess.run(command + ["--max-summary-groups", "0"],
                                     text=True, capture_output=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(invalid.stdout, "")

    def test_pc_difference_is_computed_only_for_unambiguous_same_line_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            path.write_text(
                "pc start: 0x100000000000, current: 0x100000000014\n"
                "pc start: 0x2000, current: 0x1ff0\n"
                "pc start: 0x2000, current: 0x2000\n"
                "pc start: 0x1000, pc start: 0x2000, current: 0x2010\n"
                "pc start: 0x3000\ncurrent: 0x3020\n")
            observations = self.module.scan_logs(path)["observations"]
            for index, decimal, hexadecimal in ((0, "20", "0x14"),
                                                 (1, "-16", "-0x10"), (2, "0", "0x0")):
                with self.subTest(index=index):
                    calculation = observations[index]["calculations"]["pc_offset_bytes"]
                    self.assertEqual(calculation["value_decimal"], decimal)
                    self.assertEqual(calculation["value_hex"], hexadecimal)
                    self.assertEqual(calculation["operands"], {
                        "pc_current": observations[index]["fields"]["pc_current"],
                        "pc_start": observations[index]["fields"]["pc_start"]})
                    self.assertEqual(calculation["operation"], "subtract")
                    self.assertEqual(calculation["unit"], "bytes")
                    self.assertEqual(observations[index]["line"], index + 1)
            self.assertNotIn("calculations", observations[3])
            self.assertNotIn("calculations", observations[4])
            self.assertEqual(len(observations), 5)

    def test_oversized_pc_is_preserved_without_unbounded_integer_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            value = "0x" + "f" * 5000
            path.write_text("pc start: 0x1000, current: " + value + "\n")
            observation = self.module.scan_logs(path)["observations"][0]
            self.assertEqual(observation["fields"]["pc_current"], value)
            self.assertNotIn("calculations", observation)

    def test_malformed_duplicate_pc_labels_do_not_become_unique_operands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            for text in (
                    "pc start: 0x1000, current: 0x1010, current: 0xGG",
                    "pc start: 0x1000, pc start: 0xGG, current: 0x1010"):
                with self.subTest(text=text):
                    path.write_text(text + "\n")
                    observation = self.module.scan_logs(path)["observations"][0]
                    self.assertEqual(observation["raw"], text)
                    self.assertNotIn("calculations", observation)

    def test_unrelated_current_value_on_a_pc_line_is_not_a_pc_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            path.write_text("pc start: 0x1000, allocator current: 0x1010\n")
            observation = self.module.scan_logs(path)["observations"][0]
            self.assertEqual(observation["fields"], {"pc_start": "0x1000"})
            self.assertNotIn("calculations", observation)

    def test_observations_are_not_joined_or_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = ("[AIC_INFO] args(0 to 0) before execute:0x1000.\n"
                    "[AIC_INFO] args(0 to 0) after execute:0x2000.\n"
                    "[DFX_INFO]fault kernel_name=kernel, task_id=0, hash=12345678901234567890\n")
            (root / "plog.log").write_text(text)
            (root / "screen.log").write_text(text)
            result = self.module.scan_logs(root)
            self.assertEqual(result["status"], "complete")
            observations = result["observations"]
            self.assertEqual(len(observations), 6)
            self.assertEqual({row["source"] for row in observations}, {"plog.log", "screen.log"})
            first = observations[0]
            self.assertEqual(first["line"], 1)
            self.assertEqual(first["raw"], text.splitlines()[0])
            self.assertNotIn("task_id", first["fields"])
            self.assertNotIn("arguments", observations[2]["fields"])

    def test_cap_does_not_publish_a_truncated_line_as_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plog.log"
            first = b"task_id=0\n"
            path.write_bytes(first + b"fault kernel_name=other, hash=123456789\n")
            result = self.module.scan_logs(path, max_file_bytes=len(first) + 4)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(len(result["observations"]), 1)
            self.assertEqual(result["files"][0]["status"], "truncated")
            self.assertEqual(result["files"][0]["bytes_read"], len(first) + 4)
            self.assertEqual(result["observations"][0]["fields"], {"task_id": "0"})

    def test_invalid_text_and_symlink_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "logs"
            logs.mkdir()
            (logs / "bad.log").write_bytes(b"task_id=0\n\xffinvalid\n")
            external = root / "external.log"
            external.write_text("fault kernel_name=secret\n")
            (logs / "link.log").symlink_to(external)
            result = self.module.scan_logs(logs)
            self.assertEqual(result["status"], "partial")
            self.assertEqual({row["status"] for row in result["files"]},
                             {"decode_error", "symlink_skipped"})
            self.assertEqual(len(result["observations"]), 1)
            self.assertNotIn("secret", json.dumps(result))

    def test_directory_read_failure_is_not_silently_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plog.log").write_text("task_id=0\n")
            walk = self.module.os.walk

            def partial_walk(path, **kwargs):
                yield from walk(path, **kwargs)
                if kwargs.get("onerror"):
                    error = PermissionError("unreadable directory")
                    error.filename = str(root / "hidden")
                    kwargs["onerror"](error)

            with patch.object(self.module.os, "walk", partial_walk):
                result = self.module.scan_logs(root)
            self.assertEqual(result["status"], "partial")
            self.assertTrue(any(row["source"] == "hidden" and row["status"] == "read_error"
                                for row in result["files"]))

    def test_total_budget_reports_unread_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b"task_id=0\n"
            (root / "a.log").write_bytes(data)
            (root / "b.log").write_bytes(data)
            result = self.module.scan_logs(root, max_total_bytes=len(data))
            self.assertEqual(result["status"], "partial")
            self.assertEqual(sum(row["bytes_read"] for row in result["files"]), len(data))
            self.assertEqual(result["files"][1]["status"], "budget_skipped")
            self.assertEqual(len(result["observations"]), 1)

    def test_repeated_fields_and_argument_phases_are_preserved(self):
        fields = self.module.extract_fields(
            "task_id=1, task_id=2; args(0 to 0) before execute:0x1000; "
            "args(0 to 0) after execute:0x2000.")
        self.assertEqual(fields["task_id"], ["1", "2"])
        self.assertEqual([row["phase"] for row in fields["arguments"]], ["before", "after"])
        self.assertEqual([row["values"] for row in fields["arguments"]], [["0x1000"], ["0x2000"]])

    def test_malformed_numbers_are_not_published_as_shorter_values(self):
        for text in ("task_id=12oops", "task_id=12.5", "tilingKey=0xZZ", "pc start:0x12wrong",
                     "args(0 to 1) before execute:0x1000, 0xGG"):
            with self.subTest(text=text):
                self.assertEqual(self.module.extract_fields(text), {})

    def test_unscoped_fields_are_not_relabelled_as_kernel_or_pc(self):
        fields = self.module.extract_fields("allocator current:0x1234, hash=123")
        self.assertNotIn("pc_current", fields)
        self.assertNotIn("kernel_hash", fields)

    def test_observation_limit_reports_remaining_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.log").write_text("task_id=0\ntask_id=1\ntask_id=2\n")
            (root / "b.log").write_text("task_id=3\n")
            result = self.module.scan_logs(root, max_observations=1)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(len(result["observations"]), 1)
            self.assertEqual([row["status"] for row in result["files"]],
                             ["observation_limit", "observation_limit"])
            self.assertEqual(result["files"][1]["bytes_read"], 0)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires no-follow file open")
    def test_leaf_symlink_replacement_is_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "logs"
            logs.mkdir()
            path = logs / "a.log"
            path.write_text("task_id=1\n")
            external = root / "external.log"
            external.write_text("task_id=2\n")
            real_open = self.module.os.open

            def replace_then_open(candidate, flags, *args, **kwargs):
                path.unlink()
                path.symlink_to(external)
                return real_open(candidate, flags, *args, **kwargs)

            with patch.object(self.module.os, "open", replace_then_open):
                result = self.module.scan_logs(logs)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["observations"], [])

    def test_file_limit_reports_unscanned_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.log").write_text("task_id=0\n")
            (root / "b.log").write_text("task_id=1\n")
            result = self.module.scan_logs(root, max_files=1)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(len(result["observations"]), 1)
            self.assertEqual(result["files"][-1]["status"], "file_limit")

    def test_unreadable_directories_share_the_file_record_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def failed_walk(path, **kwargs):
                for index in range(5):
                    error = PermissionError("unreadable directory")
                    error.filename = str(root / str(index))
                    kwargs["onerror"](error)
                return iter(())

            with patch.object(self.module.os, "walk", failed_walk):
                result = self.module.scan_logs(root, max_files=2)
            self.assertEqual(result["status"], "partial")
            self.assertEqual([row["status"] for row in result["files"]],
                             ["read_error", "read_error", "file_limit"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFO support")
    def test_nonregular_input_is_explicit_without_opening_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipe"
            os.mkfifo(path)
            result = self.module.scan_logs(path)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["files"],
                             [{"source": "pipe", "status": "unsupported", "bytes_read": 0}])

    def test_cli_only_prints_json_and_keeps_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "plog.log"
            data = b"fault kernel_name=kernel, hash=18446744073709551615\n"
            path.write_bytes(data)
            result = subprocess.run(["python3", str(SCRIPT), str(root)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["observations"][0]["fields"]["kernel_hash"],
                             "18446744073709551615")
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(list(root.iterdir()), [path])

    def test_cli_accepts_repo_input_flag_and_compacts_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "plog.log"
            path.write_text("task_id=0\n")
            result = subprocess.run(["python3", str(SCRIPT), "--input", str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout.splitlines()), 1)
            self.assertEqual(json.loads(result.stdout)["observations"][0]["fields"], {"task_id": "0"})
            conflict = subprocess.run(["python3", str(SCRIPT), str(path), "--input", str(path)],
                                      capture_output=True, text=True)
            self.assertNotEqual(conflict.returncode, 0)
            self.assertEqual(conflict.stdout, "")

    def test_cli_rejects_repeated_input_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.log"
            second = root / "second.log"
            first.write_text("task_id=1\n")
            second.write_text("task_id=2\n")
            result = subprocess.run(["python3", str(SCRIPT), "--input", str(first),
                                     "--input", str(second)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
