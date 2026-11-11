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

import csv
import os
import pytest
import sys
import shutil
import subprocess
from unittest import mock
from pathlib import Path

from ms_interface import utils
from ms_interface.constant import Constant
from ms_interface.constant import ModeCustom
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.run_dirty_ub import run_dirty_ub_tik

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)

cur_abspath = os.path.dirname(__file__)
sys.path.append(MSAICERR_PATH)
sys.path.append(f"{cur_abspath}/../res/package")


class TestUtilsMethods(CommonAssert):
    def test_print_info_log(self):
        utils.print_info_log("test info log")

    def test_print_error_log(self):
        utils.print_error_log("test error log")

    def test_print_warn_log(self):
        utils.print_warn_log("test warn log")

    def test_check_path_special_character_is_empty(self):
        with pytest.raises(utils.AicErrException) as error:
            utils.check_path_special_character("")
        self.assertEqual(error.value.args[0], Constant.MS_AICERR_INVALID_PARAM_ERROR)

    def test_check_path_special_character_is_space(self):
        with pytest.raises(utils.AicErrException) as error:
            utils.check_path_special_character("/path with space")
        self.assertEqual(error.value.args[0], Constant.MS_AICERR_INVALID_PARAM_ERROR)

    def test_check_path_valid(self):
        with pytest.raises(utils.AicErrException) as error:
            utils.check_path_valid(";*")
        self.assertEqual(error.value.args[0], Constant.MS_AICERR_INVALID_PARAM_ERROR)

    def test_check_path_valid_accessible(self):
        with pytest.raises(utils.AicErrException) as error:
            with mock.patch("os.path.exists", return_value=False):
                with mock.patch("os.makedirs", side_effect=OSError):
                    utils.check_path_valid(
                        os.path.join(cur_abspath, "../res/ori_data/complie_path"),
                        True,
                        True,
                    )
        self.assertEqual(error.value.args[0], Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_get_str_value_empty(self):
        hexstr_value = utils.get_str_value("")
        self.assertEqual(hexstr_value, -1)

    def test_get_str_value_hex(self):
        hexstr_value = utils.get_str_value("0x11")
        self.assertEqual(hexstr_value, 17)

    def test_get_str_value_uppercase_hex_prefix(self):
        self.assertEqual(utils.get_str_value("0X11"), 17)

    def test_get_str_value_dec(self):
        hexstr_value = utils.get_str_value("11")
        self.assertEqual(hexstr_value, 11)

    def test_get_str_value_float_invalid(self):
        hexstr_value = utils.get_str_value("1.34")
        self.assertEqual(hexstr_value, -1)

    def test_get_hexstr_value_0(self):
        hexstr_value = utils.get_hexstr_value("0")
        self.assertEqual(hexstr_value, 0)

    def test_get_hexstr_value(self):
        hexstr_value = utils.get_hexstr_value("A")
        self.assertEqual(hexstr_value, 10)

    def test_get_hexstr_value_invalid(self):
        hexstr_value = utils.get_hexstr_value("G")
        self.assertEqual(hexstr_value, -1)

    def test_hexstr_to_list_bin(self):
        hexstr_value = utils.hexstr_to_list_bin("0x15")
        self.assertEqual(hexstr_value, [4, 2, 0])

    def test_get_01_from_hexstr(self):
        hexstr_value = utils.get_01_from_hexstr("0x15", 3, 0)
        self.assertEqual(hexstr_value, "0101")

    def test_execute_command(self, mocker):
        with pytest.raises(utils.AicErrException) as error:
            mocker.patch("tempfile.SpooledTemporaryFile", side_effect=FileNotFoundError)
            utils.execute_command("")
        self.assertEqual(error.value.args[0], Constant.MS_AICERR_EXECUTE_COMMAND_ERROR)

    def test_aicerr_exception_str_is_self_describing(self):
        # str() 渲染为 "[错误码] 描述"，日志与 traceback 不再出现裸数字错误码
        exc = utils.AicErrException(Constant.MS_AICERR_OPEN_FILE_ERROR)
        self.assertEqual(exc.args[0], Constant.MS_AICERR_OPEN_FILE_ERROR)
        self.assertEqual(exc.error_info, Constant.MS_AICERR_OPEN_FILE_ERROR)
        self.assertEqual(str(exc), "[5] failed to open or read the required file")

    def test_aicerr_exception_str_unknown_code(self):
        self.assertEqual(
            str(utils.AicErrException(999)), "[999] unknown msaicerr error"
        )

    def test_ms_aicerr_error_desc_covers_all_tool_error_codes(self):
        # 新增 MS_AICERR_* 工具错误码（<100）时必须同步补描述，防止再出现裸数字
        codes = {
            value
            for name, value in vars(Constant).items()
            if name.startswith("MS_AICERR_") and isinstance(value, int) and value < 100
        }
        self.assertEqual(codes - set(Constant.MS_AICERR_ERROR_DESC), set())

    def test_run_cmd_output_pass(self):
        res = utils.run_cmd_output(["ls"])
        assert res

    def test_run_cmd_output_failed(self):
        res = utils.run_cmd_output(["hello"])
        assert not res

    @staticmethod
    def test_run_cmd_output_reject_str():
        # shell=False 只接受参数列表；传字符串直接返回 False 而不是拼成单个可执行名。
        res = utils.run_cmd_output("ls -l")
        assert not res

    def test_get_inquire_result_failed(self, mocker):
        mocker.patch("ms_interface.utils.execute_command", return_value=(1, ""))
        res = utils.get_inquire_result(["xxx"], "", match_dict=True)
        assert res == []

        mocker.patch("ms_interface.utils.execute_command", return_value=(0, ""))
        res = utils.get_inquire_result(["xxx"], "asfdd", match_dict=True)
        assert res == []

    def test_parse_name_mapping_csv(self, tmp_path):
        """
        测试超长文件名的mapping.csv解析为 原名 -> 映射名，非法行被忽略
        """
        csv_path = tmp_path.joinpath(Constant.MAPPING_CSV_FILE)
        csv_path.write_text(
            "1234567890123456,long_name_a\n"
            "6543210987654321,long_name_b\n"
            "invalid_line_without_comma\n",
            encoding="utf-8",
        )
        res = utils.parse_name_mapping_csv(str(csv_path))
        self.assertEqual(
            res, {"long_name_a": "1234567890123456", "long_name_b": "6543210987654321"}
        )

    def test_parse_name_mapping_csv_not_exist(self, tmp_path):
        self.assertEqual(utils.parse_name_mapping_csv(""), {})
        self.assertEqual(
            utils.parse_name_mapping_csv(str(tmp_path.joinpath("not_exist.csv"))), {}
        )

    def test_parse_name_mapping_csv_read_failed(self, tmp_path, mocker):
        """
        测试mapping.csv读取异常时返回空字典而非向上抛异常
        """
        csv_path = tmp_path.joinpath(Constant.MAPPING_CSV_FILE)
        csv_path.write_text("1234567890123456,long_name_a\n", encoding="utf-8")
        mocker.patch("csv.reader", side_effect=csv.Error("line contains NUL"))
        self.assertEqual(utils.parse_name_mapping_csv(str(csv_path)), {})

    def test_parse_name_mapping_csv_invalid_encoding(self, tmp_path):
        """
        测试mapping.csv含非utf-8字节时返回空字典而非抛UnicodeDecodeError
        """
        csv_path = tmp_path.joinpath(Constant.MAPPING_CSV_FILE)
        csv_path.write_bytes(
            b"1234567890123456,long_name_a\n6543210987654321,long_name_\xff\xfe\n"
        )
        self.assertEqual(utils.parse_name_mapping_csv(str(csv_path)), {})

    def test_parse_name_mapping_csv_utf8_name(self, tmp_path):
        """
        测试多字节算子名不受locale影响，按utf-8解析成功
        """
        csv_path = tmp_path.joinpath(Constant.MAPPING_CSV_FILE)
        csv_path.write_bytes("1234567890123456,算子名称\n".encode("utf-8"))
        self.assertEqual(
            utils.parse_name_mapping_csv(str(csv_path)),
            {"算子名称": "1234567890123456"},
        )

    @pytest.mark.skip
    def test_run_dirty_ub(self, mocker):
        temp_dir = Path(cur_abspath).joinpath("../test_run_dirty_ub")
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = (
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, "op_test")
        config_file = single_op_case.generate_config()
        config_file.update({"compile_temp_dir": temp_dir})
        res = subprocess.run([sys.executable, "-c", ""], check=False)
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
        mocker.patch("subprocess.run", return_value=res)
        mocker.patch.object(AscendOpKernelRunner, "run")
        mocker.patch.object(AscendRTSApi, "_load_runtime_so")
        mocker.patch.object(AscendRTSApi, "register_kernel_launch_fill_func")
        mocker.patch.object(AscendRTSApi, "set_device")
        mocker.patch.object(AscendRTSApi, "create_stream")
        mocker.patch.object(AscendRTSApi, "reset")
        mocker.patch.object(AscendRTSApi, "destroy_stream")
        op_kernel_path = temp_dir.joinpath(ModeCustom.DIRTY_CUSTOM.value, "op_kernel")
        op_kernel_path.mkdir(parents=True, exist_ok=True)
        op_kernel_path.joinpath("add_custom.cpp").write_text("test", encoding="utf-8")
        compile_file_path = temp_dir.joinpath(
            ModeCustom.DIRTY_CUSTOM.value, "build_out", "op_kernel"
        )
        compile_file_path.mkdir(parents=True, exist_ok=True)
        compile_file_path.joinpath(
            f"{ModeCustom.DIRTY_CUSTOM.value}_add_custom.o"
        ).write_text("test", encoding="utf-8")
        shutil.copy(
            Path(cur_abspath).joinpath(
                "../res/ori_data/collect_milan/collection",
                "DirtyCustom_ab1b6750d7f510985325b603cb06dc8b.json",
            ),
            compile_file_path,
        )

        res = run_dirty_ub_tik(config_file, "Ascend910B1", 0)
        assert res
