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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

"""并发解析回归（Issue #224）：多文件共享 ParseTrace 实例导致时间基准串文件。"""

import os
import struct
import threading
import time

import pytest

from collect.trace import ParseTrace


@pytest.fixture
def utc_timezone():
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if old_tz is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old_tz
    time.tzset()


def _write_trace_with_real_time(
    trace_file, real_time_ns, version=2, tz_offset=0, cpu_freq=0, cycle=0
):
    # 与 conftest.great_bin 相同的最小 trace 布局，real_time/version/tz_offset/
    # cpu_freq/cycle 参数化；v3 头部在 real_time 之后依次为 cpu_freq(u64) 和
    # 8 字节保留，v2 则跳过 16 字节保留（与 parse_ctrl_head 一致）。
    header = struct.pack(
        "<II4BIIIQ",
        0xD928,
        version,
        0,
        0,
        0,
        0,
        80,
        20,
        tz_offset,
        real_time_ns,
    )
    header += struct.pack("<Q8s", cpu_freq, b"\0" * 8) if version == 3 else b"\0" * 16
    struct_segment = (
        struct.pack("<I", 1)
        + b"\0" * 36
        + b"event"
        + b"\0" * 27
        + struct.pack("<IB3s", 1, 1, b"\0" * 3)
        + b"value"
        + b"\0" * 27
        + struct.pack("<2BH4s", 6, 0, 4, b"\0" * 4)
    )
    data_segment = (
        struct.pack("<4I", 0, 4, 1, 0)
        + struct.pack("<QI?B2s", cycle, 4, False, 1, b"\0" * 2)
        + struct.pack("<I", 7)
    )
    with open(trace_file, "wb") as fw:
        fw.write(header + struct_segment + data_segment)


def test_run_isolates_header_state_across_concurrent_files(
    tmp_path, monkeypatch, utc_timezone
):
    # issue #224：barrier 强制两个线程同时完成头部读取后继续，稳定暴露
    # 实例字段共享；断言各输出使用各自头部的 real_time（1s vs 2s）。
    _write_trace_with_real_time(tmp_path / "first.bin", 1_000_000_000)
    _write_trace_with_real_time(tmp_path / "second.bin", 2_000_000_000)

    original = ParseTrace.parse_ctrl_head
    barrier = threading.Barrier(2)

    def synchronized_header(self, fp, trace_file):
        # #400（086b197）合入后 parse_ctrl_head 改为返回
        # (tz_offset, real_time, cpu_freq)，由 parse_data_segment 解包消费，
        # 包装器须转发返回值，否则线程内解包 None 抛 TypeError、输出不生成。
        ret = original(self, fp, trace_file)
        barrier.wait(timeout=30)
        return ret

    monkeypatch.setattr(ParseTrace, "parse_ctrl_head", synchronized_header)

    assert ParseTrace(is_file=True).run(str(tmp_path))

    first = (tmp_path / "first.txt").read_text(encoding="utf-8")
    second = (tmp_path / "second.txt").read_text(encoding="utf-8")
    assert first.startswith("1970-01-01 00:00:01"), (
        f"first.txt 应使用自身 1s 时间基准: {first!r}"
    )
    assert second.startswith("1970-01-01 00:00:02"), (
        f"second.txt 应使用自身 2s 时间基准: {second!r}"
    )


def test_run_isolates_v3_header_state_across_concurrent_files(
    tmp_path, monkeypatch, utc_timezone
):
    # v3 头部三个字段同时具备区分力：tz_offset 不同（60/120）、cpu_freq 非 0 且
    # 不同（2e9/1e9）、cycle 非 0，时间戳走 cycle/cpu_freq 分支（贡献 1s/3s）。
    # 期望值按公式 real_time + cycle/cpu_freq*1e6 - tz_offset*1e9（ns，TZ=UTC）实测：
    # third: 86400s + 1s - 60s = 86341s -> 1970-01-01 23:59:01
    # fourth: 172800s + 3s - 120s = 172683s -> 1970-01-02 23:58:03
    _write_trace_with_real_time(
        tmp_path / "third.bin",
        86_400_000_000_000,
        version=3,
        tz_offset=60,
        cpu_freq=2_000_000_000,
        cycle=2_000_000_000_000,
    )
    _write_trace_with_real_time(
        tmp_path / "fourth.bin",
        172_800_000_000_000,
        version=3,
        tz_offset=120,
        cpu_freq=1_000_000_000,
        cycle=3_000_000_000_000,
    )

    original = ParseTrace.parse_ctrl_head
    barrier = threading.Barrier(2)

    def synchronized_header(self, fp, trace_file):
        # #400（086b197）合入后 parse_ctrl_head 改为返回
        # (tz_offset, real_time, cpu_freq)，由 parse_data_segment 解包消费，
        # 包装器须转发返回值，否则线程内解包 None 抛 TypeError、输出不生成。
        ret = original(self, fp, trace_file)
        barrier.wait(timeout=30)
        return ret

    monkeypatch.setattr(ParseTrace, "parse_ctrl_head", synchronized_header)

    assert ParseTrace(is_file=True).run(str(tmp_path))

    third = (tmp_path / "third.txt").read_text(encoding="utf-8")
    fourth = (tmp_path / "fourth.txt").read_text(encoding="utf-8")
    assert third.startswith("1970-01-01 23:59:01"), (
        f"third.txt 应使用自身 tz_offset/cpu_freq 时间基准: {third!r}"
    )
    assert fourth.startswith("1970-01-02 23:58:03"), (
        f"fourth.txt 应使用自身 tz_offset/cpu_freq 时间基准: {fourth!r}"
    )
