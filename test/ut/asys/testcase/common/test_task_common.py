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

import os
import time

import pytest

from common.task_common import get_target_cnt, timeout_decorator
from testcase.conftest import AssertTest


class TestTaskCommon(AssertTest):
    def test_target_count_ignores_non_bin_artefacts(self, tmp_path):
        # The trace collector only parses .bin, so the progress denominator
        # must not grow with the log/txt artefacts sitting next to them.
        for name in ("a.bin", "b.bin", "notes.txt", "trace.log"):
            (tmp_path / name).write_text("", encoding="utf-8")

        assert get_target_cnt(str(tmp_path)) == 2

    def test_target_count_follows_the_suffix(self, tmp_path):
        # stackcore keeps .txt while coretrace keeps the bare coretrace* name,
        # so a hard-coded .bin filter made their denominator 0 and the
        # progress bar disappeared entirely.
        for name in ("a.bin", "b.bin", "c.txt"):
            (tmp_path / name).write_text("", encoding="utf-8")

        assert get_target_cnt(str(tmp_path), ".bin") == 2
        assert get_target_cnt(str(tmp_path), ".txt") == 1

    def test_target_count_follows_the_prefix(self, tmp_path):
        # The coretrace artefacts carry no .txt suffix, so they can only be
        # counted by their name prefix.
        for name in ("coretrace_1738757896_22994_test", "notes.txt"):
            (tmp_path / name).write_text("", encoding="utf-8")

        assert get_target_cnt(str(tmp_path), prefix="coretrace") == 1
        assert get_target_cnt(str(tmp_path), ".txt") == 1

    def test_target_count_of_an_empty_tree_is_zero(self, tmp_path):
        assert get_target_cnt(str(tmp_path)) == 0

    @pytest.mark.skipif(os.name != "posix", reason="timeout worker uses fork")
    def test_timeout_worker_failure_reaches_the_caller(self):
        # The callable runs in a child process, so its exception cannot travel
        # back by itself; a silent None used to be indistinguishable from
        # success and asys collect reported a clean run with missing sections.
        @timeout_decorator(5, raise_on_error=True)
        def boom():
            raise RuntimeError("inner failure")

        with pytest.raises(ChildProcessError):
            boom()

    @pytest.mark.skipif(os.name != "posix", reason="timeout worker uses fork")
    def test_worker_failure_stays_silent_by_default(self):
        # Compatibility: the decorator keeps its old contract unless the caller
        # opts in, because device-dependent ST cases rely on it.
        @timeout_decorator(5)
        def boom():
            raise RuntimeError("inner failure")

        assert boom() is None

    @pytest.mark.skipif(os.name != "posix", reason="timeout worker uses fork")
    def test_timeout_worker_success_returns_none(self, tmp_path):
        # The callable runs in a child process, so it reports through the
        # filesystem rather than through memory.
        marker = tmp_path / "ran"

        @timeout_decorator(5)
        def okay():
            marker.write_text("1", encoding="utf-8")

        assert okay() is None
        assert marker.exists()

    @pytest.mark.skipif(os.name != "posix", reason="timeout worker uses fork")
    def test_timeout_worker_still_reports_a_timeout(self):
        @timeout_decorator(0.2)
        def slow():
            time.sleep(5)

        with pytest.raises(TimeoutError):
            slow()
