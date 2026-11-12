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

import stat
import enum


class ModeCustom(enum.Enum):
    ADD_CUSTOM = "AddCustom"
    DIRTY_CUSTOM = "DirtyCustom"


class RetCode(enum.Enum):
    SUCCESS = 0
    FAILED = 1
    NOT_RUN = 2


# Single-operator execution result markers from ascend_tbe_op.py,
# used by aicore_error_parser._test_single_op to detect NOT_RUN.
NOT_RUN_EXEC_FAILED = "Execute single op case failed"
NOT_RUN_LAUNCH_FAILED = "exec single op case failed"


class ChipType(enum.Enum):
    """AI Core error-code dialect, named after the chip form.

    ASCEND_910B is the Stars architecture (errorMapInfo_), ASCEND_950 the David
    architecture (g_davidErrorMapInfo); the two print `error code` differently.
    """

    ASCEND_910B = "910B"
    ASCEND_950 = "950"


class Constant:
    """
    The class for constant.
    """

    # error code for user:success
    MS_AICERR_NONE_ERROR = 0
    # error code for user: error
    MS_AICERR_INVALID_PARAM_ERROR = 1
    MS_AICERR_INVALID_PATH_ERROR = 2
    MS_AICERR_CONNECT_ERROR = 3
    MS_AICERR_INVALID_DUMP_DATA_ERROR = 4
    MS_AICERR_OPEN_FILE_ERROR = 5
    MS_AICERR_EXECUTE_COMMAND_ERROR = 6
    MS_AICERR_INVALID_CONFIG_DATA_ERROR = 7
    MS_AICERR_INVALID_SLOG_DATA_ERROR = 8
    MS_AICERR_FIND_DATA_ERROR = 9
    MS_AICERR_GET_DRIVER_AICORE_NUMBER_ERROR = 10
    MS_AICERR_GET_RUNTIME_BLOCKDIM_ERROR = 11

    MS_AICERR_SINGLE_OP_ERR = 101  # 检查到单算子运行错误
    MS_AICERR_MEMORY_ALLOCATION_ERR = 102  # 检查到内存分配错误
    MS_AICERR_HARDWARE_ERR = 103  # 检查到硬件错误
    MS_AICERR_OPERATOR_INPUT_DATA_ERR = 104  # 检查到算子输入数据错误
    MS_AICERR_FRAMEWORK_MEMSET_MISSING = 105  # 检查到框架未执行memset清零
    MS_AICERR_OPERATOR_ARGS_OVERWRITTEN = 106  # 检查到算子args被踩
    MS_AICERR_ATOMIC_OPERATOR_OVERFLOW = 107  # 检查到atomic算子遇到溢出数据导致错误

    # 工具级错误码（<100）的用户可读描述；101+ 是分析结论码，
    # 对应描述由报告的 root cause 输出，不在此表。
    MS_AICERR_ERROR_DESC = {
        MS_AICERR_NONE_ERROR: "success",
        MS_AICERR_INVALID_PARAM_ERROR: "invalid input parameter",
        MS_AICERR_INVALID_PATH_ERROR: "invalid input path",
        MS_AICERR_CONNECT_ERROR: "failed to load the parser or runtime library",
        MS_AICERR_INVALID_DUMP_DATA_ERROR: "invalid or corrupted dump file",
        MS_AICERR_OPEN_FILE_ERROR: "failed to open or read the required file",
        MS_AICERR_EXECUTE_COMMAND_ERROR: "failed to execute the external command",
        MS_AICERR_INVALID_CONFIG_DATA_ERROR: "invalid configuration file",
        MS_AICERR_INVALID_SLOG_DATA_ERROR: "required information is missing in the collected logs",
        MS_AICERR_FIND_DATA_ERROR: "the required data was not found",
        MS_AICERR_GET_DRIVER_AICORE_NUMBER_ERROR: "failed to get the AI Core number from the driver",
        MS_AICERR_GET_RUNTIME_BLOCKDIM_ERROR: "failed to get block_dim from the runtime log",
    }

    WRITE_MODES = stat.S_IWUSR | stat.S_IRUSR

    DIRECTORY_MASK = 0o700

    MAX_READ_FILE_BYTES = 1024 * 1024  # 1M
    MAX_TAR_SIZE = 1 * 1024 * 1024 * 1024  # 1G

    MAX_FILE_NAME_LEN = 255  # Linux NAME_MAX，单文件名上限
    MAPPING_CSV_FILE = "mapping.csv"  # 超长文件名映射表，每行 {映射后},{映射前}
    CUSTOM_DUMP_DIR = "custom_dump"  # 自定义dump张量产物子目录，与原始报错dump隔离

    DIR_PLOG = "plog"

    AIC_ERROR_TUPLE_LEN = 9
    # dump_data_parser
    UINT64_SIZE = 8
    TIME_LENGTH = 1000
    UINT64_FMT = "Q"

    STRUCT_FORMAT_KEY = "struct_format"
    DTYPE = "dtype"

    SIZE_OF_DTYPE = {
        "DT_FLOAT": 4,
        "DT_FLOAT16": 2,
        "DT_INT8": 1,
        "DT_INT16": 2,
        "DT_UINT16": 2,
        "DT_UINT8": 1,
        "DT_INT32": 4,
        "DT_INT64": 8,
        "DT_UINT32": 4,
        "DT_UINT64": 8,
        "DT_BOOL": 1,
        "DT_DOUBLE": 8,
        "DT_STRING, -1}, {DT_DUAL_SUB_INT8": 1,
        "DT_DUAL_SUB_UINT8": 1,
        "DT_COMPLEX64": 8,
        "DT_COMPLEX128, 16}, {DT_QINT8": 1,
        "DT_QINT16": 2,
        "DT_QINT32": 4,
        "DT_QUINT8": 1,
        "DT_QUINT16": 2,
        "DT_RESOURCE": -1,
        "DT_STRING_REF": -1,
        "DT_DUAL": 5,
        "DT_BFLOAT16": 2,
        "DT_BF16": 2,
    }
    # aicore_error_parser
    OBJ_DUMP_FILE = "cce-objdump"
    NEW_DUMP_FILE = "llvm-objdump"
    SYMBOLIZER_FILE = "llvm-symbolizer"
    GRAPH_FILE = 0

    # collection
    EXCEPTION_PATTERN = (
        r"<exception_print>TIME:(\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+)[ \S]+?"
        r"device_id=(\d+)[ \S]+?stream_id=(\d+)[ \S]+?task_id="
        r"(\d+).+?AICORE_INFO_START: core_id=(\d+).+?AIC_ERROR="
        r"(\S+).+?PC_START=(\S+)(.+?)CURRENT_PC=(\S+)"
    )

    # Reported when no error bit is set at all. The runtime does the same: it
    # only falls back to "timeout or trap error." after finding zero bits, so
    # this is a sentinel and deliberately not a member of the bit tables.
    NO_ERROR_BIT_INFO = "trap_or_timeout, timeout or trap error"

    # AI Core error bit number -> "error name, English description".
    # Source of truth: DeviceErrorProc::errorMapInfo_ in
    # runtime/src/runtime/core/src/device/device_error_core_proc.cc (Stars / 910B).
    # The "name, description" shape is required: _get_aicerror_info and
    # find_extra_pc derive the module from name.split('_')[0].
    # Every bit maps 1:1 to the C++ table. The "no error bit set" case is not a
    # bit, so it lives in NO_ERROR_BIT_INFO rather than aliasing bit 0.
    AIC_ERROR_INFO_DICT = {
        0: "biu_l2_read_oob, Bus read access error. You are advised to check the L2 code.",
        1: "biu_l2_write_oob, Bus write access error. You are advised to check the L2 code.",
        2: "ccu_call_depth_ovrflw, The depth of nested function call is greater than CTRL[5:2].",
        3: "ccu_div0, Division by 0 error.",
        4: "ccu_illegal_instr, Illegal instruction, which is usually caused by unaligned UUB addresses.",
        5: "ccu_loop_cnt_err, The loop count of the hardware loop instruction is 0. Possible cause: The compiler "
        "optimization is incorrect or the instruction is overwritten.",
        6: "ccu_loop_err, The loopend instruction is executed before executing loop instruction. Possible cause: The "
        "compiler optimization is incorrect or the instruction is overwritten.",
        7: "ccu_neg_sqrt, The number of roots is negative.",
        8: "ccu_ub_ecc, A multi-bit ECC error occurs when CCU reads/writes UB. See the RAS alarm handling.",
        9: "cube_invld_input, The data of L0a and L0b read back is the INF or NAN data.",
        10: "cube_l0a_ecc, A multi-bit ECC error occurs when CCU reads/writes L0A. See the RAS alarm handling.",
        11: "cube_l0a_rdwr_cflt, L0A read/write conflict.",
        12: "cube_l0a_wrap_around, The operation address of L0A exceeds the maximum range of L0A.",
        13: "cube_l0b_ecc, A multi-bit ECC error occurs when CUBE reads/writes L0B. See the RAS alarm handling.",
        14: "cube_l0b_rdwr_cflt, L0B read/write conflict.",
        15: "cube_l0b_wrap_around, The operation address of L0B exceeds the maximum range of L0B.",
        16: "cube_l0c_ecc, A multi-bit ECC error occurs when CUBE reads/writes L0C. See the RAS alarm handling",
        17: "cube_l0c_rdwr_cflt, L0C read/write conflict(vec read operation or cube write operation).",
        18: "cube_l0c_self_rdwr_cflt, The address for VEC to read L0C confilicts with that for CUBE to write L0C.",
        19: "cube_l0c_wrap_around, The operation address of L0C exceeds the maximum range of L0C.",
        20: "ifu_bus_err, The address of instruction is illegal when the AIcore reads instructions from GM.Possible "
        "cause: The application unloads the operator binary in advance or stack corruption occurs.",
        21: "mte_aipp_illegal_param, The configuration of AIPP is incorrect.",
        22: "mte_bas_raddr_obound, The base address of the mte load3d instruction is out of bounds.",
        23: "mte_biu_rdwr_resp, MTE accesses an invalid GM address or the cross-device memory access times out.",
        24: "mte_cidx_overflow, The C0 index of the mte load3d instruction overflows.",
        25: "mte_decomp, The number of load index entries is different from the number of data blocks to be "
        "decompressed in the latest load decompressed data.",
        26: "mte_f1wpos_larger_fsize, The 1st filter window position of the mte load3d instruction is greater than "
        "(Feature map size – Filter size).",
        27: "mte_fmap_less_kernel, The feature map size of the mte load3d instruction is less than the kernel size.",
        28: "mte_fmapwh_larger_l1size, FeatureMapW * FeatureMapH * (CIndex + 1) of the mte load3d instruction is "
        "greater than L1 buffer size/32.",
        29: "mte_fpos_larger_fsize, The fetch position in filter of the mte load3d instruction is greater than the "
        "filter size.",
        30: "mte_gdma_illegal_burst_len, The burst length of the mte instruction is incorrect.",
        31: "mte_gdma_illegal_burst_num, The burst num of the mte command is incorrect.",
        32: "mte_gdma_read_overflow, The address for the MTE instruction to read on-chip buffer is out of bounds.",
        33: "mte_gdma_write_overflow, The address for the MTE instruction to write on-chip buffer is out of bounds.",
        34: "mte_comp, A new index table is delivered before the current index is completed.",
        35: "mte_illegal_fm_size, The feature map size of the mte load3d instruction is illegal(size = 0).",
        36: "mte_illegal_l1_3d_size, The set l1 3D size of the mte load3d instruction is illegal.",
        37: "mte_illegal_stride, The stride size of the mte load3d instruction is illegal.",
        38: "mte_l0a_rdwr_cflt, L0A read/write conflict in the MTE (same address).",
        39: "mte_l0b_rdwr_cflt, L0B read/write conflict in the MTE (same address).",
        40: "mte_l1_ecc, A multi-bit ECC error occurs when MTE reads/writes L1. See the RAS alarm handling.",
        41: "mte_padding_cfg, The error in mte load3d padding configuration.",
        42: "mte_read_overflow, The read address of the mte load2d instruction is greater than the maximum address of "
        "the source (L1).",
        43: "mte_rob_ecc, A multi-bit ECC error occurs when MTE reads/writes the internal buffer. See the RAS alarm "
        "handling.",
        44: "mte_tlu_ecc, An error occurred during the ECC check of the MTE TLU.",
        45: "mte_ub_ecc, A multi-bit ECC error occurs when MTE reads/writes UB. See the RAS alarm handling.",
        46: "mte_unzip, Decompression exception: length check or parity check or empty FIFO read or full FIFO write.",
        47: "mte_write_3d_overflow, The write address of the mte load3d instruction is out of bounds.",
        48: "mte_write_overflow, The write address of the mte load2d instruction is greater than the maximum "
        "destination address.",
        49: "vec_data_excp_ccu, Data from the CCU is abnormal.",
        50: "vec_data_excp_mte, Data from the MTE is abnormal.",
        51: "vec_data_excp_vec, Data from the VEC is abnormal.",
        52: "vec_div0, VEC instruction error: reciprocal division by 0 error.",
        53: "vec_illegal_mask, VEC instruction error: the MASK instruction is all 0.",
        54: "vec_inf_nan, VEC instruction error: the data is inf or nan.",
        55: "vec_l0c_ecc, A multi-bit ECC error occurs when VEC reads L0C. See the RAS alarm handling.",
        56: "vec_l0c_rdwr_cflt, VEC reads/writes L0C and cube reads/writes L0C addresses are the same.",
        57: "vec_neg_ln, VEC instruction error: the value of ln is a negative number.",
        58: "vec_neg_sqrt, VEC instruction error: the reciprocal of the square root is a negative number.",
        59: "vec_same_blk_addr, VEC instruction error: the destination blocks have the same address.",
        60: "vec_ub_ecc, A multi-bit ECC error occurs when VEC reads UB. See the RAS alarm handling.",
        61: "vec_ub_self_rdwr_cflt, The address for VEC to read UB confilicts that for VEC to write UB.",
        62: "vec_ub_wrap_around, The address for the VEC instruction to read/write UB is out of bounds.",
        63: "biu_dfx_err, BIU error, which need to be further read from BIU_STATUS1 bit 15:11.",
        64: "ccu_sbuf_ecc, ECC is reported in the CCU Scalar buffer.",
        65: "vec_col2img_rd_fm_addr_ovflow, The value of col2img is invalid.",
        66: "vec_col2img_rd_dfm_addr_ovfflow, The value of col2img is invalid.",
        67: "vec_col2img_illegal_fm_size, The value of col2img is invalid.",
        68: "vec_col2img_illegal_stride, The value of col2img is invalid.",
        69: "vec_col2img_illegal_1st_win_pos, The value of col2img is invalid.",
        70: "vec_col2img_illegal_fetch_pos, The value of col2img is invalid.",
        71: "vec_col2img_illegal_k_size, The value of col2img is invalid.",
        72: "ccu_inf_nan, The input of the floating-point instruction run by the CCU is nan/inf.",
        73: "mte_illegal_schn_cfg, The small_channal enable flag is valid but does not meet the conditions for "
        "small_channal.",
        74: "mte_atm_addr_misalg, The address of the MTE atomic instruction is not aligned with the data type bit "
        "width.",
        75: "vec_instr_addr_misalign, The UB address accessed by the VEC instruction is not aligned.",
        76: "vec_instr_illegal_cfg, The VEC instruction parameter is invalid.",
        77: "vec_instr_undef, The VEC instruction is abnormal. Possible cause: The parameter violates the instruction "
        "constraints, the binary version does not match, or the instruction is overwritten.",
        78: "ccu_addr_err, The GM address accessed by scalar exceeds 48 bits.",
        79: "ccu_bus_err, The scalar instruction accesses an invalid GM address or the cross-device memory access "
        "times out.",
        80: "mte_err_addr_misalign, The access address of the MTE instruction is not aligned with the data type bit "
        "width.",
        81: "mte_err_dw_pad_conf_err, DEPTHWIS PADDING is incorrectly configured.",
        82: "mte_err_dw_fmap_h_illegal, The value of H configured on the DEPTHWISE FMAP is less than 3.",
        83: "mte_err_wino_l0b_write_overflow, L0B address overflow occurs when the WINOB writes to the L0B address.",
        84: "mte_err_wino_l0b_read_overflow, The L1 address read by WINOB overflows, and the loop occurs.",
        85: "mte_err_illegal_v_cov_pad_ctl, The value of WINOA V padding is invalid.",
        86: "mte_err_illegal_h_cov_pad_ctl, The value of WINOA H padding is invalid.",
        87: "mte_err_illegal_w_size, The value of WINOA fmap W is invalid.",
        88: "mte_err_illegal_h_size, The value of WINOA fmap H is invalid.",
        89: "mte_err_illegal_chn_size, The LOAD3DV2 channel size is invalid.",
        90: "mte_err_illegal_k_m_ext_step, The LOAD3DV2 K_M_EXT_STEP is invalid.",
        91: "mte_err_illegal_k_m_start_pos, The LOAD3DV2 K_M_START_POS is invalid.",
        92: "mte_err_illegal_smallk_cfg, The small K configuration of the MTE load3d instruction is incorrect.",
        93: "mte_err_read_3d_overflow, The address for the LOAD3D to read L1 is out of bounds.",
        94: "ccu_veciq_ecc, A multi-bit ECC error occurs when VEC instructions issue. See the RAS alarm handling.",
        95: "ccu_dc_data_ecc, A multi-bit ECC error occurs when scalar accesses the dcache data. See the RAS alarm "
        "handling.",
        96: "ccu_dc_tag_ecc, A multi-bit ECC error occurs when scalar accesses the dcache tag. See the RAS alarm "
        "handling.",
        97: "ccu_div0_fp, A error occurs in the FP32 DIV0.",
        98: "ccu_neg_sqrt_fp, The input of the FP SQRT calculation unit is a negative number.",
        99: "cnt_sw_bus_err, During the slow context switch, the SC transfers data through the AXI bus, and the AXI "
        "returns an error.",
        100: "fixp_err_instr_addr_misal, The address for FIXP to read L0C/L1 and write FIXP buffer is not aligned.",
        101: "fixp_err_illegal_cfg, The parameter of the FIXP instruction is invalid.",
        102: "fixp_err_read_l0c_ovflw, The address for FIXP to read L0C is out of bounds.",
        103: "fixp_err_read_l1_ovflw, The address for FIXP to read L1 is out of bounds.",
        104: "fixp_err_read_ub_ovflw, The address for FIXP to read UB is out of bounds.",
        105: "fixp_err_write_l1_ovflw, The address for FIXP to write L1 is out of bounds.",
        106: "fixp_err_write_ub_ovflw, The address for FIXP to write UB is out of bounds.",
        107: "fixp_err_fbuf_write_ovflw, The address for FIXP to write FIXP buffer is out of bounds.",
        108: "fixp_err_fbuf_read_ovflw, The address for FIXP to read FIXP buffer is out of bounds.",
        109: "sc_reg_parity_err, During safety check, parity errors occur in the registers in the nManager.",
        110: "mte_err_fifo_parity, A parity error occurs when MTE reads FIFO. See the RAS alarm handling.",
        111: "mte_err_waitset, The configuration of HWATI/HSET is incorrect.",
        112: "ccu_err_parity_err, A parity error occurs in the SU internal buffer during the safety feature.",
        113: "mte_err_cache_ecc, The MTE internal MVF cache fails.",
        114: "cube_err_hset_cnt_unf, A underflow error occurs in the CUBE HSET counter.",
        115: "cube_err_hset_cnt_ovf, A overflow error occurs in the CUBE HSET counter.",
        116: "mte_err_instr_illegal_cfg, The MTE instruction parameter is invalid.",
        117: "mte_err_hebcd, The instruction configuration of HEBCD is invalid.",
        118: "mte_err_hebce, The instruction configuration of HEBCE is invalid.",
        119: "mte_err_waipp, The instruction configuration of WAIPP is invalid.",
        120: "ccu_seq_err, The SEQ command sequence is incorrect.",
        121: "ccu_mpu_err, The address for the scalar to access the internal buffer of AICore is out of bounds.",
        122: "ccu_lsu_err, When the buffer is enabled, the stack access instruction cache is missed.",
        123: "ccu_pb_ecc_err, A multi-bit ECC error occurs when scalar read parameter buffer. See the RAS alarm "
        "handling.",
        124: "mte_ub_wr_ovflw, The address for MTE to write UB is out of bounds.",
        125: "mte_ub_rd_ovflw, The address for MTE to read UB is out of bounds.",
        126: "cube_illegal_instr, The CUBE instruction parameter is invalid.",
        127: "ccu_safety_crc_err, MTE CRC error.",
        128: "mte_timeout, An exception is reported when the MTE instruction or data times out.",
        129: "mte_ub_rd_cflt, When the MTE reads the ub, the ub read/write conflict occurs and an exception is "
        "reported.",
        130: "mte_ub_wr_cflt, When the MTE writes to the UB, the UB read/write conflict is reported.",
        131: "mte_ktable_wr_addr_overflow, An exception is reported when a write address conflict occurs when the MTE "
        "is full.",
        132: "mte_ktable_rd_addr_overflow, An exception is reported when a read address conflict occurs when the MTE "
        "is empty.",
        133: "ccu_ub_rd_cflt, When the CCU reads the UB, the UB read and write conflict is reported.",
        134: "ccu_ub_wr_cflt, When the CCU writes data to the UB, the UB read and write conflict occurs.",
        135: "ccu_ub_overflow_err, The address for scalar to read/write UB is out of bounds.",
        136: "biu_unsplit_err, An exception occurs on the BIU, for example, tag_id error or FIFO overflow.",
        137: "mte_stb_ecc_err, A multi-bit ECC error occurs when MTE read STB buffer. See the RAS alarm handling.",
        138: "mte_aipp_ecc_err, A multi-bit ECC error occurs when MTE read the internal buffer of AIPP. See the RAS "
        "alarm handling.",
        139: "ccu_lsu_atomic_err, The scalar atomic instruction accesses the GM that is modified by scalar but is not "
        "written back.",
        140: "ccu_cross_core_set_ovfl_err, The value of the flag counter for inter-core communication exceeds the "
        "maximum value 15.",
        141: "fixp_err_out_write_overflow, The GM address accessed by FIXP exceeds 48 bits.",
        142: "cube_err_pbuf_wrap_around, The address for CUBE to read FIXP buffer is out of bounds.",
        143: "fixp_l0c_ecc, A multi-bit ECC error occurs when FIXP read L0C. See the RAS alarm handling.",
        144: "mte_err_l0c_rdwr_cflt, The address for FIXP to read L0C confilicts with that for CUBE to write L0C.",
        145: "vec_data_excpt_mte, An data_exception is reported when the MTE writes/reads.",
        146: "vec_data_excpt_su, An data_exception is reported when the SU writes/reads.",
        147: "vec_data_excpt_vec, An data_exception is reported when the VECTOR writes/reads.",
        148: "vec_instr_timeout, The instruction running timeout.",
        149: "vec_instrs_undef, The instruction is not defined in ISA.",
        150: "vec_instr_ill_cfg, The instruction configuration of VEC is illegal.",
        151: "vec_instr_misalign, The instruction access UB address is not aligned.",
        152: "vec_instr_ill_mask, The mask value is invalid.",
        153: "vec_instr_ill_sqzn, The sqzn value is invalid.",
        154: "vec_ub_addr_wrap_around, The access address of the UB is out of range.",
        155: "vec_ub_ecc_mberr, Multi-bit ECC error occurs when access UB.",
        156: "vec_idata_inf_nan, The input data of the instruction operation is INF/NAN.",
        157: "vec_div_by_zero, The instruction of VEC divide-by-zero error.",
        158: "vec_valu_neg_ln, The input data of the VALU lN operation is a negative number.",
        159: "vec_valu_neg_sqrt, The input data of the VALU squart operation is a negative number.",
        160: "vec_vci_idata_out_range, The input data of the VCI instruction is out of range.",
        161: "vec_ill_vloop_op, A opcode error occurs in the VLOOP instruction.",
        162: "vec_ill_vloop_sreg, The number of VLOOP loop times at layer 4 is all 0.",
        163: "vec_ld_num_mismatch, The code segment where the ld instruction resides contains a non-ld instruction.",
        164: "vec_st_num_mismatch, The code segment where the st instruction resides contains a non-st instruction.",
        165: "vec_ex_num_mismatch, The code segment where the ex instruction resides contains a non-ex instruction.",
        166: "vec_ld_num_exceed_limit, The number of ld instructions exceeds the maximum specified in the ISA.",
        167: "vec_st_num_exceed_limit, The number of st instructions exceeds the maximum specified in the ISA.",
        168: "vec_ill_instr_padding, The PADDING instruction of the VGA and VPD is not a VNOP.",
        169: "vec_ill_vga_vpd_order, The order of the VGA and VPD commands violates IAS constraints.",
        170: "vec_ic_ecc_err, An ECC error occurs in the instruction fetched from the VEC ICACHE.",
        171: "vec_biu_resp_err, The data returned by the BIU to the VEC is incorrect.",
        172: "vec_pb_ecc_mberr, The PB data returned by the SU to the VEC contains ECC errors.",
        173: "vec_pb_read_no_resp, The SU does not respond for a long time after receiving a PB read request from the "
        "VEC.",
        174: "vec_valu_ill_issue, VALU instruction transmit order violates ISA constraints.",
        175: "vec_err_parity_err, A parity check error occurs in the VEC.",
    }

    # Key-space segmentation of AIC_ERROR_INFO_DICT_DAVID, mirroring
    # RINGBUFFER_*_ERROR_OFFSET in runtime/src/runtime/core/inc/device/device_error_info.hpp.
    DAVID_OFFSET_CUBE = 0
    DAVID_OFFSET_MTE = 64
    DAVID_OFFSET_L1 = 128
    DAVID_OFFSET_L1_1 = 160
    DAVID_OFFSET_SC = 192
    DAVID_OFFSET_SU = 256
    DAVID_OFFSET_VEC = 320
    DAVID_OFFSET_VEC_1 = 352

    # AI Core error bit number -> {"name", "desc"} for the David / 950 form.
    # Source of truth: g_davidErrorMapInfo in
    # runtime/src/runtime/core/src/device/v200_base/device_error_proc_c.cc, with keys
    # resolved through RtDavidCoreErrorType in
    # runtime/src/runtime/core/inc_c/device_error_proc_c.hpp.
    # Keys are absolute bit numbers already offset by module, so no further
    # bit scan is needed: the runtime prints the resolved list in `error code`.
    AIC_ERROR_INFO_DICT_DAVID = {
        0: {
            "name": "CUBE_ERR_L0A_RDWR_CFLT",
            "desc": "Software's L0A Ping/Pong memory allocation scheme has problem.",
        },
        1: {
            "name": "CUBE_ERR_L0B_RDWR_CFLT",
            "desc": "Software's L0B Ping/Pong memory allocation scheme has problem.",
        },
        2: {
            "name": "CUBE_ERR_L0C_RDWR_CFLT",
            "desc": "Software's L0C Ping/Pong memory allocation scheme has problem.",
        },
        4: {
            "name": "CUBE_INVLD_INPUT",
            "desc": "the data read back from L0a and L0b are INF or NAN.",
        },
        5: {
            "name": "CUBE_L0A_WRAP_AROUND",
            "desc": "The address for CUBE to operate L0A is out of bounds.",
        },
        6: {
            "name": "CUBE_L0B_WRAP_AROUND",
            "desc": "The address for CUBE to operate L0B is out of bounds.",
        },
        7: {
            "name": "CUBE_L0C_WRAP_AROUND",
            "desc": "The address for CUBE to operate L0C is out of bounds.",
        },
        8: {
            "name": "CUBE_L0A_ECC",
            "desc": "A multi-bit ECC error occurs when CUBE reads L0A. See the RAS alarm handling.",
        },
        9: {
            "name": "CUBE_L0B_ECC",
            "desc": "A multi-bit ECC error occurs when CUBE reads L0B. See the RAS alarm handling.",
        },
        10: {
            "name": "CUBE_L0C_ECC",
            "desc": "A multi-bit ECC error occurs when CUBE reads L0C. See the RAS alarm handling.",
        },
        11: {
            "name": "CUBE_ILLEGAL_INSTR",
            "desc": "The CUBE instruction is abnormal. Possible cause: The parameter violates the instruction "
            "constraints, the binary version does not match, or the instruction is overwritten",
        },
        12: {
            "name": "CUBE_ERR_HSET_CNT_OVF",
            "desc": "An overflow error occurs in the CUBE HSET counter.",
        },
        13: {
            "name": "CUBE_ERR_HSET_CNT_UNF",
            "desc": "An underflow error occurs in the CUBE HSET counter.",
        },
        14: {
            "name": "CUBE_ERR_PBUF_WRAP_AROUND",
            "desc": "The address for CUBE to operate FIXP buffer is out of bounds.",
        },
        15: {
            "name": "CUBE_ERR_PARITY_ERR",
            "desc": "Parity error for the Cube parity ERR register.",
        },
        16: {
            "name": "CUBE_ERR_SF_ECC_MB_ERR",
            "desc": "A multi-bit ECC error occurs when CUBE reads MX buffer. See the RAS alarm handling.",
        },
        17: {
            "name": "CUBE_ERR_L0ASF_WRAP_AROUND",
            "desc": "CUBE L0A memory read write conflict.",
        },
        18: {
            "name": "CUBE_ERR_L0BSF_WRAP_AROUND",
            "desc": "CUBE L0B memory read write conflict.",
        },
        32: {"name": "CUBE_INSTR_UNDEF", "desc": "The operation code is illegal."},
        33: {
            "name": "CUBE_INSTR_ILL_CFG",
            "desc": "The instruction configuration of CUBE is illegal.",
        },
        34: {
            "name": "CUBE_INSTR_ADDR_MISALIGN",
            "desc": "The CUBE instruction address misalign.",
        },
        35: {
            "name": "CUBE_FM_ADDR_OVERFLOW",
            "desc": "Feature map(conv/wino) of left matrix(matmul) exceeds L1.",
        },
        36: {
            "name": "CUBE_NONBRANCH_BIAS_OVERFLOW",
            "desc": "Non-brc bias addr exceeds L1.",
        },
        37: {"name": "CUBE_ELW_ADDR_OVERFLOW", "desc": "Elw addr exceeds L1."},
        38: {
            "name": "CUBE_KERNEL_ADDR_OVERFLOW",
            "desc": "Kernel(conv/wino) or right matrix(matmul) exceeds L1.",
        },
        39: {
            "name": "CUBE_FB_ADDR_OVERFLOW",
            "desc": "Fixp parameter buffer addr exceeds 6k.",
        },
        40: {"name": "CUBE_BT_ADDR_OVERFLOW", "desc": "Bias table addr exceeds L1."},
        41: {
            "name": "CUBE_RESULT_ADDR_OVERFLOW",
            "desc": "Cube result addr exceeds L1.",
        },
        64: {
            "name": "MTE_NDDMA_CACHE_ECC",
            "desc": "A multi-bit ECC error occurs when MTE reads NDDMA cache. See the RAS alarm handling.",
        },
        65: {
            "name": "MTE_NDDMA_REG_BUF_ECC",
            "desc": "A multi-bit ECC error occurs when MTE reads NDDMA request buffer. See the RAS alarm handling.",
        },
        66: {
            "name": "MTE_L1_ECC",
            "desc": "A multi-bit ECC error occurs when MTE2 and MTE3 read L1. See the RAS alarm handling.",
        },
        67: {
            "name": "MTE_CFG_REG_PARITY",
            "desc": "A parity error occurs when AICore reads the CFG register. See the RAS alarm handling",
        },
        68: {
            "name": "MTE_L0A_RDWR_CFLT",
            "desc": "CUBE L0A memory read write conflict.",
        },
        69: {
            "name": "MTE_L0B_RDWR_CFLT",
            "desc": "CUBE L0B memory read write conflict.",
        },
        71: {
            "name": "MTE_OFFSET_MISALIGN",
            "desc": "MTE gather/scatter dma instruction offset misalign.",
        },
        72: {
            "name": "MTE_XGAMMA_LINE_SEQ_WRON",
            "desc": "In the xgamma operation, the first line is not loaded before computation begins;moreover, there "
            "is no end-of-line marker to signal the completion of the current image before proceeding to the "
            "next image.",
        },
        73: {
            "name": "MTE_READ_OVERFLOW",
            "desc": "The address of the MTE 2D instruction to read L1 is out of bounds.",
        },
        74: {
            "name": "MTE_WRITE_OVERFLOW",
            "desc": "The address of the MTE 2D instruction to write L1/L0A/L0B is out of bounds.",
        },
        75: {
            "name": "MTE_BIF_CFG_REG_PARITY",
            "desc": "BIF configuration parity error.",
        },
        78: {
            "name": "MTE_INSTR_ILLEGAL_CFG",
            "desc": "The MTE instruction is abnormal. Possible cause: The parameter violates the instruction "
            "constraints, the binary version does not match, or the instruction is overwritten",
        },
        79: {
            "name": "MTE_ATM_ADD_ADDR_MISALIGN",
            "desc": "The MTE atomic instruction address is not aligned.",
        },
        80: {
            "name": "MTE_INSTR_ADDR_MISALIGN",
            "desc": "The MTE non-atomic instruction address is not aligned.",
        },
        81: {
            "name": "MTE_GDMA_READ_OVERFLOW",
            "desc": "The address for MTE2 to read UB and MTE3 to read L1/UB is out of bounds.",
        },
        82: {
            "name": "MTE_GDMA_WRITE_OVERFLOW",
            "desc": "The address for MTE2 to write UB and MTE3 to write L1/UB is out of bounds.",
        },
        83: {
            "name": "MTE_GDMA_ILLEGAL_BURST_NUM",
            "desc": "The burst number value of the MOV instruction is abnormal.",
        },
        84: {
            "name": "MTE_GDMA_ILLEGAL_BURST_LEN",
            "desc": "The burst length value of the MOV instruction is abnormal.",
        },
        85: {
            "name": "MTE_AIPP_ILLEGAL_PARAM",
            "desc": "AIPP decompression instruction configuration error.",
        },
        86: {
            "name": "MTE_ERR_UNZIP",
            "desc": "UNZIP decompression instruction configuration error.",
        },
        87: {
            "name": "MTE_XGAMMA_LB0_ECC",
            "desc": "MTE XGAMMA LB0 multi-bit ECC error.",
        },
        88: {
            "name": "MTE_XGAMMA_LB1_ECC",
            "desc": "MTE XGAMMA LB1 multi-bit ECC error.",
        },
        89: {"name": "MTE_ERR_WAIPP", "desc": "WAIPP instruction configuration error."},
        90: {
            "name": "MTE_STB_ECC",
            "desc": "A multi-bit ECC error occurs when MTE reads STB buffer. See the RAS alarm handling.",
        },
        91: {"name": "MTE_AIPP_ECC", "desc": "MTE AIPP multi-bit ECC error."},
        92: {
            "name": "MTE_TAGMGR_BUF_ECC",
            "desc": "A multi-bit ECC error occurs when MTE reads tagmgr buffer. See the RAS alarm handling.",
        },
        93: {
            "name": "MTE_UB_ECC",
            "desc": "A multi-bit ECC error occurs when MTE reads UB. See the RAS alarm handling.",
        },
        94: {
            "name": "MTE_ROB_ECC",
            "desc": "A multi-bit ECC error occurs when MTE reads ROB buffer. See the RAS alarm handling.",
        },
        95: {
            "name": "MTE_BIU_RDWR_RESP",
            "desc": "The MTE instruction accesses an invalid GM address or the cross-device memory access timeout.",
        },
        128: {
            "name": "L1_L0A_RDWR_CFLT",
            "desc": "The address for MTE to write L0A conflicts with that for CUBE to read L0A.",
        },
        129: {
            "name": "L1_L0B_RDWR_CFLT",
            "desc": "The address for MTE to write L0B conflicts with that for CUBE to read L0B.",
        },
        130: {
            "name": "L1_READ_2D_OVERFLOW",
            "desc": "The address of the LOAD2D instruction to read L1 is out of bounds.",
        },
        131: {
            "name": "L1_WRITE_2D_OVERFLOW",
            "desc": "The address of the LOAD2D instruction to write L0A/L0B is out of bounds.",
        },
        132: {
            "name": "L1_DWS_PAD_CONF_ERR",
            "desc": "DEPTHWISE PADDING illegal configuration.",
        },
        133: {
            "name": "L1_DWS_FMAP_H_ILLEGAL",
            "desc": "DEPTHWISE FMAP illegal configuration.",
        },
        134: {"name": "L1_WINO_L0B_WRITE_OVERFLOW", "desc": "WINOB write overflow."},
        135: {"name": "L1_WINO_L0B_READ_OVERFLOW", "desc": "WINOB read overflow."},
        136: {"name": "L1_WINO_L0A_WRITE_OVERFLOW", "desc": "WINOA write overflow."},
        137: {"name": "L1_WINO_L0A_READ_OVERFLOW", "desc": "WINOA read overflow."},
        138: {
            "name": "L1_WINO_ILLEGAL_V_COV_PAD_CTL",
            "desc": "WINO V padding value is invalid.",
        },
        139: {
            "name": "L1_WINO_ILLEGAL_H_COV_PAD_CTL",
            "desc": "WINO H padding value is invalid.",
        },
        140: {
            "name": "L1_ILLEGAL_W_SIZE",
            "desc": "WINOA FMAP width + PADDING value is less than 4.",
        },
        141: {
            "name": "L1_ILLEGAL_H_SIZE",
            "desc": "WINOA FMAP height + PADDING value is less than 4.",
        },
        142: {
            "name": "L1_ILLEGAL_CHN_SIZE",
            "desc": "The value of L1H*L1W*channel size of the LOAD3DV2 instruction is greater than the size of L1, "
            "or the channel size is not aligned.",
        },
        143: {
            "name": "L1_ILLEGAL_K_M_EXT_STEP",
            "desc": "The k start pos + k step or m start pos + m step of the LOAD3D instruction exceeds the range of "
            "the km matrix (the tail is considered as 16 if it is less than 16), or the fractal number "
            "calculated by step exceeds the range of L0A/L0B.",
        },
        144: {
            "name": "L1_ILLEGAL_K_M_START_POS",
            "desc": "The km start pos of the LOAD3D instruction is out of the range of the KM matrix, the k start "
            "pos is not an integral multiple of the number of 32-byte data elements corresponding to the "
            "data type, or the m start pos is not an integral multiple of 16.",
        },
        145: {
            "name": "L1_ILLEGAL_SCHN_CFG",
            "desc": "Small channel mode configuration error.",
        },
        146: {
            "name": "L1_ILLEGAL_SMALLK_CFG",
            "desc": "LOAD3D small k configuration error.",
        },
        147: {
            "name": "L1_ILLEGAL_FM_SIZE",
            "desc": "The width or height of the feature map of the LOAD3D instruction is greater than 0X8000, or the "
            "area of the feature map is greater than the size of the L1 memory.",
        },
        148: {
            "name": "L1_ILLEGAL_L1_3D_SIZE",
            "desc": "LOAD3DV2 L1 3D size is invalid.",
        },
        149: {
            "name": "L1_ILLEGAL_STRIDE",
            "desc": "The stride_w or stride_h of the LOAD3D instruction is 0.",
        },
        150: {
            "name": "L1_PADDING_CFG",
            "desc": "The padding configuration of the LOAD3D instruction is invalid.",
        },
        151: {
            "name": "L1_READ_3D_OVERFLOW",
            "desc": "The address for the LOAD3D instruction to read L1 is out of bounds.",
        },
        152: {
            "name": "L1_WRITE_3D_OVERFLOW",
            "desc": "The address for the LOAD3D instruction to write L0A/L0B is out of bounds.",
        },
        153: {
            "name": "L1_BAS_RADDR_OBOUND",
            "desc": "The initial address specified for the LOAD3D instruction is out of the L1 3D size range.",
        },
        155: {
            "name": "L1_F1WPOS_LARGER_FSIZE",
            "desc": "The position of the first window of LOAD3D exceeds the left or upper padding boundary, or "
            "exceeds the right or lower padding boundary of the feature map(without padding).",
        },
        156: {
            "name": "L1_FMAP_LESS_KERNEL",
            "desc": "The width of the LOAD3D filter is greater than the width of the feature map plus padding. or "
            "the height of the filter after dilation is greater than the height of the feature map plus "
            "padding.",
        },
        157: {
            "name": "L1_FMAPWH_LARGER_L1SIZE",
            "desc": "The LOAD3D parameter is invalid. L1H*L1W*(C1+1) is greater than L1 buffer size/32.",
        },
        158: {
            "name": "L1_FPOS_LARGER_FSIZE",
            "desc": "The LOAD3D K position is out of the filter range.",
        },
        160: {"name": "L1_ERR_FIFO_PARITY", "desc": "L1/FIXP fifo parity."},
        161: {
            "name": "FIXP_BIU_RDWR_RESP",
            "desc": "The address for fixpipe to write GM is invalid",
        },
        162: {
            "name": "FIXP_STB_ECC_ERR",
            "desc": "A multi-bit ECC error occurs when fixpipe reads STB buffer. See the RAS alarm handling",
        },
        163: {
            "name": "FIXP_FBUF_WR_OVERFLOW",
            "desc": "The address for fixpipe to write FBUF is out of bounds.",
        },
        164: {
            "name": "FIXP_FBUF_RD_OVERFLOW",
            "desc": "The address for fixpipe to read FBUF is out of bounds.",
        },
        165: {
            "name": "FIXP_OUT_WR_OVERFLOW",
            "desc": "An overflow error occurs when the FIXP write.",
        },
        166: {
            "name": "FIXP_L1_WR_OVERFLOW",
            "desc": "The address for fixpipe to write L1 is out of bounds.",
        },
        167: {
            "name": "FIXP_L1_RD_OVERFLOW",
            "desc": "The address for fixpipe to read L1 is out of bounds.",
        },
        168: {
            "name": "FIXP_L0C_RD_OVERFLOW",
            "desc": "The address for fixpipe to read L0C is out of bounds.",
        },
        169: {
            "name": "FIXP_ILLEGAL_CFG",
            "desc": "The fixpipe instruction parameter is invalid.",
        },
        170: {
            "name": "FIXP_ADDR_MISAL",
            "desc": "The address for fixpipe to read L0C, read/write L1, and read/write FBUF is not aligned.",
        },
        171: {
            "name": "FIXP_L0C_ECC_ERR",
            "desc": "A multi-bit ECC error occurs when fixpipe reads L0C. See the RAS alarm handling.",
        },
        172: {
            "name": "FIXP_L0C_RDWR_CFLT",
            "desc": "The address for fixpipe to read L0C conflicts with that for CUBE to write L0C.",
        },
        173: {
            "name": "FIXP_WRITE_UB_OVFLW",
            "desc": "The address for fixpipe to write UB is out of bounds.",
        },
        174: {
            "name": "L1_UB_WR_OVFLW",
            "desc": "The address for MTE to move from L1 to UB is out of bounds.",
        },
        175: {
            "name": "L1_WAITSET_ERR",
            "desc": "The configuration of HWATI/HSET is invalid.",
        },
        176: {
            "name": "L1_L1_ECC",
            "desc": "A multi-bit ECC error occurs when MTE/fixpipe reads L1. See the RAS alarm handling.",
        },
        177: {
            "name": "L1_GDMA_READ_OVERFLOW",
            "desc": "The address for the MTE instruction to read L1 is out of bounds.",
        },
        178: {
            "name": "L1_GDMA_WRITE_OVERFLOW",
            "desc": "The address for the MTE instruction to write the L0A/L0B bias table is out of bounds.",
        },
        179: {
            "name": "L1_INSTR_ILLEGAL_CFG",
            "desc": "The MTE instruction is abnormal. Possible cause: The parameter violates the instruction "
            "constraints, the binary version does not match, or the instruction is overwritten.",
        },
        180: {
            "name": "L1_INSTR_ADDR_MISALIGN",
            "desc": "The MTE instruction address is not aligned.",
        },
        181: {
            "name": "L1_SC_CFG_PARITY",
            "desc": "L1 SC configuration registers parity error.",
        },
        182: {
            "name": "L1_FIXP_BT_NAN_INF",
            "desc": "MTE1 biasbuf path conversion NaN/Inf error.",
        },
        192: {
            "name": "SC_CNT_SW_BUS_ERR",
            "desc": "During a slow context switch, SC encounters a bus error while transferring data.",
        },
        193: {
            "name": "SC_REG_PARITY_ERR",
            "desc": "A parity error occurred in the CFG register inside SC.",
        },
        194: {
            "name": "SC_SLOW_CSW_ROB_ECC_ERR",
            "desc": "During a slow CSW in SC, the ROB RAM from the SU's IFU is reused for reading,resulting in 2 "
            "2-bit ECC error.",
        },
        195: {
            "name": "SC_BUS_RESP_TIMEOUT_ERR",
            "desc": "The bus is busy, and the response times out.",
        },
        256: {
            "name": "SU_IFU_BUS_ERR_T0",
            "desc": "The address of instruction is illegal when the AIcore reads instructions from GM.Possible "
            "cause: The application unloads the operator binary in advance or stack corruption occurs.",
        },
        257: {
            "name": "SU_CCU_CALL_DEPTH_OVRFLW_T0",
            "desc": "The number of nesting times of call the function is greater than CTRL[5:2].",
        },
        258: {"name": "SU_CCU_DIV0_T0", "desc": "divide by 0."},
        259: {
            "name": "SU_CCU_ILLEGAL_INSTR_T0",
            "desc": "The scalar instruction is abnormal. Possible cause: The parameter violates the instruction "
            "constraints, the binary version does not match, or the instruction is overwritten.",
        },
        260: {"name": "SU_CCU_NEG_SQRT_T0", "desc": "The number of roots is negative."},
        261: {
            "name": "SU_CCU_UB_ECC_T0",
            "desc": "A multi-bit ECC error occurs when scalar accesses UB. See the RAS alarm handling.",
        },
        262: {
            "name": "SU_CCU_INF_NAN_T0",
            "desc": "The input of the floating-point instruction run by the CCU is nan/inf.",
        },
        263: {
            "name": "SU_CCU_ADDR_ERR_T0",
            "desc": "The address for scalar to use is unaligned or out of bounds The GM address exceeds 48 bits, or "
            "the on-chip buffer address exceeds the size of the buffer.",
        },
        264: {
            "name": "SU_CCU_BUS_ERR_T0",
            "desc": "The address for scalar to access GM is invalid",
        },
        265: {
            "name": "SU_CCU_DC_DATA_ECC_T0",
            "desc": "A multi-bit ECC error occurs when scalar accesses dcache data. See the RAS alarm handling.",
        },
        266: {
            "name": "SU_CCU_DC_TAG_ECC_T0",
            "desc": "A multi-bit ECC error occurs when scalar accesses dcache tag. See the RAS alarm handling.",
        },
        267: {"name": "SU_CCU_DIV0_FP_T0", "desc": "An error occurs in the FP32 DIV0."},
        268: {
            "name": "SU_CCU_NEG_SQRT_FP_T0",
            "desc": "The input of the FP SQRT calculation unit is a negative number.",
        },
        269: {
            "name": "SU_CCU_ERR_PARITY_ERR_T0",
            "desc": "A parity error occurs when SU reads FIFO. See the RAS alarm handling.",
        },
        270: {
            "name": "SU_CCU_SEQ_ERR_T0",
            "desc": "The SEQ command sequence is incorrect.",
        },
        271: {
            "name": "SU_CCU_MPU_ERR_T0",
            "desc": "The address for scalar to access the internal buffer is out of bounds.",
        },
        272: {
            "name": "SU_CCU_LSU_ERR_T0",
            "desc": "When the buffer is enabled, the stack access instruction cache is miss.",
        },
        273: {
            "name": "SU_CCU_PB_ECC_ERR_T0",
            "desc": "A multi-bit ECC error occurs when scalar reads parameter buffer. See the RAS alarm handling.",
        },
        274: {"name": "SU_CCU_SAFETY_CRC_ERR_T0", "desc": "MTE CRC error."},
        275: {
            "name": "SU_CCU_LSU_ATOMIC_ERR_T0",
            "desc": "The scalar atomic instruction accesses the GM that is modified by scalar but is not written "
            "back.",
        },
        276: {
            "name": "SU_CCU_CC_SET_OVFL_ERR_T0",
            "desc": "The accumulated value of the inter-core communication flag counter exceeds the maximum value "
            "15.",
        },
        277: {
            "name": "SU_SAFETY_1BIT_ECC_OVFLW_ERR_T0",
            "desc": "Overflow error when the number of 1-bit ECC errors exceeds the preset value.",
        },
        278: {
            "name": "SU_CCU_DC_SSBUF_ECC_T0",
            "desc": "A multi-bit ECC error occurs when scalar reads SS buffer. See the RAS alarm handling.",
        },
        279: {
            "name": "SU_IFU_BUS_PTY_ERR",
            "desc": "The parity code attached to the read data returned from BIF to IFU is inconsistent with the "
            "parity code calculated by IFU, triggering a parity check error.",
        },
        280: {
            "name": "SU_BMU_ERR",
            "desc": "An exception occurred in the buf_allocate or buf_free instructions related to BMU.",
        },
        282: {
            "name": "SU_HSCB_BUS_ERR",
            "desc": "SU initiates access to the HSCB path, and the HSCB bus returns an error response.",
        },
        283: {
            "name": "SU_GET_NEXT_TASK_ERR",
            "desc": "In a task program, there is an extra get_ntxt_task_hscb instruction.",
        },
        286: {
            "name": "SU_HIT_TRAP_ERR_T0",
            "desc": "The trap instruction reports an error.",
        },
        287: {
            "name": "WARN_AS_EXCEPTION_T0",
            "desc": "A 1-bit ECC err occurs 15 times or a multi-hit event occurs in IFU during AICore execution. See "
            "the RAS alarm handling.",
        },
        288: {
            "name": "SU_IC_ECC_REPEAT_ERR",
            "desc": "ECC errors frequently occur at the same address within the same bank of the IC, and the count "
            "reaches 0xFF, triggering an exception.",
        },
        289: {
            "name": "SU_IC_ECC_OTHER_ERR",
            "desc": "Subsequent ECC errors occur at a different bank and address compared to the first ECC error, "
            "and the count reaches 0xFF, triggering an exception.",
        },
        290: {
            "name": "SU_DC_ECC_REPEAT_ERR",
            "desc": "For the DC, frequent ECC errors occur at the same bank and address, and the count reaches 0xFF, "
            "triggering an exception.",
        },
        291: {
            "name": "SU_DC_ECC_OTHER_ERR",
            "desc": "For the DC, subsequent ECC errors occur at a bank and address different from the first ECC "
            "error, and the count reaches 0xFF, triggering an exception.",
        },
        320: {
            "name": "VEC_ERR_UB_ARB_DATA_EXCP_MTE_T0",
            "desc": "Data from the MTE is abnormal.",
        },
        321: {
            "name": "VEC_ERR_UB_ARB_DATA_EXCP_SU_T0",
            "desc": "Data from the CCU is abnormal.",
        },
        322: {
            "name": "VEC_ERR_UB_ARB_DATA_EXCP_VEC_T0",
            "desc": "Data from the VEC is abnormal.",
        },
        326: {
            "name": "VEC_ERR_INSTR_TIMEOUT_T0",
            "desc": "VEC VF execution timeout. Check the configuration of Runtime",
        },
        327: {
            "name": "VEC_ERR_SU_PLD_UNDEF_T0",
            "desc": "The non-VF instruction is abnormal. Possible cause: The parameter violates the instruction "
            "constraints, the binary version does not match, or the instruction is overwritten.",
        },
        328: {
            "name": "VEC_ERR_SU_PLD_ILL_CFG_T0",
            "desc": "The parameter of the non-VF instruction is invalid.",
        },
        329: {
            "name": "VEC_ERR_PC_OVERFLOW_T0",
            "desc": "PC is greater than 48 bits. Possible cause: the compiler bug or the instruction is overwritten.",
        },
        330: {
            "name": "VEC_ERR_INSTR_UNDEF_T0",
            "desc": "The instruction in VEC VF is abnormal. Possible cause: The parameter violates the instruction "
            "constraints, the binary version does not match, or the instruction is overwritten.",
        },
        331: {
            "name": "VEC_INSTR_ILLEGAL_CFG_T0",
            "desc": "The parameter of the VEC VF instruction is invalid.",
        },
        332: {
            "name": "VEC_ERR_HWLP_STACK_OVFL_T0",
            "desc": "The number of nested VLOOP exceeds the hardware limit, which may be a compiler bug.",
        },
        333: {
            "name": "VEC_ERR_HWLP_INSTR_NUM_MISMATCH_T0",
            "desc": "For the nested VLOOP, the number of instructions in the inner loop is greater than that in the "
            "outer loop, which may be a compiler bug.",
        },
        334: {
            "name": "VEC_ERR_BIU_RESP_ERR_T0",
            "desc": "SIMT accesses an invalid GM address or the cross-device memory access times out.",
        },
        335: {
            "name": "VEC_ERR_PB_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC accesses parameter buffer. See the RAS alarm handling.",
        },
        336: {
            "name": "VEC_ERR_IDATA_INF_NAN_T0",
            "desc": "The input data of the instruction operation is INF/NAN.",
        },
        337: {
            "name": "VEC_ERR_DIV_BY_ZERO_T0",
            "desc": "Divide-by-zero error occurs for the VEC instruction.",
        },
        338: {
            "name": "VEC_ERR_VALU_NEG_LN_T0",
            "desc": "The input data of the VALU ln operation is a negative number.",
        },
        339: {
            "name": "VEC_ERR_VALU_NEG_SQRT_T0",
            "desc": "The input data of the VALU sqrt operation is a negative number.",
        },
        340: {
            "name": "VEC_ERR_UB_ADDR_OVERFLOW_T0",
            "desc": "The address for VEC to access UB is not aligned.",
        },
        341: {
            "name": "VEC_UB_WRAP_AROUND",
            "desc": "The address for VEC to access UB is out of bounds.",
        },
        342: {
            "name": "VEC_ERR_UB_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC accesses UB. See the RAS alarm handling.",
        },
        343: {
            "name": "VEC_ERR_VMS_UNSORT_T0",
            "desc": "The input data of the sorting instruction is not correctly sorted.",
        },
        344: {
            "name": "VEC_ERR_CSW_DATA_T0",
            "desc": "Exception when accessing the internal SRAM during context switch (multi-bit ECC).",
        },
        345: {
            "name": "VEC_ERR_SC_CFG_PARITY_T0",
            "desc": "SC Interface configuration register parity check error occurred.",
        },
        346: {
            "name": "VEC_ERR_UB_SB_ECC_REPEAT_ERR_T0",
            "desc": "The number of single-bit ECC errors at the same address on UB has exceeded the hard failure "
            "threshold.",
        },
        347: {
            "name": "VEC_ERR_UB_SB_ECC_OTHER_ERR_T0",
            "desc": "The number of single-bit ECC errors at different addresses on UB has exceeded the hard failure "
            "threshold.",
        },
        348: {
            "name": "VEC_ERR_IC_ECC_REPEAT_ERR_T0",
            "desc": "The number of single-bit ECC errors at the same address on ICACHE has exceeded the hard failure "
            "threshold.",
        },
        349: {
            "name": "VEC_ERR_IC_ECC_OTHER_ERR_T0",
            "desc": "The number of single-bit ECC errors at different addresses on ICACHE has exceeded the hard "
            "failure threshold.",
        },
        352: {
            "name": "VEC_ERR_UNEXP_JOIN_T0",
            "desc": 'When the VEC executes a SIMT task, some warps end with "join" and some warps end with '
            '"end".',
        },
        353: {
            "name": "VEC_ERR_UB_SIZE_CFG_ERR_T0",
            "desc": "The dyn ubuf size is greater than 224 KB.",
        },
        354: {
            "name": "VEC_ERR_DC_STACK_ADDR_OVFL_T0",
            "desc": "The VEC SIMT stack overflows. Possible cause: The local variable is too large or there are too "
            "many local variables.",
        },
        355: {
            "name": "VEC_ERR_GM_ADDR_OVFL_T0",
            "desc": "The address for VEC to read GM is out of bounds(exceeding 48 bits).",
        },
        356: {
            "name": "VEC_ERR_DVG_STACK_OVFL_T0",
            "desc": "VEC SIMT DVG stack overflows, which may be caused by too many conditional branches or too many "
            "nested loops.",
        },
        357: {
            "name": "VEC_ERR_DVG_STACK_UNDFL_T0",
            "desc": "VEC SIMT push and pop operations do not match, which may be a compiler bug.",
        },
        358: {
            "name": "VEC_ERR_BHU_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC SIMT accesses BHU. See the RAS alarm handling.",
        },
        359: {
            "name": "VEC_ERR_MROB_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC SIMT accesses MROB. See the RAS alarm handling.",
        },
        360: {
            "name": "VEC_ERR_DCACHE_TAG_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC SIMT accesses dcache tag. See the RAS alarm handling.",
        },
        361: {
            "name": "VEC_ERR_DIRTY_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC SIMT accesses the dirty mem. See the RAS alarm handling.",
        },
        362: {
            "name": "VEC_ERR_VTH_ID_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC SIMT accesses thread ID register. See the RAS alarm "
            "handling.",
        },
        363: {
            "name": "VEC_ERR_MRF_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC SIMT accesses register table. See the RAS alarm handling.",
        },
        364: {
            "name": "VEC_ERR_DVG_ECC_MBERR_T0",
            "desc": "A multi-bit ECC error occurs when VEC SIMT accesses DVG stack. See the RAS alarm handling.",
        },
    }

    SOC_ERR_INFO_DICT = {
        "000": "read poison, 读到脏数据",
        "001": "read oob, 表示L2在作为buffer模式时, 读地址超过了配置的L2虚拟地址的size",
        "010": "read bus error, 读请求时数据异常, 例如安全访问请求访问了非安全的地址, "
        "非安全访问的请求访问了安全地址, 访问请求收不到response、atomic运算异常(1980)",
        "011": "read decode error, 读请求访问的目的地址不在各个模块的地址空间内, 也即越界",
        "101": "write oob, 表示L2在作为buffer模式时, 写地址超过了配置的L2虚拟地址的size",
        "110": "write bus error, 写请求时数据异常, 例如安全访问请求访问了非安全的地址, "
        "非安全访问的请求访问了安全地址, 访问请求收不到response、atomic运算异常(1980)",
        "111": "write decode error, 写请求访问的目的地址不在各个模块的地址空间内, 也即越界",
    }

    FMC_ERR_INFO_DICT = {"000": "fmc_read_over_turn_err", "001": "fmc_blk_num_zero_err"}

    FMD_ERR_INFO_DICT = {
        "000": "fmd_write_over_turn_err",
        "001": "fmd_blk_num_zero_err",
        "010": "fmd_blk_num_noequal_err",
        "011": "fmd_header_err",
        "100": "fmd_decompress_err",
    }

    UNZIP_ERR_INFO_DICT = {
        "000": "uzp_write_over_turn_err",
        "001": "uzp_blk_num_zero_err",
        "010": "uzp_index_noenough_err",
        "011": "uzp_index_err",
        "100": "uzp_decompress_err",
    }

    AIPP_ERR_INFO_DICT = {
        "000": "aipp_mte_ex_round : 表示访问外部存储绕回",
        "001": "aipp_mte_l1_round : 表示访问L1 buffer绕回",
        "010": "aipp_mte_inerr : 表示配置AIPP SPR相关的fp16为INF或者NAN",
    }

    IFU_KEY = "IFU_ERR_INFO"
    CCU_KEY = "CCU_ERR_INFO"
    BIU_KEY = "BIU_ERR_INFO"
    CUBE_KEY = "CUBE_ERR_INFO"
    MTE_KEY = "MTE_ERR_INFO"
    VEC_KEY = "VEC_ERR_INFO"

    # 判型用：两种芯片 dump info 行上互不重叠的寄存器名，见
    # device_error_proc_c.cc（950）与 device_error_core_proc.cc（910B）。
    DAVID_ONLY_DUMP_KEYS = ("sc error info:", "su error info:", "l1 error info:")
    STARS_ONLY_DUMP_KEYS = ("ifu error info:", "ccu error info:", "biu error info:")

    # dump tiling type
    TILING_TYPE = 7

    @property
    def max_top_n(self: any) -> int:
        """
        max top n
        """
        return 100

    @property
    def min_top_n(self: any) -> int:
        """
        mix top n
        """
        return 1


class RegexPattern:
    """
    regex pattern
    """

    # core_err_type 捕获 "the error is aicore error" / "there is an aivec error" 中的
    # 类型词（PrintDavidCoreInfo / GetStarsRingBufferHeadMsg）。AIC 与 AIV 共用数字
    # core id，必须按类型词区分，否则同一 core id 会被重复统计进同一列表。
    # 类型词前有 " error" 时尽可能捕获（保护性分支），无类型词的旧日志也能匹配，
    # 由 detect_core_err_type 缺省按 aic 处理，保证整条日志不因缺类型词而漏匹配。
    _CORE_ERR_TYPE = r"aivector|aivec|aicore|aiv|aic"

    AICORE_ERR_OCCUR = (
        r"(?P<err_time>\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).+?\.(?:cc|cpp)\:\d+\](?P<thread_id>\d+)"
        r".+?device\((?P<dev_id>[a-zA-Z0-9\s,:]{1,})\),\s"
        r"[a-zA-Z0-9\s,]*?(?:(?P<core_err_type>"
        + _CORE_ERR_TYPE
        + r")\s+error[^,]*?|(?![a-zA-Z0-9\s,]*?(?:"
        + _CORE_ERR_TYPE
        + r")\s+error)[a-zA-Z0-9\s,]+?),\s+"
        r"core id is (?P<core_id>\d+),\s+error code = "
        r"(?P<error_code>0x[0-9a-fA-F]+|\d+(?:,\s*\d+)*),.*?"
        r"pc start:\s(?P<start_pc>\S+),\scurrent:\s(?P<current_pc>\S+),\s(?P<extra_info>.*?\.)"
    )

    AICORE_ERR_OCCUR_OST = (
        r"(?P<err_time>\d+-\d+-\d+-\d+:\d+:\d+\.\d+\.\d+).+?\.(?:cc|cpp)\:\d+\](?P<thread_id>\d+)"
        r".+?device\((?P<dev_id>[a-zA-Z0-9\s,:]{1,})\),\s"
        r"[a-zA-Z0-9\s,]*?(?:(?P<core_err_type>"
        + _CORE_ERR_TYPE
        + r")\s+error[^,]*?|(?![a-zA-Z0-9\s,]*?(?:"
        + _CORE_ERR_TYPE
        + r")\s+error)[a-zA-Z0-9\s,]+?),\s+"
        r"core id is (?P<core_id>\d+),\s+error code = "
        r"(?P<error_code>0x[0-9a-fA-F]+|\d+(?:,\s*\d+)*),.*?"
        r"current:\s(?P<current_pc>\S+),\s(?P<extra_info>.*?)"
        r",\sfirst pc start:\s(?P<start_pc>\S+),.*?second pc start:\s(?P<s_start_pc>\S+),.*?"
    )

    # adump 已修正好的 PC，见 runtime kernel_symbol_locator.cpp PrintErrorForCore。
    ADUMP_FIXED_PC = (
        r"Error PC information\.\scoreId=(?P<core_id>\d+),\scoreType=(?P<core_type>\d+),\s"
        r"originalStartPC=(?P<start_pc>[^,]+),\sfixedStartPC=(?P<fixed_start_pc>[^,]+),\s"
        r"originalCurrentPC=(?P<current_pc>[^,]+),\sfixedCurrentPC=(?P<fixed_current_pc>[^,]+),\s"
        r"fixedPCOffset=(?P<fixed_pc_offset>[^,.\s]+)"
    )

    # FIXP 寄存器在 runtime 的 extend info 行上，非 AICORE_ERR_OCCUR 那行。
    PLOG_FIXP_ERR = r"fixp_error0 info:\s(\S+?),\sfixp_error1 info:\s(\S+?)[,\s]"

    # adump 的逐寄存器 dump，见 PrintErrorRegisters，单核可能分多条打印。
    ADUMP_ERR_REGS = (
        r"Error register information\.\scoreId=(?P<core_id>\d+),\scoreType=(?P<core_type>\d+),\s"
        r"(?P<regs>[A-Z0-9_]+=0x[0-9a-fA-F]+(?:\s+[A-Z0-9_]+=0x[0-9a-fA-F]+)*)"
    )

    # adump 的源码位置汇总，见 BuildGroupSummaryText；cores 行与 outerSrc 行按
    # group_idx 关联，用于判断该组是否包含本核。
    ADUMP_SYMBOLIZE_SRC = r"Group\[(?P<group_idx>\d+)\]\souterSrc=(?P<outer_src>\S+)\sinnerSrc=(?P<inner_src>\S+)"
    ADUMP_SUMMARY_CORES = r"Group\[(?P<group_idx>\d+)\]\scores=\[(?P<cores>[^\]]*)\]"
