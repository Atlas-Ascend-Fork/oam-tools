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

import ctypes
import json
import sys
from unittest.mock import Mock

import numpy as np
import pytest

from conftest import MSAICERR_PATH, make_mock_device
from ms_interface import utils
from ms_interface.single_op_test_frame.common import ascend_tbe_op
from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
    AscendOpKernel,
    AscendOpKernelParam,
    AscendOpKernelRunner,
    AscendOpKernelRunnerParam,
)

sys.path.append(MSAICERR_PATH)


SAMPLE_JSON = {
    "blockDim": 8,
    "kernelName": "test_kernel",
    "magic": "RT_DEV_BINARY_MAGIC_ELF",
    "parameters": [None],
    "workspace": {"size": [128]},
    "opParaSize": 64,
}


def _build_kernel(mocker, json_obj=None):
    json_obj = json_obj if json_obj is not None else SAMPLE_JSON
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(json_obj)))
    return AscendOpKernel("bin_path", "json_path")


def test_init_and_parse(mocker):
    kernel = _build_kernel(mocker)
    assert kernel.block_dim == 8
    assert kernel.stub_func_name == "test_kernel"
    assert kernel.workspace == [128]
    assert kernel.has_tiling is True
    assert kernel.tiling_data_size == 64
    assert kernel.need_do_tiling is True


def test_init_no_workspace_no_tiling(mocker):
    obj = {"blockDim": 1, "kernelName": "k", "magic": "m", "parameters": []}
    kernel = _build_kernel(mocker, obj)
    assert kernel.workspace == []
    assert kernel.has_tiling is False
    assert kernel.tiling_data_size == 0


def test_init_bin_path_not_exist(mocker):
    mocker.patch("os.path.exists", return_value=False)
    with pytest.raises(IOError):
        AscendOpKernel("bin_path", "json_path")


def test_init_json_path_not_exist(mocker):
    mocker.patch("os.path.exists", side_effect=[True, False])
    with pytest.raises(IOError):
        AscendOpKernel("bin_path", "json_path")


def test_is_registered_to_device(mocker):
    kernel = _build_kernel(mocker)
    assert kernel.is_registered_to_device() is False
    kernel.set_stub_func_p(ctypes.c_void_p(16))
    assert kernel.is_registered_to_device() is True


def test_set_infos(mocker):
    kernel = _build_kernel(mocker)
    kernel.set_input_info(["in"])
    kernel.set_output_info(["out"])
    kernel.set_compile_info({"k": "v"})
    assert kernel.input_infos == ["in"]
    assert kernel.output_infos == ["out"]
    assert kernel.compile_info == {"k": "v"}
    assert kernel.need_do_tiling is True


def test_init_with_np_data():
    data = np.ones((2, 3), dtype=np.float16)
    param = AscendOpKernelParam(np_data=data)
    assert getattr(param, "_is_const") is True
    assert param.shape == (2, 3)
    assert param.dtype == "float16"
    assert param.shape_size == 6


def test_init_with_bytes():
    param = AscendOpKernelParam(np_data=b"\x01\x02\x03\x04")
    assert getattr(param, "_is_const") is True
    assert param.dtype == "int8"


def test_init_bfloat16_like():
    data = np.zeros(4, dtype=np.dtype("V2"))
    param = AscendOpKernelParam(np_data=data)
    assert param.dtype == "float16"


def test_init_with_shape_dtype():
    param = AscendOpKernelParam(shape=(4,), dtype="int32")
    assert getattr(param, "_is_const") is False
    assert param.size == 16


def test_build_op_param_by_np_data():
    data = np.ones(4, dtype=np.int8)
    param = AscendOpKernelParam.build_op_param_by_np_data(data)
    assert isinstance(param, AscendOpKernelParam)


def test_build_op_param_by_data_file(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("numpy.fromfile", return_value=np.ones(8, dtype=np.float16))
    param = AscendOpKernelParam.build_op_param_by_data_file("f.bin", "float16", [4])
    assert param.shape_size == 4


def test_build_op_param_by_data_file_not_exist(mocker):
    mocker.patch("os.path.exists", return_value=False)
    with pytest.raises(IOError):
        AscendOpKernelParam.build_op_param_by_data_file("f.bin", "float16", [4])


def test_build_op_param_by_data_file_bad_dtype(mocker):
    mocker.patch("os.path.exists", return_value=True)
    with pytest.raises(RuntimeError):
        AscendOpKernelParam.build_op_param_by_data_file("f.bin", "no_dtype", [4])


def test_build_op_param_by_data_file_data_too_small(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("numpy.fromfile", return_value=np.ones(2, dtype=np.float16))
    with pytest.raises(RuntimeError):
        AscendOpKernelParam.build_op_param_by_data_file("f.bin", "float16", [100])


def test_sync_to_device_ori():
    device = make_mock_device()
    param = AscendOpKernelParam(np_data=np.ones(4, dtype=np.int8))
    param.sync_to_device_ori(device)
    assert getattr(param, "_hbm_pointer") == device.copy_bin_to_hbm.return_value


def test_sync_to_device_magic():
    device = make_mock_device()
    param = AscendOpKernelParam(np_data=np.ones(8, dtype=np.int8))
    param.sync_to_device(device, mode="magic")
    assert getattr(param, "_origin_pointer") is not None
    assert getattr(param, "_magic_pointer") is not None
    assert device.memcpy.called


def test_sync_to_device_tail():
    device = make_mock_device()
    param = AscendOpKernelParam(np_data=np.ones(64, dtype=np.int8))
    param.sync_to_device(device, mode="tail")
    assert getattr(param, "_origin_pointer") is not None


def test_sync_to_device_tail_zero_size():
    device = make_mock_device()
    param = AscendOpKernelParam(shape=(0,), dtype="int8")
    param.sync_to_device(device, mode="tail")
    assert getattr(param, "_hbm_pointer") is not None


def test_sync_to_device_other_mode():
    device = make_mock_device()
    param = AscendOpKernelParam(np_data=np.ones(4, dtype=np.int8))
    param.sync_to_device(device, mode="other")
    assert getattr(param, "_hbm_pointer") == device.copy_bin_to_hbm.return_value


def test_is_in_device():
    param = AscendOpKernelParam(shape=(4,), dtype="int8")
    assert param.is_in_device() is False
    setattr(param, "_hbm_pointer", ctypes.c_void_p(16))
    assert param.is_in_device() is True


def test_release_device_with_origin():
    device = make_mock_device()
    param = AscendOpKernelParam(shape=(4,), dtype="int8")
    setattr(param, "_ascend_device", device)
    setattr(param, "_origin_pointer", ctypes.c_void_p(16))
    param.release_device()
    assert getattr(param, "_hbm_pointer") is None
    assert getattr(param, "_ascend_device") is None


def test_release_device_with_hbm_only():
    device = make_mock_device()
    param = AscendOpKernelParam(shape=(4,), dtype="int8")
    setattr(param, "_ascend_device", device)
    setattr(param, "_hbm_pointer", ctypes.c_void_p(16))
    param.release_device()
    assert getattr(param, "_hbm_pointer") is None


def test_concat_into_kernel_args():
    param = AscendOpKernelParam(shape=(4,), dtype="int8")
    setattr(param, "_hbm_pointer", ctypes.c_void_p(16))
    args = []
    param.concat_into_kernel_args(args)
    assert len(args) == 1


def test_create_ref():
    param = AscendOpKernelParam(shape=(4,), dtype="int8")
    assert param.create_ref() is param


def test_pointer_properties():
    param = AscendOpKernelParam(shape=(4,), dtype="int8")
    setattr(param, "_origin_pointer", ctypes.c_void_p(16))
    setattr(param, "_magic_pointer", ctypes.c_void_p(32))
    setattr(param, "_hbm_pointer", ctypes.c_void_p(48))
    assert param.origin_pointer.value == 16
    assert param.magic_pointer.value == 32
    assert param.hbm_pointer.value == 48


def test_hbm_pointer_lazy_malloc():
    device = make_mock_device()
    param = AscendOpKernelParam(shape=(4,), dtype="int8")
    setattr(param, "_ascend_device", device)
    setattr(param, "_hbm_pointer", ctypes.c_void_p(None))
    result = param.hbm_pointer
    assert device.malloc.called
    assert result is not None


def make_runner(mocker, **kwargs):
    """Build a runner with AscendRTSApi fully mocked out."""
    device = make_mock_device()
    mocker.patch.object(AscendOpKernelRunner, "get_rts_api", return_value=device)
    runner = AscendOpKernelRunner(**kwargs)
    return (runner, device)


def make_kernel_obj(**overrides):
    kernel = Mock(spec=AscendOpKernel)
    kernel.bin_path = "bin_path"
    kernel.block_dim = 8
    kernel.magic = "magic"
    kernel.stub_func_name = "kname"
    kernel.workspace = []
    kernel.parameters = [None]
    kernel.need_do_tiling = False
    kernel.input_infos = []
    kernel.output_infos = []
    kernel.is_registered_to_device.return_value = False
    kernel.stub_func_p = ctypes.c_void_p(16384)
    for key, value in overrides.items():
        setattr(kernel, key, value)
    return kernel


def test_init_ok(mocker):
    _, device = make_runner(mocker)
    assert device.register_kernel_launch_fill_func.called
    assert device.set_device.called
    assert device.create_stream.called


def test_init_bad_profiling_times_type(mocker):
    mocker.patch.object(
        AscendOpKernelRunner, "get_rts_api", return_value=make_mock_device()
    )
    with pytest.raises(TypeError):
        AscendOpKernelRunner(profiling_times="x")


def test_init_bad_profiling_times_range(mocker):
    mocker.patch.object(
        AscendOpKernelRunner, "get_rts_api", return_value=make_mock_device()
    )
    with pytest.raises(ValueError):
        AscendOpKernelRunner(profiling_times=0)


def test_get_rts_api(mocker):
    fake_api = Mock()
    mocker.patch.object(ascend_tbe_op, "AscendRTSApi", return_value=fake_api)
    result = AscendOpKernelRunner.get_rts_api(None, "soc", None, "./model")
    assert result is fake_api


def test_enter_exit(mocker):
    runner, device = make_runner(mocker)
    param = Mock()
    setattr(runner, "_kernel_params", [param])
    with runner as r:
        assert r is runner
    assert param.release_device.called
    assert device.destroy_stream.called
    assert device.reset.called


def test_build_kernel_param_npy(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch("numpy.load", return_value=np.ones(4, dtype=np.int8))
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("numpy.fromfile", return_value=np.ones(4, dtype=np.int8))
    param = runner.build_kernel_param("data.npy", shape=[4], dtype="int8")
    assert param in getattr(runner, "_kernel_params")


def test_build_kernel_param_np_data(mocker):
    runner, _ = make_runner(mocker)
    param = runner.build_kernel_param(np.ones(4, dtype=np.int8))
    assert param in getattr(runner, "_kernel_params")


def test_cache_kernel_param(mocker):
    runner, _ = make_runner(mocker)
    param = Mock()
    runner.cache_kernel_param(param)
    runner.cache_kernel_param(param)
    assert getattr(runner, "_kernel_params").count(param) == 1


def test_fill_inputs_with_param_obj(mocker):
    runner, _ = make_runner(mocker)
    in_param = AscendOpKernelParam(np_data=np.ones(4, dtype=np.int8))
    setattr(in_param, "_hbm_pointer", ctypes.c_void_p(16))
    kernel_args, input_params = ([], [])
    getattr(runner, "_fill_inputs")([in_param], kernel_args, input_params, "magic")
    assert in_param in input_params
    assert len(kernel_args) == 1


def test_fill_inputs_with_np(mocker):
    runner, _ = make_runner(mocker)
    kernel_args, input_params = ([], [])
    getattr(runner, "_fill_inputs")(
        [np.ones(4, dtype=np.int8)], kernel_args, input_params, "magic"
    )
    assert len(kernel_args) == 1


def test_fill_workspace_random(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(workspace=[128], parameters=[None])
    kernel_args, wksp = ([], [])
    getattr(runner, "_fill_workspace")(kernel, 0, wksp, kernel_args, "magic")
    assert len(wksp) == 1


def test_fill_workspace_with_param(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(
        workspace=[128], parameters=[{"dtype": "float16", "init_value": 1}]
    )
    kernel_args, wksp = ([], [])
    getattr(runner, "_fill_workspace")(kernel, 0, wksp, kernel_args, "magic")
    assert len(wksp) == 1


def test_fill_tiling_skip_no_tiling(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(need_do_tiling=False)
    kernel_args, tiling_hbm = ([], [])
    getattr(runner, "_fill_tiling")(kernel, b"data", tiling_hbm, kernel_args)
    assert tiling_hbm == []


def test_fill_tiling_none_data(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(need_do_tiling=True)
    kernel_args, tiling_hbm = ([], [])
    getattr(runner, "_fill_tiling")(kernel, None, tiling_hbm, kernel_args)
    assert tiling_hbm == []


def test_fill_tiling_ok(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(need_do_tiling=True)
    kernel_args, tiling_hbm = ([], [])
    getattr(runner, "_fill_tiling")(kernel, b"data", tiling_hbm, kernel_args)
    assert len(tiling_hbm) == 1
    assert len(kernel_args) == 1


def test_fill_outputs_normal(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(parameters=[None])
    out_info = [{"shape": [4], "dtype": "float16"}]
    output_params, kernel_args = ([], [])
    getattr(runner, "_fill_outputs")(
        kernel, [], out_info, [], output_params, kernel_args, "magic"
    )
    assert len(output_params) == 1


def test_fill_outputs_with_ref(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj()
    in_param = AscendOpKernelParam(np_data=np.ones(4, dtype=np.int8))
    setattr(in_param, "_hbm_pointer", ctypes.c_void_p(16))
    out_info = [{"shape": [4], "dtype": "float16"}]
    output_params, kernel_args = ([], [])
    getattr(runner, "_fill_outputs")(
        kernel, [[0, 0]], out_info, [in_param], output_params, kernel_args, "magic"
    )
    assert len(output_params) == 1


def test_fill_outputs_skip_none(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj()
    output_params, kernel_args = ([], [])
    getattr(runner, "_fill_outputs")(
        kernel, [], [None], [], output_params, kernel_args, "magic"
    )
    assert output_params == []


def test_check_magic_true(mocker):
    runner, device = make_runner(mocker)
    device.get_data_from_hbm.return_value = (np.zeros(4, dtype=np.int8).tobytes(), 0)
    assert getattr(runner, "_check_magic")(ctypes.c_void_p(16), "head") is True


def test_check_magic_false(mocker):
    runner, device = make_runner(mocker)
    magic_bytes = (
        np.ones(AscendOpKernel.MagicMemorySize, dtype=np.int8)
        * AscendOpKernel.MagicData
    ).tobytes()
    device.get_data_from_hbm.return_value = (magic_bytes, 0)
    assert getattr(runner, "_check_magic")(ctypes.c_void_p(16), "head") is False


def test_check_magic_memory_clean(mocker):
    runner, _ = make_runner(mocker)
    param = Mock()
    param.origin_pointer = None
    setattr(runner, "_kernel_params", [param])
    assert getattr(runner, "_check_magic_memory")() == 0


def test_check_magic_memory_forward_destroy(mocker):
    runner, _ = make_runner(mocker)
    param = Mock()
    param.origin_pointer = ctypes.c_void_p(16)
    param.magic_pointer = ctypes.c_void_p(32)
    setattr(runner, "_kernel_params", [param])
    mocker.patch.object(runner, "_check_magic", return_value=True)
    assert getattr(runner, "_check_magic_memory")() == AscendOpKernel.ForwardDestroy


def test_fill_binary_normal(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"\x01\x02\x03\x04"))
    chip = Mock()
    chip.get_complete_platform.return_value = "Ascend910B"
    dsmi = Mock()
    dsmi.get_chip_info.return_value = chip
    mocker.patch.object(ascend_tbe_op, "DSMIInterface", return_value=dsmi)
    hbm_list, kernel_args = ([], [])
    getattr(runner, "_fill_binary")(["a.0.bin"], hbm_list, kernel_args, {}, "magic")
    assert len(hbm_list) == 1
    assert len(kernel_args) == 1


def test_fill_binary_ascend310_padding(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"\x01\x02\x03"))
    chip = Mock()
    chip.get_complete_platform.return_value = "Ascend310"
    dsmi = Mock()
    dsmi.get_chip_info.return_value = chip
    mocker.patch.object(ascend_tbe_op, "DSMIInterface", return_value=dsmi)
    hbm_list, kernel_args = ([], [])
    getattr(runner, "_fill_binary")(["a.0.bin"], hbm_list, kernel_args, {}, "magic")
    assert len(kernel_args) == 1


def test_fill_binary_subptr(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"\x01\x02\x03\x04"))
    mocker.patch.object(ascend_tbe_op.utils, "get_hexstr_value", return_value=16)
    sub_ptr = {"0": {"dynamic_tensor_count": 1, "args_list": ["0x10"]}}
    kernel_args = []
    getattr(runner, "_fill_binary")(["x.0.bin"], [], kernel_args, sub_ptr, "magic")
    assert len(kernel_args) == 1


def test_fill_binary_subptr_empty_args(mocker):
    runner, _ = make_runner(mocker)
    kernel_args = []
    getattr(runner, "_fill_binary_subptr")(
        [], 1, kernel_args, {"args_list": []}, "magic"
    )
    assert kernel_args == []


def test_read_tensor_bytes_bin(tmp_path):
    """bin文件按原始字节读取"""
    bin_file = tmp_path.joinpath("a.input.0.int4.bin")
    bin_file.write_bytes(b"\x01\x02\x03\x04")
    assert (
        getattr(AscendOpKernelRunner, "_read_tensor_bytes")(str(bin_file))
        == b"\x01\x02\x03\x04"
    )


def test_read_tensor_bytes_npy_strips_header(tmp_path):
    """npy文件需经numpy加载，不能把npy头当作tensor数据下发到device"""
    array = np.arange(6, dtype=np.float32).reshape(2, 3)
    npy_file = tmp_path.joinpath("a.input.0.float32.npy")
    np.save(str(npy_file), array)
    data = getattr(AscendOpKernelRunner, "_read_tensor_bytes")(str(npy_file))
    assert data == array.tobytes()
    # 直接读原始字节会多出npy头
    assert len(npy_file.read_bytes()) > len(data)


def _forge_npy_with_unknown_dtype(path, array, fake_dtype=b"bfloat16"):
    """生成header中dtype为本环境未注册类型、且header长度字段合法的npy"""
    np.save(str(path), array)
    raw = bytearray(open(str(path), "rb").read())
    header_len = int.from_bytes(raw[8:10], "little")
    header = bytes(raw[10 : 10 + header_len])
    body = bytes(raw[10 + header_len :])
    real_descr = header.split(b"'descr': ")[1].split(b",")[0]
    new_header = header.replace(real_descr, b"'" + fake_dtype + b"'").rstrip(b" \n")
    # header需以\n结尾且总长保持不变
    new_header = new_header + b" " * (header_len - len(new_header) - 1) + b"\n"
    open(str(path), "wb").write(bytes(raw[:10]) + new_header + body)


@pytest.mark.parametrize("dtype", [np.int16, np.float32])
def test_read_tensor_bytes_npy_unregistered_dtype(tmp_path, dtype):
    """落盘环境有bfloat16ext而回放环境没有时，跳过npy头取原始数据而非直接失败"""
    array = np.arange(4, dtype=dtype)
    npy_file = tmp_path.joinpath("k.input.0.bfloat16.npy")
    _forge_npy_with_unknown_dtype(npy_file, array)
    assert (
        getattr(AscendOpKernelRunner, "_read_tensor_bytes")(str(npy_file))
        == array.tobytes()
    )


def test_read_npy_payload_invalid_magic(tmp_path):
    """magic不合法时报错，不把非npy内容当作tensor下发"""
    bad = tmp_path.joinpath("bad.npy")
    bad.write_bytes(b"NOTANPY!" + b"\x00" * 16)
    with pytest.raises(utils.AicErrException):
        getattr(AscendOpKernelRunner, "_read_npy_payload")(str(bad))


@pytest.mark.parametrize(
    "name, expected",
    [
        ("k.input.0.float32.npy", 0),
        ("k.input.12.int64.npy", 12),
        ("k.input.3.int4.bin", 3),
        ("k.input.2.bin", 2),
        ("k.workspace.1.int8.npy", 1),
        ("k.output.3.float16.npy", 3),
        # dtype段为原始枚举值(纯数字)，不能被当成下标
        ("k.input.0.99.bin", 0),
        ("k.input.1.77.bin", 1),
        ("k.input.0.undefined.bin", 0),
        # kernel名自身含数字段
        ("exception_info.2.1.20250609144925349.input.0.99.bin", 0),
        ("exception_info.2.1.20250609144925349.input.0.float32.bin", 0),
        # kernel名自身含parse_type词，取最后一个
        ("my.input.k.input.5.99.bin", 5),
        ("no_index.npy", -1),
        ("k.input.bin", -1),
    ],
)
def test_get_tensor_index(name, expected):
    """从dump文件名解析tensor下标，兼容带dtype/不带dtype/dtype为纯数字枚举等命名"""
    assert getattr(AscendOpKernelRunner, "_get_tensor_index")(name) == expected


def test_fill_binary_npy_input(mocker, tmp_path):
    """bin_list中为npy时按numpy加载后下发，下发字节数与数组一致"""
    runner, _ = make_runner(mocker)
    array = np.arange(4, dtype=np.float32)
    npy_file = tmp_path.joinpath("a.input.0.float32.npy")
    np.save(str(npy_file), array)
    chip = Mock()
    chip.get_complete_platform.return_value = "Ascend910B"
    dsmi = Mock()
    dsmi.get_chip_info.return_value = chip
    mocker.patch.object(ascend_tbe_op, "DSMIInterface", return_value=dsmi)
    build = mocker.patch.object(
        ascend_tbe_op.AscendOpKernelParam,
        "build_op_param_by_np_data",
        return_value=Mock(),
    )
    hbm_list, kernel_args = ([], [])
    getattr(runner, "_fill_binary")([str(npy_file)], hbm_list, kernel_args, {}, "magic")
    assert len(kernel_args) == 1
    assert build.call_args.kwargs["np_data"] == array.tobytes()


def test_fill_binary_subptr_matches_npy_by_index(mocker, tmp_path):
    """subptr场景下按文件名中的下标匹配，带dtype的npy也能被选中"""
    runner, _ = make_runner(mocker)
    files = []
    for idx in range(2):
        npy_file = tmp_path.joinpath(f"k.input.{idx}.float32.npy")
        np.save(str(npy_file), np.zeros(2, dtype=np.float32))
        files.append(str(npy_file))
    mocker.patch.object(ascend_tbe_op.utils, "get_hexstr_value", return_value=16)
    mocker.patch.object(
        ascend_tbe_op.AscendOpKernelParam,
        "build_op_param_by_np_data",
        return_value=Mock(),
    )
    subptr = mocker.patch.object(runner, "_fill_binary_subptr")
    sub_ptr = {"0": {"dynamic_tensor_count": 2, "args_list": ["0x10"]}}
    getattr(runner, "_fill_binary")(files, [], [], sub_ptr, "magic")
    # 两个npy均按下标0、1被匹配进subptr列表
    assert subptr.call_args[0][0] == files


def test_fill_binary_subptr_matches_numeric_dtype_name(mocker, tmp_path):
    """dtype枚举未知时文件名形如 k.input.0.99.bin，dtype段不能被当成下标导致漏匹配"""
    runner, _ = make_runner(mocker)
    files = []
    for idx in range(2):
        bin_file = tmp_path.joinpath(f"k.input.{idx}.99.bin")
        bin_file.write_bytes(b"\x01\x02\x03\x04")
        files.append(str(bin_file))
    mocker.patch.object(ascend_tbe_op.utils, "get_hexstr_value", return_value=16)
    mocker.patch.object(
        ascend_tbe_op.AscendOpKernelParam,
        "build_op_param_by_np_data",
        return_value=Mock(),
    )
    subptr = mocker.patch.object(runner, "_fill_binary_subptr")
    sub_ptr = {"0": {"dynamic_tensor_count": 2, "args_list": ["0x10"]}}
    getattr(runner, "_fill_binary")(files, [], [], sub_ptr, "magic")
    assert subptr.call_args[0][0] == files


def test_execute_kernel_register_kernel0(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(stub_func_name="op__kernel0")
    kernel.is_registered_to_device.return_value = False
    ret = getattr(runner, "_execute_kernel")(kernel, [16, 32], 8, 0)
    assert ret == [0, 0]
    assert kernel.set_stub_func_p.called


def test_execute_kernel_register_with_tiling_key(mocker):
    runner, _ = make_runner(mocker)
    kernel = make_kernel_obj(stub_func_name="op")
    kernel.is_registered_to_device.return_value = False
    ret = getattr(runner, "_execute_kernel")(kernel, [16], 8, 3)
    assert ret == [0, 0]


def test_execute_kernel_register_fallback(mocker):
    runner, device = make_runner(mocker)
    kernel = make_kernel_obj(stub_func_name="op")
    kernel.is_registered_to_device.return_value = False
    device.register_function.side_effect = [
        RuntimeError("fail"),
        ctypes.c_void_p(16384),
    ]
    ret = getattr(runner, "_execute_kernel")(kernel, [16], 8, 0)
    assert ret == [0, 0]


def test_execute_kernel_profiling(mocker):
    runner, device = make_runner(mocker, profiling=True, profiling_times=2)
    kernel = make_kernel_obj()
    kernel.is_registered_to_device.return_value = True
    ret = getattr(runner, "_execute_kernel")(kernel, [16], 8, 0)
    assert ret == [0, 0]
    assert device.start_online_profiling.called


def _exec_param(**overrides):
    kernel = make_kernel_obj()
    param = AscendOpKernelRunnerParam(kernel=kernel)
    for key, value in overrides.items():
        setattr(param, key, value)
    return param


def test_exec_single_case_l1(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch.object(runner, "_check_magic_memory", return_value=0)
    in_param = AscendOpKernelParam(np_data=np.ones(4, dtype=np.int8))
    setattr(in_param, "_hbm_pointer", ctypes.c_void_p(16))
    param = _exec_param(inputs=[in_param])
    _, rets = runner.exec_single_case(param, "magic")
    assert rets == [0, 0, 0]


def test_exec_single_case_with_bin_list(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch.object(runner, "_fill_binary")
    mocker.patch.object(runner, "_check_magic_memory", return_value=0)
    param = _exec_param(bin_list=["a.0.bin"])
    _, rets = runner.exec_single_case(param, "magic")
    assert rets[0] == 0


def test_exec_single_case_ffts(mocker):
    runner, device = make_runner(mocker)
    mocker.patch.object(runner, "_check_magic_memory", return_value=0)
    in_param = AscendOpKernelParam(np_data=np.ones(4, dtype=np.int8))
    setattr(in_param, "_hbm_pointer", ctypes.c_void_p(16))
    param = _exec_param(inputs=[in_param], ffts_addrs_num=1)
    _, _ = runner.exec_single_case(param, "magic")
    assert device.get_c2c_ctrl_addr.called


def test_run_success(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch.object(runner, "exec_single_case", return_value=[None, [0, 0, 0]])
    param = _exec_param()
    result = runner.run(param)
    assert "success" in result


def test_run_failed_ret(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch.object(
        runner, "exec_single_case", side_effect=[[None, [1, 0, 0]], [None, [0, 0, 2]]]
    )
    param = _exec_param()
    result = runner.run(param)
    assert "failed" in result


def test_run_success_with_memory_status(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch.object(
        runner, "exec_single_case", side_effect=[[None, [0, 0, 0]], [None, [0, 0, 2]]]
    )
    param = _exec_param()
    result = runner.run(param)
    assert "success" in result
    assert "memory status check result : 2." in result


def test_run_exception(mocker):
    runner, _ = make_runner(mocker)
    mocker.patch.object(runner, "exec_single_case", side_effect=RuntimeError("boom"))
    param = _exec_param()
    result = runner.run(param)
    assert "failed" in result
