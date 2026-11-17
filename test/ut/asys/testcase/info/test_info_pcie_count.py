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

import pytest

from info import asys_info
from testcase.conftest import AssertTest


class TestPcieCountRows(AssertTest):
    @pytest.fixture(autouse=True)
    def _table(self):
        self.table = {asys_info.PCIE_INFO: []}
        yield self.table

    def _scan(self, mocker, replies):
        queue = iter(replies)
        mocker.patch.object(
            asys_info,
            "run_command",
            side_effect=lambda _cmd, timeout=None: next(queue),
        )
        asys_info.AsysInfo._AsysInfo__get_pcie_info(self.table)
        return self.table

    def test_all_three_probes_compute_the_normal_count(self, mocker):
        # The total and (normal) probes run the very same lspci, so they can
        # only answer the same number; feeding different ones would pin a
        # shape that cannot happen on a real host.
        table = self._scan(mocker, ["4", "4", "1"])
        rows = table[asys_info.PCIE_INFO]
        self.assertTrue(
            [row[0] for row in rows]
            == [
                "PCIe Dev Count",
                "PCIe Dev Count(normal)",
                "PCIe Dev Count(abnormal)",
            ]
        )
        self.assertTrue(rows[1][1] == 3)  # total 4 - abnormal 1, not the raw lspci 4

    def test_failed_abnormal_probe_keeps_the_total_and_drops_normal(self, mocker):
        # total and (normal) are the same lspci, so (normal) can only be
        # trusted once it has been replaced by total - abnormal (#345).
        table = self._scan(mocker, ["4", "4", "N/A"])
        rows = table[asys_info.PCIE_INFO]
        self.assertTrue(rows == [["PCIe Dev Count", "4"]])

    def test_failed_first_probe_keeps_the_later_rows(self, mocker):
        table = self._scan(mocker, ["", "3", "1"])
        rows = table[asys_info.PCIE_INFO]
        # Without the total the (normal) row is still the raw lspci count, so
        # it carries no information and is dropped as well.
        self.assertTrue(rows == [["PCIe Dev Count(abnormal)", "1"]])

    def test_no_pcie_device_drops_the_section(self, mocker):
        # A real zero count still means "nothing to report".
        table = self._scan(mocker, ["0"])
        self.assertTrue(asys_info.PCIE_INFO not in table)

    def test_all_probes_failing_drops_the_section(self, mocker):
        table = self._scan(mocker, ["N/A", "N/A", "N/A"])
        self.assertTrue(asys_info.PCIE_INFO not in table)

    def test_only_the_normal_probe_answering_drops_the_section(self, mocker):
        # Filtering the (normal) row used to leave {" PCIe Info ": []} behind,
        # which rendered as an empty section header.
        table = self._scan(mocker, ["", "4", ""])
        self.assertTrue(asys_info.PCIE_INFO not in table)

    def test_total_and_abnormal_without_normal_still_shows_normal(self, mocker):
        # The normal value is computable from the other two, so a failed
        # (normal) probe must not hide it.
        table = self._scan(mocker, ["4", "N/A", "1"])
        rows = table[asys_info.PCIE_INFO]
        self.assertTrue(
            rows
            == [
                ["PCIe Dev Count", "4"],
                ["PCIe Dev Count(normal)", 3],
                ["PCIe Dev Count(abnormal)", "1"],
            ]
        )
