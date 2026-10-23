#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PrecisionSourceGuidanceTests(unittest.TestCase):
    def test_precision_flow_requires_scalar_type_and_arch_variant_source_trace(self):
        text = (ROOT / "references" / "fault-flows" / "precision-flow.md").read_text(
            encoding="utf-8"
        )
        for marker in ("ScalarT", "scalarCalcType", "arch35", "T"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_aicore_flow_binds_build_labels_without_inventing_constants(self):
        text = (ROOT / "references" / "fault-flows" / "aicore-error-flow.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "atomic_dirty_cacheline",
            "dcache_biu_response",
            "fixp_b4_misalign",
            "fixpipe_addr_misalign",
            "FixpipeParamsV220",
            "凭目录名补出源码常量",
            "标签不证明 atomic 路径实际执行",
            "若确为 `FixpipeParamsV220`，核对其源布局",
            "先确认芯片、CANN 版本和实际 API 变体",
            "缺失时记录证据缺口并降低标签置信度",
            "在标签与设备错误一致时",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn("srcStride=3200", text)
        self.assertNotIn("unitFlag=4", text)


if __name__ == "__main__":
    unittest.main()
