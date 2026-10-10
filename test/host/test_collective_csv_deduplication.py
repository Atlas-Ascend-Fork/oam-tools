# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Real kernel CSV CLI preserves independent communication work and known pairs."""

import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills/cann-perf-breakdown/1-perf-breakdown/scripts/analyze_kernels.py"
)
FIELDS = [
    "Step Id",
    "Name",
    "Duration(us)",
    "Start Time(us)",
    "Stream ID",
    "Accelerator Core",
]


def _run(tmp_path, rows):
    source = tmp_path / "kernel_details.csv"
    with source.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        for index, row in enumerate(rows):
            stream, start, duration, core = row
            writer.writerow(
                {
                    "Step Id": "0",
                    "Name": f"HcclAllReduce_{index}",
                    "Duration(us)": duration,
                    "Start Time(us)": start,
                    "Stream ID": stream,
                    "Accelerator Core": core,
                }
            )
    output = tmp_path / "raw_ops.json"
    details = tmp_path / "raw_ops_details.json"
    compact = tmp_path / "raw_ops.compact.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "-f",
            str(source),
            "-o",
            str(output),
            "-d",
            str(details),
            "--compact-out",
            str(compact),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payloads = tuple(
        json.loads(path.read_text(encoding="utf-8"))
        for path in (output, details, compact)
    )
    assert all(
        "_dedup_times_valid" not in op
        for payload in payloads
        for op in payload.get("operators", [])
    )
    return payloads


@pytest.mark.parametrize(
    "streams", [("10", "20"), ("0", "1"), ("", "N/A"), ("", "10", "20")]
)
def test_ambiguous_or_independent_records_are_not_deduplicated(tmp_path, streams):
    raw, details, compact = _run(
        tmp_path, [(stream, 100, 20, "COMMUNICATION") for stream in streams]
    )

    assert raw["total_duration_us"] == 20 * len(streams)
    assert raw["duplicate_collective_count"] == 0
    assert raw["kernel_count"] == len(streams)
    assert [op["index"] for op in raw["operators"]] == list(range(len(streams)))
    assert [op["org_index"] for op in raw["operators"]] == list(range(len(streams)))
    assert all(
        "duplicate_of" not in op for op in raw["operators"] + details["operators"]
    )
    assert details["total_duration_us"] == raw["total_duration_us"]
    assert compact["kernel_count"] == len(streams)


@pytest.mark.parametrize("streams", [("", "10"), ("N/A", "0"), ("20", "")])
def test_one_summary_one_stream_pair_remains_deduplicated(tmp_path, streams):
    raw, details, compact = _run(
        tmp_path, [(stream, 100, 20, "COMMUNICATION") for stream in streams]
    )
    primary = next(
        index for index, stream in enumerate(streams) if stream in ("", "N/A")
    )
    duplicate = 1 - primary

    assert raw["total_duration_us"] == 20
    assert raw["duplicate_collective_count"] == 1
    assert raw["kernel_count"] == 2
    assert raw["operators"][duplicate]["duplicate_of"] == primary
    assert details["operators"][duplicate]["duplicate_of"] == primary
    assert "duplicate_of" not in raw["operators"][primary]
    assert [op["index"] for op in raw["operators"]] == [0, 1]
    assert compact["kernel_count"] == 2


@pytest.mark.parametrize(
    "rows",
    [
        [("10", 100, 20, "COMMUNICATION"), ("20", 101, 20, "COMMUNICATION")],
        [("10", 100, 20, "COMMUNICATION"), ("20", 100, 30, "COMMUNICATION")],
        [("10", 100, 20, "AI_CORE"), ("20", 100, 20, "AI_CORE")],
    ],
)
def test_distinct_times_durations_or_compute_rows_keep_full_sum(tmp_path, rows):
    raw, _, _ = _run(tmp_path, rows)
    assert raw["total_duration_us"] == sum(row[2] for row in rows)
    assert raw["duplicate_collective_count"] == 0


def test_two_separate_unambiguous_pairs_each_count_once(tmp_path):
    rows = [
        ("", 100, 20, "COMMUNICATION"),
        ("10", 100, 20, "COMMUNICATION"),
        ("N/A", 200, 30, "COMMUNICATION"),
        ("20", 200, 30, "COMMUNICATION"),
    ]
    raw, details, _ = _run(tmp_path, rows)
    assert raw["total_duration_us"] == 50
    assert raw["duplicate_collective_count"] == 2
    assert [
        op["duplicate_of"] for op in details["operators"] if "duplicate_of" in op
    ] == [0, 2]


@pytest.mark.parametrize("start", ["", "N/A", "not-a-time", "NaN", "Inf"])
def test_missing_or_invalid_timestamp_is_not_evidence_of_duplication(tmp_path, start):
    rows = [("", start, 20, "COMMUNICATION"), ("10", start, 20, "COMMUNICATION")]
    raw, details, _ = _run(tmp_path, rows)
    assert raw["total_duration_us"] == 40
    assert raw["duplicate_collective_count"] == 0
    assert all(
        "duplicate_of" not in op for op in raw["operators"] + details["operators"]
    )


def test_real_zero_timestamp_remains_valid_pairing_evidence(tmp_path):
    raw, _, _ = _run(
        tmp_path, [("", "0", 20, "COMMUNICATION"), ("10", "0", 20, "COMMUNICATION")]
    )
    assert raw["total_duration_us"] == 20
    assert raw["duplicate_collective_count"] == 1
