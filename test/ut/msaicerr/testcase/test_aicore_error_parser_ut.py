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

import os
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

# conftest 已把 MSAICERR_PATH 加入 sys.path（其导入早于下面的 ms_interface），
# 故此处无需重复 append；被测模块导入期也不依赖 te，import 可留在文件顶部。
from conftest import CommonAssert, cur_abspath, ori_data_path
from ms_interface import utils
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.collection import Collection
from ms_interface.constant import Constant, RegexPattern, RetCode
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.tiling_data_parser import TilingDataParser

# te 仅在用例运行期被 mock 使用，桩放在 import 之后即可
te = Mock(name="te")
te.__name__ = "te"
sys.modules["te"] = te


class Selflib:
    @staticmethod
    def rtGetAiCoreCount(_driver_core_num):
        return 0


@pytest.mark.usefixtures("change_test_dir")
class TestUtilsMethods(CommonAssert):
    # fixture/setup_method 中赋值，此处声明以明确实例属性集合
    debug_info = None
    temp = None

    def test_get_atomic_err_log(self, mocker):
        mocker.patch("ms_interface.utils.execute_command", return_value=[1, ""])
        collection = Collection(
            os.path.join(cur_abspath, "../res/ori_data/complie_path"),
            os.path.join(cur_abspath, "../res/ori_data/complie_path"),
        )
        collection.collect_plog_path = "dest_path"
        parser = AicoreErrorParser(collection)
        atomic_err_log = getattr(parser, "_get_atomic_err_log")()
        self.assertEqual(atomic_err_log, False)

    def test_check_addr_in_range_hex(self):
        flag = getattr(AicoreErrorParser, "_check_addr_in_range")(1, 24, [("0x0", 256)])
        self.assertEqual(flag, True)

    def test_check_addr_in_range_dec(self):
        flag = getattr(AicoreErrorParser, "_check_addr_in_range")(1, 24, [("0", 256)])
        self.assertEqual(flag, True)

    def test_check_addr_in_range_error(self):
        flag = getattr(AicoreErrorParser, "_check_addr_in_range")(1, 256, [("0", 24)])
        self.assertEqual(flag, False)

    def test_get_info_for_decompile(self, mocker):
        mocker.patch(
            "ms_interface.aic_error_info.AicErrorInfo.find_extra_pc",
            return_value="10100110",
        )
        parser = AicoreErrorParser("collection")
        info = AicErrorInfo()
        info.aic_error_info["current_pc"] = "x1435"
        info.aic_error_info["start_pc"] = "x0123"
        err_pc = getattr(parser, "_get_info_for_decompile")(info)
        self.assertEqual(err_pc, "1176")

    def test_get_cce_tbe_code_number_decompile_not_exist(self):
        parser = AicoreErrorParser("collection")
        flag = getattr(parser, "_get_cce_tbe_code_number")(
            "decompile_file", "loc_json_file", "err_pc", "info"
        )
        self.assertEqual(flag, False)

    def test_get_cce_tbe_code_number_loc_not_exist(self, mocker):
        mocker.patch("os.path.exists", side_effect=[True, False])
        mocker.patch(
            "ms_interface.aicore_error_parser.AicoreErrorParser._read_decompile_file",
            return_value="0x1234",
        )
        parser = AicoreErrorParser("collection")
        flag = getattr(parser, "_get_cce_tbe_code_number")(
            "decompile_file", "loc_json_file", "err_pc", "info"
        )
        self.assertEqual(flag, True)

    def test_get_cce_tbe_code_number_no_cce_code_num(self, mocker):
        parser = AicoreErrorParser("collection")
        mocker.patch("os.path.exists", side_effect=[True, True])
        mocker.patch.object(parser, "_read_decompile_file", return_value="")
        mocker.patch.object(parser, "_read_loc_json_file", return_value=None)
        flag = getattr(parser, "_get_cce_tbe_code_number")(
            "decompile_file", "loc_json_file", "err_pc", "info"
        )
        self.assertEqual(flag, False)

    def test_print_single_op_result(self):
        parser = AicoreErrorParser("collection")
        flag = parser.print_single_op_result("../res/ori_data")
        self.assertEqual(flag, None)

    def test_get_data_dump_result_ret(self, mocker):
        mocker.patch("ms_interface.utils.execute_command", return_value=[0, ""])
        collection = Collection(
            os.path.join(cur_abspath, "../res/ori_data/complie_path"),
            os.path.join(cur_abspath, "../res/ori_data/complie_path"),
        )
        collection.collect_plog_path = "dest_path"
        parser = AicoreErrorParser(collection)
        flag = getattr(parser, "_get_data_dump_result")()
        self.assertEqual(flag, False)

    def test_need_atomic_clean(self):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        parser = AicoreErrorParser("collection")
        flag = getattr(parser, "_need_atomic_clean")(
            os.path.join(cur_abspath, "../res/ori_data/complie_path"), info
        )
        self.assertEqual(flag, False)

    def test_run_golden_op(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        temp_dir = Path(cur_abspath).joinpath("../temp_test_run_golden_op")
        temp_dir.mkdir(parents=True, exist_ok=True)
        parser = AicoreErrorParser("collection")
        mock_return = MagicMock()
        mock_return.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_return)
        mocker.patch.object(AicoreErrorParser, "search_aicerr_log", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(
            Path,
            "rglob",
            return_value=[
                Path(cur_abspath).joinpath(
                    "../res/ori_data/collect_milan/collection/AddCustom_ab1b6750d7f510985325b603cb06dc8b.json"
                )
            ],
        )
        mocker.patch("shutil.rmtree")
        flag = parser.run_test_env("Ascend910B4")
        self.assertEqual(flag, False)

    def test_ffts_get_kernel_name_l0_success(self):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, "1")

    def test_not_ffts_get_kernel_name_l0_data(self):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/notffts/")
        )
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, "6")

    def test_sk_get_kernel_name_l0(self):
        # SK场景：标志性打印中的kernelName才是正确的算子名，覆盖原逻辑解析结果
        collect_path = self.temp.joinpath("sk_collect")
        plog_path = collect_path.joinpath("collection/plog")
        plog_path.mkdir(parents=True, exist_ok=True)
        plog_path.joinpath("plog.log").write_text(
            "[Dump][Exception] Begin to dump callback exception. coreType=0, coreId=1, argAddr=0x1, "
            "argSize=64, binHandle=0x2, extraTensorNum=2, kernelName=Add_sk_kernel_900016000.",
            encoding="utf-8",
        )
        parser = AicoreErrorParser(str(collect_path))
        aic_info = parser.get_kernel_name_l0("node_name")
        self.assertEqual(aic_info.kernel_name, "Add_sk_kernel_900016000")
        self.assertEqual(aic_info.node_name, "node_name")

    def test_sk_get_kernel_name_l0_keep_stream_task_from_data_name(self):
        # 纯SK场景：plog无普通报错行，stream_id/task_id应保留dump文件名中解析出的值，不丢失
        collect_path = self.temp.joinpath("sk_collect_keep")
        plog_path = collect_path.joinpath("collection/plog")
        plog_path.mkdir(parents=True, exist_ok=True)
        plog_path.joinpath("plog.log").write_text(
            "[Dump][Exception] Begin to dump callback exception. coreType=0, coreId=1, argAddr=0x1, "
            "argSize=64, binHandle=0x2, extraTensorNum=2, kernelName=Add_sk_kernel_900016000.",
            encoding="utf-8",
        )
        parser = AicoreErrorParser(str(collect_path))
        # data_name 形如 name.stream_id.task_id.timestamp，可解析出 stream_id=42, task_id=1
        aic_info = parser.get_kernel_name_l0("exception_info.42.1.1726159207469285")
        self.assertEqual(aic_info.kernel_name, "Add_sk_kernel_900016000")
        self.assertEqual(aic_info.stream_id, "42")
        self.assertEqual(aic_info.task_id, "1")

    def test_ffts1_get_kernel_name_l0_info(self):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, "1")

    def test_get_dump_data_info(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts")
        )
        dump_data_info_list = parser.get_dump_data_info()
        thread_id, _ = dump_data_info_list[0]
        self.assertEqual(thread_id, "1592077")

    def test_get_dump_data_info_keeps_hyphens_in_the_data_name(self, tmp_path):
        # The level 0 name capture must not stop at a hyphen, otherwise the
        # parsed data_name no longer matches the collected dump file.
        plog_dir = tmp_path.joinpath("info/collection/plog")
        plog_dir.mkdir(parents=True)
        data_name = "exception_info.42-1.1726159207469285"
        plog_dir.joinpath("aicore_error.log").write_text(
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.226 [tid:123] [Dump][Exception] "
            "dump exception to file, file: x/extra-info/data-dump/0/" + data_name,
            encoding="utf-8",
        )
        parser = AicoreErrorParser(str(tmp_path.joinpath("info")))
        err_info = parser.get_dump_data_info()
        self.assertEqual(err_info[0], ("123", data_name))

    def test_get_dump_data_info_keeps_hyphens_in_the_adump_record(self, tmp_path):
        # Same charset rule for the level 1 adump branch.
        plog_dir = tmp_path.joinpath("info/collection/plog")
        plog_dir.mkdir(parents=True)
        data_name = "exception_info.42-1.1726159207469285"
        plog_dir.joinpath("aicore_error.log").write_text(
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.226 [tid:123] [Dump][Exception] "
            "dump exception to file, file: x/extra-info/data-dump/0/" + data_name,
            encoding="utf-8",
        )
        parser = AicoreErrorParser(str(tmp_path.joinpath("info")))
        parser.parse_level = 1
        err_info = parser.get_dump_data_info()
        self.assertEqual(err_info[0], ("123", data_name))

    def test_get_dump_data_info_keeps_hyphens_in_the_ge_record(self, tmp_path):
        # Same charset rule for the level 1 GE DumpNodeInfo branch.
        plog_dir = tmp_path.joinpath("info/collection/plog")
        plog_dir.mkdir(parents=True)
        data_name = "GatherV2-decode.GatherV21.1.1733469426252033"
        plog_dir.joinpath("aicore_error.log").write_text(
            "[ERROR] GE(1582604,python3):2024-12-06-15:17:06.252.046 "
            "[exception_dumper.cc:424]1582604 DumpNodeInfo: "
            "ErrorNo: 4294967295(failed) [INIT][DEFAULT][Dump][Exception] "
            "dump exception to file, file: /home/aic_test/dump/extra-info/data-dump/1/"
            + data_name,
            encoding="utf-8",
        )
        parser = AicoreErrorParser(str(tmp_path.joinpath("info")))
        parser.parse_level = 1
        err_info = parser.get_dump_data_info()
        self.assertEqual(err_info[0], ("1582604", data_name))

    def test_get_custom_dump_files_keeps_hyphens_in_the_data_name(self, tmp_path):
        # The custom dump name capture must keep hyphens, otherwise an
        # existing custom dump file is silently dropped from parsing.
        collect_path = tmp_path.joinpath("info")
        plog_dir = collect_path.joinpath("collection/plog")
        dump_dir = collect_path.joinpath("collection/dump")
        plog_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.mkdir(parents=True, exist_ok=True)
        custom_name = "exception_info.42-1.1726159207469285.custom.1726159207469000"
        plog_dir.joinpath("aicore_error.log").write_text(
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.227 [tid:1] [Dump][Exception] "
            "dump custom exception to file, file: x/extra-info/data-dump/0/"
            + custom_name,
            encoding="utf-8",
        )
        custom_file = dump_dir.joinpath(custom_name)
        custom_file.touch()
        parser = AicoreErrorParser(str(collect_path), device_id=0)
        res = getattr(parser, "_get_custom_dump_files")(str(dump_dir))
        self.assertEqual(res, [str(custom_file)])

    def test_get_custom_dump_files(self, tmp_path):
        """只认dump目录下实际存在的自定义dump文件，不按命令行device过滤
        （采集侧已按报错device过滤，解析侧再按self.device_id过滤会在device
        不一致时漏解析）"""
        collect_path = tmp_path.joinpath("info")
        plog_dir = collect_path.joinpath("collection/plog")
        dump_dir = collect_path.joinpath("collection/dump")
        plog_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.mkdir(parents=True, exist_ok=True)
        plog_dir.joinpath("aicore_error.log").write_text(
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.227 [tid:1] [Dump][Exception] "
            "dump custom exception to file, file: x/extra-info/data-dump/0/"
            "exception_info.42.1.1726159207469285.custom.1726159207469000\n"
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.228 [tid:1] [Dump][Exception] "
            "dump custom exception to file, file: x/extra-info/data-dump/1/"
            "exception_info.42.1.1726159207469285.custom.1726159207469001\n"
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.229 [tid:1] [Dump][Exception] "
            "dump custom exception to file, file: x/extra-info/data-dump/0/"
            "GatherV2.custom.1726159207469002\n",
            encoding="utf-8",
        )
        dev0_file = dump_dir.joinpath(
            "exception_info.42.1.1726159207469285.custom.1726159207469000"
        )
        dev0_file.touch()
        dev1_file = dump_dir.joinpath(
            "exception_info.42.1.1726159207469285.custom.1726159207469001"
        )
        dev1_file.touch()
        parser = AicoreErrorParser(str(collect_path), device_id=0)
        res = getattr(parser, "_get_custom_dump_files")(str(dump_dir))
        # device 1 的9001文件实际存在，即使命令行device为0也解析
        self.assertEqual(res, [str(dev0_file), str(dev1_file)])

    def test_get_custom_dump_files_oversize_uses_mapping(self, tmp_path):
        """超长自定义dump被runtime改为随机数字串时，按mapping.csv反查实际文件名"""
        collect_path = tmp_path.joinpath("info")
        plog_dir = collect_path.joinpath("collection/plog")
        dump_dir = collect_path.joinpath("collection/dump")
        plog_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.mkdir(parents=True, exist_ok=True)
        oversize_custom = (
            "exception_info.42.1.1726159207469285"
            + "n" * 260
            + ".custom.1726159207469000"
        )
        mapped_name = "1234567890123456"
        plog_dir.joinpath("aicore_error.log").write_text(
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.227 [tid:1] [Dump][Exception] "
            "dump custom exception to file, file: x/extra-info/data-dump/0/"
            f"{oversize_custom}\n",
            encoding="utf-8",
        )
        mapped_file = dump_dir.joinpath(mapped_name)
        mapped_file.touch()
        dump_dir.joinpath("mapping.csv").write_text(
            f"{mapped_name},{oversize_custom}\n", encoding="utf-8"
        )
        parser = AicoreErrorParser(str(collect_path), device_id=0)
        res = getattr(parser, "_get_custom_dump_files")(str(dump_dir))
        self.assertEqual(res, [str(mapped_file)])

    def test_get_custom_dump_files_no_custom_log(self, tmp_path):
        """plog中无自定义dump日志时返回空列表，不抛异常"""
        collect_path = tmp_path.joinpath("info")
        plog_dir = collect_path.joinpath("collection/plog")
        plog_dir.mkdir(parents=True, exist_ok=True)
        plog_dir.joinpath("aicore_error.log").write_text(
            "[Dump][Exception] dump exception to file, file: x/extra-info/data-dump/0/"
            "exception_info.42.1.1726159207469285",
            encoding="utf-8",
        )
        parser = AicoreErrorParser(str(collect_path))
        res = getattr(parser, "_get_custom_dump_files")(str(plog_dir))
        self.assertEqual(res, [])

    def test_get_custom_dump_files_dump_missing(self, tmp_path):
        """日志指示的自定义dump未落盘时返回空列表"""
        collect_path = tmp_path.joinpath("info")
        plog_dir = collect_path.joinpath("collection/plog")
        dump_dir = collect_path.joinpath("collection/dump")
        plog_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.mkdir(parents=True, exist_ok=True)
        plog_dir.joinpath("aicore_error.log").write_text(
            "[ERROR] IDEDD(1,python3):2024-09-12-16:40:08.360.230 [tid:1] [Dump][Exception] "
            "dump custom exception to file, file: x/extra-info/data-dump/0/"
            "exception_info.42.1.1726159207469285.custom.1726159207469000",
            encoding="utf-8",
        )
        parser = AicoreErrorParser(str(collect_path), device_id=0)
        res = getattr(parser, "_get_custom_dump_files")(str(dump_dir))
        self.assertEqual(res, [])
        # plog有自定义dump日志却一个都没落盘时应给出告警，提示不解析
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"),
            "Custom dump file(s) are detected in the plog but none can be found",
        )

    def test_build_dump_parser_passes_custom_dump_files(self, tmp_path, mocker):
        """Step7构造DumpDataParser时传入检测到的自定义dump文件"""
        collect_path = tmp_path.joinpath("info")
        dump_dir = collect_path.joinpath("collection/dump")
        dump_dir.mkdir(parents=True, exist_ok=True)
        custom_file = dump_dir.joinpath("exception_info.custom.1726159207469000")
        custom_file.touch()
        info = AicErrorInfo()
        parser = AicoreErrorParser(str(collect_path), device_id=0)
        mocker.patch.object(
            parser, "_get_custom_dump_files", return_value=[str(custom_file)]
        )
        dump_parser = parser._build_dump_parser(str(dump_dir), info)
        self.assertEqual(dump_parser.custom_dump_files, [str(custom_file)])

    def test_collect_driver_aicore_number(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        os.environ["LD_LIBRARY_PATH"] = (
            os.environ.get("LD_LIBRARY_PATH", "") + "/runtime/libruntime.so"
        )
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        mocker.patch("ctypes.cdll.LoadLibrary", return_value=Selflib())
        aic_info = parser.collect_driver_aicore_number()
        self.assertEqual(aic_info, 0)

    def test_invalid_args_compare(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        res = getattr(parser, "_get_args_from_info")(
            r"\[AIC_INFO\] args.*after execute"
        )
        self.assertEqual(res[0], 255085623939072)

    def test_get_atomic_err_log_ffts(self):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        res = getattr(parser, "_get_atomic_err_log")()
        self.assertEqual(res, True)

    def test_update_err_pc(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        res = getattr(parser, "_update_err_pc")("0x0", "/", info.node_name)
        self.assertEqual(res, "0x0")
        mocker.patch.object(utils, "get_inquire_result", return_value="111")
        res = getattr(parser, "_update_err_pc")("0x1", "", "")

    def test_ffts_get_kernel_name_l0_task_id(self):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        parser.check_plog_info()
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, "1")

    def test_cal_shape_size(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        res = getattr(parser, "_cal_shape_size")("[]")
        self.assertEqual(res, 1)

    def test_get_err_pc(self, mocker):
        mocker.patch(
            "ms_interface.aic_error_info.AicErrorInfo.find_extra_pc", return_value=""
        )
        parser = AicoreErrorParser("collection")
        mocker.patch.object(parser, "_get_err_pc", return_value="")
        info = AicErrorInfo()
        info.aic_error_info["current_pc"] = "x1435"
        info.aic_error_info["start_pc"] = "x0123"
        err_pc = getattr(parser, "_get_info_for_decompile")(info)
        self.assertEqual(err_pc, "")

    def test_get_err_pc_display_with_0x_prefix(self, mocker):
        """展示行Error occurred most likely at line后带0x前缀，返回的err_pc保持无前缀"""
        mocker.patch(
            "ms_interface.aic_error_info.AicErrorInfo.find_extra_pc", return_value=""
        )
        parser = AicoreErrorParser("collection")
        info = AicErrorInfo()
        info.instr = ""
        err_pc = getattr(parser, "_get_err_pc")(info, 5173, 291)
        self.assertEqual(err_pc, "1312")
        self.assertIn(info.instr, "Error occurred most likely at line: 0x1312")

    def test_set_corrected_instr_display_with_0x_prefix(self, mocker):
        """corrected instr的Error occurred most likely at line后带0x前缀"""
        info = AicErrorInfo()
        info.corrected_pc = {"offset": 4470, "plog_path": ""}
        info.aic_error_info["core_id"] = "0"
        mocker.patch(
            "ms_interface.aicore_error_parser.pc_corrector.derive_core_type",
            return_value="AIV",
        )
        mocker.patch(
            "ms_interface.aicore_error_parser.pc_corrector.get_corrected_src",
            return_value=None,
        )
        mocker.patch.object(AicoreErrorParser, "_get_symbolize_o_file", return_value="")
        AicoreErrorParser._set_corrected_instr(info)
        self.assertIn(
            info.corrected_instr, "Error occurred most likely at line: 0x1176"
        )

    def test_update_err_pc_data(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = "kernel_name"
        info.node_name = "node_name"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        mocker.patch.object(utils, "get_inquire_result", return_value="111")
        res = getattr(parser, "_update_err_pc")("0x1", "", "")
        self.assertEqual(res, "2")

    def test_need_atomic_clean_ffts(self):
        info = AicErrorInfo()
        info.kernel_name = "te_assign_d623a1e1b515a45cdc8c9658e58e2860034dbfbd9ab35f92e1415a0fda9d35c1_1"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        abs_path = os.path.join(
            cur_abspath, "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/"
        )
        res = getattr(parser, "_need_atomic_clean")(abs_path, info)
        self.assertEqual(res, False)

    def test_get_sub_ptr(self):
        info = AicErrorInfo()
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        info.bin_list = ["xxx"]
        res = getattr(parser, "_get_sub_ptr")(info)
        self.assertEqual(res, {})

    @pytest.mark.skip
    def test_read_decompile_file(self):
        info = AicErrorInfo()
        info.kernel_name = "te_assign_d623a1e1b515a45cdc8c9658e58e2860034dbfbd9ab35f92e1415a0fda9d35c1_1"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        abs_path = os.path.join(
            cur_abspath,
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1.cce",
        )
        res = getattr(parser, "_read_decompile_file")(abs_path, "", info)
        self.assertEqual(res, "")

    def test_get_kernel_and_json_file(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        res = getattr(parser, "_get_kernel_and_json_file")("kernel_name", "tiling_key")
        self.assertEqual(res, None)

    def test_get_kernel_and_json_file_in_collect_path(self, mocker):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/no_cce/asys_aicerror")
        )
        json_path = os.path.join(
            cur_abspath,
            "../res/ori_data/no_cce/asys_aicerror/asys_output_20250508095626087/dfx/ops/GatherV3_9e31943a1a48bf81ddff1fc6379e0be3_high_performance.json",
        )
        o_path_out_collection = os.path.join(
            cur_abspath,
            "../res/ori_data/asys_output_20230713074104794/dfx/ops/0/te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1.o",
        )
        mocker.patch.object(
            utils, "get_inquire_result", return_value=[json_path, o_path_out_collection]
        )
        res = getattr(parser, "_get_kernel_and_json_file")(
            "GatherV3_9e31943a1a48bf81ddff1fc6379e0be3_high_performance", "tiling_key"
        )
        self.assertEqual(res.json_file != "", True)
        self.assertEqual(res.bin_file == "", True)

    @pytest.mark.skip
    def test_parse(self, mocker):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        info = AicErrorInfo()
        info.aic_error_info["err_time"] = "2024-06-22-07:15:34.158.818"
        info.tiling_data_bytes = "data tiling".encode("utf-8")
        info.bin_file = "xxx.bin"
        mocker.patch.object(parser, "add_objdump_to_path", return_value=None)
        mocker.patch.object(parser, "check_plog_info", return_value=1)
        mocker.patch.object(parser, "get_op_info", return_value=info)
        mocker.patch.object(parser, "check_dump_result", return_value=True)
        mocker.patch.object(
            parser, "_test_single_op", return_value=[False, "11", "single_op"]
        )
        mocker.patch.object(parser, "check_hash_id", return_value=True)
        mocker.patch.object(DumpDataParser, "parse", return_value="")
        res = parser.parse()
        self.assertEqual(res, 101)

    def test_check_dump_result_dump_fail(self):
        info = AicErrorInfo()
        dfx_message = ""
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, False)

    def test_check_dump_result_dump_noffts_fail(self):
        info = AicErrorInfo()
        dfx_message = ""
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/notffts/")
        )
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, False)

    def test_check_dump_result_invalid_addr(self):
        info = AicErrorInfo()
        dfx_message = "[Dump][Exception] the address maybe invalid"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, False)

    def test_check_dump_result_valid(self):
        info = AicErrorInfo()
        dfx_message = "[Dump][Exception] begin to load normal tensor, index:1"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, True)

    @pytest.mark.parametrize(
        "grep_result, result, key_log",
        [
            (
                [[], [("node", "stream", "task")], ["hash"]],
                None,
                "[AIC_INFO] dev_func:",
            ),
            ([["kernel"], [], ["hash"]], None, "Failed to get node name"),
            (
                [["kernel"], [("node", "stream", "task")], []],
                None,
                "Cannot get hash id in plog",
            ),
        ],
    )
    def test_get_node_and_kernel_name_l1_failed(
        self, mocker, grep_result, result, key_log
    ):
        mocker.patch.object(utils, "get_inquire_result", side_effect=grep_result)
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts1/")
        )
        res = parser.get_node_and_kernel_name_l1()
        self.assertEqual(res, result)
        self.assertIn(utils.ExceptionRootCause().format_causes(), key_log)

    def test_get_node_and_kernel_name_l1_noffts(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/notffts/")
        )
        res = parser.get_node_and_kernel_name_l1()
        self.assertEqual(res[0], "2")

    def test_get_node_and_kernel_name_l1_not_hash(self):
        utils.ExceptionRootCause().causes = []
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/hash_check/")
        )
        res = parser.get_node_and_kernel_name_l1()
        self.assertEqual(
            "Cannot get hash id in plog" in utils.ExceptionRootCause().format_causes(),
            True,
        )
        self.assertEqual(res, None)

    def test_not_get_dump_data_info_L0_data(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/hash_check")
        )
        parser.parse_level = 0
        with pytest.raises(utils.AicErrException) as error:
            parser.get_dump_data_info()
        self.assertEqual(error.value.args[0], Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_not_get_dump_data_info_L1_data(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/hash_check")
        )
        parser.parse_level = 1
        with pytest.raises(utils.AicErrException) as error:
            parser.get_dump_data_info()
        self.assertEqual(error.value.args[0], Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_check_hash_id(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/notffts/")
        )
        res = parser.check_hash_id(
            "15656883929986130445",
            os.path.join(
                cur_abspath,
                "../res/ori_data/collect/notffts/collection/plog/plog-370_20230713074107861.log",
            ),
        )
        self.assertEqual(res, True)

    def test_check_hash_id_1_failed(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/notffts/")
        )
        res = parser.check_hash_id(
            "1565688392998613",
            os.path.join(
                cur_abspath,
                "../res/ori_data/collect/notffts/collection/plog/plog-370_20230713074107861.log",
            ),
        )
        self.assertEqual(res, False)

    def test_check_hash_id_2_failed(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        res = parser.check_hash_id(
            "1565688392998613",
            os.path.join(
                cur_abspath,
                "../res/ori_data/collect/ffts/collection/plog/test_hash_id.log",
            ),
        )
        self.assertEqual(res, False)

    def test_test_single_op(self, mocker):
        # 用例进程正常退出(0)且日志无 aicore error，才算单算子执行成功。
        mocker.patch(
            "subprocess.run", return_value=Mock(returncode=0, stdout=b"", stderr=b"")
        )
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        info = AicErrorInfo()
        res = getattr(parser, "_test_single_op")(info, "", "temp_dir", "single_op")
        self.assertEqual(res[0], RetCode.SUCCESS)

    def test_test_single_op_subprocess_failed(self, mocker):
        # 用例进程非 0 退出、日志里也没有 aicore error：用例没真正跑起来，
        # 不能按执行成功上报，也不能误判为已复现（否则掩盖依赖缺失/语法错误等真实原因）。
        mocker.patch(
            "subprocess.run",
            return_value=Mock(
                returncode=1,
                stdout=b"",
                stderr=b"ModuleNotFoundError: No module named tbe",
            ),
        )
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        info = AicErrorInfo()
        res = getattr(parser, "_test_single_op")(info, "", "temp_dir", "single_op")
        self.assertEqual(res[0], RetCode.NOT_RUN)

    @pytest.mark.parametrize(
        "returncode, stdout_text, expect",
        [
            # 子进程非 0 退出 + 日志无 aicore error → NOT_RUN（进程崩溃/依赖缺失）
            (1, b"", RetCode.NOT_RUN),
            # 子进程非 0 退出 + stdout 含 NOT_RUN 标记 → NOT_RUN
            (1, b"exec single op case failed.\r\n", RetCode.NOT_RUN),
            (
                1,
                b"Execute single op case failed, please check testcase file.\n",
                RetCode.NOT_RUN,
            ),
            # 子进程 0 退出 + stdout 含 NOT_RUN 标记 → NOT_RUN（launch 失败但进程正常退出）
            (0, b"exec single op case failed.\r\n", RetCode.NOT_RUN),
            # 子进程 0 退出 + 日志无 aicore error + stdout 无 NOT_RUN 标记 → SUCCESS
            (0, b"exec single op case success.\r\n", RetCode.SUCCESS),
        ],
    )
    def test_test_single_op_not_run(self, mocker, returncode, stdout_text, expect):
        parser = AicoreErrorParser("")
        info = AicErrorInfo()
        info.kernel_name = "AddCustom_1"
        mocker.patch.object(
            AicoreErrorParser,
            "_AicoreErrorParser__generate_case",
            return_value=str(self.temp.joinpath("case.py")),
        )
        mocker.patch.object(AicoreErrorParser, "comment_cce_in_case")
        mocker.patch.object(AicoreErrorParser, "print_single_op_result")
        mocker.patch.object(AicoreErrorParser, "search_aicerr_log", return_value=False)
        mocker.patch("ms_interface.aicore_error_parser.SingleOpCase")
        mocker.patch(
            "subprocess.run",
            return_value=Mock(returncode=returncode, stdout=stdout_text, stderr=b""),
        )
        res = parser._test_single_op(info, str(self.temp), "temp_dir", "single_op")
        self.assertEqual(res[0], expect)

    def test_get_extra_info(self):
        aic_error = "vec error info: 0x51000070f7, mte error info: 0x500300004d, ifu error info: 0x29883d2080000, ccu error info: 0x22c090001000046, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c1c0000400."
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        res = getattr(parser, "_get_extra_info")(aic_error)
        data = "extra info:\nIFU_ERR_INFO=0x29883d2080000\nCCU_ERR_INFO=0x22c090001000046\nBIU_ERR_INFO=0\nCUBE_ERR_INFO=0\nMTE_ERR_INFO=0x500300004d\nVEC_ERR_INFO=0x51000070f7\n"
        self.assertEqual(res, data)

    def test_get_extra_info_error(self):
        aic_error = "mte error info: 0x500300004d, ccu error info: 0x22c090001000046, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c1c0000400."
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        res = getattr(parser, "_get_extra_info")(aic_error)
        data = "extra info:\nCCU_ERR_INFO=0x22c090001000046\nBIU_ERR_INFO=0\nCUBE_ERR_INFO=0\nMTE_ERR_INFO=0x500300004d\n"
        self.assertEqual(res, data)

    def test_get_op_info(self, mocker):
        os.environ["LD_LIBRARY_PATH"] = os.environ.get("LD_LIBRARY_PATH", "") + "./"
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect_milan")
        )
        mocker.patch.object(parser, "collect_driver_aicore_number", return_value=1)
        info = parser.get_op_info()
        self.assertIn("AddCustom_ab1b6750d7f510985325b603cb06dc8b_0", info.kernel_name)

    def test_get_tiling_data_None(self, mocker):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect_milan")
        )
        mocker.patch.object(parser, "_get_aic_info", return_value="[AIC_INFO] aaa: 0")
        self.assertEqual(getattr(parser, "_get_tiling_data_l1")("a"), "")

    def test_get_tiling_data_value(self, mocker):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect_milan")
        )
        mocker.patch.object(
            parser, "_get_aic_info", return_value="[AIC_INFO] tiling_data:0x0001"
        )
        self.assertEqual(
            getattr(parser, "_get_tiling_data_l1")("a"), bytes.fromhex("0001")
        )

    def test_get_tiling_data_other(self, mocker):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect_milan")
        )
        mocker.patch.object(
            parser, "_get_aic_info", return_value="[AIC_INFO] tiling_data:1"
        )
        self.assertEqual(
            getattr(parser, "_get_tiling_data_l1")("a"), bytes("1", "utf-8")
        )

    def test_get_tiling_data(self, mocker):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect_milan")
        )
        mocker.patch.object(TilingDataParser, "parse", return_value=b"0x1")
        tiling_data = parser.get_tiling_data("a")
        self.assertEqual(tiling_data, b"0x1")

    def test_tiling_data_success(self):
        info = AicErrorInfo()
        info.kernel_path = self.temp
        info.tiling_data_bytes = b"0x1"
        info.kernel_name = "test"
        parser = AicoreErrorParser("")
        parser.write_tiling_data_to_file(info)
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"), "Tiling data is saved to"
        )

    @pytest.mark.parametrize(
        "test_single_mock, dump_result, expect_log_level",
        [
            ([(RetCode.SUCCESS, "", ""), (RetCode.FAILED, "", "")], True, "info"),
            (
                [
                    (RetCode.SUCCESS, "", ""),
                    (RetCode.SUCCESS, "", ""),
                    (RetCode.SUCCESS, "", ""),
                ],
                True,
                "debug",
            ),
        ],
    )
    def test_run_single_operator(
        self, mocker, test_single_mock, dump_result, expect_log_level
    ):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        info = AicErrorInfo()
        info.data_dump_result = dump_result
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("shutil.rmtree", return_value=None)
        info_mock = mocker.patch("ms_interface.utils.print_info_log")
        debug_mock = mocker.patch("ms_interface.utils.print_debug_log")
        warn_mock = mocker.patch("ms_interface.utils.print_warn_log")
        mocker.patch.object(AicoreErrorParser, "check_hash_id", return_value=True)
        mocker.patch.object(
            AicoreErrorParser, "_find_sk_host_o", return_value="kernel_host.o"
        )
        mocker.patch.object(
            AicoreErrorParser, "_test_single_op", side_effect=test_single_mock
        )
        parser.run_single_operator(info, "err_i_folder")
        if expect_log_level == "debug":
            self.assertEqual(debug_mock.call_count, 1)
        elif expect_log_level == "info":
            self.assertEqual(info_mock.call_count, 2)
        elif expect_log_level == "warn":
            self.assertEqual(warn_mock.call_count, 1)

    def test_run_single_operator_sk(self, mocker):
        # SK场景：只校验bin_file、只跑host_single_op，跳过device单算子测试
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        parser.is_sk = True
        info = AicErrorInfo()
        info.data_dump_result = True
        info.json_file = ""
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("shutil.rmtree", return_value=None)
        mocker.patch.object(AicoreErrorParser, "check_hash_id", return_value=True)
        mocker.patch.object(
            AicoreErrorParser, "_find_sk_host_o", return_value="kernel_host.o"
        )
        single_op_mock = mocker.patch.object(
            AicoreErrorParser, "_test_single_op", return_value=(RetCode.SUCCESS, "", "")
        )
        parser.run_single_operator(info, "err_i_folder")
        # SK下只执行host_single_op一次，device single_op/error_single_op被跳过
        self.assertEqual(single_op_mock.call_count, 1)
        self.assertEqual(single_op_mock.call_args[0][3], "host_single_op")

    def test_run_single_operator_sk_no_host_o(self, mocker):
        # SK场景：bin_file不存在时跳过单算子执行
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        parser.is_sk = True
        info = AicErrorInfo()
        info.bin_file = ""
        info.json_file = ""
        mocker.patch("shutil.rmtree", return_value=None)
        info_mock = mocker.patch("ms_interface.utils.print_info_log")
        single_op_mock = mocker.patch.object(
            AicoreErrorParser, "_test_single_op", return_value=(RetCode.SUCCESS, "", "")
        )
        parser.run_single_operator(info, "err_i_folder")
        single_op_mock.assert_not_called()
        self.assertIn(str(info_mock.call_args_list), "Skip exec single op case")

    @pytest.mark.parametrize(
        "cce_exist, content, result",
        [
            (False, "", "Ascend910B2"),
            (True, "//soc_version xxx", "Ascend910B2"),
            (True, '//soc_version Ascend310B"', "Ascend310B1"),
            (True, '//soc_version Ascend910B"', "Ascend910B"),
            (True, '//soc_version Ascend910B1"', "Ascend910B1"),
        ],
    )
    def test_get_soc_version_from_cce(
        self, mocker, cce_exist, content, result, tmp_path
    ):
        mocker.patch("os.path.isfile", return_value=cce_exist)
        mocker.patch.object(Path, "read_text", return_value=content)
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        res = parser.get_soc_version_from_cce(str(tmp_path / "cce.txt"))
        self.assertEqual(res, result)

    def test_aicerr_regexp(self):
        log = "RUNTIME(200280,python3):2025-07-07-10:12:17.088.944 [device_error_core_proc.cc:314]201695 ProcessStarsCoreErrorInfo:[EXEC][EXEC]The error from device(chipId:0, dieId:0), serial number is 31, there is an exception of aivec error, core id is 36, error code = 0, dump info: pc start: 0x12400001638c, current: 0x1240000167bc, vec error info: 0x6106ff4758, mte error info: 0x302aa40, ifu error info: 0x2000017df8400, ccu error info: 0x482a21100000000, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12d0c0000800."
        aic_err_ret = utils.regexp_match_dict(RegexPattern.AICORE_ERR_OCCUR, log)
        assert aic_err_ret != []
        aic_err_map = aic_err_ret[0]
        self.assertEqual(aic_err_map["err_time"], "2025-07-07-10:12:17.088.944")
        self.assertEqual(aic_err_map["dev_id"], "chipId:0, dieId:0")
        self.assertEqual(aic_err_map["thread_id"], "201695")
        self.assertEqual(aic_err_map["core_id"], "36")
        self.assertEqual(aic_err_map["core_err_type"], "aivec")
        self.assertEqual(aic_err_map["error_code"], "0")
        self.assertEqual(aic_err_map["start_pc"], "0x12400001638c")
        self.assertEqual(aic_err_map["current_pc"], "0x1240000167bc")
        self.assertEqual(
            aic_err_map["extra_info"],
            "vec error info: 0x6106ff4758, mte error info: 0x302aa40, ifu error info: 0x2000017df8400, ccu error info: 0x482a21100000000, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12d0c0000800.",
        )

    @pytest.mark.parametrize(
        "log, expected_type",
        [
            (
                "RUNTIME(8953,None):2020-12-24-01:10:54.176.179 [../../../../../../runtime/feature/src/"
                "device_error_proc.cc:371]8958 ProcessCoreErrorInfo:The error from device(0), serial number "
                "is 1, there is a aicore error, core id is 0, error code = 0x10, error string = Illegal "
                "instruction. dump info: pc start: 0x108080056000, current: 0x1080800560a4, vec error "
                "info: 0x3e27677, mte error info: 0x21, ifu error info: 0x13b023938000, ccu error info: "
                "0x3227004600001721, cube error info: 0x3e, biu error info: 0x0, aic error mask: "
                "0x6de01200d0122c8, para base: 0x10808001a000.",
                "aicore",
            ),
            (
                "RUNTIME(1592077,python3):2024-09-12-16:40:07.362.023 [device_error_proc.cc:1402]1592077 "
                "ProcessStarsCoreErrorInfo:[INIT][DEFAULT]The error from device(chipId:0, dieId:0), serial "
                "number is 87, there is an fftsplus aivector error exception, core id is 0, error code = 0, "
                "dump info: pc start: 0x12c042d73754, current: 0x12c042d75b18, vec error info: "
                "0x99000000a2, mte error info: 0x5003000031, ifu error info: 0x200000007ffc0, ccu error "
                "info: 0x280d00000084, cube error info: 0, biu error info: 0, aic error mask: "
                "0x6500020bd00028c, para base: 0x12c040569000.",
                "aivector",
            ),
            (
                "RUNTIME(588579,execute_add_op):2025-04-02-07:19:26.376.560 [device_error_proc.cc:1434]"
                "588579 ProcessStarsCoreErrorInfo:The error from device(chipId:0, dieId:0), serial number "
                "is 48, there is an aivec error exception, core id is 16, error code = 0x200000000, dump "
                "info: pc start: 0x12c0c002e000, current: 0x12c0c002e5e8, vec error info: 0x51000070f7, "
                "mte error info: 0xb90000006a, ifu error info: 0x29883d2080000, ccu error info: "
                "0xc791c207288000f7, cube error info: 0, biu error info: 0, aic error mask: "
                "0x6500020bd00028c, para base: 0x12c100010000.",
                "aivec",
            ),
            (
                "RUNTIME(200280,python3):2025-07-07-10:12:17.088.944 [device_error_proc_c.cc:659]201695 "
                "ProcessDavidStarsCoreErrorInfo:[EXEC][EXEC]An error occurs on the device(chipId:0, "
                "dieId:0), the serial number is 31, the error is aicore error, core id is 36, error code "
                "= 64, 78, dump info: pc start: 0x12400001638c, current: 0x1240000167bc, sc error info: "
                "0x0, su error info: 0x0,0x0, mte error info: 0x1, vec error info: 0x0, cube error info: "
                "0x0, l1 error info: 0x0, aic error mask: 0x0, para base: 0x12d0c0000800, mte error: "
                "0x1, aic cond: 0x0.",
                "aicore",
            ),
            (
                "RUNTIME(8953,None):2020-12-24-01:10:54.176.179 [../../../../../../runtime/feature/src/"
                "device_error_proc.cc:371]8958 ProcessCoreErrorInfo:The error from device(0), serial "
                "number is 1, there is an exception, core id is 0, error code = 0x10, error string = "
                "Illegal instruction. dump info: pc start: 0x108080056000, current: 0x1080800560a4, vec "
                "error info: 0x3e27677, mte error info: 0x21, ifu error info: 0x13b023938000, ccu error "
                "info: 0x3227004600001721, cube error info: 0x3e, biu error info: 0x0, aic error mask: "
                "0x6de01200d0122c8, para base: 0x10808001a000.",
                None,
            ),
        ],
    )
    def test_aicerr_regexp_core_err_type(self, log, expected_type):
        aic_err_ret = utils.regexp_match_dict(RegexPattern.AICORE_ERR_OCCUR, log)
        assert aic_err_ret != []
        self.assertEqual(aic_err_ret[0]["core_err_type"], expected_type)
        assert aic_err_ret[0]["core_id"] is not None

    def test_get_ffts_addrs_num(self):
        parser = AicoreErrorParser(
            os.path.join(cur_abspath, "../res/ori_data/collect/ffts/")
        )
        self.assertEqual(parser.get_ffts_addrs_num(), 1)

    def test_get_return_code(self):
        aic_info = AicErrorInfo()
        aic_info.atomic_clean_check = False
        aic_info.atomic_add_err = True
        aic_info.single_op_test_result = RetCode.FAILED
        aic_info.dump_info = "data invalid"
        aic_info.check_args_result = False
        aic_info.data_dump_result = False
        aic_info.env_available = False
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info),
            Constant.MS_AICERR_FRAMEWORK_MEMSET_MISSING,
        )
        aic_info.atomic_clean_check = True
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info),
            Constant.MS_AICERR_ATOMIC_OPERATOR_OVERFLOW,
        )
        aic_info.atomic_add_err = False
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info),
            Constant.MS_AICERR_OPERATOR_INPUT_DATA_ERR,
        )
        aic_info.dump_info = ""
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info),
            Constant.MS_AICERR_OPERATOR_ARGS_OVERWRITTEN,
        )
        aic_info.check_args_result = True
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info),
            Constant.MS_AICERR_MEMORY_ALLOCATION_ERR,
        )
        aic_info.data_dump_result = True
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info),
            Constant.MS_AICERR_SINGLE_OP_ERR,
        )
        aic_info.single_op_test_result = RetCode.SUCCESS
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info), Constant.MS_AICERR_HARDWARE_ERR
        )
        aic_info.env_available = True
        self.assertEqual(
            AicoreErrorParser.get_return_code(aic_info), Constant.MS_AICERR_NONE_ERROR
        )

    @pytest.mark.parametrize(
        "plog_content, result",
        [
            ("AtomicLaunchKernelWithFlag_test", True),
            ("AtomicLaunchKernelWithFlag_aaaa", False),
        ],
    )
    def test_check_atomic_clean(self, plog_content, result):
        aic_info = AicErrorInfo()
        aic_info.node_name = "test"
        aic_info.kernel_name = "test"
        self.temp.joinpath(f"{aic_info.node_name}.json").write_text(
            '{"compile_info": "1","parameters": ["1", "2", "3"]}', encoding="utf-8"
        )
        self.temp.joinpath("test.plog").write_text(plog_content, encoding="utf-8")
        parser = AicoreErrorParser(self.temp)
        res = getattr(parser, "_check_atomic_clean")(str(self.temp), aic_info)
        self.assertEqual(res, result)

    @pytest.mark.parametrize(
        "log_content, kernel_name, result",
        [
            ("there is an aivec error exception,  test_mix_aic", "test_mix_aic", True),
            ("there is an aicore error exception,  test_mix_aic", "test_mix_aic", True),
            (
                "there is an exception of aivec error,  test_mix_aic",
                "test_mix_aic",
                True,
            ),
            (
                "there is an exception of aicore error,  test_mix_aic",
                "test_mix_aic",
                True,
            ),
            ("aicore exception,  test_mix_aic", "test_mix_aic", True),
            ("there is an aivec error exception,  aaa_mix_aic", "test_mix_aic", False),
            ("there is not error exception,  test_mix_aic", "test_mix_aic", False),
        ],
    )
    def test_search_aicerr_log(self, log_content, kernel_name, result):
        self.temp.joinpath("test.log").write_text(log_content, encoding="utf-8")
        parser = AicoreErrorParser(self.temp)
        self.assertEqual(parser.search_aicerr_log(kernel_name, self.temp), result)

    def test_get_tiling_l0_ffts(self, mocker):
        log = "[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07.362.023 [device_error_proc.cc:1402]1592077 ProcessStarsCoreErrorInfo:[INIT][DEFAULT]The error from device(chipId:0, dieId:0), serial number is 87, there is an fftsplus aivector error exception, core id is 0, error code = 0, dump info: pc start: 0x12c042d73754, current: 0x12c042d75b18, vec error info: 0x99000000a2, mte error info: 0x5003000031, ifu error info: 0x200000007ffc0, ccu error info: 0x280d00000084, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c040569000."
        mocker.patch("ms_interface.utils.execute_command", return_value=("", log))
        parser = AicoreErrorParser("")
        mocker.patch.object(parser, "ffts_flag", True)
        res = getattr(parser, "_get_tiling_l0")()
        self.assertEqual(res, (0, 0))

    def test_get_tiling_l1_success(self, mocker):
        log = (
            r"[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.111 [dump_operator.cpp:139][tid:201695] [AIC_INFO] dev_func:GatherV2_daad10a93d32be95786cd6e84e734751_high_precision"
            r"[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.126 [dump_operator.cpp:139][tid:201695] [AIC_INFO] tiling_key:900016000"
            r"[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.126 [dump_operator.cpp:139][tid:201695] [AIC_INFO] tiling_key:900016000"
            r"[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.126 [dump_operator.cpp:139][tid:201695] [AIC_INFO] tiling_key:900016000"
            r"[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.088 [dump_operator.cpp:139][tid:201695] [AIC_INFO] block_dim:1"
        )
        mocker.patch("ms_interface.utils.execute_command", return_value=(0, log))
        parser = AicoreErrorParser("")
        res = getattr(parser, "_get_tiling_l1")(
            "GatherV2_daad10a93d32be95786cd6e84e734751_high_precision"
        )
        self.assertEqual(res, (900016000, 1))

    def test_add_objdump_to_path(self, mocker):
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("shutil.which", return_value="")
        with pytest.raises(utils.AicErrException):
            AicoreErrorParser.add_objdump_to_path()
        self.assertIn(
            self.debug_info.read_text(encoding="utf-8"),
            "Cannot find cce-objdump! please add cce-objdump path in env PATH",
        )

    def test_get_data_dump_result(self, mocker):
        mocker.patch(
            "ms_interface.utils.execute_command",
            side_effect=[(1, ""), (1, ""), (1, "")],
        )
        parser = AicoreErrorParser("")
        self.assertEqual(getattr(parser, "_get_data_dump_result")(), True)

        mocker.patch(
            "ms_interface.utils.execute_command",
            side_effect=[(1, ""), (0, ""), (0, "")],
        )
        self.assertEqual(getattr(parser, "_get_data_dump_result")(), False)

    def test_decompile(self, mocker):
        parser = AicoreErrorParser("")
        parser.parse_level = 1
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("ms_interface.utils.copy_src_to_dest", return_value=None)
        mocker.patch.object(parser, "_get_decompile_status", return_value=0)
        info = AicErrorInfo()
        info.bin_file = str(
            ori_data_path.joinpath(
                "decompile_with_o/GatherV2_daad10a93d32be95786cd6e84e734751_high_precision.o"
            )
        )
        self.assertEqual(getattr(parser, "_decompile")("", "", info), False)

    def test_get_kernel_and_json_file_sk(self):
        # SK场景：bin_file指向<kernel_name>*_host.o，json/cce为空
        kernel_name = "Add_sk_kernel_900016000"
        compile_path = self.temp.joinpath("collection/compile")
        compile_path.mkdir(parents=True, exist_ok=True)
        host_file = compile_path.joinpath(f"{kernel_name}_xxx_host.o")
        host_file.touch()
        parser = AicoreErrorParser(str(self.temp))
        parser.is_sk = True
        kernel_file = getattr(parser, "_get_kernel_and_json_file")(kernel_name, "0")
        self.assertEqual(kernel_file.bin_file, str(host_file))
        self.assertEqual(kernel_file.json_file, "")
        self.assertEqual(kernel_file.cce_file, "")

    def test_decompile_sk_only_host_o(self, mocker):
        # SK场景：只反编译host.o，跳过L1的cce/tbe行号匹配，直接返回True
        parser = AicoreErrorParser("")
        parser.parse_level = 1
        parser.is_sk = True
        mocker.patch("os.path.exists", return_value=True)
        copy_mock = mocker.patch(
            "ms_interface.utils.copy_src_to_dest", return_value=None
        )
        mocker.patch.object(parser, "_get_decompile_status", return_value=0)
        info = AicErrorInfo()
        info.bin_file = str(
            ori_data_path.joinpath(
                "decompile_with_o/GatherV2_daad10a93d32be95786cd6e84e734751_high_precision.o"
            )
        )
        self.assertEqual(getattr(parser, "_decompile")("", "", info), True)
        # SK下只复制host.o一个文件
        copy_mock.assert_called_once_with([info.bin_file], "")

    def test_get_v300_error_code(self):
        parser = AicoreErrorParser("")
        parser.collect_path = str(ori_data_path.joinpath("collect_milan"))
        self.assertEqual(getattr(parser, "_get_v300_error_code")(), "0x200000000")

    @pytest.mark.parametrize(
        "get_dump_data_info, get_inquire_result, execute_command, log_res",
        [
            (
                [("1", "data_name")],
                [],
                ["", ""],
                "Aicore error exception does not match",
            ),
            (
                [("1", "data_name")],
                [{"thread_id": "2"}],
                ["", ""],
                "Dump data tid is not the same with rts tid.",
            ),
            (
                [("1", "data_name")],
                [{"thread_id": "1"}],
                ["aa", "aa"],
                "Get runtime block_dim failed",
            ),
        ],
    )
    def test_get_op_info_failed(
        self, mocker, get_dump_data_info, get_inquire_result, execute_command, log_res
    ):
        parser = AicoreErrorParser("")
        mocker.patch.object(
            parser, "get_dump_data_info", return_value=get_dump_data_info
        )
        mocker.patch(
            "ms_interface.utils.get_inquire_result", return_value=get_inquire_result
        )
        mocker.patch("ms_interface.utils.execute_command", return_value=execute_command)
        parser.get_op_info()
        self.assertIn(self.debug_info.read_text(encoding="utf-8"), log_res)

    def test_collect_driver_aicore_number_filed(self, mocker):
        self.assertEqual(True, True)
        parser = AicoreErrorParser("")

        class SelflibCoreNumOne:
            @staticmethod
            def rtGetAiCoreCount(_driver_core_num):
                return 1

        mocker.patch("ms_interface.aicore_error_parser._find_runtime_so")
        mocker.patch("ctypes.cdll.LoadLibrary", return_value=SelflibCoreNumOne())
        try:
            parser.collect_driver_aicore_number()
        except utils.AicErrException as e:
            self.assertEqual(
                str(e), "[10] failed to get the AI Core number from the driver"
            )
        else:
            self.assertEqual(False, True)

    def test_outstanding_complex_scenario(self, mocker):
        parser = AicoreErrorParser("")
        task_info = [
            ("3800", "5", "62", "7", "62", "0"),
            ("3800", "2", "62", "7", "62", "0"),
            ("3800", "5", "62", "2", "62", "1"),
        ]
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("ms_interface.utils.execute_command", return_value=(0, ""))
        mocker.patch("re.findall", return_value=task_info)
        result = parser.get_is_concurrentexe_value("")
        self.assertIn(self.debug_info.read_text(encoding="utf-8"), "3 tasks detected")
        self.assertEqual(result, {})
