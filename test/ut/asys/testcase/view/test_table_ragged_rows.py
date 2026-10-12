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

import sys

from testcase.conftest import ASYS_SRC_PATH

sys.path.insert(0, ASYS_SRC_PATH)

from view.table import generate_report  # noqa: E402


def test_generate_report_pads_short_rows_instead_of_index_error():
    report = generate_report(
        [["FIELD", "VALUE"]],
        {"none": [["missing-value"], ["status", "ok", "extra"]]},
    )

    assert "missing-value" in report
    assert "status" in report
    assert "extra" in report
    data_lines = [
        line
        for line in report.splitlines()
        if any(value in line for value in ("missing-value", "status", "extra"))
    ]
    assert len({len(line) for line in data_lines}) == 1
    assert all(line.count("|") == 4 for line in data_lines)
