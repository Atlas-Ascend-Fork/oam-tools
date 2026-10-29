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

import collect.coretrace.coretrace_collect as coretrace
from collect.coretrace.coretrace_collect import ParseCoreTrace
from common.task_common import get_target_cnt
from testcase.conftest import AssertTest


class TestCoreTraceTargetCount(AssertTest):
    def test_prefix_count_follows_the_coretrace_naming(self, tmp_path):
        # coretrace artefacts carry no .txt suffix: the repo data is
        # coretrace_1738757896_22994_test and coretrace.log-daemon.<pid>.<n>.
        for name in (
            "coretrace_1738757896_22994_test",
            "coretrace.log-daemon.1749023973.11",
            "atrace_0.bin",
            "notes.txt",
        ):
            (tmp_path / name).write_text("", encoding="utf-8")

        assert get_target_cnt(str(tmp_path), prefix="coretrace") == 2

    def test_run_parses_the_files_that_have_no_txt_suffix(self, tmp_path, mocker):
        # A .txt filter here skipped every coretrace file, left the result list
        # empty and made run() return False while the files sat in the output.
        for name in ("coretrace_a", "coretrace_b", "atrace_0.bin"):
            (tmp_path / name).write_text("", encoding="utf-8")

        instance = object.__new__(ParseCoreTrace)
        mocker.patch.object(ParseCoreTrace, "check_tool_exists", return_value=True)
        mocker.patch.object(ParseCoreTrace, "start_parse_file", return_value=True)
        seen = []
        mocker.patch.object(
            coretrace, "out_progress_bar", side_effect=lambda _c, n=0: seen.append(n)
        )

        assert instance.run(str(tmp_path), count=2) is True
        assert max(seen) == 2, seen
