#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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

"""
ascend_tbe_op module
"""

import importlib
import math
import os
import struct
import json
import ctypes
from dataclasses import dataclass
from dataclasses import field

from typing import List
from typing import Dict
from typing import Union

import numpy as np
from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common import dtype_trans
from ms_interface.single_op_test_frame.utils import shape_utils
from ms_interface.single_op_test_frame.common import logger
from ms_interface import utils
from ms_interface.constant import Constant, NOT_RUN_EXEC_FAILED, NOT_RUN_LAUNCH_FAILED
from ms_interface.dsmi_interface import DSMIInterface

# parse_type words written into dump file names by DumpDataParser, used to locate the
# tensor index in the name. "space" is normalized to "workspace" before the name is built.
_DUMP_PARSE_TYPES = ("input", "output", "workspace")

# npy file layout, used to read the data bytes without parsing the dtype
_NPY_MAGIC_PREFIX = b"\x93NUMPY"
_NPY_MAGIC_LEN = 8
_NPY_HEADER_LEN_SIZE_V1 = 2
_NPY_HEADER_LEN_SIZE_V2 = 4


# 'pylint: disable=too-many-locals,too-many-arguments,too-few-public-methods
# 'pylint: disable=too-many-instance-attributes,too-many-boolean-expressions
class AscendOpKernel:
    """
    Class AscendOpKernel
    """

    PageMemorySize = 0x200000  # 内存页大小
    MagicMemorySize = 0x80  # 前后各128个魔术字：0x55
    MagicData = 0x55
    ForwardDestroy = 1
    BackwardDestroy = 2

    def __init__(self, bin_path: str, json_path: str):
        if not os.path.exists(bin_path):
            raise IOError("bin_path not exist, path: %s" % bin_path)

        if not os.path.exists(json_path):
            raise IOError("json_path not exist, path: %s" % json_path)

        self.bin_path = bin_path
        self.json_path = json_path
        self.need_do_tiling = False
        self.parameters = []
        self.stub_func_p = None
        self.input_infos = []
        self.output_infos = []
        self.compile_info = None
        self._parse_json_file(json_path)

    def is_registered_to_device(self):
        """
        check whether registered to device
        """
        return self.stub_func_p is not None

    def set_stub_func_p(self, stub_func_p):
        """
        set_stub_func_p
        """
        self.stub_func_p = stub_func_p

    def _parse_json_file(self, json_path):
        """
        parse json file
        """
        with open(json_path, encoding="utf-8") as json_f:
            json_str = json_f.read()

        json_obj = json.loads(json_str)
        self.block_dim = json_obj.get("blockDim")
        self.stub_func_name = json_obj.get("kernelName")
        self.magic = json_obj.get("magic")
        self.parameters = json_obj.get("parameters")
        workspace_info = json_obj.get("workspace")
        if not workspace_info:
            self.workspace = []
        else:
            self.workspace = workspace_info.get("size", [])
        op_para_size = json_obj.get("opParaSize", None)
        if not op_para_size:
            self.has_tiling = False
            self.tiling_data_size = 0
        else:
            self.has_tiling = True
            self.tiling_data_size = op_para_size
            self.need_do_tiling = True

    def set_input_info(self, input_infos):
        """
        set input info
        """
        self.input_infos = input_infos

    def set_output_info(self, output_infos):
        """
        set output info
        """
        self.output_infos = output_infos

    def set_compile_info(self, compile_info):
        """
        set compile info
        """
        self.compile_info = compile_info
        self.need_do_tiling = True


class AscendOpKernelParam:
    """
    Class AscendOpKernelParam
    """

    # 'pylint: disable=too-many-arguments
    def __init__(
        self,
        np_data=None,
        shape=None,
        dtype=None,
        ascend_device: AscendRTSApi = None,
        hbm_pointer: ctypes.c_void_p = None,
    ):
        if np_data is not None:
            if isinstance(np_data, bytes):
                np_data = np.frombuffer(np_data, dtype=np.int8)
            self._np_data = np_data
            self._is_const = True
            self.shape = np_data.shape
            if str(np_data.dtype) == "|V2":
                logger.log_info(
                    "self.dtype is None, MayBe bfloat16, same size with float16"
                )
                self.dtype = "float16"
            else:
                self.dtype = dtype_trans.np_dtype_to_str(np_data.dtype)
        else:
            self._np_data = None
            self._is_const = False
            self.shape = shape
            self.dtype = dtype
        shape_size = shape_utils.calc_shape_size(self.shape)
        self.size = shape_utils.calc_op_param_size(shape_size, self.dtype)
        self.shape_size = shape_size
        self._origin_pointer = None  # 保存偏移前的原始地址
        self._magic_pointer = None  # 保存有效内存的尾部地址
        self._hbm_pointer = hbm_pointer
        self._ascend_device = ascend_device

    @staticmethod
    def build_op_param_by_np_data(np_data):
        """
        build op param by numpy data
        """
        return AscendOpKernelParam(np_data=np_data)

    @staticmethod
    def build_op_param_by_data_file(data_file_path: str, dtype: str, shape: List[int]):
        """
        build op param by data file
        """
        if not os.path.exists(data_file_path):
            raise IOError("data_file_path is not exist, path: %s" % data_file_path)
        np_dtype = dtype_trans.str_to_np_dtype(dtype)
        if not np_dtype:
            raise RuntimeError(
                "dtype must in [%s]" % ",".join(dtype_trans.get_all_str_dtypes())
            )
        np_data = np.fromfile(data_file_path, dtype=np_dtype)
        shape_size = shape_utils.calc_shape_size(shape)
        if shape_size < 0:
            raise RuntimeError("Shape size < 0")
        if shape_size > len(np_data):
            raise RuntimeError(
                "Data size(%d) in data_file < shape size(%d)"
                % (len(np_data), shape_size)
            )
        np_data = np_data[:shape_size].reshape(shape)
        return AscendOpKernelParam(np_data=np_data)

    def sync_to_device_ori(self, ascend_device: AscendRTSApi):
        """
        sync_to_device
        """
        self._ascend_device = ascend_device
        self._hbm_pointer = self._ascend_device.copy_bin_to_hbm(self._np_data.tobytes())

    def sync_to_device(self, ascend_device: AscendRTSApi, mode="magic"):
        """
        同步数据到设备内存
        :param ascend_device:
        :param mode: 模式定义，支持：tail与magic模式
        :return:
        """
        self._ascend_device = ascend_device
        shape_size = shape_utils.calc_shape_size(self.shape)
        if shape_size < 0:
            raise RuntimeError("Shape size < 0.")

        self.size = shape_utils.calc_op_param_size(shape_size, self.dtype)

        if mode == "tail":
            size_align_page = (
                int(math.ceil(self.size / AscendOpKernel.PageMemorySize))
                * AscendOpKernel.PageMemorySize
            )
            if size_align_page == 0:
                out_hbm_pointer = self._ascend_device.malloc(0x400)
                self._hbm_pointer = out_hbm_pointer
                return
            else:
                out_hbm_pointer = self._ascend_device.malloc(size_align_page)
            self._origin_pointer = ctypes.c_void_p(out_hbm_pointer.value)
            out_hbm_pointer.value = (
                out_hbm_pointer.value + size_align_page - self.size
            )  # -->> 63*4 252
            self._hbm_pointer = out_hbm_pointer
        elif mode == "magic":
            _align_size = math.ceil(self.size / 32) * 32
            adjust_size = _align_size + AscendOpKernel.MagicMemorySize * 2
            out_hbm_pointer = self._ascend_device.malloc(adjust_size)
            self._origin_pointer = ctypes.c_void_p(out_hbm_pointer.value)
            self._magic_pointer = ctypes.c_void_p(
                out_hbm_pointer.value + AscendOpKernel.MagicMemorySize + _align_size
            )
            _magic_data = np.ones(adjust_size, dtype=np.int8) * AscendOpKernel.MagicData
            self._ascend_device.memcpy(
                self._origin_pointer,
                adjust_size,
                _magic_data.tobytes(),
                adjust_size,
                "RT_MEMCPY_HOST_TO_DEVICE",
            )
            out_hbm_pointer.value = (
                out_hbm_pointer.value + AscendOpKernel.MagicMemorySize
            )
            self._hbm_pointer = out_hbm_pointer
        else:
            self.sync_to_device_ori(ascend_device)
            return
        if self._np_data is not None:
            real_mem_len = int(math.ceil(self._np_data.nbytes / 32) * 32 + 32)
            if self._hbm_pointer.value:
                self._ascend_device.memcpy(
                    self._hbm_pointer,
                    real_mem_len,
                    self._np_data.tobytes(),
                    self._np_data.nbytes,
                    "RT_MEMCPY_HOST_TO_DEVICE",
                )

    def is_in_device(self):
        """
        check whether in_device
        """
        return self._hbm_pointer is not None

    def release_device(self):
        """
        release device
        """
        if self._ascend_device and self._origin_pointer is not None:
            # 显式与 0/None 比较：pylint 对 c_void_p.value 直接做真值测试会误判为常量
            origin_addr = self._origin_pointer.value
            if origin_addr is not None and origin_addr != 0:
                self._ascend_device.free(self._origin_pointer)
            self._origin_pointer = None
            self._hbm_pointer = None
        elif self._ascend_device and self._hbm_pointer:
            self._ascend_device.free(self._hbm_pointer)
            self._hbm_pointer = None

        if self._ascend_device:
            self._ascend_device = None

    def concat_into_kernel_args(self, kernel_args: List):
        """
        concat into kernel args
        """
        kernel_args.append(self._hbm_pointer)

    def create_ref(self):
        """
        create ref
        """
        return self

    @property
    def hbm_pointer(self):
        if self._hbm_pointer.value is None:
            self._hbm_pointer = self._ascend_device.malloc(0x400)
        return self._hbm_pointer

    @property
    def allocated_hbm_pointer(self):
        """返回已分配的 HBM 指针，不触发分配。

        与 hbm_pointer 的区别：后者在指针为空时会顺带 malloc(0x400)。
        调用方只想读取现有指针时用本属性，避免多分配显存。
        """
        return self._hbm_pointer

    @property
    def origin_pointer(self):
        return self._origin_pointer

    @property
    def magic_pointer(self):
        return self._magic_pointer


@dataclass
class AscendOpKernelRunnerParam:
    kernel: AscendOpKernel
    inputs: List[str] = field(default_factory=list)
    output_input_ref: List[List[int]] = field(default_factory=list)
    tiling_data: bytes = None
    tiling_key: int = 0
    block_dim: int = 0
    actual_out_info: List[Dict] = field(default_factory=list)
    bin_list: List[str] = field(default_factory=list)
    sub_ptr_addrs: dict = field(default_factory=dict)
    ffts_addrs_num: int = 0
    workspace: int = 0
    op_test: str = ""


class AscendOpKernelRunner:
    """
    Class AscendOpKernelRunner
    """

    _kernel_params: List[AscendOpKernelParam]

    _block_size = 32
    _bit32_size = 4

    # 'pylint: disable=unused-argument
    def __init__(
        self,
        simulator_mode=None,
        device_id=0,
        soc_version=None,
        simulator_lib_path=None,
        simulator_dump_path="./model",
        auto_copy_device_data=False,
        profiling=False,
        profiling_times=1,
    ):
        if not isinstance(profiling_times, int):
            raise TypeError("profiling times should be a int.")
        if profiling_times < 1 or profiling_times > 100:
            raise ValueError("profiling times should between [1, 100]")
        self.device_id = device_id
        self.ascend_device = self.get_rts_api(
            simulator_mode, soc_version, simulator_lib_path, simulator_dump_path
        )
        self._simulator_mode = simulator_mode
        self._simulator_dump_path = simulator_dump_path

        self.ascend_device.register_kernel_launch_fill_func()
        self.ascend_device.set_device(device_id=device_id)
        self._stream = self.ascend_device.create_stream()
        self._kernel_params = []
        self.profiling = profiling
        self.profiling_times = profiling_times
        self.has_subptr = None

    @staticmethod
    def get_rts_api(
        simulator_mode, soc_version, simulator_lib_path, simulator_dump_path
    ):
        return AscendRTSApi(
            simulator_mode=simulator_mode,
            soc_version=soc_version,
            simulator_lib_path=simulator_lib_path,
            simulator_dump_path=simulator_dump_path,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        for kernel_param in self._kernel_params:
            kernel_param.release_device()
        self.ascend_device.destroy_stream(self._stream)
        self.ascend_device.reset(self.device_id)

    def build_kernel_param(
        self, data, shape=None, dtype=None, mode="magic"
    ) -> AscendOpKernelParam:
        """
        build_kernel_param
        """
        # foolproof design
        if isinstance(data, str) and data.endswith(".npy"):
            data = np.load(data)
        if isinstance(data, str):
            kernel_param = AscendOpKernelParam.build_op_param_by_data_file(
                data_file_path=data, shape=shape, dtype=dtype
            )
        else:
            kernel_param = AscendOpKernelParam.build_op_param_by_np_data(np_data=data)
        kernel_param.sync_to_device(self.ascend_device, mode)
        self._kernel_params.append(kernel_param)
        return kernel_param

    def cache_kernel_param(self, param):
        """
        cache_kernel_param
        """
        if param not in self._kernel_params:
            self._kernel_params.append(param)

    def _fill_inputs(
        self,
        inputs: List[Union[AscendOpKernelParam]],
        kernel_args: List,
        input_params: List,
        mode,
    ):
        for input_info in inputs:
            if isinstance(input_info, AscendOpKernelParam):
                if input_info not in self._kernel_params:
                    self._kernel_params.append(input_info)
                if not input_info.is_in_device():
                    input_info.sync_to_device(self.ascend_device, mode)
                input_params.append(input_info)
                input_info.concat_into_kernel_args(kernel_args)
            else:
                input_param = self.build_kernel_param(input_info, mode=mode)
                input_param.concat_into_kernel_args(kernel_args)

    def _fill_workspace(
        self,
        kernel: AscendOpKernel,
        workspace: int,
        wksp_hbm_pointers: List,
        kernel_args: List,
        mode,
    ):
        for _, workspace_size in enumerate(kernel.workspace):
            workspace_shape = 0
            param_index = len(kernel_args)
            if (
                param_index >= len(kernel.parameters)
                or not kernel.parameters[param_index]
            ):
                if workspace_size > 0:
                    workspace_shape = workspace_size
                else:
                    workspace_shape = workspace
                kernel_param = AscendOpKernelParam(
                    shape=(workspace_shape,),
                    dtype="int8",
                    ascend_device=self.ascend_device,
                    hbm_pointer=None,
                )
                kernel_param.sync_to_device(self.ascend_device, mode)
                # 用 allocated_hbm_pointer 只读现有指针（hbm_pointer 取值会顺带 malloc）
                wksp_hbm_p = kernel_param.allocated_hbm_pointer
                wksp_hbm_pointers.append(wksp_hbm_p)
                kernel_args.append(kernel_param.allocated_hbm_pointer)
            else:
                data_dtype = kernel.parameters[param_index].get("dtype")
                init_value = kernel.parameters[param_index].get("init_value")
                dtype_size = dtype_trans.get_dtype_byte(data_dtype)
                shape = (math.ceil(workspace_size / dtype_size),)
                data = (
                    np.ones(shape) * init_value if init_value else np.zeros(shape)
                ).astype(data_dtype)
                kernel_param = AscendOpKernelParam.build_op_param_by_np_data(
                    np_data=data
                )
                kernel_param.sync_to_device(self.ascend_device, mode)
                # 同上：只读现有指针，不触发分配
                wksp_hbm_pointers.append(kernel_param.allocated_hbm_pointer)
                kernel_args.append(kernel_param.origin_pointer)
                logger.log_info(
                    f"Fill init_value[{init_value}] to parameters[{param_index}]"
                )
            self._kernel_params.append(kernel_param)

    def _create_output_param_with_pages(self, kernel, data_info: List, mode: str):
        output_info, kernel_args, shape = data_info
        dtype = output_info.get("dtype")
        param_index = len(kernel_args)
        if param_index >= len(kernel.parameters) or not kernel.parameters[param_index]:
            logger.log_info(f"Fill random data to parameters[{param_index}]")
            kernel_param = AscendOpKernelParam(
                shape=shape,
                dtype=dtype,
                ascend_device=self.ascend_device,
                hbm_pointer=None,
            )
            kernel_param.sync_to_device(self.ascend_device, mode)
        else:
            data_dtype = kernel.parameters[param_index].get("dtype")
            init_value = kernel.parameters[param_index].get("init_value")
            data = (
                np.ones(shape) * init_value if init_value else np.zeros(shape)
            ).astype(data_dtype)
            kernel_param = AscendOpKernelParam.build_op_param_by_np_data(np_data=data)
            kernel_param.sync_to_device(self.ascend_device, mode)

            logger.log_info(
                f"Fill init_value[{init_value}] to parameters[{param_index}]"
            )
        return kernel_param

    def _fill_outputs(
        self,
        kernel: AscendOpKernel,
        output_input_ref: List[List[int]],
        actual_output_info: List[Dict],
        input_params: List[AscendOpKernelParam],
        output_params: List[AscendOpKernelParam],
        kernel_args: List,
        mode: str,
    ):
        output_input_ref_map = dict(output_input_ref) if output_input_ref else {}
        output_info_list = (
            actual_output_info if actual_output_info else kernel.output_infos
        )
        for output_idx, output_info in enumerate(output_info_list):
            if output_info is None:
                continue
            if output_idx in output_input_ref_map:
                output_param = input_params[
                    output_input_ref_map[output_idx]
                ].create_ref()
            else:
                shape = output_info.get("run_shape") or output_info.get("shape")
                data_info = [output_info, kernel_args, shape]
                output_param = self._create_output_param_with_pages(
                    kernel, data_info, mode
                )
            output_params.append(output_param)
            output_param.concat_into_kernel_args(kernel_args)
            self.cache_kernel_param(output_param)
            self._kernel_params.append(output_param)

    def _fill_tiling(
        self,
        kernel: AscendOpKernel,
        tiling_data: bytes,
        tiling_hbm: List,
        kernel_args: List,
    ):
        if not kernel.need_do_tiling:
            return
        if not tiling_data:
            utils.print_warn_log("Tiling data is None")
            return
        hbm_pointer = self.ascend_device.copy_bin_to_hbm(tiling_data)
        tiling_hbm.append(hbm_pointer)
        kernel_args.append(hbm_pointer)

    @staticmethod
    def _read_tensor_bytes(tensor_file: str) -> bytes:
        """
        Read the raw device bytes of a dumped tensor file.
        The dump parser saves numpy supported dtypes as .npy, the npy header must not
        be copied to the device, so such files are loaded by numpy instead of read raw.
        """
        if not tensor_file.endswith(".npy"):
            with open(tensor_file, "rb") as bin_f:
                return bin_f.read()
        try:
            # 仅为触发 numpy 注册 bfloat16（副作用导入），不需要绑定名字
            importlib.import_module("bfloat16ext")
        except ImportError:
            pass
        try:
            return np.load(tensor_file, allow_pickle=False).tobytes()
        except (ValueError, TypeError):
            # the dtype in the npy header is not registered in this environment, e.g. the
            # dump env has bfloat16ext but this one does not. The payload after the header
            # is the device bytes as is, so skip the header instead of failing.
            return AscendOpKernelRunner._read_npy_payload(tensor_file)

    @staticmethod
    def _read_npy_payload(tensor_file: str) -> bytes:
        """
        Read the data bytes of a npy file by skipping its header, without letting numpy
        parse the dtype. The npy layout is:
        6 bytes magic + 2 bytes version + header length (2 bytes for v1, 4 for v2+) + header.
        The dump parser only writes C contiguous arrays, so the rest is the device bytes.
        """
        with open(tensor_file, "rb") as npy_f:
            magic = npy_f.read(_NPY_MAGIC_LEN)
            if magic[: len(_NPY_MAGIC_PREFIX)] != _NPY_MAGIC_PREFIX:
                utils.print_error_log(f"{tensor_file} is not a valid npy file.")
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)
            major = magic[-2]
            len_size = (
                _NPY_HEADER_LEN_SIZE_V1 if major == 1 else _NPY_HEADER_LEN_SIZE_V2
            )
            header_len = int.from_bytes(npy_f.read(len_size), byteorder="little")
            npy_f.seek(header_len, os.SEEK_CUR)
            return npy_f.read()

    @staticmethod
    def _get_tensor_index(tensor_file: str) -> int:
        """
        Get the tensor index from a dumped tensor file name.
        The name is {kernel_name}.{parse_type}.{index}[.{dtype}].{npy|bin}
        The index is located by the parse_type token rather than by scanning for digits:
        the dtype segment is the raw dtype enum value when the enum is unknown to the
        dump parser (e.g. kernel.input.0.99.bin), and the kernel name itself may contain
        numeric segments (e.g. exception_info.2.1.20250609144925349).
        @return: the tensor index, or -1 when it can not be resolved
        """
        segments = os.path.basename(tensor_file).split(".")
        # the kernel name may also contain a parse_type word, take the last one
        for pos in range(len(segments) - 1, -1, -1):
            if segments[pos] in _DUMP_PARSE_TYPES:
                index = segments[pos + 1] if pos + 1 < len(segments) else ""
                return int(index) if index.isdigit() else -1
        return -1

    def _fill_binary(
        self,
        bin_files: List,
        hbm_list: List,
        kernel_args: List,
        sub_ptr_addrs: dict,
        mode,
    ):
        sub_ptr_idx = [int(idx) for idx in list(sub_ptr_addrs.keys())]
        if len(sub_ptr_idx) > 0:
            self.has_subptr = True
        current_idx = 0
        for idx, bin_file in enumerate(bin_files):
            if idx < current_idx:
                continue
            if idx in sub_ptr_idx:
                # idx is subptr tensor
                sub_ptr_dict = sub_ptr_addrs.get(str(idx))
                dynamic_tensor_count = sub_ptr_dict.get("dynamic_tensor_count")
                if dynamic_tensor_count is None:
                    utils.print_warn_log(
                        f"The current dump tensor index is {idx} \
                                         and no pointer tensor is obtained, please check plogs."
                    )
                current_idx = idx + dynamic_tensor_count
                sub_ptr_indexes = set(range(idx, current_idx))
                bin_files_list = [
                    file_name
                    for file_name in bin_files
                    if self._get_tensor_index(file_name) in sub_ptr_indexes
                ]
                self._fill_binary_subptr(
                    bin_files_list,
                    dynamic_tensor_count,
                    kernel_args,
                    sub_ptr_addrs.get(str(idx)),
                    mode,
                )
            else:
                # idx is normal tensor
                data = self._read_tensor_bytes(bin_file)
                soc_version = DSMIInterface().get_chip_info(0).get_complete_platform()
                if soc_version.find("Ascend310") >= 0:
                    if len(data) % self._bit32_size != 0:
                        _assign_bit = self._bit32_size - len(data) % self._bit32_size
                        data = data + b"\x00" * _assign_bit
                    _assign_num = 0
                    if len(data) % self._block_size != 0:
                        _assign_num = int(
                            (self._block_size - len(data) % self._block_size) / 4
                        )
                    data = data + struct.pack("f", np.nan) * _assign_num
                kernel_param = AscendOpKernelParam.build_op_param_by_np_data(
                    np_data=data
                )
                kernel_param.sync_to_device(self.ascend_device, mode=mode)
                hbm_list.append(kernel_param.hbm_pointer)
                self._kernel_params.append(kernel_param)
                kernel_args.append(kernel_param.hbm_pointer)
                current_idx += 1

    def _fill_binary_subptr(
        self,
        bin_files: List,
        dynamic_tensor_count: int,
        kernel_args: List,
        sub_ptr_addrs: dict,
        mode,
    ):
        args_list = sub_ptr_addrs.get("args_list")
        if args_list is None or len(args_list) == 0:
            utils.print_error_log("Incorrect pointer tensor information, please check.")
            return
        byte_size = (
            utils.get_hexstr_value(args_list[0]) // 8 * 8 + dynamic_tensor_count * 8
        )
        _align_size = math.ceil(byte_size / 32) * 32
        out_hbm_pointer = self.ascend_device.malloc(_align_size)

        for idx, shape_info in enumerate(args_list):
            pointer_tmp = ctypes.c_void_p(out_hbm_pointer.value + idx * 8)
            self.ascend_device.memcpy(
                pointer_tmp,
                8,
                np.array(int(shape_info, 16)).tobytes(),
                8,
                "RT_MEMCPY_HOST_TO_DEVICE",
            )
        for idx, bin_file in enumerate(bin_files):
            data = self._read_tensor_bytes(bin_file)
            kernel_param = AscendOpKernelParam.build_op_param_by_np_data(np_data=data)
            kernel_param.sync_to_device(self.ascend_device, mode=mode)
            self._kernel_params.append(kernel_param)

            pointer_tmp = ctypes.c_void_p(
                out_hbm_pointer.value + (idx + len(args_list)) * 8
            )

            self.ascend_device.memcpy(
                pointer_tmp,
                8,
                np.array(kernel_param.hbm_pointer.value).tobytes(),
                8,
                "RT_MEMCPY_HOST_TO_DEVICE",
            )
        kernel_args.append(out_hbm_pointer)

    def _execute_kernel(
        self, kernel: AscendOpKernel, kernel_args, block_dim, tiling_key
    ) -> [int, int]:
        if self.profiling:
            self.ascend_device.start_online_profiling(
                self._stream, self.profiling_times
            )
        if not kernel.is_registered_to_device():
            registered_binary = self.ascend_device.register_device_binary_kernel(
                kernel.bin_path, magic=kernel.magic
            )
            try:
                if kernel.stub_func_name.endswith("kernel0"):
                    stub_func_p = self.ascend_device.register_function(
                        registered_binary, f"{kernel.stub_func_name}", 0
                    )
                else:
                    stub_func_p = self.ascend_device.register_function(
                        registered_binary, f"{kernel.stub_func_name}_{tiling_key}", 0
                    )
            except RuntimeError:
                stub_func_p = self.ascend_device.register_function(
                    registered_binary, f"{kernel.stub_func_name}__kernel0", 0
                )
            kernel.set_stub_func_p(stub_func_p)

        def _execute_kernel() -> [int, int]:
            _hex_knl_args = []
            for _args in kernel_args:
                _hex_knl_args.append(hex(_args))
            l_ret = self.ascend_device.launch_kernel(
                kernel.stub_func_p,
                block_dim,
                kernel_args,
                len(kernel_args),
                None,
                self._stream,
            )
            s_ret = self.ascend_device.synchronize_with_stream(self._stream)
            return l_ret, s_ret

        launch_ret = 0
        sync_ret = 0
        if self.profiling:
            for _ in range(self.profiling_times):
                _l_ret, _s_ret = _execute_kernel()
                launch_ret = launch_ret if launch_ret != 0 else _l_ret
                sync_ret = sync_ret if sync_ret != 0 else _s_ret
        else:
            launch_ret, sync_ret = _execute_kernel()
        return [launch_ret, sync_ret]

    def _check_magic(self, pointer, position) -> bool:
        c_buffer, _ = self.ascend_device.get_data_from_hbm(
            pointer, AscendOpKernel.MagicMemorySize
        )
        magic = np.frombuffer(c_buffer, dtype=np.int8)
        if np.any(np.any(magic != AscendOpKernel.MagicData)):
            utils.print_info_log(f"{position} magic memory: {magic}")
            return True
        return False

    def _check_magic_memory(self) -> int:
        for kernel_param in self._kernel_params:
            if (
                kernel_param.origin_pointer is None
                or kernel_param.magic_pointer is None
            ):
                continue

            if self._check_magic(kernel_param.origin_pointer, "head"):
                return AscendOpKernel.ForwardDestroy

            if self._check_magic(kernel_param.magic_pointer, "tail"):
                return AscendOpKernel.BackwardDestroy
        return 0

    def exec_single_case(
        self, ascend_op_param: AscendOpKernelRunnerParam, mode: str = "magic"
    ) -> [Union[AscendOpKernelParam, List[AscendOpKernelParam], None], [int, int]]:
        utils.print_debug_log(f"Start run exec_single_case {mode}...")
        inputs = (
            ascend_op_param.inputs
            if isinstance(ascend_op_param.inputs, (list, tuple))
            else [ascend_op_param.inputs]
        )
        kernel = ascend_op_param.kernel

        input_params = []
        kernel_args = []
        bin_params = []
        output_params = []
        workspace_hbm_p_list = []

        if ascend_op_param.bin_list:
            # only L0 use bin_params
            self._fill_binary(
                ascend_op_param.bin_list,
                bin_params,
                kernel_args,
                ascend_op_param.sub_ptr_addrs,
                mode,
            )
        else:
            # L1 use input output workspace
            self._fill_inputs(inputs, kernel_args, input_params, mode)

            self._fill_outputs(
                kernel,
                ascend_op_param.output_input_ref,
                ascend_op_param.actual_out_info,
                input_params,
                output_params,
                kernel_args,
                mode,
            )

            self._fill_workspace(
                kernel,
                ascend_op_param.workspace,
                workspace_hbm_p_list,
                kernel_args,
                mode,
            )

        tiling_hbm = []
        self._fill_tiling(kernel, ascend_op_param.tiling_data, tiling_hbm, kernel_args)
        if None in [arg.value for arg in kernel_args]:
            raise RuntimeError(f"kernel_args: {kernel_args}")

        knl_args = []
        for _ in range(ascend_op_param.ffts_addrs_num):
            ffts_addr = self.ascend_device.get_c2c_ctrl_addr()
            knl_args.append(ffts_addr.value)
        knl_args.extend([arg.value for arg in kernel_args])
        block_dim = (
            kernel.block_dim
            if not ascend_op_param.block_dim
            else ascend_op_param.block_dim
        )

        if ascend_op_param.op_test == "error_single_op":
            knl_args[-1] = 0
        launch_ret, sync_ret = self._execute_kernel(
            kernel, knl_args, block_dim, ascend_op_param.tiling_key
        )
        magic_ret = self._check_magic_memory()
        for tiling_hbm_p in tiling_hbm:
            self.ascend_device.free(tiling_hbm_p)

        utils.print_debug_log(
            f"Run single case over, result: [{launch_ret, sync_ret, magic_ret}]"
        )
        ret_output_info = output_params[0] if len(output_params) == 1 else output_params
        return [ret_output_info, [launch_ret, sync_ret, magic_ret]]

    def run(self, ascend_op_param: AscendOpKernelRunnerParam) -> str:
        """
        run
        """
        aic_info = ""
        try:
            utils.print_debug_log("Start exec_single_case with tail...")
            _, [launch_ret, sync_ret, _] = self.exec_single_case(
                ascend_op_param, "tail"
            )
            utils.print_debug_log("exec_single_case with tail over...")
            utils.print_debug_log("Start exec_single_case with magic...")
            _, [_, _, magic_ret] = self.exec_single_case(ascend_op_param, "magic")
            utils.print_debug_log("exec_single_case with magic over...")
        except (
            OSError,
            ValueError,
            RuntimeError,
            AttributeError,
            utils.AicErrException,
        ):
            return f"{NOT_RUN_EXEC_FAILED}, please check testcase file(test_single_op.py) or plog."

        if launch_ret != 0 or sync_ret != 0:
            aic_info = f"{aic_info}{NOT_RUN_LAUNCH_FAILED}.\r\n"
            aic_info = f"{aic_info}launch kernel result : {launch_ret}.\r\n"
            aic_info = f"{aic_info}execute result : {sync_ret}.\r\n"
            aic_info = f"{aic_info}memory status check result : {magic_ret}.\r\n"
            utils.print_error_log(aic_info)
        else:
            aic_info = f"{aic_info}exec single op case success.\r\n"
            if magic_ret != 0:
                aic_info = f"{aic_info}memory status check result : {magic_ret}.\r\n"

            utils.print_debug_log(aic_info)
        return aic_info
