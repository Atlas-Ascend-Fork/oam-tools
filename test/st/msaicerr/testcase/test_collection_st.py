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
from ms_interface.collection import Collection
from ms_interface.constant import Constant
import os
import sys
import pytest

from conftest import (
    MSAICERR_PATH,
    RES_PATH,
    CUR_TIME_STR,
    DUMP_EXCEPTION_STR,
    AIC_INFO_DEV_FUNC,
    AIC_INFO_DEV_FUNC_ERROR,
    EXCEPTION_INFO_DUMP_ARGS_DATA,
    L1_DUMP_EXCEPTION_TO_FILE,
    AIC_INFO_NODE_NAME,
    AIC_INFO_NODE_NAME_ERROR,
    L0_DUMP_EXCEPTION_TO_FILE0,
    AICORE_KERNEL_EXECUTE_FAILED,
    AICORE_KERNEL_EXECUTE_FAILED_ERROR,
    FFTS_PLUS_TASK_EXECUTE_FAILED_ERROR,
    mkdir_dump_file_path,
    FFTS_PLUS_TASK_EXECUTE_FAILED,
    write_log_keyword_to_file,
    SK_DUMP_CALLBACK_EXCEPTION,
    CommonAssert,
)

sys.path.append(MSAICERR_PATH)


class TestUtilsMethods(CommonAssert):
    # fixture/setup_method 中赋值，此处声明以明确实例属性集合
    debug_info = None
    old_cwd = None
    temp = None

    @pytest.fixture(autouse=True)
    def change_test_dir(self, tmp_path):
        self.old_cwd = os.getcwd()
        self.temp = tmp_path
        self.debug_info = tmp_path.joinpath("debug_info.txt")
        os.chdir(tmp_path)
        yield
        os.chdir(self.old_cwd)

    @pytest.mark.parametrize(
        "src_path, expected",
        [
            ("ori_data/asys_output_20240912164014958", True),  # 验证正常流程
            # 验证在日志中无法匹配dump exception to file
            ("ori_data/asys_output_20230713074104794", False),
            ("ori_data/collect/ffts", False),  # 验证在目录中无法通过dump名找到dump文件
        ],
    )
    def test_run_collect(self, src_path, expected):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath(src_path)
        collection = Collection(input_path, output_path)
        res = collection.collect()
        self.assertEqual(res, expected)

    def test_collect_execute_command_error(self):
        """
        测试获取dump log失败
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath("ori_data/complie_path")
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            self.temp.joinpath("debug_info.txt").read_text(encoding="utf-8"),
            "Adump log '[Dump][Exception]' cannot be found",
        )

    @pytest.mark.parametrize(
        "keywords, expected, log_path",
        [
            ([DUMP_EXCEPTION_STR, FFTS_PLUS_TASK_EXECUTE_FAILED], True, "aicore_error"),
            # 验证日志包含\[Dump\]\[Exception\] + fftsplus task execute failed 在相同文件中
            (
                [DUMP_EXCEPTION_STR, EXCEPTION_INFO_DUMP_ARGS_DATA],
                False,
                "exception_dump",
            ),
            # 验证日志包含 [Dump\]\[Exception\] + exception info dump args data
            (
                [
                    DUMP_EXCEPTION_STR,
                    EXCEPTION_INFO_DUMP_ARGS_DATA,
                    FFTS_PLUS_TASK_EXECUTE_FAILED,
                ],
                False,
                # 验证日志包含 [Dump\]\[Exception\] + exception info dump args data + fftsplus
                "exception_dump",
            ),
        ],
    )
    def test_collect_plog_file_l0(self, keywords, expected, log_path):
        """
        测试日志收集相关
        """
        node_name = "exception_info.42.1.1726159207469285"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        report_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        report_path.mkdir(parents=True, exist_ok=True)
        define_keywords = [L0_DUMP_EXCEPTION_TO_FILE0]
        write_log_keyword_to_file(report_path, define_keywords + keywords)
        mkdir_dump_file_path(node_name, report_path)
        collection = Collection(report_path, output_path)
        res = collection.collect()
        self.assertEqual(res, True)
        check_dest_file = bool(
            list(output_path.joinpath(f"collection/plog/{log_path}").rglob("*.txt"))
        )
        self.assertEqual(check_dest_file, expected)

    def test_not_ffts_get_kernel_name_l0(self, mocker):
        """
        测试获取kernel name从l0中
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath("ori_data/asys_output_20240912164014957")
        collection = Collection(input_path, output_path)
        mocker.patch.object(collection, "check_dump_data_is_valid")
        mocker.patch.object(
            collection, "check_host_and_device_kernel_name", return_value=True
        )
        collection.collect()
        text = self.debug_info.read_text(encoding="utf-8")
        self.assertIn(
            text,
            "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic",
        )

    def test_not_ffts_get_kernel_name_l0_kernel_info(self):
        """
        测试 非ffts获取kernel name从l0中
        """
        node_name = "exception_info.42.1.1726159207469285"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                L0_DUMP_EXCEPTION_TO_FILE0,
                AICORE_KERNEL_EXECUTE_FAILED,
            ],
        )
        mkdir_dump_file_path(node_name, input_path)
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"),
            "AicoreError Found, kernel_name",
        )

    def test_not_ffts_get_kernel_name_l0_get_node_name_failed(self):
        """
        测试 非ffts获取kernel name失败从l0中
        """
        node_name = "exception_info.42.1.1726159207469285"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                L0_DUMP_EXCEPTION_TO_FILE0,
                AICORE_KERNEL_EXECUTE_FAILED_ERROR,
            ],
        )
        mkdir_dump_file_path(node_name, input_path)
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            self.debug_info.read_text(),
            """Failed to get \"Aicore kernel execute failed|AI Core kernel execution failed\" in plog.""",
        )

    def test_ffts_get_kernel_name_from_l0(self, mocker):
        """
        测试获取kernel name从l0中
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath("ori_data/collect/ffts")
        collection = Collection(input_path, output_path)
        mocker.patch.object(collection, "check_dump_data_is_valid")
        mocker.patch.object(
            collection, "check_host_and_device_kernel_name", return_value=True
        )
        collection.collect()
        text = self.debug_info.read_text(encoding="utf-8")
        self.assertIn(
            text,
            "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic",
        )

    def test_ffts_get_node_and_kernel_name_l0_failed(self):
        """
        测试获取kernel name从l0中, 失败
        """
        node_name = "exception_info.42.1.1726159207469285"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                FFTS_PLUS_TASK_EXECUTE_FAILED_ERROR,
                L0_DUMP_EXCEPTION_TO_FILE0,
                AICORE_KERNEL_EXECUTE_FAILED_ERROR,
            ],
        )
        mkdir_dump_file_path(node_name, input_path)
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"),
            'Failed to get "fftsplus task execute failed" in plog.',
        )

    def test_sk_get_kernel_name_l0(self):
        """
        测试SK场景：标志性打印中的kernelName才是正确的算子名，优先返回
        """
        data_name = "exception_info.42.1.1726159207469285"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath("collection/plog")
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        # 同时存在SK标志性打印和普通fault kernel_name，SK场景应优先返回SK的kernelName
        collection_plog_path.joinpath("plog.log").write_text(
            f"{SK_DUMP_CALLBACK_EXCEPTION}\n{AICORE_KERNEL_EXECUTE_FAILED}",
            encoding="utf-8",
        )
        collection = Collection(input_path, output_path)
        collection.ffts_flag = False
        kernel_name, node_name = collection.get_kernel_name_l0(data_name)
        self.assertEqual(kernel_name, "Add_sk_kernel_900016000")
        self.assertEqual(node_name, data_name)

    def test_get_dump_file(self):
        """
        测试获取dump信息
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        collection = Collection(input_path, output_path)
        collection.collect_level = 1
        collection.collect()
        text = self.debug_info.read_text(encoding="utf-8")
        self.assertIn(text, "aclnnIndexSelect_0_L0.GatherV3AiCore.1.20241205153328944")
        self.assertIn(text, "2024-12-05-15:33:29.760.012")

    def test_get_dump_file_from_ge(self):
        """
        测试从ge日志中获取dump信息
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                AIC_INFO_DEV_FUNC,
                DUMP_EXCEPTION_STR,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                L1_DUMP_EXCEPTION_TO_FILE,
            ],
        )
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            self.debug_info.read_text(),
            "Cannot find dump file GatherV2.GatherV21.1.1733469426252033",
        )

    @pytest.mark.skip
    def test_check_not_host_and_device_kernel_name(self, mocker):
        """
        测试host和device 没有kernel name
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath("ori_data/asys_output_20230713074104794")
        collection = Collection(input_path, output_path)
        mocker.patch.object(collection, "check_dump_data_is_valid")
        mocker.patch.object(
            collection,
            "get_dump_data_info",
            return_value=("_", 0, "GatherV2.GatherV2.6.1689234160564442"),
        )
        collection.collect()
        text = self.debug_info.read_text(encoding="utf-8")
        self.assertIn(text, "Cannot find host kernel or device kernel")

    def test_host_and_device_is_different(self, mocker):
        """
        测试host和device 不同
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath("ori_data/asys_output_20230713074104794")
        collection = Collection(input_path, output_path)
        mocker.patch.object(collection, "check_dump_data_is_valid")
        mocker.patch.object(
            collection, "check_host_and_device_kernel_name", return_value=False
        )
        collection.collect()
        text = self.debug_info.read_text(encoding="utf-8")
        assert "The kernel load on the host is different from the device" not in text
        self.assertNotIn(
            text, "The kernel load on the host is different from the device"
        )

    def test_run_collect_level_ffts(self, mocker):
        """
        执行msaicerr collect 覆盖数据找不到功能
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath("ori_data/asys_output_20240912164014958")
        collection = Collection(input_path, output_path)
        mocker.patch.object(
            collection,
            "get_dump_data_info",
            return_value=("_", 0, "GatherV2.GatherV2.6.1689234160564442"),
        )
        mocker.patch.object(
            collection, "check_host_and_device_kernel_name", return_value=True
        )
        mocker.patch.object(
            utils,
            "get_inquire_result",
            return_value=[
                str(
                    input_path.joinpath(
                        "dfx/log/host/run/plog/plog-1592007_20240912163952762.log"
                    )
                )
            ],
        )
        collection.collect()
        self.assertEqual(collection.collect_level, 1)
        self.assertEqual(collection.ffts_flag, True)

    def test_get_node_and_kernel_name_l1_get_kernel_name_failed(self):
        """
        测试L1无法找到kernel_name 失败报错
        """
        node_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                AIC_INFO_DEV_FUNC_ERROR,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                L1_DUMP_EXCEPTION_TO_FILE,
            ],
        )
        mkdir_dump_file_path(node_name, input_path)
        utils.ExceptionRootCause().cache_error = True
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            utils.ExceptionRootCause().format_causes(),
            """Failed to get "[AIC_INFO] dev_func:" in plog. Cannot run L1 test""",
        )

    def test_get_node_and_kernel_name_l1_get_node_name_failed(self):
        """
        测试L1无法找到node_name失败报错
        """
        node_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                AIC_INFO_DEV_FUNC,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                L1_DUMP_EXCEPTION_TO_FILE,
                AIC_INFO_NODE_NAME_ERROR,
            ],
        )
        mkdir_dump_file_path(node_name, input_path)
        utils.ExceptionRootCause().cache_error = True
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            utils.ExceptionRootCause().format_causes(),
            """Failed to get node name in plog. Cannot run L1 test""",
        )

    def test_run_collect_oversize_data_name(self):
        """
        测试超长算子名场景：dump文件被框架重命名为随机数字串，
        collect通过mapping.csv找到实际落盘文件，并把mapping.csv一并收集
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        dump_path = input_path.joinpath("extra-info/data-dump/0")
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_path.joinpath(rename).touch()
        dump_path.joinpath("te_gatherv2.o").touch()
        dump_path.joinpath("te_gatherv2_host.o").touch()
        dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(
            f"{rename},{data_name}\n", encoding="utf-8"
        )
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                AICORE_KERNEL_EXECUTE_FAILED,
                "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.226 [dump_args.cpp:807]"
                "[tid:1592077] [1] dump exception to file, file: "
                f"./new/extra-info/data-dump/0/{data_name}",
            ],
        )
        collection = Collection(input_path, output_path)
        res = collection.collect()
        self.assertEqual(res, True)
        self.assertEqual(collection.dump_file_rename, rename)
        self.assertEqual(
            bool(list(output_path.rglob(f"collection/dump/{rename}"))), True
        )
        self.assertEqual(
            bool(
                list(output_path.rglob(f"collection/dump/{Constant.MAPPING_CSV_FILE}"))
            ),
            True,
        )
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"),
            f"use mapped name {rename} instead of",
        )

    def test_run_collect_oversize_data_name_no_mapping(self):
        """
        测试超长算子名但缺失mapping.csv：退化为按原始名查找，报dump文件找不到
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.226 [dump_args.cpp:807]"
                "[tid:1592077] [1] dump exception to file, file: "
                f"./new/extra-info/data-dump/0/{data_name}",
            ],
        )
        collection = Collection(input_path, output_path)
        res = collection.collect()
        self.assertEqual(res, False)
        self.assertEqual(collection.dump_file_rename, "")
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"),
            f"Cannot find dump file {data_name}",
        )

    def test_get_node_and_kernel_name_l1_get_node_name_have_multiple_dump(self):
        """
        测试L1无法找到node_name失败报错
        """
        node_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        write_log_keyword_to_file(
            input_path,
            [
                DUMP_EXCEPTION_STR,
                AIC_INFO_DEV_FUNC,
                EXCEPTION_INFO_DUMP_ARGS_DATA,
                L1_DUMP_EXCEPTION_TO_FILE,
                AIC_INFO_NODE_NAME,
            ],
        )
        mkdir_dump_file_path(node_name, input_path)
        mkdir_dump_file_path(node_name, input_path.joinpath("input1"))
        mkdir_dump_file_path(node_name, input_path.joinpath("input2"))
        collection = Collection(input_path, output_path)
        collection.collect()
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"),
            "Find dump file GatherV2.GatherV21.1.1733469426252033",
        )
