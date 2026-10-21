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

from common.const import RetCode
from common.ascend910_93.ascend91093_handler import Ascend91093Handler
from ..conftest import AssertTest


class FakeDevice:
    """DeviceInfo stand-in for the 910_93 master-grouping logic.

    get_phyid_from_logicid / get_masterid_from_phyid fail for the logic ids
    listed in unresolvable, i.e. the situation the ERROR_DEVICE_ID sentinel
    describes.  The detection itself works and the devices listed in
    failing_devices report a genuine fault.
    """

    def __init__(self, unresolvable=(), failing_devices=(), master_map=None):
        self.unresolvable = set(unresolvable)
        self.failing_devices = set(failing_devices)
        self.master_map = master_map or {}
        self.detected = []

    def get_phyid_from_logicid(self, device_id):
        if device_id in self.unresolvable:
            return RetCode.FAILED
        return device_id

    def get_masterid_from_phyid(self, phyid):
        if phyid in self.unresolvable:
            return RetCode.FAILED
        return self.master_map.get(phyid, phyid)

    def get_ecc_isolated_page(self, device_id):
        return 0

    @property
    def ascend_ml(self):
        device = self

        class _Ml:
            @staticmethod
            def AmlHbmDetectWithType(device_id, timeout, hbm_type):
                # device_id arrives as ctypes.c_int32 -> read its .value
                dev_id = int(getattr(device_id, "value", device_id))
                device.detected.append(dev_id)
                return 1 if dev_id in device.failing_devices else 0

            @staticmethod
            def AmlCpuDetect(device_id, timeout):
                dev_id = int(getattr(device_id, "value", device_id))
                device.detected.append(dev_id)
                return 1 if dev_id in device.failing_devices else 0

        return _Ml()


class TestAscend91093Diagnose(AssertTest):
    def test_diagnose_91093_unresolved_master_id_detects_each_device(self):
        """Every device whose master id cannot be resolved is detected on its own.

        Before the fix, all such devices shared the ERROR_DEVICE_ID key, so only
        the first one was detected and the others silently reused its result.
        """
        device = FakeDevice(unresolvable={0, 1}, failing_devices={1})

        ret = Ascend91093Handler.run_diagnose(device, [0, 1], "hbm_detect")

        self.assertTrue(sorted(device.detected) == [0, 1])
        self.assertTrue(ret[0] == ["Pass", "0"])
        self.assertTrue(ret[1] == ["Warn", "0"])

    def test_diagnose_91093_unresolved_master_id_not_shared_with_resolved(self):
        """A device with an unresolved master id must not reuse another one's result."""
        device = FakeDevice(unresolvable={1}, failing_devices={1})

        ret = Ascend91093Handler.run_diagnose(device, [0, 1], "hbm_detect")

        self.assertTrue(sorted(device.detected) == [0, 1])
        self.assertTrue(ret[0] == ["Pass", "0"])
        self.assertTrue(ret[1] == ["Warn", "0"])

    def test_diagnose_91093_master_slave_pair_detected_once(self):
        """Devices sharing one master id are still detected only once."""
        # device 0 and device 1 are the two dies of one card -> one master id.
        device = FakeDevice(master_map={1: 0})

        ret = Ascend91093Handler.run_diagnose(device, [0, 1], "hbm_detect")

        self.assertTrue(sorted(device.detected) == [0])
        self.assertTrue(ret[0] == ret[1])

    def test_diagnose_91093_unresolved_master_id_cpu_detect(self):
        """The cpu_detect mode groups devices by master id the same way."""
        device = FakeDevice(unresolvable={0, 1}, failing_devices={1})

        ret = Ascend91093Handler.run_diagnose(device, [0, 1], "cpu_detect")

        self.assertTrue(sorted(device.detected) == [0, 1])
        self.assertTrue(ret[0] == "Pass")
        self.assertTrue(ret[1] == "Warn")

    @pytest.mark.parametrize(
        ["devices", "unresolvable", "expect_detected"],
        [
            ([0, 1], {0, 1}, [0, 1]),
            ([0, 1], {1}, [0, 1]),
            ([0, 1], {0}, [0, 1]),
            ([0, 1, 2], {0, 1, 2}, [0, 1, 2]),
            ([0, 1, 2], {1}, [0, 1, 2]),
        ],
    )
    def test_diagnose_91093_no_device_skipped(
        self, devices, unresolvable, expect_detected
    ):
        """No device may be skipped because of an unresolved master id."""
        device = FakeDevice(unresolvable=unresolvable)

        Ascend91093Handler.run_diagnose(device, devices, "hbm_detect")

        self.assertTrue(sorted(device.detected) == expect_detected)

    def test_diagnose_91093_unresolved_master_id_result_per_device(self):
        """Each device gets the result of its own detection."""
        device = FakeDevice(unresolvable={0, 1}, failing_devices={1})

        ret = Ascend91093Handler.run_diagnose(device, [0, 1], "hbm_detect")

        self.assertTrue(len(ret) == 2)
        self.assertTrue(ret[0] != ret[1])
        self.assertTrue(ret[0] == ["Pass", "0"])
        self.assertTrue(ret[1] == ["Warn", "0"])
