# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ("skills/cann-perf-breakdown/2-adapt-breakdown-to-ui-json/scripts",)

# Passing `ts_us=OMIT` leaves the key out of the Timeline event entirely, which is how a test
# asks for the "field missing" case. Every other value -- including None -- is written
# verbatim, because deciding what an unusable start time means is the adapter's job.
OMIT = object()


def run_binding(adapter, tmp_path, row, raw, *, event_count=1, rows=None, ts_us=0):
    """Run the adapter over one Timeline event per attribution row and hand back the process.

    The Timeline event's `ts_us` comes from the `ts_us` argument and from nowhere else.
    `emit_ui_facts.py` is what derives it from the attribution row's `start_time_us`, as
    `float(row.get("start_time_us") or 0.0)`, so an unreadable value arrives here as a
    finite 0.0. Re-deriving it inside this fixture would test the copy rather than the
    adapter, and would hide that the adapter's own guard cannot fire on a zero-fill. See
    `test_upstream_zero_filled_start_time_is_not_caught_by_the_guard` for what that gap
    looks like end to end.

    `ts_us` may be one value for every event, or a list with one per row.
    """
    if rows is None:
        rows = [{**row, "op_index": index} for index in range(event_count)]
    stamps = list(ts_us) if isinstance(ts_us, (list, tuple)) else [ts_us] * len(rows)
    events = []
    for item, stamp in zip(rows, stamps):
        index = item["op_index"]
        event = {
            "event_id": f"e{index}",
            "op_index": index,
            "owner_node_id": f"n{index}",
        }
        if stamp is not OMIT:
            event["ts_us"] = stamp
        events.append(event)
    timeline = {"model_id": "fixture", "report_id": "fixture", "events": events}
    values = {
        "timeline": timeline,
        "attribution": {"rows": rows},
        "trace": raw,
    }
    for name, value in values.items():
        (tmp_path / (name + ".json")).write_text(json.dumps(value))
    output = tmp_path / "bindings.json"
    args = [sys.executable, str(ROOT / adapter / "build_trace_bindings.py")]
    for name in values:
        args += ["--" + name, str(tmp_path / (name + ".json"))]
    args += ["--out", str(output)]
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    return result, output


def inputs():
    return (
        {"op_index": 0, "op_name": "Kernel", "start_time_us": 0, "duration_us": 0},
        {"ph": "X", "name": "Kernel", "ts": 0, "dur": 0},
    )


BAD_VALUES = {
    "none": None,
    "nan": float("nan"),
    "infinity": float("inf"),
    "negative": -1,
    "text": "not-a-time",
}


def mutate(target, key, bad):
    if bad == "missing":
        target.pop(key)
    else:
        target[key] = BAD_VALUES[bad]


def bad_stamp(bad):
    """The same bad values as `mutate`, for a field this fixture writes directly."""
    return OMIT if bad == "missing" else BAD_VALUES[bad]


def assert_clean_failure(result, output, field):
    assert result.returncode == 1
    assert not output.exists()
    diagnostic = result.stdout + result.stderr
    assert "UNRESOLVED op_index=0" in diagnostic
    assert field in diagnostic
    assert "could not be bound" in diagnostic
    assert "Traceback" not in diagnostic


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("which", ["row", "raw"])
@pytest.mark.parametrize(
    "bad", ["missing", "none", "nan", "infinity", "negative", "text"]
)
def test_invalid_used_duration_has_clean_contract_failure(
    adapter, which, bad, tmp_path
):
    row, raw = inputs()
    mutate(
        row if which == "row" else raw, "duration_us" if which == "row" else "dur", bad
    )
    result, output = run_binding(adapter, tmp_path, row, [raw])
    assert_clean_failure(result, output, "duration")


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("bad", ["missing", "nan", "negative"])
def test_bad_unused_candidate_does_not_abort_valid_match(adapter, bad, tmp_path):
    row, raw = inputs()
    invalid = dict(raw)
    mutate(invalid, "dur", bad)
    result, output = run_binding(adapter, tmp_path, row, [invalid, raw])
    assert result.returncode == 0, result.stdout + result.stderr
    binding = json.loads(output.read_text())["bindings"][0]
    assert binding["raw_source_event_index"] == 1


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("which", ["event", "raw"])
@pytest.mark.parametrize("bad", ["missing", "nan"])
def test_unreadable_start_time_is_not_zero_filled_into_a_match(
    adapter, which, bad, tmp_path
):
    # The start time is one of the three joined fields, so an unreadable one must fail
    # cleanly instead of defaulting to 0 and matching a raw event whose `ts` is 0.
    #
    # The adapter reads the start time from the Timeline event's `ts_us` and from the raw
    # event's `ts`. It never reads the attribution row's `start_time_us`, so this pins the
    # adapter's own guard on the two fields it actually owns. What `emit_ui_facts.py` puts
    # into `ts_us` upstream is a separate contract, and it is not a safe one yet -- see
    # `test_upstream_zero_filled_start_time_is_not_caught_by_the_guard`.
    row, raw = inputs()
    if which == "event":
        result, output = run_binding(
            adapter, tmp_path, row, [raw], ts_us=bad_stamp(bad)
        )
    else:
        mutate(raw, "ts", bad)
        result, output = run_binding(adapter, tmp_path, row, [raw])
    assert_clean_failure(result, output, "start time")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_upstream_zero_filled_start_time_is_not_caught_by_the_guard(adapter, tmp_path):
    """Known upstream gap, pinned on purpose so it cannot widen unnoticed.

    `emit_ui_facts.py` builds the Timeline event's start time as
    `float(row.get("start_time_us") or 0.0)`, and `analyze_kernels.py` already returns 0.0
    for a start time it could not parse. So a row whose start time is unusable arrives here
    as a perfectly finite 0.0, `required_time()` accepts it, and the guard this file exists
    to test cannot fire. What comes out is a misleading `ts=0.0` diagnostic that names no
    invalid field, while the real kernel sits at 12.5 us.

    Fixing that belongs to `emit_ui_facts.py` / `analyze_kernels.py`, not to the adapter.
    This case records the behaviour a caller sees today and is expected to fail -- and
    should then be updated -- once the upstream zero-fill is removed.
    """
    row, raw = inputs()
    row["start_time_us"] = (
        "not-a-time"  # unreadable upstream, so 0.0 by the time we see it
    )
    raw["ts"] = 12.5  # where the kernel really ran
    result, output = run_binding(adapter, tmp_path, row, [raw], ts_us=0.0)
    assert result.returncode == 1
    assert not output.exists()
    diagnostic = result.stdout + result.stderr
    assert "UNRESOLVED op_index=0" in diagnostic
    # The honest failure would name the field; this one only reports a mismatch at 0.0.
    assert "no free raw X event named 'Kernel' matching ts=0.0" in diagnostic
    assert "Missing or invalid start time" not in diagnostic
    assert "closest unmatched: #0 dts=12.500000us" in diagnostic


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_readable_but_wrong_start_time_is_not_bound(adapter, tmp_path):
    # Nearest-duration matching bound this happily: the duration agreed exactly, so the
    # start-time disagreement stayed invisible and the owner could come out swapped.
    row, raw = inputs()
    result, output = run_binding(adapter, tmp_path, row, [{**raw, "ts": 900}])
    assert_clean_failure(result, output, "no free raw X event named 'Kernel'")


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("timestamp", [0, -1])
def test_zero_duration_and_finite_timestamps_remain_valid(adapter, timestamp, tmp_path):
    row, raw = inputs()
    row["start_time_us"] = raw["ts"] = timestamp
    result, output = run_binding(adapter, tmp_path, row, [raw], ts_us=timestamp)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(output.read_text())["bindings"][0]["node_id"] == "n0"


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("bad_first", [True, False])
def test_exhausted_same_name_candidates_report_no_free_raw_event(
    adapter, bad_first, tmp_path
):
    row, raw = inputs()
    unrelated = {**raw, "name": "OtherKernel"}
    unrelated.pop("dur")
    events = [unrelated, raw] if bad_first else [raw, unrelated]
    result, output = run_binding(adapter, tmp_path, row, events, event_count=2)
    assert result.returncode == 1
    assert not output.exists()
    diagnostic = result.stdout + result.stderr
    assert "UNRESOLVED op_index=1: no free raw X event named 'Kernel'" in diagnostic
    assert "invalid raw matching fields" not in diagnostic
    assert "1 Timeline event(s) could not be bound" in diagnostic
    assert "Traceback" not in diagnostic


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_distinct_same_name_candidates_bind_each_timeline_event_once(adapter, tmp_path):
    row, raw = inputs()
    rows = [
        {**row, "op_index": 0, "start_time_us": 0},
        {**row, "op_index": 1, "start_time_us": 10},
    ]
    # Raw order reversed on purpose: the start time, not the array position, decides.
    events = [{**raw, "ts": 10}, {**raw, "ts": 0}]
    result, output = run_binding(
        adapter, tmp_path, row, events, rows=rows, ts_us=[0, 10]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    bindings = json.loads(output.read_text())["bindings"]
    assert [binding["raw_source_event_index"] for binding in bindings] == [1, 0]
    assert [binding["node_id"] for binding in bindings] == ["n0", "n1"]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_indistinguishable_same_name_candidates_are_ambiguous(adapter, tmp_path):
    # Two raw events agreeing on all three joined fields leave no evidence for which
    # Timeline event owns which; binding the first one would be a guess reported as
    # `confidence: high` while the coverage summary still reads 100%.
    row, raw = inputs()
    result, output = run_binding(
        adapter, tmp_path, row, [raw, dict(raw)], event_count=2
    )
    assert result.returncode == 1
    assert not output.exists()
    diagnostic = result.stdout + result.stderr
    assert "UNRESOLVED op_index=0: ambiguous raw X event match" in diagnostic
    assert "UNRESOLVED op_index=1: ambiguous raw X event match" in diagnostic
    assert "2 Timeline event(s) could not be bound" in diagnostic
    assert "Traceback" not in diagnostic


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_duplicate_mark_and_stream_id_take_no_part_in_the_join(adapter, tmp_path):
    """Upstream can already tell a re-recorded collective apart; this join cannot.

    `analyze_kernels.mark_duplicate_collective_records` only tags `duplicate_of` when it has
    proof of one device work written twice -- a group of exactly two COMMUNICATION rows with
    an identical (start time, duration) and exactly one of them without a Stream ID. So for
    every tagged pair the two rows necessarily differ in `stream_id`, and
    `attribute_kernels` carries both the mark and the stream through to `emit_ui_facts`,
    which puts `stream_id` on the Timeline event.

    None of that reaches the adapter: it joins on (name, ts, dur) only. The marked duplicate
    therefore still asks for a raw event that is not there, and the whole report fails. That
    is the correct behaviour for this file's contract -- the adapter must not invent a
    binding -- and the root-cause fix is for the `emit_ui_facts` timeline loop to skip
    `duplicate_of` rows, which is not this adapter's to make. This case pins that carrying
    the fields changes nothing here, so a future change to the join key is a deliberate one.

    The mark does change the *wording*: the failure names `duplicate_of` and points at that
    loop, because the row already proves where the extra Timeline event came from and a
    generic `no free raw X event` reads as a defect of the join.
    """
    row, raw = inputs()
    rows = [
        {**row, "op_index": 0, "stream_id": "N/A", "accelerator_core": "COMMUNICATION"},
        {
            **row,
            "op_index": 1,
            "stream_id": "21",
            "accelerator_core": "COMMUNICATION",
            "duplicate_of": 0,
        },
    ]
    # One raw event for one piece of device work, as `trace_view.json` writes it.
    result, output = run_binding(
        adapter, tmp_path, row, [dict(raw)], rows=rows, ts_us=[0, 0]
    )
    assert result.returncode == 1
    assert not output.exists()
    diagnostic = result.stdout + result.stderr
    assert "UNRESOLVED op_index=0" not in diagnostic
    assert "UNRESOLVED op_index=1: no free raw X event named 'Kernel'" in diagnostic
    assert "marked duplicate_of=0" in diagnostic
    assert "emit_ui_facts.py" in diagnostic
    assert "1 Timeline event(s) could not be bound" in diagnostic
    assert "Traceback" not in diagnostic
