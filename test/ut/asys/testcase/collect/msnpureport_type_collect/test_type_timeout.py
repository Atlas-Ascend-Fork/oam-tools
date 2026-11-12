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

# ruff: noqa: E501, S607  # test mock methods, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock patterns

import pytest

from collect.msnpureport_type_collect import (
    MSNPUREPORT_TYPE_TABLE,
    MSNPUREPORT_TYPE_TIMEOUTS,
    collect_msnpureport_type_info,
)
from testcase.conftest import AssertTest


def setup_module():
    print("TestMsnpureportTypeTimeout ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestMsnpureportTypeTimeout ut test finish.")  # noqa: T201  # test diagnostic output


class TestMsnpureportTypeTimeout(AssertTest):
    def test_full_export_timeout_budget_is_one_minute(self):
        # #399 拍板规格：msnpureport 全量导出(-f)超时 60s
        self.assertTrue(MSNPUREPORT_TYPE_TIMEOUTS["-f"] == 60)

    @pytest.mark.parametrize(
        "type_id, budget",
        [
            (5, 120),
            (6, 100),
            (7, 120),
            (8, 240),
            (9, 120),
            (10, 100),
            (11, 40),
        ],
    )
    def test_typed_export_budgets_match_spec(self, type_id, budget):
        # #399 拍板规格：-t5 120s / -t6 100s / -t7 120s / -t8 240s /
        # -t9 120s / -t10 100s / -t11 40s
        self.assertTrue(MSNPUREPORT_TYPE_TIMEOUTS[type_id] == budget)

    def test_typed_export_table_covers_all_timeouts(self):
        # 支持矩阵里每个 -t 命令都必须有预算，缺一个就是配置遗漏
        self.assertTrue(
            set(MSNPUREPORT_TYPE_TABLE) == set(MSNPUREPORT_TYPE_TIMEOUTS) - {"-f"}
        )

    def test_typed_export_passes_its_budget(self, mocker, tmp_path):
        # 各 -t 命令必须把自己的预算传给 run_cmd_output，超时时归入
        # 既有失败告警路径（合并一条 error，部分失败不影响整体返回）。
        seen = {}

        def fake_run_cmd_output(command, timeout=None, **_kwargs):
            seen[command] = timeout
            return True, ""

        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            side_effect=fake_run_cmd_output,
        )
        mocker.patch(
            "collect.msnpureport_type_collect._get_chip_infos",
            return_value=["Ascend950"],
        )
        mocker.patch(
            "collect.msnpureport_type_collect._archive_type_output", return_value=True
        )
        mocker.patch("collect.msnpureport_type_collect.parse_ub_in_place")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.delete_dirs")
        mocker.patch(
            "collect.msnpureport_type_collect.ParamDict.get_env_type", return_value="EP"
        )

        self.assertTrue(collect_msnpureport_type_info(str(tmp_path)) is True)
        # 950 芯片支持 -t5 到 -t11 全部命令，每条都按自己的预算下发
        self.assertTrue(len(seen) == 7)
        for command, budget in seen.items():
            self.assertTrue(command.count("msnpureport report -t") == 1)
            expected = MSNPUREPORT_TYPE_TIMEOUTS[int(command.rsplit(" -t ", 1)[-1])]
            self.assertTrue(budget == expected)
