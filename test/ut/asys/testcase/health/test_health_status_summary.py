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

from health.asys_health import AsysHealth
from params import ParamDict
from testcase.conftest import AssertTest


def _ret(*statuses):
    """The shape run_health_check produces: ret[device_id] = [status, err_list]."""
    return {index: [status, []] for index, status in enumerate(statuses)}


class _Args:
    subparser_name = "health"
    d = None


class TestHealthStatusSummary(AssertTest):
    def test_healthy_devices_report_healthy(self):
        assert AsysHealth._get_highest_status(_ret("Healthy", "Healthy")) == "Healthy"

    def test_critical_outranks_healthy(self):
        assert AsysHealth._get_highest_status(_ret("Healthy", "Critical")) == "Critical"

    def test_alarm_outranks_warning(self):
        assert AsysHealth._get_highest_status(_ret("Warning", "Alarm")) == "Alarm"

    def test_unknown_outranks_everything(self):
        assert AsysHealth._get_highest_status(_ret("Critical", "Unknown")) == "Unknown"

    def test_short_entry_degrades_instead_of_raising(self):
        # Defensive only: the real path always fills [status, err_info].
        ret = _ret("Healthy")
        ret[1] = []
        assert AsysHealth._get_highest_status(ret) == "Healthy"

    def test_malformed_entry_degrades_instead_of_raising(self):
        ret = _ret("Healthy")
        ret[1] = None
        assert AsysHealth._get_highest_status(ret) == "Healthy"

    def test_non_string_status_degrades_instead_of_raising(self):
        # The status slot is a string in the real shape. The guard keeps a
        # malformed entry out of the comparison list, so a later change to
        # the comparison itself cannot start raising on it.
        ret = _ret("Healthy")
        ret[1] = [123, []]
        assert AsysHealth._get_highest_status(ret) == "Healthy"

    def test_run_reports_the_overall_health_on_screen(self, mocker, capsys):
        # End to end through run(): the screen is what the user reads, and a
        # change that turns every status into "" would still leave the
        # unit level cases above green.
        mocker.patch("health.asys_health.DeviceInfo.get_device_count", return_value=2)
        mocker.patch(
            "health.asys_health.DeviceInfo.get_device_health",
            side_effect=["Healthy", "Critical"],
        )
        mocker.patch(
            "health.asys_health.DeviceInfo.get_device_errorcode", return_value=[]
        )
        ParamDict.clear()
        ParamDict().set_env_type("EP")
        ParamDict().set_args(_Args())

        assert AsysHealth().run() is True

        printed = capsys.readouterr().out
        assert "Overall Health: Critical" in printed, printed
        ParamDict.clear()
