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

import re
import sys

from conftest import MSAICERR_PATH
from ms_interface.aic_error_info import (
    AicErrorInfo,
    detect_chip_type,
    parse_david_error_codes,
    parse_stars_error_bits,
)
from ms_interface.constant import ChipType, Constant, RegexPattern

sys.path.append(MSAICERR_PATH)

GET_AICERROR_INFO = "_get_aicerror_info"

# Module prefixes that _get_aicerror_info dispatches on for the Stars form.
STARS_DISPATCH_PREFIXES = ("vec", "ifu", "mte", "cube", "ccu", "biu")


def _resolve(error_code, extra_info=""):
    info = AicErrorInfo()
    info.aic_error_info = {"error_code": error_code}
    info.extra_info = extra_info
    return getattr(info, GET_AICERROR_INFO)()


# --------------------------------------------------------------------------
# chip type detection
# --------------------------------------------------------------------------


def test_detect_chip_type_stars_hex():
    assert detect_chip_type("0x12345678") == ChipType.ASCEND_910B
    assert detect_chip_type("0Xabcdef") == ChipType.ASCEND_910B
    assert detect_chip_type("0x0") == ChipType.ASCEND_910B


def test_detect_chip_type_david_bit_list():
    assert detect_chip_type("64, 78") == ChipType.ASCEND_950
    assert detect_chip_type("64,78") == ChipType.ASCEND_950
    assert detect_chip_type("128") == ChipType.ASCEND_950


def test_detect_chip_type_bare_zero_is_stars():
    # Both forms render a zero error code as "0": %#PRIx64 drops the 0x prefix
    # for zero, and David writes "0" explicitly. Routing it to the Stars path
    # keeps the trap_or_timeout fallback that both forms share.
    assert detect_chip_type("0") == ChipType.ASCEND_910B


def test_detect_chip_type_empty_is_stars():
    assert detect_chip_type("") == ChipType.ASCEND_910B
    assert detect_chip_type("   ") == ChipType.ASCEND_910B


# --------------------------------------------------------------------------
# David bit-list parsing
# --------------------------------------------------------------------------


def test_parse_david_error_codes_preserves_order():
    assert parse_david_error_codes("192, 256, 64") == [192, 256, 64]


def test_parse_david_error_codes_skips_garbage():
    assert parse_david_error_codes("64, , bad, 78") == [64, 78]


# --------------------------------------------------------------------------
# AIC_ERROR_INFO_DICT (910B / Stars)
# --------------------------------------------------------------------------


def test_stars_dict_is_contiguous():
    assert len(Constant.AIC_ERROR_INFO_DICT) == 176
    assert sorted(Constant.AIC_ERROR_INFO_DICT) == list(range(176))


def test_stars_dict_values_keep_name_prefix():
    # _get_aicerror_info and find_extra_pc both derive the module from
    # value.split('_')[0], so every entry must stay in "name, desc" shape.
    for bit, value in Constant.AIC_ERROR_INFO_DICT.items():
        assert ", " in value, f"bit {bit} has no description separator"
        name = value.split(",")[0]
        assert re.fullmatch(r"[a-z0-9_]+", name), (
            f"bit {bit} name {name!r} not snake_case"
        )


def test_stars_dict_dispatch_prefixes_present():
    prefixes = {v.split("_")[0].lower() for v in Constant.AIC_ERROR_INFO_DICT.values()}
    for expected in STARS_DISPATCH_PREFIXES:
        assert expected in prefixes


def test_stars_dict_bit0_is_biu_read_oob():
    # Bit 0 maps 1:1 to the C++ table's BIU_L2_READ_OOB; the "no bit set" case
    # is held by NO_ERROR_BIT_INFO instead of aliasing this entry.
    assert Constant.AIC_ERROR_INFO_DICT[0].startswith("biu_l2_read_oob,")


def test_no_error_bit_sentinel_is_not_in_table():
    assert Constant.NO_ERROR_BIT_INFO.startswith("trap_or_timeout,")
    assert Constant.NO_ERROR_BIT_INFO not in Constant.AIC_ERROR_INFO_DICT.values()


def test_stars_bit0_and_no_bit_are_distinct():
    # 0x1 really sets bit 0; 0x0 sets none. They must not collapse together.
    bit0 = _resolve("0x1")
    no_bit = _resolve("0x0")
    assert "biu_l2_read_oob" in bit0
    assert "trap_or_timeout" in no_bit
    assert bit0 != no_bit


def test_stars_biu_read_write_symmetry():
    # bit 0 is the read side, bit 1 the write side; both must resolve.
    assert "biu_l2_read_oob" in _resolve("0x1")
    assert "biu_l2_write_oob" in _resolve("0x2")


def test_stars_unparsable_code_is_not_bit0():
    # get_hexstr_value returns -1 for these, whose binary form would otherwise
    # scan as bit 0 and be misreported as a bus read error.
    for code in ("", "   ", "garbage"):
        result = _resolve(code)
        assert "trap_or_timeout" in result, f"{code!r} misresolved"
        assert "biu_l2_read_oob" not in result, f"{code!r} became a false BIU error"


def test_parse_stars_error_bits_guards_invalid():
    assert parse_stars_error_bits("0x1") == [0]
    assert parse_stars_error_bits("0x5") == [2, 0]
    assert parse_stars_error_bits("0x0") == []
    assert parse_stars_error_bits("") == []
    assert parse_stars_error_bits("garbage") == []


def test_stars_dict_is_english():
    for bit, value in Constant.AIC_ERROR_INFO_DICT.items():
        assert all(ord(ch) < 128 or ch == "–" for ch in value), f"bit {bit} not English"


# --------------------------------------------------------------------------
# AIC_ERROR_INFO_DICT_DAVID (950 / David)
# --------------------------------------------------------------------------


def test_david_dict_entry_count():
    assert len(Constant.AIC_ERROR_INFO_DICT_DAVID) == 187


def test_david_dict_entry_shape():
    for bit, entry in Constant.AIC_ERROR_INFO_DICT_DAVID.items():
        assert set(entry) == {"name", "desc"}, f"bit {bit} has unexpected keys"
        assert entry["name"] and entry["desc"], f"bit {bit} incomplete"
        assert re.fullmatch(r"[A-Z0-9_]+", entry["name"]), (
            f"bit {bit} name not an enum name"
        )


def test_david_dict_covers_every_offset_segment():
    offsets = [
        Constant.DAVID_OFFSET_CUBE,
        Constant.DAVID_OFFSET_MTE,
        Constant.DAVID_OFFSET_L1,
        Constant.DAVID_OFFSET_L1_1,
        Constant.DAVID_OFFSET_SC,
        Constant.DAVID_OFFSET_SU,
        Constant.DAVID_OFFSET_VEC,
        Constant.DAVID_OFFSET_VEC_1,
    ]
    keys = Constant.AIC_ERROR_INFO_DICT_DAVID
    for offset in offsets:
        assert any(offset <= bit < offset + 32 for bit in keys), (
            f"segment {offset} empty"
        )


def test_david_offsets_match_runtime_header():
    # Mirrors RINGBUFFER_*_ERROR_OFFSET in device_error_info.hpp.
    assert Constant.DAVID_OFFSET_CUBE == 0
    assert Constant.DAVID_OFFSET_MTE == 64
    assert Constant.DAVID_OFFSET_L1 == 128
    assert Constant.DAVID_OFFSET_L1_1 == 160
    assert Constant.DAVID_OFFSET_SC == 192
    assert Constant.DAVID_OFFSET_SU == 256
    assert Constant.DAVID_OFFSET_VEC == 320
    assert Constant.DAVID_OFFSET_VEC_1 == 352


# --------------------------------------------------------------------------
# end-to-end resolution
# --------------------------------------------------------------------------


def test_stars_single_bit_is_bit_scanned():
    # 0x4 sets bit 2, so it must resolve to bit 2 rather than key 4.
    result = _resolve("0x4")
    assert "ccu_call_depth_ovrflw" in result
    assert "ccu_illegal_instr" not in result


def test_stars_multiple_bits():
    # 0x10004 sets bits 2 and 16.
    result = _resolve("0x10004")
    assert "ccu_call_depth_ovrflw" in result
    assert "cube_l0c_ecc" in result


def test_stars_zero_reports_trap_or_timeout():
    assert "trap_or_timeout" in _resolve("0x0")


def test_david_single_bit_no_bit_scan():
    # 64 is already a resolved bit number, so it maps straight to MTE bit 64.
    result = _resolve("64")
    assert "MTE_NDDMA_CACHE_ECC" in result


def test_david_multiple_bits():
    result = _resolve("64, 78")
    assert "MTE_NDDMA_CACHE_ECC" in result
    assert "MTE_INSTR_ILLEGAL_CFG" in result


def test_david_unknown_bit_is_reported():
    # Bit 63 has no g_davidErrorMapInfo entry; the bit number is still shown.
    result = _resolve("64, 63")
    assert "MTE_NDDMA_CACHE_ECC" in result
    assert "unknown error bit 63" in result


def test_david_zero_reports_trap_or_timeout():
    assert "trap_or_timeout" in _resolve("0")


def test_david_find_extra_pc_returns_empty():
    info = AicErrorInfo()
    info.aic_error_info = {"error_code": "64, 78"}
    info.extra_info = "MTE_ERR_INFO=0x1"
    assert info.find_extra_pc() == ""


# --------------------------------------------------------------------------
# log regex
# --------------------------------------------------------------------------


def _david_log(error_code):
    return (
        "RUNTIME(200280,python3):2025-07-07-10:12:17.088.944 "
        "[device_error_proc_c.cc:659]201695 ProcessDavidStarsCoreErrorInfo:[EXEC][EXEC]"
        "The error from device(chipId:0, dieId:0), serial number is 31, "
        "there is an exception of aivec error, core id is 36, "
        f"error code = {error_code}, dump info: "
        "pc start: 0x12400001638c, current: 0x1240000167bc, "
        "sc error info: 0x0, su error info: 0x0,0x0, mte error info: 0x1, "
        "vec error info: 0x0, cube error info: 0x0, l1 error info: 0x0, "
        "aic error mask: 0x0, para base: 0x12d0c0000800, mte error: 0x1, aic cond: 0x0."
    )


def _stars_log(error_code):
    return (
        "RUNTIME(200280,python3):2025-07-07-10:12:17.088.944 "
        "[device_error_core_proc.cc:314]201695 ProcessStarsCoreErrorInfo:[EXEC][EXEC]"
        "The error from device(chipId:0, dieId:0), serial number is 31, "
        "there is an exception of aivec error, core id is 36, "
        f"error code = {error_code}, dump info: "
        "pc start: 0x12400001638c, current: 0x1240000167bc, "
        "vec error info: 0x6106ff4758, mte error info: 0x302aa40, "
        "ifu error info: 0x2000017df8400, ccu error info: 0x482a21100000000, "
        "cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, "
        "para base: 0x12d0c0000800."
    )


def test_regex_captures_stars_hex_code():
    match = re.search(RegexPattern.AICORE_ERR_OCCUR, _stars_log("0x12345678"))
    assert match is not None
    assert match.group("error_code") == "0x12345678"


def test_regex_captures_stars_zero_code():
    match = re.search(RegexPattern.AICORE_ERR_OCCUR, _stars_log("0"))
    assert match is not None
    assert match.group("error_code") == "0"


def test_regex_captures_david_bit_list():
    # The old \S+ form stopped at the comma and captured only "64,".
    match = re.search(RegexPattern.AICORE_ERR_OCCUR, _david_log("64, 78"))
    assert match is not None
    assert match.group("error_code") == "64, 78"


def test_regex_stops_before_dump_info():
    # A greedy [\d, ]+ would run past the list into ", dump info:".
    match = re.search(RegexPattern.AICORE_ERR_OCCUR, _david_log("64, 78, 128"))
    assert match is not None
    assert match.group("error_code") == "64, 78, 128"
    assert "dump" not in match.group("error_code")
