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

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)

from ms_interface.single_op_test_frame.runtime.rts_info import (
    RT_DEV_BINARY_MAGIC_PLAIN,
    RT_DEV_BINARY_MAGIC_PLAIN_AICPU,
    RT_DEV_BINARY_MAGIC_PLAIN_AIVEC,
    RT_DEV_BINARY_MAGIC_ELF,
    RT_DEV_BINARY_MAGIC_ELF_AICPU,
    RT_DEV_BINARY_MAGIC_ELF_AIVEC,
    RT_DEV_BINARY_MAGIC_ELF_AICUBE,
    MAGIC_MAP,
    RT_MEMORY_TYPE,
    RT_MODULE_TYPE,
    RT_INFO_TYPE,
    RT_MEMORY_POLICY,
    RT_MEMCPY_KIND,
    MEMORY_INFO_TYPE,
    RT_CONTEXT_MODE,
    RT_KERNEL_FLAGS,
    RT_FUNC_MODE_DICT,
    RT_ENV_TYPE,
    RT_ERROR_TYPE_DICT,
    RT_ERROR_CODE_DICT,
    RT_ERROR_NONE,
    ACL_RT_SUCCESS,
    ACL_ERROR_RT_PARAM_INVALID,
    ACL_ERROR_RT_FEATURE_NOT_SUPPORT,
)


class TestRtsInfoMethods(CommonAssert):
    def test_rt_dev_binary_magic_plain_value(self):
        self.assertEqual(RT_DEV_BINARY_MAGIC_PLAIN, 0xABCEED50)

    def test_rt_dev_binary_magic_plain_aicpu_value(self):
        self.assertEqual(RT_DEV_BINARY_MAGIC_PLAIN_AICPU, 0xABCEED51)

    def test_rt_dev_binary_magic_plain_aivec_value(self):
        self.assertEqual(RT_DEV_BINARY_MAGIC_PLAIN_AIVEC, 0xABCEED52)

    def test_rt_dev_binary_magic_elf_value(self):
        self.assertEqual(RT_DEV_BINARY_MAGIC_ELF, 0x43554245)

    def test_rt_dev_binary_magic_elf_aicpu_value(self):
        self.assertEqual(RT_DEV_BINARY_MAGIC_ELF_AICPU, 0x41415243)

    def test_rt_dev_binary_magic_elf_aivec_value(self):
        self.assertEqual(RT_DEV_BINARY_MAGIC_ELF_AIVEC, 0x41415246)

    def test_rt_dev_binary_magic_elf_aicube_value(self):
        self.assertEqual(RT_DEV_BINARY_MAGIC_ELF_AICUBE, 0x41494343)

    def test_magic_map_contains_all_keys(self):
        expected_keys = [
            "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
            "RT_DEV_BINARY_MAGIC_ELF_AIVECTOR",
            "RT_DEV_BINARY_MAGIC_ELF",
            "RT_DEV_BINARY_MAGIC_ELF_AICPU",
            "RT_DEV_BINARY_MAGIC_PLAIN_AIVEC",
            "RT_DEV_BINARY_MAGIC_PLAIN_AICPU",
            "RT_DEV_BINARY_MAGIC_PLAIN",
            "RT_DEV_BINARY_MAGIC_ELF_AICUBE",
        ]
        for key in expected_keys:
            self.assertIn(MAGIC_MAP, key)

    def test_magic_map_maps_correctly(self):
        self.assertEqual(
            MAGIC_MAP["RT_DEV_BINARY_MAGIC_ELF_AIVEC"], RT_DEV_BINARY_MAGIC_ELF_AIVEC
        )
        self.assertEqual(
            MAGIC_MAP["RT_DEV_BINARY_MAGIC_ELF_AIVECTOR"], RT_DEV_BINARY_MAGIC_ELF_AIVEC
        )
        self.assertEqual(MAGIC_MAP["RT_DEV_BINARY_MAGIC_ELF"], RT_DEV_BINARY_MAGIC_ELF)
        self.assertEqual(
            MAGIC_MAP["RT_DEV_BINARY_MAGIC_ELF_AICPU"], RT_DEV_BINARY_MAGIC_ELF_AICPU
        )
        self.assertEqual(
            MAGIC_MAP["RT_DEV_BINARY_MAGIC_PLAIN"], RT_DEV_BINARY_MAGIC_PLAIN
        )

    def test_rt_memory_type_contains_expected_keys(self):
        self.assertIn(RT_MEMORY_TYPE, "RT_MEMORY_DEFAULT")
        self.assertIn(RT_MEMORY_TYPE, "RT_MEMORY_HBM")
        self.assertIn(RT_MEMORY_TYPE, "RT_MEMORY_DDR")
        self.assertIn(RT_MEMORY_TYPE, "RT_MEMORY_L1")
        self.assertIn(RT_MEMORY_TYPE, "RT_MEMORY_L2")

    def test_rt_memory_type_values(self):
        self.assertEqual(RT_MEMORY_TYPE["RT_MEMORY_DEFAULT"], 0)
        self.assertEqual(RT_MEMORY_TYPE["RT_MEMORY_HBM"], 2)
        self.assertEqual(RT_MEMORY_TYPE["RT_MEMORY_RESERVED"], 0x100)

    def test_rt_module_type_contains_expected_keys(self):
        self.assertIn(RT_MODULE_TYPE, "MODULE_TYPE_SYSTEM")
        self.assertIn(RT_MODULE_TYPE, "MODULE_TYPE_AICORE")
        self.assertIn(RT_MODULE_TYPE, "MODULE_TYPE_AICPU")

    def test_rt_module_type_values(self):
        self.assertEqual(RT_MODULE_TYPE["MODULE_TYPE_SYSTEM"], 0)
        self.assertEqual(RT_MODULE_TYPE["MODULE_TYPE_AICORE"], 4)
        self.assertEqual(RT_MODULE_TYPE["MODULE_TYPE_PCIE"], 6)

    def test_rt_info_type_contains_expected_keys(self):
        self.assertIn(RT_INFO_TYPE, "INFO_TYPE_ENV")
        self.assertIn(RT_INFO_TYPE, "INFO_TYPE_CORE_NUM")
        self.assertIn(RT_INFO_TYPE, "INFO_TYPE_ERROR_MAP")

    def test_rt_info_type_values(self):
        self.assertEqual(RT_INFO_TYPE["INFO_TYPE_ENV"], 0)
        self.assertEqual(RT_INFO_TYPE["INFO_TYPE_CORE_NUM"], 3)
        self.assertEqual(RT_INFO_TYPE["INFO_TYPE_ENDIAN"], 10)

    def test_rt_memory_policy_values(self):
        self.assertEqual(RT_MEMORY_POLICY["RT_MEMORY_POLICY_NONE"], 0x0)
        self.assertEqual(RT_MEMORY_POLICY["RT_MEMORY_POLICY_HUGE_PAGE_FIRST"], 0x400)

    def test_rt_memcpy_kind_values(self):
        self.assertEqual(RT_MEMCPY_KIND["RT_MEMCPY_HOST_TO_HOST"], 0)
        self.assertEqual(RT_MEMCPY_KIND["RT_MEMCPY_HOST_TO_DEVICE"], 1)
        self.assertEqual(RT_MEMCPY_KIND["RT_MEMCPY_DEVICE_TO_DEVICE"], 3)

    def test_memory_info_type_values(self):
        self.assertEqual(MEMORY_INFO_TYPE["RT_MEMORYINFO_DDR"], 0)
        self.assertEqual(MEMORY_INFO_TYPE["RT_MEMORYINFO_HBM"], 1)

    def test_rt_context_mode_values(self):
        self.assertEqual(RT_CONTEXT_MODE["RT_CTX_NORMAL_MODE"], 0)
        self.assertEqual(RT_CONTEXT_MODE["RT_CTX_GEN_MODE"], 1)

    def test_rt_kernel_flags_values(self):
        self.assertEqual(RT_KERNEL_FLAGS["default"], 0x00)
        self.assertEqual(RT_KERNEL_FLAGS["dumpflag"], 0x02)

    def test_rt_func_mode_dict_values(self):
        self.assertEqual(RT_FUNC_MODE_DICT["FUNC_MODE_NORMAL"], 0)
        self.assertEqual(RT_FUNC_MODE_DICT["FUNC_MODE_BUTT"], 5)

    def test_rt_env_type_values(self):
        self.assertEqual(RT_ENV_TYPE[0], "FPGA")
        self.assertEqual(RT_ENV_TYPE[1], "EMU")
        self.assertEqual(RT_ENV_TYPE[2], "ESL")

    def test_rt_error_type_dict_contains_expected(self):
        self.assertIn(RT_ERROR_TYPE_DICT, 0x00000000)
        self.assertIn(RT_ERROR_TYPE_DICT, 0x00080000)
        self.assertIn(RT_ERROR_TYPE_DICT, 0x00170000)

    def test_rt_error_type_dict_values(self):
        self.assertEqual(RT_ERROR_TYPE_DICT[0x00000000], "UNKNOWN")
        self.assertEqual(RT_ERROR_TYPE_DICT[0x00080000], "KERNEL")
        self.assertEqual(RT_ERROR_TYPE_DICT[0x00FF0000], "RESERVED")

    def test_rt_error_code_dict_contains_major_types(self):
        major_types = [
            0x00000000,
            0x00010000,
            0x00020000,
            0x00080000,
            0x000E0000,
            0x00150000,
            0x00FF0000,
        ]
        for mt in major_types:
            self.assertIn(RT_ERROR_CODE_DICT, mt)

    def test_rt_error_none_value(self):
        self.assertEqual(RT_ERROR_NONE, 0)

    def test_acl_rt_success_value(self):
        self.assertEqual(ACL_RT_SUCCESS, 0)

    def test_acl_error_rt_param_invalid_value(self):
        self.assertEqual(ACL_ERROR_RT_PARAM_INVALID, 107000)

    def test_acl_error_rt_feature_not_support_value(self):
        self.assertEqual(ACL_ERROR_RT_FEATURE_NOT_SUPPORT, 207000)
