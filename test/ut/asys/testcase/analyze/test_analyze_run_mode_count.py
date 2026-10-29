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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import os
import shutil
from argparse import Namespace

from testcase.conftest import test_trace_tmp, ut_root_path

from analyze import AsysAnalyze
from common.task_common import create_out_timestamp_dir
from params import ParamDict
from ..conftest import AssertTest


class TestAnalyzeRunModeCount(AssertTest):
    """The progress denominator has to match the naming of each run mode.

    A .txt filter counted every coretrace artefact as 0, so the bar vanished;
    a .bin filter did the same for stackcore. These cases pin the count that
    each run mode hands to the parser, so the three-way branch cannot be
    collapsed back to a single suffix without turning a case red.
    """

    @staticmethod
    def setup_method():
        if os.path.exists(test_trace_tmp):
            shutil.rmtree(test_trace_tmp)
        os.mkdir(test_trace_tmp)
        ParamDict.clear()

    @staticmethod
    def teardown_method():
        ParamDict.clear()
        if os.path.exists(test_trace_tmp):
            os.chmod(test_trace_tmp, 0o777)  # nosec B103  # test asserts permission-mask behavior
            shutil.rmtree(test_trace_tmp)

    @staticmethod
    def _args(run_mode, path):
        return Namespace(
            subparser_name="analyze",
            r=run_mode,
            path=path,
            file=None,
            exe_file=None,
            core_file=None,
            symbol=None,
            symbol_path=ut_root_path,
            reg=0,
            d=0,
            output=test_trace_tmp,
        )

    def test_coretrace_count_follows_the_coretrace_prefix(self, mocker, tmp_path):
        # The coretrace artefacts carry no .txt suffix, so a .txt denominator
        # counted 0 and the progress bar disappeared for the whole run.
        for name in (
            "coretrace_1738757896_22994_test",
            "coretrace.log-daemon.1749023973.11",
            "notes.txt",
        ):
            (tmp_path / name).write_text("", encoding="utf-8")

        ParamDict().set_args(self._args("coretrace", str(tmp_path)))
        create_out_timestamp_dir()

        seen = {}

        class FakeParse:
            def __init__(self, *_args, **_kwargs):
                pass

            def run(self, _output, count=0):
                seen["count"] = count
                return True

        mocker.patch("analyze.asys_analyze.ParseCoreTrace", FakeParse)
        assert AsysAnalyze().run() is True
        assert seen["count"] == 2, seen

    def test_stackcore_count_follows_the_txt_suffix(self, mocker, tmp_path):
        # The stackcore artefacts are stackcore_*.txt, so the denominator has
        # to follow the .txt suffix.
        for name in (
            "stackcore_tracer_atrace_test_40945_1716517732910.txt",
            "stackcore_tracer_6_570350_atrace_test_20241010031221412850.txt",
            "notes.log",
        ):
            (tmp_path / name).write_text("", encoding="utf-8")

        ParamDict().set_args(self._args("stackcore", str(tmp_path)))
        create_out_timestamp_dir()

        seen = {}

        class FakeParse:
            def __init__(self, *_args, **_kwargs):
                pass

            def run(self, _output, count=0):
                seen["count"] = count
                return True

        mocker.patch("analyze.asys_analyze.ParseStackCore", FakeParse)
        assert AsysAnalyze().run() is True
        assert seen["count"] == 2, seen

    def test_trace_count_follows_the_bin_suffix(self, mocker, tmp_path):
        for name in ("atrace_0.bin", "atrace_1.bin", "notes.txt"):
            (tmp_path / name).write_text("", encoding="utf-8")

        ParamDict().set_args(self._args("trace", str(tmp_path)))
        create_out_timestamp_dir()

        seen = {}

        class FakeParse:
            def __init__(self, *_args, **_kwargs):
                pass

            def run(self, _output, count=0):
                seen["count"] = count
                return True

        mocker.patch("analyze.asys_analyze.ParseTrace", FakeParse)
        assert AsysAnalyze().run() is True
        assert seen["count"] == 2, seen
