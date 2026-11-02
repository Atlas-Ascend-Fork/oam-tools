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
#
"""The raw TraceView join must be by (name, start time, duration), never by name alone.

A repeated layer or a repeated call emits many kernels under one name, and within a step
those kernels frequently share a duration too. Name-plus-nearest-duration then has nothing
left to distinguish them, so the choice silently falls back to the raw trace's array order
-- which has no reason to agree with the Timeline order. Every case here pins one half of
that contract: the start time is compared, a unique match binds, and a non-unique or
absent match fails instead of inventing a high-confidence binding.
"""

import importlib.util
import json
import math
import random
import subprocess
import sys
from collections import defaultdict
from itertools import permutations
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_trace_bindings.py"
SPEC = importlib.util.spec_from_file_location("build_trace_bindings", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def timeline_event(
    op_index, owner, layer, ts_us, duration_us=5.0, name="SameKernel", **extra
):
    return {
        "event_id": f"e{op_index}",
        "op_index": op_index,
        "owner_node_id": owner,
        "layer_index": layer,
        "submodule": name,
        "name": name,
        "ts_us": ts_us,
        "duration_us": duration_us,
        **extra,
    }


def attribution_row(op_index, duration_us=5.0, name="SameKernel", **extra):
    return {
        "op_index": op_index,
        "op_name": name,
        "duration_us": duration_us,
        "owner_node_id": f"node{op_index}",
        "attribution_evidence": "declared_op_indices",
        **extra,
    }


def raw_event(name, ts, dur):
    return {"ph": "X", "name": name, "ts": ts, "dur": dur, "args": {}}


def run_binding(tmp_path, timeline, attribution, trace):
    """Run the script as the pipeline does and hand back the process plus its outputs."""
    inputs = {
        "timeline.json": timeline,
        "attribution.json": attribution,
        "trace.json": trace,
    }
    for name, value in inputs.items():
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")

    out = tmp_path / "bindings.json"
    enriched = tmp_path / "enriched.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--timeline",
            str(tmp_path / "timeline.json"),
            "--attribution",
            str(tmp_path / "attribution.json"),
            "--trace",
            str(tmp_path / "trace.json"),
            "--out",
            str(out),
            "--enrich-trace",
            str(enriched),
        ],
        capture_output=True,
        text=True,
    )
    return proc, out, enriched


def test_repeated_equal_duration_binds_by_start_time(tmp_path):
    """Two identical kernels in reversed array order still land on their own owner.

    This is issue #292: same name, same duration, different start times, and the raw
    trace ordered opposite to the Timeline. Nearest-duration matching has a tie here and
    `min` resolves it by array position, swapping both owners while still reporting 100%
    coverage.
    """
    timeline = {
        "model_id": "m",
        "report_id": "r",
        "events": [
            timeline_event(0, "node0", 0, ts_us=100.0),
            timeline_event(1, "node1", 1, ts_us=200.0),
        ],
    }
    attribution = {"rows": [attribution_row(0), attribution_row(1)]}
    trace = [raw_event("SameKernel", 200.0, 5.0), raw_event("SameKernel", 100.0, 5.0)]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode == 0, proc.stderr
    result = json.loads(enriched.read_text(encoding="utf-8"))
    assert [
        (event["ts"], event["args"]["owner_node_id"], event["args"]["layer_index"])
        for event in result
    ] == [(200.0, "node1", 1), (100.0, "node0", 0)]

    bindings = json.loads(out.read_text(encoding="utf-8"))
    assert bindings["summary"]["coverage_pct"] == 100.0
    # Each Timeline event must point at the raw event carrying its own start time.
    assert [
        (b["op_index"], trace[b["raw_source_event_index"]]["ts"])
        for b in bindings["bindings"]
    ] == [(0, 100.0), (1, 200.0)]
    assert {b["confidence"] for b in bindings["bindings"]} == {"high"}


def test_ambiguous_start_time_and_duration_is_rejected(tmp_path):
    """Two raw events agreeing on all three fields are unresolvable, so nothing is written.

    Picking either one would be a guess presented as `confidence: high`, and the coverage
    summary would still read 100%. Failing is the only honest outcome.
    """
    timeline = {
        "model_id": "m",
        "report_id": "r",
        "events": [timeline_event(0, "node0", 0, ts_us=100.0)],
    }
    attribution = {"rows": [attribution_row(0)]}
    trace = [raw_event("SameKernel", 100.0, 5.0), raw_event("SameKernel", 100.0, 5.0)]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert "ambiguous raw X event match" in proc.stdout
    assert "indices [0, 1]" in proc.stdout
    # No attribution row here carries the mark, so the reason must not claim one. Naming a
    # re-recorded collective over a genuinely ambiguous pair would send the operator to
    # `emit_ui_facts.py` to fix something that is not wrong there.
    assert "duplicate_of" not in proc.stdout
    assert not out.exists()
    assert not enriched.exists()


def test_start_time_mismatch_is_not_bound(tmp_path):
    """A right-named kernel at the wrong time is no match, however close its duration.

    Nearest-duration matching bound this happily: the duration agreed exactly, so the
    start-time disagreement was invisible. It must now report no match.
    """
    timeline = {
        "model_id": "m",
        "report_id": "r",
        "events": [timeline_event(0, "node0", 0, ts_us=100.0)],
    }
    attribution = {"rows": [attribution_row(0)]}
    trace = [raw_event("SameKernel", 900.0, 5.0)]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert "no free raw X event named" in proc.stdout
    assert "ts=100.0" in proc.stdout
    assert not out.exists()
    assert not enriched.exists()


def test_one_raw_kernel_is_never_bound_twice(tmp_path):
    """`used` keeps the join one-to-one even when both events would match the same kernel."""
    timeline = {
        "model_id": "m",
        "report_id": "r",
        "events": [
            timeline_event(0, "node0", 0, ts_us=100.0),
            timeline_event(1, "node1", 1, ts_us=100.0),
        ],
    }
    attribution = {"rows": [attribution_row(0), attribution_row(1)]}
    trace = [raw_event("SameKernel", 100.0, 5.0)]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert "no free raw X event named" in proc.stdout
    assert not out.exists()


def test_match_tolerance_is_absolute_not_relative():
    """The slack is a fixed number of nanoseconds, and it is actually usable.

    A long capture pushes `ts` towards 1e9 us. With a relative tolerance the allowed slack
    grows with it -- `rel_tol=1e-9` at 1e9 us is a whole microsecond, enough to equate two
    neighbouring kernels. `rel_tol=0.0` keeps it absolute at any magnitude.

    `abs_tol` is not exactly the slack you get, though. `math.isclose` compares
    `abs(a - b) <= abs_tol`, and neither `1e-3` nor the subtraction result is exactly
    representable, so an offset that reads as "1 ns" can land a few ULPs above a 1e-3 bound
    and miss. That is why the default is 2e-3: the first assertion below pins a 1 ns offset
    as a match at every magnitude that matters, which a 1e-3 default would fail.
    """
    raw_events = [raw_event("K", 1.0e9, 5.0)]
    by_name = defaultdict(list, {"K": [0]})

    def match(start, duration, tolerance=MODULE.DEFAULT_TIME_MATCH_TOLERANCE_US):
        candidates, _rejected, _near = MODULE.matching_raw_events(
            raw_events, by_name, set(), "K", start, duration, tolerance
        )
        return candidates

    assert match(1.0e9, 5.0) == [0]
    # Half a microsecond away is far outside the tolerance, whatever the magnitude.
    assert match(1.0e9 + 0.5, 5.0) == []
    # A duration that disagrees is not rescued by an agreeing start time.
    assert match(1.0e9, 5.5) == []


def test_one_nanosecond_offset_matches_at_every_magnitude():
    """The slack the comment promises has to be slack the comparison actually gives.

    Both sides of the join are rounded to microsecond decimals independently, so the same
    kernel legitimately comes out ~1 ns apart. Under a 1e-3 default this failed at every
    magnitude tested -- the boundary was open exactly where the docstring said it closed --
    and one such kernel took the whole report down with `no free raw X event`.
    """
    for magnitude in (1.0e2, 1.0e6, 1.0e8, 1.0e9, 5.0e9, 1.0e10):
        raw_events = [raw_event("K", magnitude, 5.0)]
        by_name = defaultdict(list, {"K": [0]})
        # `nextafter` walks one float step up, so this is a true 1 ns offset expressed at
        # whatever resolution the magnitude allows, plus the rounding noise of forming it.
        one_ns = magnitude + 1e-3
        candidates, _rejected, _near = MODULE.matching_raw_events(
            raw_events, by_name, set(), "K", one_ns, 5.0
        )
        assert candidates == [0], f"1 ns offset missed at ts={magnitude:g}"

        # And it stays tight: half a microsecond is never rescued at any magnitude.
        far = magnitude + 0.5
        candidates, _rejected, _near = MODULE.matching_raw_events(
            raw_events, by_name, set(), "K", far, 5.0
        )
        assert candidates == [], f"0.5 us offset matched at ts={magnitude:g}"


def test_time_tolerance_is_configurable_but_refuses_nonsense(tmp_path):
    """`--time-tolerance-us` widens the join on demand; zero, negative and NaN are refused.

    A capture whose two exports disagree by more than the default needs a knob, not a
    source edit. Zero is refused because it turns the join back into the exact float
    comparison the default exists to avoid; negative and non-finite values would match
    nothing or everything. Failing at parse time beats reporting a binding failure whose
    reason never mentions the flag.
    """
    timeline = {
        "model_id": "m",
        "report_id": "r",
        "events": [timeline_event(0, "node0", 0, ts_us=100.0)],
    }
    attribution = {"rows": [attribution_row(0)]}
    # 1 us apart: outside the 2 ns default, inside an explicitly widened tolerance.
    trace = [raw_event("SameKernel", 101.0, 5.0)]

    proc, out, _enriched = run_binding(tmp_path, timeline, attribution, trace)
    assert proc.returncode != 0
    assert "no free raw X event named" in proc.stdout
    assert not out.exists()

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--timeline",
            str(tmp_path / "timeline.json"),
            "--attribution",
            str(tmp_path / "attribution.json"),
            "--trace",
            str(tmp_path / "trace.json"),
            "--out",
            str(tmp_path / "bindings.json"),
            "--time-tolerance-us",
            "2.0",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (
        json.loads((tmp_path / "bindings.json").read_text(encoding="utf-8"))["summary"][
            "coverage_pct"
        ]
        == 100.0
    )

    for bad in ("0", "-1", "nan", "inf", "not-a-number"):
        # Start from no output each time: the widened run above did write the file, and a
        # leftover would make the "nothing was written" assertion pass for the wrong reason.
        (tmp_path / "bindings.json").unlink(missing_ok=True)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--timeline",
                str(tmp_path / "timeline.json"),
                "--attribution",
                str(tmp_path / "attribution.json"),
                "--trace",
                str(tmp_path / "trace.json"),
                "--out",
                str(tmp_path / "bindings.json"),
                "--time-tolerance-us",
                bad,
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 2, (bad, proc.stdout, proc.stderr)
        assert "argument --time-tolerance-us:" in proc.stderr
        assert not (tmp_path / "bindings.json").exists()


def test_already_used_raw_event_is_not_a_candidate():
    """An index claimed by an earlier Timeline event drops out of later candidate sets."""
    raw_events = [raw_event("K", 100.0, 5.0), raw_event("K", 200.0, 5.0)]
    by_name = defaultdict(list, {"K": [0, 1]})

    def match(used, start):
        candidates, _rejected, _near = MODULE.matching_raw_events(
            raw_events, by_name, used, "K", start, 5.0
        )
        return candidates

    assert match(set(), 100.0) == [0]
    assert match({0}, 100.0) == []
    assert match({0}, 200.0) == [1]


def test_unreadable_raw_time_is_rejected_not_zero_filled():
    """A candidate whose `ts`/`dur` cannot be read is refused, and never silently becomes 0.

    Zero-filling would let a kernel with no usable time match a raw event whose time happens
    to be 0, and the binding would still be reported as `confidence: high`. The rejection is
    reported so the pipeline can say which field was unusable; it does not abort the search,
    because a readable sibling may still match.

    The rejection names its raw index. Without it a capture holding several unreadable
    siblings prints the same sentence once per sibling, so the reader cannot tell how many
    events are broken nor which ones to go and look at.
    """
    raw_events = [
        raw_event("K", 100.0, 5.0),
        {"ph": "X", "name": "K", "dur": 5.0, "args": {}},
    ]
    by_name = defaultdict(list, {"K": [0, 1]})

    candidates, rejected, near = MODULE.matching_raw_events(
        raw_events, by_name, set(), "K", 100.0, 5.0
    )
    assert candidates == [0]
    assert rejected == [(1, "Missing or invalid start time: None")]
    assert near == []

    # The readable candidate is what binds, so the unreadable one is not the reason for failure.
    assert MODULE.matching_raw_events(raw_events, by_name, {0}, "K", 100.0, 5.0) == (
        [],
        [(1, "Missing or invalid start time: None")],
        [],
    )


def test_every_unreadable_candidate_is_named_by_its_own_raw_index():
    """Four broken siblings must stay four distinguishable entries, not one repeated sentence.

    The review measured exactly this on a real trace: three to four identical
    `Missing or invalid duration: None` lines in a row. `trace_view.json` can hold a million
    events, so an unindexed list of those is not greppable and does not say how many events
    are damaged. The `near` branch has always carried `#index`; this aligns the two
    diagnostics. Index order, not scan order, so the listing is a function of the trace.
    """
    broken = {"ph": "X", "name": "K", "ts": 100.0, "args": {}}
    raw_events = [
        broken,
        raw_event("K", 100.0, 5.0),
        # Same unreadable field as index 0, different event: the sentence alone cannot tell
        # the two apart, which is the whole point of carrying the index.
        {**broken, "ts": 200.0},
        {"ph": "X", "name": "K", "dur": 5.0, "args": {}},
    ]
    # A differently-broken sibling too, so the fix is not "one message, many indices".
    raw_events.append(
        {"ph": "X", "name": "K", "ts": "not-a-time", "dur": 5.0, "args": {}}
    )
    raw_events.append(raw_event("Other", 100.0, 5.0))
    # `by_name` walked out of index order on purpose: the reported order must not follow it.
    by_name = defaultdict(list, {"K": [4, 3, 2, 0]})

    candidates, rejected, near = MODULE.matching_raw_events(
        raw_events, by_name, set(), "K", 100.0, 5.0
    )

    assert candidates == []
    assert [index for index, _message in rejected] == [0, 2, 3, 4]
    assert rejected == [
        (0, "Missing or invalid duration: None"),
        (2, "Missing or invalid duration: None"),
        (3, "Missing or invalid start time: None"),
        (4, "Missing or invalid start time: 'not-a-time'"),
    ]
    assert near == []
    reason = MODULE.no_match_reason("K", 100.0, 5.0, rejected, near)
    assert "#0 Missing or invalid duration: None" in reason
    assert "#2 Missing or invalid duration: None" in reason
    assert "#3 Missing or invalid start time: None" in reason
    assert "#4 Missing or invalid start time: 'not-a-time'" in reason
    # Index 5 is a different op name, so it must not be swept into this event's diagnostics.
    assert "#5" not in reason


def test_failure_names_the_near_miss_alongside_the_unreadable_field(tmp_path):
    """One failure message carries every reason, not whichever one sorts first.

    The old wording was `invalid raw matching fields` *or* the mismatch text, so a raw event
    with a missing `ts` swallowed the fact that the real kernel sat 2 ns outside the
    tolerance. Reading the log then sent you after the wrong fix.
    """
    timeline = {
        "model_id": "m",
        "report_id": "r",
        "events": [timeline_event(0, "node0", 0, ts_us=100.0)],
    }
    attribution = {"rows": [attribution_row(0)]}
    trace = [
        {"ph": "X", "name": "SameKernel", "dur": 5.0, "args": {}},
        raw_event("SameKernel", 100.5, 5.0),
    ]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert not out.exists()
    assert not enriched.exists()
    line = [ln for ln in proc.stdout.splitlines() if ln.startswith("UNRESOLVED")][0]
    assert "no free raw X event named 'SameKernel' matching ts=100.0, dur=5.0" in line
    assert "invalid raw matching fields: #0 Missing or invalid start time: None" in line
    assert "closest unmatched: #1 dts=0.500000us ddur=0.000000us" in line


def collective_pair():
    """The real shape behind issue #292, not two made-up kernels.

    msprof writes one collective twice into `op_summary.csv`: a COMMUNICATION record with no
    Stream ID, and the AIV kernel that executes it on a real stream, with an identical
    (start time, duration). `analyze_kernels.mark_duplicate_collective_records` proves they
    are the same device work -- it only marks a group of exactly two where exactly one row
    has no Stream ID -- and tags the second `duplicate_of`. `attribute_kernels` carries both
    the mark and `stream_id` through, and `emit_ui_facts` puts `stream_id` on the Timeline
    event.

    So upstream can already tell these two apart; the raw join cannot, because it only looks
    at (name, ts, dur). Skipping `duplicate_of` rows in the emit_ui_facts timeline loop is
    the root-cause fix and belongs to that file. These two cases pin what this adapter does
    until then, for both ways `trace_view.json` can come out.
    """
    common = {
        "duration_us": 73000.0,
        "name": "AllReduce",
        "accelerator_core": "COMMUNICATION",
    }
    primary = attribution_row(0, stream_id="N/A", **common)
    duplicate = attribution_row(1, stream_id="21", duplicate_of=0, **common)
    events = [
        timeline_event(0, "node0", 0, ts_us=1000.0, stream_id="N/A", **common),
        timeline_event(
            1, "node1", 0, ts_us=1000.0, stream_id="21", duplicate_of=0, **common
        ),
    ]
    return events, [primary, duplicate]


def test_marked_duplicate_pair_with_one_raw_event_exhausts_the_join(tmp_path):
    """Sub-case A: `trace_view.json` wrote the collective once, the Timeline twice.

    The first event claims the only raw `X` event; the marked duplicate then finds nothing
    free and reports `no free raw X event`. This is the honest outcome for the adapter -- it
    must not invent a binding for an event the capture has no kernel for -- but it means one
    marked duplicate takes the whole report down. The fix is upstream: emit_ui_facts must not
    emit a timeline event for a `duplicate_of` row. The reason therefore names the mark and
    points there, so the operator is not sent hunting for a defect in this join.
    """
    events, rows = collective_pair()
    timeline = {"model_id": "m", "report_id": "r", "events": events}
    attribution = {"rows": rows}
    trace = [raw_event("AllReduce", 1000.0, 73000.0)]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert not out.exists()
    assert not enriched.exists()
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("UNRESOLVED")]
    assert len(lines) == 1
    assert "op_index=1" in lines[0]
    assert "no free raw X event named 'AllReduce'" in lines[0]
    assert "marked duplicate_of=0" in lines[0]
    assert "emit_ui_facts.py" in lines[0]
    # Diagnostic text only: the row is still refused, not skipped, so the report stays empty.
    assert "1 Timeline event(s) could not be bound" in proc.stdout + proc.stderr


def test_marked_duplicate_pair_with_two_raw_events_is_ambiguous(tmp_path):
    """Sub-case B: `trace_view.json` also wrote it twice, so nothing distinguishes them.

    Both raw `X` events agree on all three joined fields, and `stream_id` -- the one field
    that does separate the pair -- is not part of this join and its presence in the raw
    export is not established anywhere in the repo. So the adapter reports `ambiguous` for
    both events instead of guessing, which is what the module docstring has always promised.
    Note this is a behaviour change from name-plus-nearest-duration, which bound both and
    reported 100% coverage while possibly swapping the owners.

    Only the row carrying the mark can name it -- `attribute_kernels` writes
    `duplicate_of: None` on the primary -- so the primary's line stays the generic
    interchangeability statement while the duplicate's names the origin.
    """
    events, rows = collective_pair()
    timeline = {"model_id": "m", "report_id": "r", "events": events}
    attribution = {"rows": rows}
    trace = [
        raw_event("AllReduce", 1000.0, 73000.0),
        raw_event("AllReduce", 1000.0, 73000.0),
    ]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert not out.exists()
    assert not enriched.exists()
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("UNRESOLVED")]
    assert len(lines) == 2
    assert all("ambiguous raw X event match" in ln for ln in lines)
    assert "indices [0, 1]" in lines[0]
    assert "op_index=0" in lines[0]
    assert "op_index=1" in lines[1]
    assert "duplicate_of" not in lines[0]
    assert "marked duplicate_of=0" in lines[1]
    assert "emit_ui_facts.py" in lines[1]
    assert "interchangeable with Timeline op_index [0]" in lines[1]


def test_every_unresolved_case_is_printed_and_listed_in_a_sidecar(tmp_path):
    """Nothing is truncated away, and the full list survives the pipeline's 800-char cut.

    One root cause fails in pairs across a whole capture: the DS3.2 capture that
    `emit_ui_facts.counter_sum` documents carries 16 duplicate pairs. Printing only the
    first ten then read as "ten unrelated problems" and hid the pattern that lived in the
    cases beyond the cut. `run_pipeline.py` keeps just the last 800 characters of a failed
    stage, so the sidecar path travels in the exit message rather than only in the stdout
    listing.
    """
    count = 25
    events = [timeline_event(i, f"node{i}", i, ts_us=100.0 + i) for i in range(count)]
    attribution = {"rows": [attribution_row(i) for i in range(count)]}
    timeline = {"model_id": "m", "report_id": "r", "events": events}
    trace = []  # nothing to bind against

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert not out.exists()
    assert not enriched.exists()
    printed = [ln for ln in proc.stdout.splitlines() if ln.startswith("UNRESOLVED")]
    assert len(printed) == count, "every case must be printed, not just the first ten"

    sidecar = tmp_path / "bindings.json.unresolved.json"
    assert sidecar.exists()
    listed = json.loads(sidecar.read_text(encoding="utf-8"))
    assert listed["unresolved_count"] == count
    assert [item["op_index"] for item in listed["unresolved"]] == list(range(count))
    assert all(item["reason"] for item in listed["unresolved"])
    # The pointer has to be in the exit message itself, which is what the pipeline relays.
    assert str(sidecar) in proc.stderr
    assert f"{count} Timeline event(s) could not be bound" in proc.stderr


def crowded_out_shape():
    """Two Timeline events, and only one of the two raw kernels is genuinely up for grabs.

    Raw #0 starts at 100.000 us and raw #1 at 100.003 us. Event `op_index=0` starts at
    100.0015 us, so it is inside the 2 ns tolerance of *both* and, read on its own, looks
    ambiguous. Event `op_index=1` starts at 100.003 us, which raw #0 is outside of, so that
    event can only take raw #1. Which forces the other one onto raw #0: exactly one
    assignment binds both events, and it is the only one.

    A scan that claims raw kernels as it goes cannot see this. Reading the events in array
    order, event 0 arrives first, counts two free candidates and fails the whole report --
    so the same capture either binds at 100% or produces nothing according to an ordering
    nobody chose. This is the counterexample from the PR #880 review.
    """
    events = [
        timeline_event(0, "node0", 0, ts_us=100.0015),
        timeline_event(1, "node1", 1, ts_us=100.003),
    ]
    rows = [attribution_row(0), attribution_row(1)]
    trace = [
        raw_event("SameKernel", 100.0, 5.0),
        raw_event("SameKernel", 100.003, 5.0),
    ]
    return events, rows, trace


def test_crowded_out_event_binds_in_either_timeline_order(tmp_path):
    """The forced assignment is found even when the picky event is listed second."""
    events, rows, trace = crowded_out_shape()
    attribution = {"rows": rows}

    for name, ordered in (("as_listed", events), ("reversed", list(reversed(events)))):
        workdir = tmp_path / name
        workdir.mkdir()
        timeline = {"model_id": "m", "report_id": "r", "events": ordered}
        proc, out, enriched = run_binding(workdir, timeline, attribution, trace)

        assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
        bindings = json.loads(out.read_text(encoding="utf-8"))
        assert bindings["summary"]["coverage_pct"] == 100.0
        assert {
            (b["op_index"], b["raw_source_event_index"]) for b in bindings["bindings"]
        } == {(0, 0), (1, 1)}, name


def short_match_shape():
    """Three Timeline events over two raw kernels: the capture is simply one short.

    Same raw pair as `crowded_out_shape`, plus a third event at 100.000 us that only raw #0
    can serve. Two events then have to share one kernel, so no one-to-one assignment covers
    all three and exactly one event is left over.

    This is the shape that separates two different claims. The holder of the contested raw
    is `op_index=0` at 100.0015 us, which is inside the 2 ns tolerance of *both* raws -- so
    it is not true that the raw it took was its only possible match. A reason that says "the
    only match of Timeline op_index [0]" asserts exactly that, and sends the reader hunting
    for a picky event when the real cause is a capture with too few kernels. What the
    maximum matching does prove is who holds the raw now and that no reshuffle frees it, so
    that is all the reason may say. Counterexample from the PR #880 review.
    """
    events = [
        timeline_event(0, "node0", 0, ts_us=100.0015),
        timeline_event(1, "node1", 1, ts_us=100.0),
        timeline_event(2, "node2", 2, ts_us=100.003),
    ]
    rows = [attribution_row(0), attribution_row(1), attribution_row(2)]
    trace = [
        raw_event("SameKernel", 100.0, 5.0),
        raw_event("SameKernel", 100.003, 5.0),
    ]
    return events, rows, trace


def test_short_match_names_the_holder_without_claiming_it_was_picky(tmp_path):
    """The leftover event blames who holds the raw, not a uniqueness nobody proved."""
    events, rows, trace = short_match_shape()
    timeline = {"model_id": "m", "report_id": "r", "events": events}

    proc, out, _enriched = run_binding(tmp_path, timeline, {"rows": rows}, trace)

    assert proc.returncode != 0
    assert not out.exists()
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("UNRESOLVED")]
    assert len(lines) == 1, lines
    assert "op_index=2" in lines[0]
    assert (
        "indices [1] do match but are already taken by Timeline op_index [0]"
        in lines[0]
    )
    assert "no reassignment frees them" in lines[0]
    # The claim the review ruled out: raw #1 was *not* the only match of op_index=0, which
    # also matches raw #0. Nothing here proves exclusivity, so the text must not assert it.
    assert "only match" not in lines[0]
    assert "ambiguous" not in lines[0]


def test_short_match_reason_is_the_same_in_every_timeline_order(tmp_path):
    """Who gets named is a property of the capture, not of the array order."""
    events, rows, trace = short_match_shape()
    attribution = {"rows": rows}
    reasons = set()

    for permutation in permutations(events):
        tag = "".join(str(event["op_index"]) for event in permutation)
        workdir = tmp_path / tag
        workdir.mkdir()
        timeline = {"model_id": "m", "report_id": "r", "events": list(permutation)}
        proc, out, _enriched = run_binding(workdir, timeline, attribution, trace)

        assert proc.returncode != 0, (tag, proc.stdout)
        assert not out.exists()
        lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("UNRESOLVED")]
        assert len(lines) == 1, (tag, lines)
        reasons.add(lines[0])

    assert len(reasons) == 1, reasons


def order_independent_shapes():
    """Fixtures whose greedy outcome used to depend on the Timeline array order.

    Each one is checked under *every* permutation of its events, so the property being
    pinned is the one the review asked for: the order the file lists events in changes
    nothing -- not the return code, not which raw kernel each event gets, not the failure
    text. Success and failure both have to be stable; a matcher that simply failed on every
    permutation would pass the first half of that and is exactly as order-blind as the
    greedy scan it replaced.
    """
    crowded_events, crowded_rows, crowded_trace = crowded_out_shape()
    duplicate_events, duplicate_rows = collective_pair()
    one_raw = [raw_event("AllReduce", 1000.0, 73000.0)]
    two_raws = one_raw * 2
    return {
        # Binds, and must bind the same way however the two events are ordered.
        "crowded_out": (crowded_events, {"rows": crowded_rows}, crowded_trace),
        # One kernel short: fails, and the single victim is named the same either way.
        "duplicate_pair_one_raw": (duplicate_events, {"rows": duplicate_rows}, one_raw),
        # Genuinely ambiguous: fails, and both events are named the same either way.
        "duplicate_pair_two_raws": (
            duplicate_events,
            {"rows": duplicate_rows},
            two_raws,
        ),
    }


def test_result_does_not_depend_on_timeline_event_order(tmp_path):
    outcomes_by_shape = {}
    for name, (events, attribution, trace) in order_independent_shapes().items():
        outcomes = []
        for permutation in permutations(events):
            tag = "".join(str(event["op_index"]) for event in permutation)
            workdir = tmp_path / name / tag
            workdir.mkdir(parents=True)
            timeline = {
                "model_id": "m",
                "report_id": "r",
                "events": list(permutation),
            }
            proc, out, _enriched = run_binding(workdir, timeline, attribution, trace)

            bound = None
            if out.exists():
                payload = json.loads(out.read_text(encoding="utf-8"))
                bound = tuple(
                    sorted(
                        (b["op_index"], b["raw_source_event_index"])
                        for b in payload["bindings"]
                    )
                )
            unresolved = tuple(
                sorted(
                    line
                    for line in proc.stdout.splitlines()
                    if line.startswith("UNRESOLVED")
                )
            )
            outcomes.append((proc.returncode, bound, unresolved))

        assert len(set(outcomes)) == 1, (name, outcomes)
        outcomes_by_shape[name] = outcomes[0]

    # Both halves of the property are real, so the check above is not vacuous: one shape
    # binds every permutation, the other two refuse every permutation.
    returncode, bound, unresolved = outcomes_by_shape["crowded_out"]
    assert (returncode, bound, unresolved) == (0, ((0, 0), (1, 1)), ())
    for name in ("duplicate_pair_one_raw", "duplicate_pair_two_raws"):
        returncode, bound, unresolved = outcomes_by_shape[name]
        assert returncode != 0 and bound is None, name
        assert unresolved, name


def test_an_event_pointing_into_an_exchange_cycle_is_not_blamed(tmp_path):
    """Only the interchangeable events are reported, not everything upstream of them.

    Events 0 and 1 both start at 100.0 us against two identical raw kernels, so they can
    swap and neither assignment is forced. Event 2 starts at 200.0 us and is the only event
    raw #2 matches, so its binding is forced even though it sits in the same report. Naming
    event 2 as well would tell the reader to go hunting for a third duplicate that is not
    there, and would understate what actually has to be fixed upstream.
    """
    timeline = {
        "model_id": "m",
        "report_id": "r",
        "events": [
            timeline_event(0, "node0", 0, ts_us=100.0),
            timeline_event(1, "node1", 1, ts_us=100.0),
            timeline_event(2, "node2", 2, ts_us=200.0),
        ],
    }
    attribution = {"rows": [attribution_row(0), attribution_row(1), attribution_row(2)]}
    trace = [
        raw_event("SameKernel", 100.0, 5.0),
        raw_event("SameKernel", 100.0, 5.0),
        raw_event("SameKernel", 200.0, 5.0),
    ]

    proc, out, enriched = run_binding(tmp_path, timeline, attribution, trace)

    assert proc.returncode != 0
    assert not out.exists()
    assert not enriched.exists()
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("UNRESOLVED")]
    assert len(lines) == 2, lines
    assert [ln.split(":")[0] for ln in lines] == [
        "UNRESOLVED op_index=0",
        "UNRESOLVED op_index=1",
    ]
    assert all("ambiguous raw X event match" in ln for ln in lines)
    assert all("interchangeable with Timeline op_index" in ln for ln in lines)
    assert "indices [0, 1]" in lines[0]
    # Interchangeability on its own is not evidence of a re-recorded collective.
    assert all("duplicate_of" not in ln for ln in lines)


def test_bucketed_lookup_agrees_with_the_full_scan():
    """The fast candidate lookup must return exactly what the documented scan returns.

    `candidate_raw_events` exists only to keep the success path off a per-event walk of every
    same-name kernel, which is quadratic in the number of repeats and was measured at 186 s for
    20000 of them. `matching_raw_events` is the predicate the module docstring describes and
    the unit tests above pin, so if the bucketed shortcut ever disagreed with it the failure
    messages would describe a different candidate set from the one actually matched -- and a
    wrong bucket boundary would drop a legitimate kernel with no diagnostic naming it.

    Randomised across tolerances, timestamp magnitudes, duplicate and negative times,
    unreadable times and non-`X` events. The tables come from `index_raw_events`, the same
    function the script calls, so this compares the two lookups rather than a copy of the
    indexing rules.
    """
    rng = random.Random(20261031)
    names = ["K", "Other", None]
    magnitudes = [0.0, 100.0, 1e6, 1e9, -50.0]

    for _trial in range(300):
        tolerance = rng.choice([2e-3, 1e-3, 0.5, 1.0, 5.0])
        raw_events = []
        for _ in range(rng.randint(0, 12)):
            kind = rng.random()
            if kind < 0.10:
                # A same-name event with no usable time: never a candidate, always `rejected`.
                raw_events.append({"ph": "X", "name": rng.choice(names), "args": {}})
            elif kind < 0.15:
                # Not a complete duration event, so the join ignores it entirely.
                raw_events.append({"ph": "i", "name": "K", "ts": 100.0, "dur": 5.0})
            else:
                offset = rng.choice([0.0, 1e-3, 2e-3, -1e-3, -2e-3, 0.5, rng.random()])
                raw_events.append(
                    {
                        "ph": "X",
                        "name": rng.choice(names),
                        "ts": rng.choice(magnitudes) + offset,
                        "dur": rng.choice([5.0, 5.0 + 1e-3, 0.0, 7.0]),
                        "args": {},
                    }
                )

        by_name, by_bucket = MODULE.index_raw_events(raw_events, tolerance)
        for name in names:
            for _ in range(4):
                offset = rng.choice([0.0, 1e-3, 2e-3, -1e-3, 0.5, rng.random()])
                start = rng.choice(magnitudes) + offset
                duration = rng.choice([5.0, 0.0, 7.0])
                fast = MODULE.candidate_raw_events(
                    by_bucket, name, start, duration, tolerance
                )
                slow, _rejected, _near = MODULE.matching_raw_events(
                    raw_events, by_name, set(), name, start, duration, tolerance
                )
                assert fast == slow, (
                    name,
                    start,
                    duration,
                    tolerance,
                    fast,
                    slow,
                    raw_events,
                )


def test_near_miss_list_is_capped_while_scanning_without_losing_a_closer_one():
    """The `near` cap must not be paid for by sorting every disagreeing same-name kernel.

    A capture repeats one kernel name thousands of times, so a Timeline event that matches
    none of them used to collect one entry per same-name kernel and sort the whole list, to
    keep three of it. The review measured that: 3000 same-name events on the all-fail path
    cost 7.8 s where the pre-change code cost 1.9 s, and 20000 did not finish in 70 s. The
    cap is now enforced during the scan, which is only worth doing if it returns exactly the
    entries the collect-everything-then-sort version returned.

    Three things have to hold, and the first two are the ones a bounded scan gets wrong:

    * while fewer than `NEAR_MISS_LIMIT` misses are kept, a *worse* one still belongs in the
      report -- pruning against the worst kept entry only becomes legal once the list is full;
    * ties keep the lower raw index, which is what the previous stable sort produced;
    * the kept entries are the closest by the worse of the two deltas, in ascending order.

    Cross-checked against the collect-then-sort reference over random inputs rather than
    asserting one hand-built trace, because the failure this guards against is a listing that
    is merely *shorter*, which any single example can look like it got right.
    """
    rng = random.Random(20261101)
    limit = MODULE.NEAR_MISS_LIMIT

    def reference(raw_events, by_name, used, op_name, start, duration, tolerance):
        """Collect every disagreeing free event, then sort and slice -- the old behaviour."""
        everything = []
        for raw_index in by_name.get(op_name, []):
            if raw_index in used:
                continue
            event = raw_events[raw_index]
            try:
                raw_start = MODULE.required_time(event.get("ts"), "start time")
                raw_duration = MODULE.required_time(event.get("dur"), "duration")
            except ValueError:
                continue
            if math.isclose(
                raw_start, start, rel_tol=0.0, abs_tol=tolerance
            ) and math.isclose(raw_duration, duration, rel_tol=0.0, abs_tol=tolerance):
                continue
            everything.append(
                (raw_index, abs(raw_start - start), abs(raw_duration - duration))
            )
        everything.sort(key=lambda miss: (max(miss[1], miss[2]), miss[0]))
        return everything[:limit]

    # Fewer readable siblings than the limit, each worse than the last: a scan that prunes
    # against the worst entry before the list is full drops these and reports one miss
    # instead of three, which is the shape the all-fail measurement would never notice.
    sparse = [raw_event("K", 100.0 + step, 5.0) for step in (1.0, 2.0, 3.0)]
    _candidates, _rejected, near = MODULE.matching_raw_events(
        sparse, defaultdict(list, {"K": [0, 1, 2]}), set(), "K", 100.0, 5.0
    )
    assert [index for index, _ds, _dd in near] == [0, 1, 2]

    # Exactly tied deltas, walked out of index order: the listing still goes by raw index.
    tied = [raw_event("K", 101.0, 5.0) for _ in range(limit + 2)]
    by_name_tied = defaultdict(list, {"K": [4, 3, 2, 1, 0]})
    _candidates, _rejected, near = MODULE.matching_raw_events(
        tied, by_name_tied, set(), "K", 100.0, 5.0
    )
    assert near == [(index, 1.0, 0.0) for index in range(limit)]

    for _trial in range(300):
        tolerance = rng.choice([2e-3, 1e-3, 0.5, 1.0, 5.0])
        raw_events = []
        for _ in range(rng.randint(0, 14)):
            kind = rng.random()
            if kind < 0.10:
                # Unreadable times land in `rejected`, never in `near`.
                raw_events.append({"ph": "X", "name": "K", "args": {}})
            elif kind < 0.15:
                raw_events.append({"ph": "i", "name": "K", "ts": 100.0, "dur": 5.0})
            else:
                raw_events.append(
                    {
                        "ph": "X",
                        "name": rng.choice(["K", "Other", None]),
                        # Repeated values on purpose, so ties are the common case.
                        "ts": rng.choice(
                            [100.0, 100.0, 100.5, 101.0, 99.5, -100.0, 0.0]
                        )
                        + rng.choice([0.0, 1e-3, 2e-3, 0.25]),
                        "dur": rng.choice([5.0, 5.0, 5.0 + 1e-3, 0.0, 7.0]),
                        "args": {},
                    }
                )

        by_name, _by_bucket = MODULE.index_raw_events(raw_events, tolerance)
        indices = by_name.get("K", [])
        for _ in range(4):
            used = {index for index in indices if rng.random() < 0.3}
            start = rng.choice([100.0, 100.0, 99.75, 101.0, 0.0, -100.0])
            duration = rng.choice([5.0, 0.0, 7.0])
            _candidates, _rejected, near = MODULE.matching_raw_events(
                raw_events, by_name, used, "K", start, duration, tolerance
            )
            assert near == reference(
                raw_events, by_name, used, "K", start, duration, tolerance
            ), (start, duration, tolerance, sorted(used), near, raw_events)
            assert len(near) <= limit
