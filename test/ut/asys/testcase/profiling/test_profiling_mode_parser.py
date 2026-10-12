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
from pathlib import Path
from types import SimpleNamespace

import pytest


ASYS_SRC = Path(__file__).resolve().parents[5] / "src" / "asys"
sys.path.insert(0, str(ASYS_SRC))

from profiling.asys_profiling import AsysProfiling  # noqa: E402


@pytest.mark.parametrize("run_modes", ["aicore, dvpp,", "aicore , dvpp ,"])
def test_check_param_accepts_comma_separated_modes_with_spaces(monkeypatch, run_modes):
    obj = object.__new__(AsysProfiling)
    obj.period = 10
    obj.device_id = 0
    obj.output_path = None
    obj.run_modes = run_modes
    obj.lp_mode = 0

    monkeypatch.setattr(
        "profiling.asys_profiling.AsysProfilingSupportedChip.get_supported_chip_info",
        lambda _self, _device_id: (True, "Ascend910"),
    )
    monkeypatch.setattr(
        "profiling.asys_profiling.ChipHandler.get_handler",
        lambda _self, _chip: SimpleNamespace(
            need_lp_param=lambda: False, support_dvpp=lambda: True
        ),
    )

    assert obj._check_param() is True
    assert obj.run_modes == {"aicore", "dvpp"}


@pytest.mark.parametrize("run_modes", ["", " , "])
def test_check_param_rejects_empty_modes(monkeypatch, run_modes):
    obj = object.__new__(AsysProfiling)
    obj.period = 10
    obj.device_id = 0
    obj.output_path = None
    obj.run_modes = run_modes
    obj.lp_mode = 0

    monkeypatch.setattr(
        "profiling.asys_profiling.AsysProfilingSupportedChip.get_supported_chip_info",
        lambda _self, _device_id: (True, "Ascend910"),
    )
    monkeypatch.setattr(
        "profiling.asys_profiling.ChipHandler.get_handler",
        lambda _self, _chip: SimpleNamespace(
            need_lp_param=lambda: False, support_dvpp=lambda: True
        ),
    )

    assert obj._check_param() is False
