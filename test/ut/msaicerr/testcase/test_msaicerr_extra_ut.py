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
from unittest.mock import Mock

import pytest
import numpy as np

from conftest import MSAICERR_PATH
from ms_interface import utils
from ms_interface.constant import Constant
import msaicerr

sys.path.append(MSAICERR_PATH)


@pytest.fixture(autouse=True)
def _restore_global_result():
    # handle_exception() flips utils.GLOBAL_RESULT to False; restore it after
    # each test so the global state does not leak into later cases.
    saved = utils.GLOBAL_RESULT
    yield
    utils.GLOBAL_RESULT = saved


def _report_args(**kwargs):
    args = Mock()
    args.device_id = 0
    args.output_path = ""
    args.report_path = "/some/report"
    args.tar_file = ""
    for key, value in kwargs.items():
        setattr(args, key, value)
    return args


def _dump_args(**kwargs):
    args = Mock()
    args.data = "/dump/data.bin"
    args.output_path = ""
    args.dest_dtype = "float16"
    for key, value in kwargs.items():
        setattr(args, key, value)
    return args


def test_handle_exception_keyboard_interrupt(mocker):
    hook = mocker.patch("sys.__excepthook__")
    msaicerr.handle_exception(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert hook.called


def test_handle_exception_other(mocker):
    mocker.patch("traceback.print_exception")
    msaicerr.handle_exception(ValueError, ValueError("x"), None)
    assert utils.GLOBAL_RESULT is False


def _tar_member(name, sym=False, lnk=False, dev=False, fifo=False):
    member = Mock()
    member.name = name
    member.issym.return_value = sym
    member.islnk.return_value = lnk
    member.isdev.return_value = dev
    member.isfifo.return_value = fifo
    return member


def test_extract_tar(mocker):
    fake_tar = Mock()
    fake_tar.getmembers.return_value = [_tar_member("data/a.txt")]
    mocker.patch("tarfile.open", return_value=fake_tar)
    msaicerr.extract_tar("a.tar", "/dest")
    assert fake_tar.extractall.called
    assert fake_tar.close.called


def test_extract_tar_skips_path_traversal_and_links(mocker):
    normal = _tar_member("data/a.txt")
    escaping = _tar_member("../../etc/passwd")
    symlink = _tar_member("data/evil", sym=True)
    hardlink = _tar_member("data/evil2", lnk=True)
    fake_tar = Mock()
    fake_tar.getmembers.return_value = [normal, escaping, symlink, hardlink]
    mocker.patch("tarfile.open", return_value=fake_tar)
    msaicerr.extract_tar("a.tar", "/dest")
    # 只有目标目录内的普通文件被解压，逃逸成员与链接类成员全部丢弃。
    assert fake_tar.extractall.call_args.kwargs["members"] == [normal]
    assert fake_tar.close.called


def test_extract_tar_skips_absolute_path_and_special_files(mocker):
    normal = _tar_member("data/a.txt")
    absolute = _tar_member("/etc/passwd")
    device = _tar_member("data/dev_node", dev=True)
    fifo = _tar_member("data/pipe", fifo=True)
    fake_tar = Mock()
    fake_tar.getmembers.return_value = [normal, absolute, device, fifo]
    mocker.patch("tarfile.open", return_value=fake_tar)
    msaicerr.extract_tar("a.tar", "/dest")
    # 绝对路径成员会落到 /dest 之外，设备节点/FIFO 不是采集数据的正常内容，均丢弃。
    assert fake_tar.extractall.call_args.kwargs["members"] == [normal]


def test_get_select_dir_single(mocker):
    mocker.patch("os.listdir", return_value=["only"])
    assert msaicerr.get_select_dir("/p").endswith("only")


def test_get_select_dir_multiple(mocker):
    mocker.patch("os.listdir", return_value=["a", "b"])
    with pytest.raises(ValueError):
        msaicerr.get_select_dir("/p")


def test_is_sub_path_true():
    assert msaicerr.is_sub_path("/a/b/c", "/a/b") is True


def test_is_sub_path_false():
    assert msaicerr.is_sub_path("/a/b", "/x/y") is False


def test_is_sub_path_value_error(mocker):
    mocker.patch("os.path.commonpath", side_effect=ValueError)
    assert msaicerr.is_sub_path("/a", "/b") is False


def test_verify_device_id_valid(mocker):
    dsmi = Mock()
    dsmi.get_device_count.return_value = 8
    mocker.patch("msaicerr.DSMIInterface", return_value=dsmi)
    assert msaicerr.verify_device_id(0) is True


def test_verify_device_id_negative(mocker):
    dsmi = Mock()
    dsmi.get_device_count.return_value = 8
    mocker.patch("msaicerr.DSMIInterface", return_value=dsmi)
    assert msaicerr.verify_device_id(-1) is False


def test_verify_device_id_too_large(mocker):
    dsmi = Mock()
    dsmi.get_device_count.return_value = 8
    mocker.patch("msaicerr.DSMIInterface", return_value=dsmi)
    assert msaicerr.verify_device_id(8) is False


def test_check_device_valid_true(mocker):
    mocker.patch("msaicerr.verify_device_id", return_value=True)
    assert msaicerr.check_device_valid(0) is True


def test_check_device_valid_false(mocker):
    mocker.patch("msaicerr.verify_device_id", return_value=False)
    assert msaicerr.check_device_valid(99) is False


def test_analyse_invalid_device(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=False)
    ret = msaicerr.analyse_report_path(_report_args())
    assert ret == Constant.MS_AICERR_INVALID_PARAM_ERROR


def test_analyse_subpath_error(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch("msaicerr.is_sub_path", return_value=True)
    ret = msaicerr.analyse_report_path(_report_args())
    assert ret == Constant.MS_AICERR_INVALID_PATH_ERROR


def test_analyse_full_flow(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch("msaicerr.is_sub_path", return_value=False)
    mocker.patch("ms_interface.utils.check_path_valid")
    collection = Mock()
    collection.collect.return_value = True
    mocker.patch("msaicerr.Collection", return_value=collection)
    parser = Mock()
    parser.parse.return_value = Constant.MS_AICERR_NONE_ERROR
    mocker.patch("msaicerr.AicoreErrorParser", return_value=parser)
    ret = msaicerr.analyse_report_path(_report_args())
    assert ret == Constant.MS_AICERR_NONE_ERROR


def test_analyse_aic_exception(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch("msaicerr.is_sub_path", return_value=False)
    mocker.patch(
        "ms_interface.utils.check_path_valid",
        side_effect=utils.AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR),
    )
    ret = msaicerr.analyse_report_path(_report_args())
    assert ret == Constant.MS_AICERR_INVALID_PATH_ERROR


def test_convert_dump_invalid_path(mocker):
    mocker.patch(
        "ms_interface.utils.check_path_valid",
        side_effect=utils.AicErrException(Constant.MS_AICERR_INVALID_PATH_ERROR),
    )
    ret = msaicerr.convert_dump_data(_dump_args(), "/dump/data.bin")
    assert ret == Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR


def test_convert_dump_with_output_path(mocker):
    mocker.patch("ms_interface.utils.check_path_valid")
    mocker.patch("msaicerr.DumpDataParser", return_value=Mock())
    ret = msaicerr.convert_dump_data(_dump_args(output_path="/out"), "/dump/data.bin")
    assert ret == Constant.MS_AICERR_NONE_ERROR


def test_convert_dump_parse_exception(mocker):
    mocker.patch("ms_interface.utils.check_path_valid")
    parser = Mock()
    parser.parse.side_effect = RuntimeError("boom")
    mocker.patch("msaicerr.DumpDataParser", return_value=parser)
    ret = msaicerr.convert_dump_data(_dump_args(), "/dump/data.bin")
    assert ret == Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR


def test_env_invalid_device(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=False)
    assert msaicerr.test_env(99) == Constant.MS_AICERR_INVALID_PARAM_ERROR


def test_env_success(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch("msaicerr.get_soc_version", return_value="Ascend910B")
    mocker.patch(
        "ms_interface.aicore_error_parser.AicoreErrorParser.run_test_env",
        return_value=True,
    )
    assert msaicerr.test_env(0) == Constant.MS_AICERR_NONE_ERROR


def test_env_fail(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch("msaicerr.get_soc_version", return_value="Ascend910B")
    mocker.patch(
        "ms_interface.aicore_error_parser.AicoreErrorParser.run_test_env",
        return_value=False,
    )
    assert msaicerr.test_env(0) == Constant.MS_AICERR_HARDWARE_ERR


def test_env_exception(mocker):
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch("msaicerr.get_soc_version", side_effect=RuntimeError("boom"))
    assert msaicerr.test_env(0) == Constant.MS_AICERR_HARDWARE_ERR


def test_env_attribute_error(mocker):
    # get_chip_info() 取芯片信息失败返回 None，get_soc_version() 对其取属性抛
    # AttributeError，须按环境检查失败上报而非直接崩溃。
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch(
        "msaicerr.get_soc_version",
        side_effect=AttributeError(
            "'NoneType' object has no attribute 'get_complete_platform'"
        ),
    )
    assert msaicerr.test_env(0) == Constant.MS_AICERR_HARDWARE_ERR


def test_formatted_arg_falls_back_to_dest(mocker):
    # 未经 _register_argument 登记的 dest（有人直接 add_argument）不应抛 KeyError，
    # 而是回退成 --dest，保证参数校验的报错信息仍可读。
    mocker.patch.dict(msaicerr.DEST_OPTIONS_MAP, {}, clear=True)
    assert (
        msaicerr.RequireOtherArgs.formatted_arg("report_path", None) == "--report_path"
    )


def test_env_type_error(mocker):
    # run_test_env() 拼 PYTHONPATH 等环境变量时若取到 None 会抛 TypeError，
    # 须按环境检查失败上报而不是崩溃（根因已用 or '' 兜底，这里守边界）。
    mocker.patch("msaicerr.check_device_valid", return_value=True)
    mocker.patch("msaicerr.get_soc_version", return_value="Ascend910B")
    mocker.patch(
        "ms_interface.aicore_error_parser.AicoreErrorParser.run_test_env",
        side_effect=TypeError(
            "unsupported operand type(s) for +: 'NoneType' and 'str'"
        ),
    )
    assert msaicerr.test_env(0) == Constant.MS_AICERR_HARDWARE_ERR


@pytest.mark.parametrize(
    "options",
    [
        ["--data", "data.bin", "--dest_dtype", "float32", "--output_path", "out"],
        ["--data=data.bin", "--dest_dtype=float32", "--output_path=out"],
        ["-d=data.bin", "-dtype=float32", "-out=out"],
        ["--dest_dtype=float32", "--output_path=out", "--data=data.bin"],
        ["-ddata.bin", "--dest_dtype=float32", "--output_path=out"],
        ["--dest_dtype=float32", "--output_path=out", "-ddata.bin"],
        ["--da=data.bin", "--dest_dtype=float32", "--output_path=out"],
        ["--dest_dtype=float32", "--output_path=out", "--da=data.bin"],
    ],
)
def test_main_converts_bin_with_dependent_options(monkeypatch, tmp_path, options):
    # Run the public CLI through its actual host-side file conversion. The OPP
    # variable is only a startup prerequisite; this path does not use a device.
    monkeypatch.chdir(tmp_path)
    opp_path = tmp_path / "opp"
    opp_path.mkdir()
    monkeypatch.setenv("ASCEND_OPP_PATH", str(opp_path))
    values = np.array([0.5, -1.25, 3.0], dtype=np.float32)
    values.tofile("data.bin")
    monkeypatch.setattr(sys, "argv", ["msaicerr.py", *options])

    assert msaicerr.main() == Constant.MS_AICERR_NONE_ERROR
    converted = np.load(tmp_path / "out" / "data.float32.npy")
    np.testing.assert_array_equal(converted, values)
    assert converted.dtype == values.dtype


def test_main_still_rejects_missing_dependent_option(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASCEND_OPP_PATH", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["msaicerr.py", "--dest_dtype=float32"])

    with pytest.raises(SystemExit) as error:
        msaicerr.main()

    assert error.value.code == 2
    assert "--dest_dtype must be used with -d/--data" in capsys.readouterr().err


@pytest.mark.parametrize(
    "options",
    [
        ["--rep=/r", "--output_path=/o"],
        ["--output_path=/o", "--rep=/r"],
        ["--env", "--device_id=0"],
        ["--device_id=0", "--env"],
    ],
)
def test_argparse_recognized_dependencies_preserve_order(
    monkeypatch, tmp_path, options
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASCEND_OPP_PATH", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["msaicerr.py", *options])
    if any(option.startswith("--rep") for option in options):
        handler = Mock(return_value=Constant.MS_AICERR_NONE_ERROR)
        monkeypatch.setattr(msaicerr, "analyse_report_path", handler)
    else:
        handler = Mock(return_value=Constant.MS_AICERR_NONE_ERROR)
        monkeypatch.setattr(msaicerr, "test_env", handler)
    assert msaicerr.main() == Constant.MS_AICERR_NONE_ERROR
    handler.assert_called_once()


@pytest.mark.parametrize(
    "options",
    [
        ["--output_path=/o", "--device_id=0"],
        ["--data=data.bin", "--device_id=0"],
        ["--report_path=/r", "--dest_dtype=float32"],
    ],
)
def test_unrelated_options_do_not_satisfy_dependency(monkeypatch, tmp_path, options):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASCEND_OPP_PATH", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["msaicerr.py", *options])
    with pytest.raises(SystemExit) as error:
        msaicerr.main()
    assert error.value.code == 2
