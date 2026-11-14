#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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
"""Exercise stackcore discovery against real host directories and files."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from collect.stacktrace.stacktrace_collect import AsysStackTrace
from collect.stacktrace import stacktrace_collect


class TestStackcoreFileDiscovery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="asys-stackcore-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.collector = AsysStackTrace.__new__(AsysStackTrace)
        self.collector.remote_id = 12345
        self.collector.trace_work_path = str(self.root / "atrace")

    def create_binary(self, suffix="1", trace="1", remote=12345, mtime=100):
        directory = (
            Path(self.collector.trace_work_path)
            / f"trace_{trace}"
            / f"stackcore_event_{remote}_{suffix}"
        )
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"stackcore_tracer_35_{remote}_{suffix}.bin"
        path.write_bytes(b"host filename fixture, not native stackcore data")
        os.utime(path, (mtime, mtime))
        return str(path)

    def assert_discovered(self, binary):
        self.assertEqual(self.collector._get_exists_bin_file_num(), 1)
        self.assertEqual(self.collector._get_last_bin_file_name(), binary)

    def test_plain_work_path(self):
        self.assert_discovered(self.create_binary())

    def test_work_path_with_spaces(self):
        self.collector.trace_work_path = str(self.root / "work space" / "atrace")
        self.assert_discovered(self.create_binary())

    def test_work_path_with_quote(self):
        self.collector.trace_work_path = str(self.root / "user's work" / "atrace")
        self.assert_discovered(self.create_binary())

    def test_work_path_with_literal_glob_characters(self):
        self.collector.trace_work_path = str(self.root / "work [1]" / "atrace")
        self.assert_discovered(self.create_binary())

    def test_latest_file_uses_modification_time_across_trace_directories(self):
        self.create_binary(suffix="later-name", trace="2", mtime=100)
        latest = self.create_binary(suffix="earlier-name", trace="1", mtime=200)
        self.assertEqual(self.collector._get_exists_bin_file_num(), 2)
        self.assertEqual(self.collector._get_last_bin_file_name(), latest)

    def test_two_level_layout_is_discovered(self):
        # In-repo UT/ST fixtures drop the file right under trace_* without the
        # stackcore_event level; arbitrary-depth matching must keep finding it.
        directory = Path(self.collector.trace_work_path) / "trace_17965_17965_1"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "stackcore_tracer_35_12345_2024.bin"
        path.write_bytes(b"host filename fixture, not native stackcore data")
        os.utime(path, (100, 100))
        self.assert_discovered(str(path))

    def test_other_remote_process_is_not_counted(self):
        self.create_binary(remote=45678)
        self.assert_discovered(self.create_binary())

    def test_unrelated_filename_is_not_counted(self):
        binary = self.create_binary()
        (Path(binary).parent / "stackcore_tracer_35_12345_extra.txt").write_text(
            "not a binary", encoding="utf-8"
        )
        self.assert_discovered(binary)

    def test_matching_directory_is_not_a_binary(self):
        binary = self.create_binary()
        (Path(binary).parent / "stackcore_tracer_35_12345_directory.bin").mkdir()
        self.assert_discovered(binary)

    def test_missing_work_directory(self):
        self.assertEqual(self.collector._get_exists_bin_file_num(), 0)
        self.assertEqual(self.collector._get_last_bin_file_name(), "")

    def test_empty_work_directory(self):
        Path(self.collector.trace_work_path).mkdir()
        self.assertEqual(self.collector._get_exists_bin_file_num(), 0)
        self.assertEqual(self.collector._get_last_bin_file_name(), "")

    def assert_wait_finds_binary(self):
        self.collector.timeout = 2
        binary = self.create_binary()
        original_run = stacktrace_collect.run_cmd_list

        def run_command(command, **kwargs):
            if command == ["lsof", binary]:
                return (False, "")
            return original_run(command, **kwargs)

        with patch(
            "collect.stacktrace.stacktrace_collect.run_cmd_list",
            side_effect=run_command,
        ) as command:
            with patch("collect.stacktrace.stacktrace_collect.time.sleep"):
                self.assertEqual(self.collector._wait_bin_file_generate(0), binary)
        args, kwargs = command.call_args
        self.assertEqual(kwargs["timeout"], 5)
        self.assertEqual(args[0], ["lsof", binary])

    def test_wait_preserves_complete_filename_for_open_file_check(self):
        self.collector.trace_work_path = str(self.root / "work space" / "atrace")
        self.assert_wait_finds_binary()

    def test_wait_plain_directory_control(self):
        self.assert_wait_finds_binary()
