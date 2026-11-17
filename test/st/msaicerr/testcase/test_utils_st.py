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

from ms_interface import utils
import os
import sys
from unittest.mock import Mock

te = Mock(name="te")
te.__name__ = "te"
sys.modules["te"] = te
sys.path.append("../../../../../../../asl/devtools/msaicerr/ms_interface")

cur_abspath = os.path.dirname(__file__)


class TestUtilsMethods:
    def test_get_inquire_result_failed(self, mocker):
        mocker.patch("ms_interface.utils.execute_command", return_value=(1, ""))
        res = utils.get_inquire_result(["xxx"], "", match_dict=True)
        assert res == []

        mocker.patch("ms_interface.utils.execute_command", return_value=(0, ""))
        res = utils.get_inquire_result(["xxx"], "asfdd", match_dict=True)
        assert res == []
