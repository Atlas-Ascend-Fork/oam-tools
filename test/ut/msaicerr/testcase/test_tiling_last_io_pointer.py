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

import struct
import hashlib
from pathlib import Path

import pytest
from ms_interface.tiling_data_parser import TilingDataParser


@pytest.mark.parametrize(
    "io_args",
    [
        ["0x2000", "0x2000", "0x3000", "0x2000"],
        ["0x3000", "0x2000", "0x3000", "0x2000"],
        ["0x2000", "0x3000", "0x4000", "0x5000"],
    ],
)
def test_tiling_pointer_follows_the_last_io_occurrence(mocker, io_args):
    args = io_args + ["0x1028", "0x1122334455667788", "0x9"]
    text = "args(0 to 6) after execute:" + ",".join(args)
    io_pointers = list(dict.fromkeys(io_args))
    mocker.patch(
        "ms_interface.utils.get_inquire_result",
        # Four queries in this order: args, IO pointer dump, [Dump][Exception]
        # markers, para base.  The "begin to load normal tensor" query was
        # dropped, so no fifth return value is needed.
        side_effect=[
            [text],
            io_pointers,
            [],
            ["0x1000"],
        ],
    )
    assert TilingDataParser("/logs").parse() == struct.pack(
        "<QQ", 0x1122334455667788, 9
    )


@pytest.mark.parametrize("pointer", ["0xff8", "0x1020", "0x2000"])
def test_invalid_data_offset_is_reported(mocker, pointer):
    text = "args(0 to 4) after execute:0x3000," + pointer + ",0x1,0x2"
    mocker.patch(
        "ms_interface.utils.get_inquire_result",
        side_effect=[
            [text],
            ["0x3000"],
            [],
            ["0x1000"],
        ],
    )
    warning = mocker.patch("ms_interface.utils.print_warn_log")
    assert TilingDataParser("/logs").parse() == b""
    expected_offset = (int(pointer, 16) - 0x1000) // 8
    warning.assert_called_once_with(
        f"Tiling data offset {expected_offset} is outside the captured args "
        f"(count=4, tiling_ptr={pointer}, para_base=0x1000)."
    )


@pytest.mark.parametrize(
    "sample,size,digest",
    [
        (
            "collect/ffts/collection/plog/plog-1592007_20240912164003456.log",
            2304,
            "3b11c4850073755e2b863b420c6064090f20ea025fbb92115cd750534366da3b",
        ),
        (
            "collect/ffts1/collection/plog/plog-1592007_20240912164003456.log",
            2312,
            "c570017fec5ea28f0981250453d572e46b661a37e6b15842720350e020e4245c",
        ),
        (
            "asys_output_20240912164014957"
            "/dfx/log/host/cann/debug/plog/plog-1592007_20240912164003456.log",
            2304,
            "3b11c4850073755e2b863b420c6064090f20ea025fbb92115cd750534366da3b",
        ),
        (
            "asys_output_20240912164014958"
            "/dfx/log/host/cann/debug/plog/plog-1592007_20240912164003456.log",
            2304,
            "3b11c4850073755e2b863b420c6064090f20ea025fbb92115cd750534366da3b",
        ),
        (
            "collect_milan/collection/plog/plog-588579_20250402071926352.log",
            40,
            "7cd732e03d26142b80657a79eddb64a1edb3f5e6e2f519b73bf47ccbf9b7a0f8",
        ),
    ],
)
def test_real_logs_preserve_nonzero_begin_index(sample, size, digest):
    # Golden digests come from the original parser and unchanged repository
    # logs; dropping the "begin to load normal tensor" offset does not change
    # them.  Every sample is pinned to one file: the parent directories also
    # hold unrelated captures (plog-test.log, invalid-tiling-test.log), so a
    # directory input would depend on grep's file enumeration order.
    root = Path(__file__).resolve().parents[1] / "res/ori_data"
    result = TilingDataParser(str(root / sample)).parse()
    assert isinstance(result, bytes)
    assert len(result) == size
    assert hashlib.sha256(result).hexdigest() == digest


@pytest.mark.parametrize(
    "sample",
    [
        "collect/ffts1",
        "collect_milan",
    ],
)
def test_directory_samples_are_unambiguous(sample):
    # Guards the two directory inputs kept above: they must contain exactly one
    # log with "after execute:", otherwise the golden result would depend on
    # which file grep happens to reach first.
    root = Path(__file__).resolve().parents[1] / "res/ori_data" / sample
    matches = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and "after execute:" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert len(matches) == 1, f"{sample} matched {len(matches)} logs: {matches}"


def test_milan_uses_explicit_tiling_index_over_workspace_and_padding():
    root = Path(__file__).resolve().parents[1] / "res/ori_data/collect_milan"
    # The log names index 4 as tiling; 0x12c100010038 - para_base = 7 words.
    # Words 0..6 are IO/workspace/tiling pointers, never tiling payload.
    assert TilingDataParser(str(root)).parse() == struct.pack(
        "<QQQQQ", 0x800004000, 0xA5A5A5A500000000, 0, 0, 0
    )


def test_tiling_marker_before_pointer_block_keeps_explicit_index(tmp_path):
    log = tmp_path / "pointer.log"
    log.write_text(
        "[Dump][Exception] begin to load tiling data, index:4\n"
        "[Dump][Exception] begin to load input pointer tensor, addr:0x2000\n"
        "[Dump][Exception] exception info dump args data, addr:0x3000;\n"
        "[Dump][Exception] end to load input pointer tensor\n"
        "args(0 to 8) after execute:0x2000,0x3000,0x4000,0x5000,0x1038,"
        "0x0,0x0,0x1122334455667788,0x9\n"
        "after execute:args print end\n"
        "para base: 0x1000.\n",
        encoding="utf-8",
    )
    assert TilingDataParser(str(log)).parse() == struct.pack(
        "<QQ", 0x1122334455667788, 9
    )


def test_missing_after_execute_is_empty_data(tmp_path):
    log = tmp_path / "missing.log"
    log.write_text("[Dump][Exception] no captured arguments\n", encoding="utf-8")
    assert TilingDataParser(str(log)).parse() == b""


def test_missing_after_execute_cli_has_documented_error_without_binary(tmp_path):
    import os
    import subprocess
    import sys

    from ms_interface.constant import Constant

    root = Path(__file__).resolve().parents[4] / "src/msaicerr"
    log = tmp_path / "missing.log"
    log.write_text("[Dump][Exception] no captured arguments\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(root / "parse_tiling.py"), "-t", str(log)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == Constant.MS_AICERR_FIND_DATA_ERROR, (
        result.stdout + result.stderr
    )
    assert "Traceback" not in result.stderr
    assert not list(tmp_path.glob("tilingdata_*.bin"))


def test_cli_reports_a_write_failure_without_a_traceback(mocker, monkeypatch, tmp_path):
    from parse_tiling import parse_tiling_data
    from ms_interface.constant import Constant

    monkeypatch.chdir(tmp_path)
    mocker.patch(
        "ms_interface.utils.get_inquire_result",
        side_effect=[
            ["args(0 to 3) after execute:0x3000,0x1010,0x1122334455667788,0x9"],
            ["0x3000"],
            [],
            ["0x1000"],
        ],
    )
    mocker.patch("parse_tiling.open", side_effect=OSError("Permission denied"))
    assert parse_tiling_data("/controlled/logs") == Constant.MS_AICERR_OPEN_FILE_ERROR
    assert not list(tmp_path.glob("tilingdata_*.bin"))


@pytest.mark.parametrize("index", [8, 9, 40])
def test_explicit_tiling_index_out_of_range_is_rejected(mocker, index):
    # The captured args hold 8 entries; any explicit index at or past the end
    # is a static-shape style log and must not be turned into an offset.
    text = "args(0 to 7) after execute:" + ",".join(
        ["0x2000", "0x3000", "0x4000", "0x5000", "0x6000", "0x7000", "0x1010", "0x9"]
    )
    mocker.patch(
        "ms_interface.utils.get_inquire_result",
        side_effect=[
            [text],
            ["0x2000"],
            [f"begin to load tiling data, index:{index}"],
            ["0x1000"],
        ],
    )
    warning = mocker.patch("ms_interface.utils.print_warn_log")
    assert TilingDataParser("/logs").parse() == b""
    warning.assert_called_once_with(
        "Failed to get tiling_ptr after execute, maybe static shape case."
    )


def test_repeated_tiling_markers_use_the_first_index(mocker):
    # A recomputed operator emits the marker more than once; the first one is
    # the authoritative index and later duplicates must not override it.
    text = "args(0 to 8) after execute:" + ",".join(
        [
            "0x2000",
            "0x3000",
            "0x4000",
            "0x5000",
            "0x1038",
            "0x0",
            "0x0",
            "0x1122334455667788",
            "0x9",
        ]
    )
    mocker.patch(
        "ms_interface.utils.get_inquire_result",
        side_effect=[
            [text],
            ["0x2000"],
            [
                "begin to load tiling data, index:4",
                "begin to load tiling data, index:7",
            ],
            ["0x1000"],
        ],
    )
    assert TilingDataParser("/logs").parse() == struct.pack(
        "<QQ", 0x1122334455667788, 9
    )
