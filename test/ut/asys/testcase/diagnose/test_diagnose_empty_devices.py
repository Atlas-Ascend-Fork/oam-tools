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

import logging

from common import close_log, open_log
from common.const import UNKNOWN
from diagnose.asys_diagnose import AsysDiagnose
from testcase.conftest import AssertTest


class _Recorder(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


class TestDiagnoseWithoutDevices(AssertTest):
    def teardown_method(self):
        open_log()

    def test_hbm_table_without_devices_is_one_row(self):
        # devices_ret and devices_ecc are both empty here, so the old code
        # produced a trailing "()" row out of the empty error-code list.
        rows = AsysDiagnose._AsysDiagnose__get_hbm_table_data(False, {})
        assert rows == [["HBM Detect", UNKNOWN]], rows

    def test_other_table_without_devices(self):
        assert AsysDiagnose._AsysDiagnose__get_other_table_data(False, {}) == UNKNOWN

    def test_the_warning_survives_close_log(self):
        # asys diagnose runs close_log() first, and that disables WARNING, so
        # a plain log_warning leaves no trace in the shipped tool. The
        # warning only has to be raised once, and force=True is what keeps it
        # visible there.
        recorder = _Recorder()
        root = logging.getLogger()
        root.addHandler(recorder)
        try:
            close_log()
            AsysDiagnose._AsysDiagnose__get_hbm_table_data(False, {})
        finally:
            root.removeHandler(recorder)

        assert any("No device responded" in msg for msg in recorder.records), (
            recorder.records
        )
