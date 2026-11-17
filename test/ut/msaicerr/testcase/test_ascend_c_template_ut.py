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

from ms_interface.ascend950.ascend_c_template import (
    ADD_OP_KERNEL_TEMPLATE,
    DIRTY_OP_KERNEL_TEMPLATE,
)


class TestAscendCTemplateMethods(CommonAssert):
    def test_add_op_kernel_template_is_not_empty(self):
        assert len(ADD_OP_KERNEL_TEMPLATE) != 0

    def test_add_op_kernel_template_contains_keyword(self):
        self.assertIn(ADD_OP_KERNEL_TEMPLATE, "add_custom")

    def test_add_op_kernel_template_contains_kernel_add(self):
        self.assertIn(ADD_OP_KERNEL_TEMPLATE, "class KernelAdd")

    def test_add_op_kernel_template_contains_process(self):
        self.assertIn(ADD_OP_KERNEL_TEMPLATE, "Process")

    def test_add_op_kernel_template_contains_dtype_placeholder(self):
        self.assertIn(ADD_OP_KERNEL_TEMPLATE, "DTYPE_X")
        self.assertIn(ADD_OP_KERNEL_TEMPLATE, "DTYPE_Y")
        self.assertIn(ADD_OP_KERNEL_TEMPLATE, "DTYPE_Z")

    def test_dirty_op_kernel_template_is_not_empty(self):
        assert len(DIRTY_OP_KERNEL_TEMPLATE) != 0

    def test_dirty_op_kernel_template_contains_keyword(self):
        self.assertIn(DIRTY_OP_KERNEL_TEMPLATE, "dirty_custom")

    def test_dirty_op_kernel_template_contains_kernel_dirty(self):
        self.assertIn(DIRTY_OP_KERNEL_TEMPLATE, "class KernelDirty")

    def test_dirty_op_kernel_template_contains_kernel_operator_header(self):
        self.assertIn(ADD_OP_KERNEL_TEMPLATE, "kernel_operator.h")
        self.assertIn(DIRTY_OP_KERNEL_TEMPLATE, "kernel_operator.h")

    def test_templates_have_different_content(self):
        assert ADD_OP_KERNEL_TEMPLATE != DIRTY_OP_KERNEL_TEMPLATE
