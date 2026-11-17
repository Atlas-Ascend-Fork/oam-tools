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

import datetime
import sys

import numpy as np

from conftest import MSAICERR_PATH
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.constant import Constant, RetCode

sys.path.append(MSAICERR_PATH)

# private members reached by name to avoid direct protected-member access
CAL_SHAPE_SIZE = "_cal_shape_size"
CHECK_ADDR_IN_RANGE = "_check_addr_in_range"
GEN_CASE = "_AicoreErrorParser__generate_case"
CHECK_ARGS = "_check_args"


def _make_info(**kwargs):
    info = AicErrorInfo()
    info.atomic_clean_check = True
    info.atomic_add_err = False
    info.dump_info = ""
    info.check_args_result = True
    info.data_dump_result = True
    info.single_op_test_result = RetCode.SUCCESS
    info.env_available = True
    for key, value in kwargs.items():
        setattr(info, key, value)
    return info


def _mocked_parser(mocker, info=None, collect_succ=True):
    parser = AicoreErrorParser("/collect", collect_succ=collect_succ)
    for name in (
        "add_objdump_to_path",
        "check_plog_info",
        "_write_errorinfo_file",
        "_write_summary_file",
        "run_single_operator",
        "write_tiling_data_to_file",
    ):
        mocker.patch.object(parser, name)
    mocker.patch.object(parser, "get_op_info", return_value=info)
    mocker.patch.object(parser, "_get_graph_file", return_value="graph")
    mocker.patch.object(parser, "_get_op_by_graph", return_value=True)
    mocker.patch.object(parser, "_get_args_after_exc", return_value=[1])
    mocker.patch.object(parser, "_get_args_before_exc", return_value=[1])
    mocker.patch.object(parser, "_check_args", return_value=True)
    mocker.patch.object(parser, "_decompile", return_value=True)
    mocker.patch.object(parser, "_check_atomic_clean", return_value=True)
    mocker.patch.object(parser, "_get_data_dump_result", return_value=True)
    mocker.patch.object(parser, "get_ffts_addrs_num", return_value=0)
    mocker.patch.object(parser, "_get_sub_ptr", return_value={})
    mocker.patch.object(parser, "get_workspace_info", return_value=0)
    mocker.patch.object(AicoreErrorParser, "run_test_env", return_value=True)
    mocker.patch.object(AicoreErrorParser, "get_soc_version", return_value="Ascend910B")
    mocker.patch("ms_interface.aicore_error_parser.utils.check_path_valid")
    dump_parser = mocker.MagicMock()
    dump_parser.get_input_data.return_value = []
    dump_parser.get_output_data.return_value = []
    dump_parser.get_workspace_data.return_value = []
    dump_parser.get_bin_data.return_value = []
    mocker.patch(
        "ms_interface.aicore_error_parser.DumpDataParser", return_value=dump_parser
    )
    return parser


def test_cal_shape_size_scalar():
    assert getattr(AicoreErrorParser, CAL_SHAPE_SIZE)("[]") == 1


def test_cal_shape_size_normal():
    assert getattr(AicoreErrorParser, CAL_SHAPE_SIZE)("[2,3,4]") == 24


def test_check_addr_in_range_hex_true():
    ranges = [("0x100", 0x100)]
    assert getattr(AicoreErrorParser, CHECK_ADDR_IN_RANGE)(0x110, 0x10, ranges) is True


def test_check_addr_in_range_dec_false():
    ranges = [("256", 16)]
    assert getattr(AicoreErrorParser, CHECK_ADDR_IN_RANGE)(1000, 8, ranges) is False


def test_check_addr_in_range_str_addr():
    ranges = [("0x100", 0x100)]
    assert getattr(AicoreErrorParser, CHECK_ADDR_IN_RANGE)("272", 16, ranges) is True


def test_get_workspace_info_level0():
    assert AicoreErrorParser.get_workspace_info(0, [128, 256]) == 0


def test_get_workspace_info_level1(mocker):
    mocker.patch(
        "ms_interface.aicore_error_parser.np.load",
        return_value=np.ones(4, dtype=np.float16),
    )
    assert AicoreErrorParser.get_workspace_info(1, ["w.npy"]) == 8


def test_comment_cce_in_case(mocker):
    m = mocker.mock_open(read_data='config = {"cce_file": "x"}')
    mocker.patch("builtins.open", m)
    AicoreErrorParser.comment_cce_in_case("case.py")
    assert m().write.called


def test_print_single_op_result(mocker):
    log = mocker.patch("ms_interface.utils.print_debug_log")
    AicoreErrorParser.print_single_op_result("case.py")
    assert log.called


def test_generate_case(mocker):
    mocker.patch("builtins.open", mocker.mock_open())
    result = getattr(AicoreErrorParser, GEN_CASE)({"k": "v"}, "/case", "single_op")
    assert result.endswith("test_single_op.py")


def test_get_ffts_addrs_num_none(mocker):
    parser = AicoreErrorParser("/p")
    mocker.patch("ms_interface.utils.get_inquire_result", return_value=[])
    assert parser.get_ffts_addrs_num() == 0


def test_get_ffts_addrs_num_value(mocker):
    parser = AicoreErrorParser("/p")
    mocker.patch("ms_interface.utils.get_inquire_result", return_value=["5"])
    assert parser.get_ffts_addrs_num() == 5


def test_return_code_memset_missing():
    info = _make_info(atomic_clean_check=False)
    assert (
        AicoreErrorParser.get_return_code(info)
        == Constant.MS_AICERR_FRAMEWORK_MEMSET_MISSING
    )


def test_return_code_atomic_overflow():
    info = _make_info(atomic_add_err=True)
    assert (
        AicoreErrorParser.get_return_code(info)
        == Constant.MS_AICERR_ATOMIC_OPERATOR_OVERFLOW
    )


def test_return_code_data_invalid():
    info = _make_info(dump_info="data invalid here")
    assert (
        AicoreErrorParser.get_return_code(info)
        == Constant.MS_AICERR_OPERATOR_INPUT_DATA_ERR
    )


def test_return_code_args_overwritten():
    info = _make_info(check_args_result=False)
    assert (
        AicoreErrorParser.get_return_code(info)
        == Constant.MS_AICERR_OPERATOR_ARGS_OVERWRITTEN
    )


def test_return_code_mem_alloc():
    info = _make_info(data_dump_result=False)
    assert (
        AicoreErrorParser.get_return_code(info)
        == Constant.MS_AICERR_MEMORY_ALLOCATION_ERR
    )


def test_return_code_single_op_err():
    info = _make_info(single_op_test_result=RetCode.FAILED)
    assert AicoreErrorParser.get_return_code(info) == Constant.MS_AICERR_SINGLE_OP_ERR


def test_return_code_hardware_err():
    info = _make_info(env_available=False)
    assert AicoreErrorParser.get_return_code(info) == Constant.MS_AICERR_HARDWARE_ERR


def test_return_code_none_error():
    info = _make_info()
    assert AicoreErrorParser.get_return_code(info) == Constant.MS_AICERR_NONE_ERROR


def test_parser_data_name_valid():
    stream_id, task_id = AicoreErrorParser.parser_data_name("exception_info.42.1.12345")
    assert stream_id == "42"
    assert task_id == "1"


def test_parser_data_name_too_few_parts():
    stream_id, task_id = AicoreErrorParser.parser_data_name("a.b")
    assert stream_id is None and task_id is None


def test_parser_data_name_non_numeric():
    stream_id, task_id = AicoreErrorParser.parser_data_name("exception.aa.bb.cc")
    assert stream_id is None and task_id is None


def test_scalar_register_empty_rets():
    assert AicoreErrorParser.is_scalar_register_err(1, []) is False


def test_scalar_register_in_range(mocker):
    mocker.patch("ms_interface.utils.get_str_value", return_value=300)
    rets = [{"thread_id": 1, "error_code": "0x12c"}]
    assert AicoreErrorParser.is_scalar_register_err(1, rets) is True


def test_scalar_register_out_of_range(mocker):
    mocker.patch("ms_interface.utils.get_str_value", return_value=100)
    rets = [{"thread_id": 1, "error_code": "0x64"}]
    assert AicoreErrorParser.is_scalar_register_err(1, rets) is False


def test_scalar_register_tid_mismatch(mocker):
    mocker.patch("ms_interface.utils.get_str_value", return_value=300)
    rets = [{"thread_id": 2, "error_code": "0x12c"}]
    assert AicoreErrorParser.is_scalar_register_err(1, rets) is False


def test_concurrentexe_path_not_exist(mocker):
    mocker.patch("os.path.exists", return_value=False)
    assert AicoreErrorParser.get_is_concurrentexe_value("/no/path") == {}


def test_concurrentexe_command_fail(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("ms_interface.utils.execute_command", return_value=(1, ""))
    assert AicoreErrorParser.get_is_concurrentexe_value("/p") == {}


def test_concurrentexe_no_match(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("ms_interface.utils.execute_command", return_value=(0, "nothing"))
    assert AicoreErrorParser.get_is_concurrentexe_value("/p") == {}


def test_concurrentexe_match_two_tasks(mocker):
    mocker.patch("os.path.exists", return_value=True)
    log = (
        "[file.cc:10]5 first taskid: 1 first streamid: 2 "
        "second taskid: 3 second streamid: 4 isconcurrentexe: 1"
    )
    mocker.patch("ms_interface.utils.execute_command", return_value=(0, log))
    result = AicoreErrorParser.get_is_concurrentexe_value("/p")
    assert "5" in result
    assert result["5"]["is_concurrentexe"] == "1"


def test_concurrentexe_match_too_many_tasks(mocker):
    mocker.patch("os.path.exists", return_value=True)
    log = (
        "[file.cc:10]5 first taskid: 1 first streamid: 2 "
        "second taskid: 3 second streamid: 4 isconcurrentexe: 1\n"
        "[file.cc:11]6 first taskid: 7 first streamid: 8 "
        "second taskid: 9 second streamid: 10 isconcurrentexe: 1"
    )
    mocker.patch("ms_interface.utils.execute_command", return_value=(0, log))
    assert AicoreErrorParser.get_is_concurrentexe_value("/p") == {}


def test_check_args_before_empty():
    assert getattr(AicoreErrorParser, CHECK_ARGS)([0, 0], [1, 2]) is True


def test_check_args_match():
    assert getattr(AicoreErrorParser, CHECK_ARGS)([1, 2], [2, 9]) is True


def test_check_args_no_match():
    assert getattr(AicoreErrorParser, CHECK_ARGS)([1, 2], [9]) is False


def test_kernel_info_default():
    ret = [("2", "6", "GatherV2", "123")]
    stream_id, task_id, kernel, h = AicoreErrorParser.parser_kernel_info(
        ret, None, None
    )
    assert (stream_id, task_id, kernel, h) == ("2", "6", "GatherV2", "123")


def test_kernel_info_match_by_ids():
    ret = [("2", "6", "A", "1"), ("3", "7", "B", "2")]
    kernel = AicoreErrorParser.parser_kernel_info(ret, "3", "7")[2]
    assert kernel == "B"


def test_kernel_info_with_ext_info():
    ret = [("2", "6", "node", "K0", "h0")]
    result = AicoreErrorParser.parser_kernel_info_with_ext_info(ret, None, None)
    assert result[2] == "K0"
    assert result[3] == "h0"


def test_update_dumpinfo_no_concurrent(mocker):
    parser = AicoreErrorParser("/path")
    mocker.patch.object(parser, "get_is_concurrentexe_value", return_value={})
    dump_list = [("5", "data.5")]
    err_task, dump = parser.update_dumpinfo_for_outstanding("/p", dump_list, [])
    assert err_task is None
    assert dump == ("5", "data.5")


def test_update_dumpinfo_concurrent_second_error(mocker):
    parser = AicoreErrorParser("/path")
    concur = {"5": {"first": "2.1", "second": "4.3", "is_concurrentexe": "1"}}
    mocker.patch.object(parser, "get_is_concurrentexe_value", return_value=concur)
    mocker.patch.object(parser, "is_scalar_register_err", return_value=True)
    dump_list = [("5", "stream_4.3_data")]
    err_task = parser.update_dumpinfo_for_outstanding("/p", dump_list, [{}])[0]
    assert err_task["is_second_error"] is True


def test_parse_no_info(mocker):
    parser = _mocked_parser(mocker, info=None)
    assert parser.parse() == Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR


def test_parse_collect_fail(mocker):
    parser = _mocked_parser(mocker, info=AicErrorInfo(), collect_succ=False)
    assert parser.parse() == Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR


def test_parse_full_flow(mocker):
    info = AicErrorInfo()
    info.aic_error_info = {
        "err_time": "2024-09-12-16:40:08.360.397",
        "error_code": "0x0",
        "dev_id": "0",
        "core_id": "0",
    }
    info.single_op_test_result = RetCode.SUCCESS
    parser = _mocked_parser(mocker, info=info)
    parser.parse_level = 1
    mocker.patch(
        "ms_interface.aicore_error_parser.utils.strplogtime",
        return_value=datetime.datetime(2024, 9, 12, 16, 40, 8),
    )
    mocker.patch.object(info, "analyse", return_value="result")
    assert parser.parse() == Constant.MS_AICERR_NONE_ERROR
