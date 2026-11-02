#!/usr/bin/env python3
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
"""Bind every normalized Timeline event to one structure node and one raw TraceView event.

The UI skill's own `build-trace-bindings.mjs` re-derives ownership from one model's kernel
shapes (RmsNorm layer boundaries, an `mtp_scaffold` stage, hardcoded lm_head node ids), so it
only runs for that model. The attribution this pipeline already produced is stronger evidence:
it comes from the breakdown's declared `op_indices` and instance ranges, verified at 100%
coverage. This joins that attribution to the raw trace instead of guessing it again.

The raw join is by (op name, start time, duration) against `X` events, with the two times
compared to within `DEFAULT_TIME_MATCH_TOLERANCE_US`.

The whole Timeline is assigned at once instead of event by event. A scan that claims a raw
kernel as it goes makes the outcome depend on the order the Timeline happens to list its
events in: an event with several candidates would be called ambiguous even when a later
event takes all but one of them, so the same capture either binds at 100% or produces
nothing at all according to an ordering nobody chose. Assignment is therefore a maximum
one-to-one matching over the candidate graph, taken in a canonical order, and it is
accepted only when it covers every Timeline event and is the only cover that does.

A kernel that matches no raw event, or whose match is not forced, is an error rather than a
silent drop. Every such case is printed and also written to `<out>.unresolved.json` next to
the output path, since one repeated root cause can produce far more cases than fit in a
pipeline's truncated stage log.
"""

import argparse
import bisect
import json
import math
import os
from collections import defaultdict, deque

# Both sides of the join come from one msprof capture but leave it through two different
# exports: `op_summary.csv` -> breakdown -> attribution -> Timeline `ts_us`/`duration_us`,
# and `trace_view.json` -> raw `X` event `ts`/`dur`. Each side is rounded to microsecond
# decimals, so the same kernel can come out of the two exports up to ~1 ns apart.
#
# The default is 2 ns, not 1 ns, because the promised slack and the effective slack are not
# the same number. `math.isclose` uses `abs(a - b) <= abs_tol`, and `1e-3` is not exactly
# representable, so a difference of a "clean" 1 ns can land a few ULPs above the bound and
# miss. Measured at `ts` magnitudes from 1e2 to 1e10 us, a 1 ns offset plus that rounding
# noise never exceeds ~1.002e-3 us -- inside 2e-3 with room to spare, outside 1e-3. Keeping
# the default at 1e-3 would make the boundary open exactly where the comment says it closes,
# turning one legitimate kernel into a `no free raw X event` failure for the whole report.
#
# The tolerance still has to be absolute. A relative one scales with the timestamp
# magnitude, and on a capture whose `ts` reaches 1e9 us even `rel_tol=1e-9` would allow
# ~1 us of slack -- wide enough to equate two neighbouring kernels and re-introduce the
# ambiguity this join exists to avoid.
DEFAULT_TIME_MATCH_TOLERANCE_US = 2e-3

# How many of the closest free-but-unmatched candidates a failure message names. Enough to
# see whether the miss was 2 ns or 2 s, small enough to stay readable on a long capture.
NEAR_MISS_LIMIT = 3

# How many timestamp buckets either side of the query a candidate lookup reads. One is enough
# in exact arithmetic: two times within `tolerance` of each other cannot sit more than one
# bucket (of width `tolerance`) apart. The extra two on each side absorb the error of dividing
# a `ts` that can reach 1e10 us by a tolerance as small as 1e-3, which at that magnitude is
# ~1e-4 of a bucket. Each extra bucket costs one dict probe and can never admit a wrong
# candidate -- every index found is still checked with the same `math.isclose` the full scan
# uses -- so the slack is free insurance against a boundary rounding the wrong way.
BUCKET_SCAN_OFFSETS = (-2, -1, 0, 1, 2)


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def positive_float(value):
    """argparse type for `--time-tolerance-us`: finite, and strictly greater than zero.

    Zero would turn the join back into an exact float comparison, which is the open-boundary
    failure the default exists to avoid; a negative or non-finite slack would match nothing
    or everything. Refusing the value at parse time beats reporting it as a binding failure
    with a reason that does not mention the flag.
    """
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from error
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError(
            f"must be a finite number > 0 us, got {value!r}"
        )
    return result


def required_time(value, label):
    """Read one timestamp/duration field, refusing to invent a number for it.

    Both a missing field and a non-finite one are errors: zero-filling either side of the
    join would let a kernel that carries no usable time match a raw event by luck and still
    be reported as `confidence: high`. Durations are additionally rejected when negative.
    """
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Missing or invalid {label}: {value!r}") from error
    if not math.isfinite(result) or (label == "duration" and result < 0):
        raise ValueError(f"Invalid {label}: {value!r}")
    return result


def matching_raw_events(
    raw_events,
    by_name,
    used,
    op_name,
    start,
    duration,
    tolerance=DEFAULT_TIME_MATCH_TOLERANCE_US,
):
    """Free raw `X` events whose name, start time and duration all match, plus why others lost.

    Returns `(candidates, rejected, near)`. All three fields must agree within `tolerance`
    microseconds; name alone is not enough because a repeated layer or a repeated call
    emits many kernels under one name. `used` holds the indices already claimed by an
    earlier Timeline event, so one raw kernel is never bound twice.

    A free event whose `ts`/`dur` is missing or non-finite cannot take part in an exact
    join, so it lands in `rejected` as `(raw_index, required_time message)` instead of being
    zero-filled. It does not abort the search: another free event may still match, and one
    unreadable sibling must not cost an otherwise bindable kernel its binding.

    A free event that is readable but disagrees lands in `near` as
    `(raw_index, abs(start delta), abs(duration delta))`, closest first and capped at
    `NEAR_MISS_LIMIT`. The cap is enforced while scanning, not by sorting afterwards: a
    capture can hold thousands of same-name kernels that all disagree, and building and
    sorting a list that long on every failing event, only to throw all but three of it away,
    cost more than the scan itself.

    Both carry the raw index: a capture can hold several unreadable
    siblings, and without the index every one of them prints the same sentence, so the reader
    cannot tell how many events are broken or go and look at them. `rejected` is not capped --
    the list of indices *is* the answer, and it only ever reaches a failure message.

    `rejected` and `near` answer two different questions, and a caller
    that reports only one of them hides the other: "this candidate had no usable time" says
    nothing about the candidate that was 2 ns off, and vice versa.
    """
    candidates = []
    rejected = []
    near = []
    for raw_index in by_name.get(op_name, []):
        if raw_index in used:
            continue
        raw_event = raw_events[raw_index]
        try:
            raw_start = required_time(raw_event.get("ts"), "start time")
            raw_duration = required_time(raw_event.get("dur"), "duration")
        except ValueError as error:
            rejected.append((raw_index, str(error)))
            continue
        start_matches = math.isclose(raw_start, start, rel_tol=0.0, abs_tol=tolerance)
        duration_matches = math.isclose(
            raw_duration, duration, rel_tol=0.0, abs_tol=tolerance
        )
        if start_matches and duration_matches:
            candidates.append(raw_index)
        else:
            start_delta = abs(raw_start - start)
            duration_delta = abs(raw_duration - duration)
            worst = start_delta if start_delta >= duration_delta else duration_delta
            # `near` is kept sorted closest-first and never grows past the limit, so once it
            # is full its last entry is the worst one kept. A miss no closer than that can
            # never make the listing, and dropping it here is what stops a trace with
            # thousands of disagreeing same-name kernels from being collected and sorted once
            # per failing event. The guard has to test fullness first: while fewer than
            # NEAR_MISS_LIMIT misses are kept, even a worse one still belongs in the report.
            #
            # The comparison is over the whole sort key, not just the delta, so an exact tie
            # is resolved by raw index rather than by whichever of the tied kernels the scan
            # reached first. `by_name` is built in ascending index order, so in practice the
            # two agree; comparing the key keeps that a property of the listing instead of a
            # property of the walk, which is the same reason `rejected` is sorted by index.
            #
            # Spelled out rather than as one tuple comparison: this runs once per same-name
            # kernel per failing event, and building two throwaway tuples to compare them
            # measured slower than the collect-then-sort it replaced.
            if len(near) == NEAR_MISS_LIMIT:
                worst_kept, index_kept = near[-1][0], near[-1][1]
                if worst > worst_kept or (
                    worst == worst_kept and raw_index >= index_kept
                ):
                    continue
            # Worst of the two deltas first, then the raw index, so ties land in ascending
            # index order -- which is what the previous stable sort produced, because
            # `by_name` is built in ascending index order.
            bisect.insort(near, (worst, raw_index, start_delta, duration_delta))
            del near[NEAR_MISS_LIMIT:]
    # Ascending raw index, so the listing is a function of the trace and not of the order
    # `by_name` happened to be walked in.
    rejected.sort(key=lambda entry: entry[0])
    return (
        candidates,
        rejected,
        [
            (raw_index, start_delta, duration_delta)
            for _worst, raw_index, start_delta, duration_delta in near
        ],
    )


def time_bucket(value, tolerance):
    """Bucket index for one timestamp under an absolute tolerance of `tolerance` us.

    `math.floor`, not `int()`: a negative `ts` has to land in the bucket below it rather than
    be rounded towards zero and collide with the positive side, which would put two times a
    whole tolerance apart in one bucket and two adjacent times in buckets three apart.
    """
    return math.floor(value / tolerance)


def candidate_raw_events(by_bucket, op_name, start, duration, tolerance):
    """Raw `X` indices whose (name, ts, dur) all agree within `tolerance`, ascending.

    The same predicate `matching_raw_events` applies, but the timestamps were bucketed when the
    trace was loaded, so this reads a handful of buckets instead of every same-name event in
    the capture. That difference is the whole point: the per-event scan is quadratic in the
    number of same-name kernels, and a representative step repeats one kernel name thousands
    of times. Measured on 1500 same-name events the full scan per event took the success path
    from 1.0 s to 1.9 s, and the review measured 3000 events at 3.9 s with 20000 not finishing
    in 70 s -- all of it on a path that prints no diagnostic at all.

    `matching_raw_events` stays the single source of truth for the predicate and for the
    `rejected`/`near` diagnostics; this function deliberately computes neither, because both
    only ever reach a failure message and are now gathered lazily, for the events that actually
    failed. A test cross-checks the two candidate lists over random inputs so the fast path
    cannot drift away from the documented one.
    """
    centre = time_bucket(start, tolerance)
    found = []
    for offset in BUCKET_SCAN_OFFSETS:
        for raw_index, raw_start, raw_duration in by_bucket.get(
            (op_name, centre + offset), ()
        ):
            if math.isclose(
                raw_start, start, rel_tol=0.0, abs_tol=tolerance
            ) and math.isclose(raw_duration, duration, rel_tol=0.0, abs_tol=tolerance):
                found.append(raw_index)
    found.sort()
    return found


def index_raw_events(raw_events, tolerance):
    """Build the two lookup tables the join needs, in one pass over the raw trace.

    Returns `(by_name, by_bucket)`. `by_name` maps an op name to every raw `X` index carrying
    it, and is what `matching_raw_events` walks when a failure has to explain itself.
    `by_bucket` maps `(op name, start-time bucket)` to `(index, ts, dur)` triples, and is what
    `candidate_raw_events` reads per Timeline event.

    An event whose `ts` or `dur` cannot be read is left out of `by_bucket` -- it can never
    match anything -- but stays in `by_name`, which is what lets the diagnostics still report
    it as `rejected` instead of dropping it silently. Non-`X` events are in neither: the join
    is defined over complete duration events only.

    A function rather than inline code in `main` so the tests can build the same tables the
    script does and cross-check the two lookups against each other, instead of keeping a
    second copy of the indexing rules that could drift from this one.
    """
    by_name = defaultdict(list)
    by_bucket = defaultdict(list)
    for index, event in enumerate(raw_events):
        if event.get("ph") != "X":
            continue
        op_name = event.get("name")
        by_name[op_name].append(index)
        try:
            raw_start = required_time(event.get("ts"), "start time")
            raw_duration = required_time(event.get("dur"), "duration")
        except ValueError:
            continue
        by_bucket[(op_name, time_bucket(raw_start, tolerance))].append(
            (index, raw_start, raw_duration)
        )
    return by_name, by_bucket


def duplicate_of_clause(duplicate_of):
    """Name the root cause the attribution row already proves, or `None` if there is none.

    msprof records one collective twice: a COMMUNICATION entry plus the AIV kernel running
    it, with an identical (name, start time, duration). `analyze_kernels`'s
    `mark_duplicate_collective_records` proves the pair is one piece of device work and tags
    the second row `duplicate_of`; `attribute_kernels` carries the mark into the attribution
    row; `emit_ui_facts`'s timeline loop then emits one event per attributed row without
    skipping the mark. So the Timeline asks this join for two raw kernels where the capture
    holds one device work, and the join can only answer `no free raw X event` (the raw trace
    wrote it once) or `ambiguous` (it wrote it twice and no joined field separates them).
    Both read as a defect of this join unless the mark is named here, where it is in scope.

    Diagnostic text only. Skipping the row instead would drop a Timeline event that
    `validate-report.mjs` still counts, and its per-event binding and 100% coverage
    assertions are hard; the fix belongs to the loop that emitted the event.
    """
    if duplicate_of is None:
        return None
    return (
        f"this attribution row is marked duplicate_of={duplicate_of}: msprof recorded one "
        "device work twice and emit_ui_facts.py's timeline loop emits an event per "
        "attributed row without skipping duplicate_of, so the Timeline asks for more raw "
        "kernels than that device work has; the fix belongs in that loop, not in this join"
    )


def no_match_reason(
    op_name,
    start,
    duration,
    rejected,
    near,
    candidates=(),
    contenders=(),
    duplicate_of=None,
):
    """Say every reason the join left this event without a raw kernel it may take.

    The mismatch statement leads because it is always true; the rest follow only when there
    is something to add, and each answers a different question:

    * `duplicate_of` -- the attribution row is a proven re-recording of another row, which is
      the one cause of this failure that the data already names. It follows the mismatch
      statement and precedes the field-level detail, because it changes what the reader does
      next: the other clauses describe the symptom, this one the origin.
    * `candidates` -- matching kernels do exist, but in a maximum one-to-one assignment
      every one of them is already held by another Timeline event (`contenders`), so the
      capture is one kernel short of a cover. That is all this clause may claim: the
      assignment being maximum is what proves no reshuffle frees one, and it does *not*
      prove those events could match nothing else. Saying "the only match of" would assert
      the stronger fact, and it is false whenever the holder itself had a choice -- three
      events over two raws reads as "one event is picky" instead of "the capture is short".
      This is not ambiguity either -- there is nothing to choose between -- and reporting it
      as such would send the reader looking for a duplicate that is not there.
    * `rejected` -- a same-name candidate whose `ts`/`dur` could not be read at all, named by
      raw index so several broken events stay distinguishable.
    * `near` -- the closest readable candidates that disagreed, with both deltas.

    Naming only one hides the others: "this candidate had no usable time" says nothing
    about the kernel that was 2 ns away, and neither says anything about the kernel another
    event already holds.
    """
    parts = [
        f"no free raw X event named {op_name!r} matching ts={start}, dur={duration}"
    ]
    clause = duplicate_of_clause(duplicate_of)
    if clause:
        parts.append(clause)
    if candidates:
        parts.append(
            f"indices {sorted(candidates)} do match but are already taken by Timeline "
            f"op_index {sorted(contenders)}, and no reassignment frees them, so no "
            "one-to-one assignment covers every event"
        )
    if rejected:
        parts.append(
            "invalid raw matching fields: "
            + "; ".join(f"#{index} {message}" for index, message in rejected)
        )
    if near:
        parts.append(
            "closest unmatched: "
            + ", ".join(
                f"#{index} dts={delta_start:.6f}us ddur={delta_duration:.6f}us"
                for index, delta_start, delta_duration in near
            )
        )
    return "; ".join(parts)


def ambiguous_reason(
    op_name, start, duration, candidates, free_raws, partners, duplicate_of=None
):
    """Why a bound event is still refused: its raw kernel is not forced.

    Every Timeline event has a raw kernel and no two share one, so the only question left is
    whether that assignment is the sole one. It is not, in two distinguishable ways:

    * `free_raws` -- a candidate nobody claimed, so this event could take it and leave its
      own raw unused;
    * `partners` -- an exchange cycle, where this event could take a partner's raw and the
      partners shift along to close the loop.

    Both are reported with the candidate list because the fix differs: a free duplicate is
    usually the same device work written twice into `trace_view.json`, while a cycle means
    several kernels genuinely agree on all three joined fields and the capture needs a
    stronger key. Guessing here would print `confidence: high` over a binding that could be
    swapped with another without any evidence preferring one.

    `duplicate_of` turns "usually" into "provably" for the first of those: the attribution
    row already says this event is a re-recorded collective, so the reason names it instead
    of leaving the reader to infer it from two identical index lists.
    """
    parts = [
        f"ambiguous raw X event match for name={op_name!r}, ts={start}, dur={duration}: "
        f"indices {sorted(candidates)}"
    ]
    clause = duplicate_of_clause(duplicate_of)
    if clause:
        parts.append(clause)
    if free_raws:
        parts.append(
            f"indices {sorted(free_raws)} are claimed by no Timeline event, so binding "
            "either is a valid one-to-one assignment"
        )
    if partners:
        parts.append(
            f"interchangeable with Timeline op_index {partners} under the same "
            "(name, ts, dur), so more than one one-to-one assignment covers every event"
        )
    return "; ".join(parts)


def maximum_one_to_one(order, adjacency):
    """The largest set of (event, raw index) pairs sharing no event and no raw index.

    Breadth-first augmenting paths (Kuhn's method), written iteratively on purpose: a
    representative step can hold tens of thousands of kernels, and a recursive augmentation
    spends one interpreter frame per hop of the path it flips.

    The scan follows `order`, and each event's candidates ascend, so the matching is a
    function of the graph alone. Callers pass a canonical `order` (sorted by `op_index`),
    never the order the Timeline file listed its events in.
    """
    match_of_event = {}
    match_of_raw = {}
    for start in order:
        previous_event_of_raw = {}
        reached_events = {start}
        reached_raws = set()
        queue = deque([start])
        free_raw = None
        while queue and free_raw is None:
            event_key = queue.popleft()
            for raw_index in adjacency[event_key]:
                if raw_index in reached_raws:
                    continue
                reached_raws.add(raw_index)
                previous_event_of_raw[raw_index] = event_key
                owner = match_of_raw.get(raw_index)
                if owner is None:
                    free_raw = raw_index
                    break
                if owner not in reached_events:
                    reached_events.add(owner)
                    queue.append(owner)
        if free_raw is None:
            continue
        # Flip the path just found: every event on it takes the raw one hop ahead of it, and
        # the free raw at the far end absorbs the last one, so the matching grows by one.
        raw_index = free_raw
        while True:
            event_key = previous_event_of_raw[raw_index]
            displaced = match_of_event.get(event_key)
            match_of_event[event_key] = raw_index
            match_of_raw[raw_index] = event_key
            if displaced is None:
                break
            raw_index = displaced
    return match_of_event, match_of_raw


def interchangeable_events(order, adjacency, match_of_event, match_of_raw, op_index_of):
    """Events whose raw assignment is not forced, mapped to the alternative each one has.

    Only meaningful once the matching covers every Timeline event; the question then is not
    "can this event be bound" but "is this the only way to bind them all". Two things break
    uniqueness: a candidate nobody claimed (this event could take it and leave its own raw
    unused), or an exchange cycle (u takes v's raw, v takes w's, and so on back to u).

    Cycle members are found by peeling, not by hunting for cycles: an event with no outgoing
    exchange edge cannot sit on one, nor can one with no incoming edge, and deleting such an
    event cannot make a cycle appear, so what survives the peel is exactly the set of events
    on some cycle. An event that merely points into a cycle is left out -- its own raw is
    still forced -- which keeps a report from blaming every event upstream of one duplicate.

    `op_index_of` maps an internal event key to the `op_index` a reader can look up, so the
    returned partners are named the way the rest of the diagnostics name things.
    """
    alternatives = {}
    outgoing = defaultdict(set)
    incoming = defaultdict(set)
    for event_key in order:
        own_raw = match_of_event[event_key]
        free_raws = []
        for raw_index in adjacency[event_key]:
            if raw_index == own_raw:
                continue
            owner = match_of_raw.get(raw_index)
            if owner is None:
                free_raws.append(raw_index)
            else:
                outgoing[event_key].add(owner)
                incoming[owner].add(event_key)
        if free_raws:
            alternatives[event_key] = {"free_raws": free_raws, "partners": []}

    out_edges = {key: set(outgoing.get(key, ())) for key in order}
    in_edges = {key: set(incoming.get(key, ())) for key in order}
    alive = set(order)
    queue = deque(key for key in order if not out_edges[key] or not in_edges[key])
    while queue:
        event_key = queue.popleft()
        if event_key not in alive:
            continue
        alive.discard(event_key)
        for source in in_edges[event_key]:
            if source in alive:
                out_edges[source].discard(event_key)
                if not out_edges[source]:
                    queue.append(source)
        for target in out_edges[event_key]:
            if target in alive:
                in_edges[target].discard(event_key)
                if not in_edges[target]:
                    queue.append(target)
    for event_key in alive:
        entry = alternatives.setdefault(event_key, {"free_raws": [], "partners": []})
        entry["partners"] = sorted(
            op_index_of[peer] for peer in out_edges[event_key] if peer in alive
        )
    return alternatives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--enrich-trace",
        metavar="PATH",
        help="write a copy of the trace with structure facts added to each "
        "joined X event's args. The repeated-layer pager derives its "
        "per-layer heat from args.layer_index, so without this the dots "
        "stay uncolored even though the layers ran.",
    )
    parser.add_argument(
        "--time-tolerance-us",
        metavar="US",
        type=positive_float,
        default=DEFAULT_TIME_MATCH_TOLERANCE_US,
        help="absolute slack, in microseconds, allowed between the two "
        "exports' start time and duration. Default "
        f"{DEFAULT_TIME_MATCH_TOLERANCE_US:g} us. Raise it only when a "
        "capture is known to disagree by more; widening it re-admits "
        "the ambiguity this join exists to avoid.",
    )
    args = parser.parse_args()
    tolerance = args.time_tolerance_us

    timeline = load(args.timeline)
    attribution = load(args.attribution)
    raw = load(args.trace)
    raw_events = raw if isinstance(raw, list) else raw.get("traceEvents") or []

    rows_by_op = {int(row["op_index"]): row for row in attribution["rows"]}

    by_name, by_bucket = index_raw_events(raw_events, tolerance)

    # Pass 1 -- validate every Timeline event and collect its candidates. Nothing is claimed
    # here. Claiming while scanning is what made the outcome depend on the order the file
    # happened to list its events in, so exclusion is left entirely to the matcher below: no
    # event sees another event's choices, and the candidate graph is a function of the data.
    unresolved = []
    pending = []
    for position, event in enumerate(timeline.get("events") or []):
        op_index = int(event["op_index"])
        row = rows_by_op.get(op_index)
        if row is None:
            unresolved.append((position, op_index, "no attribution row"))
            continue
        # Both sides of the join must carry a usable time: the Timeline event's `ts_us`
        # (which emit_ui_facts derives from the attribution row's `start_time_us`) and the
        # row's `duration_us`. Neither may be defaulted, or the match below is not exact.
        try:
            start = required_time(event.get("ts_us"), "start time")
            duration = required_time(row.get("duration_us"), "duration")
        except ValueError as error:
            unresolved.append((position, op_index, str(error)))
            continue
        candidates = candidate_raw_events(
            by_bucket, row.get("op_name"), start, duration, tolerance
        )
        pending.append(
            {
                "position": position,
                "op_index": op_index,
                "event": event,
                "row": row,
                "start": start,
                "duration": duration,
                "candidates": candidates,
            }
        )

    # Pass 2 -- one global assignment for the whole Timeline, taken in a canonical order.
    # Sorting by `op_index` (then `event_id`, then position, so equal op indices still have
    # one deterministic answer) is what makes the run reproducible: the same events arriving
    # in a different array order give the same matching, the same failures and the same
    # reasons. A correct matcher alone is not enough -- it still has to name the same victim.
    order = sorted(
        range(len(pending)),
        key=lambda key: (
            pending[key]["op_index"],
            str(pending[key]["event"].get("event_id")),
            key,
        ),
    )
    adjacency = {key: pending[key]["candidates"] for key in range(len(pending))}
    op_index_of = {key: pending[key]["op_index"] for key in range(len(pending))}
    match_of_event, match_of_raw = maximum_one_to_one(order, adjacency)
    # Uniqueness only means something once every event is matched; a short matching is
    # already a failure and gets reported as one, so there is nothing to check for cycles on.
    ambiguous = (
        interchangeable_events(
            order, adjacency, match_of_event, match_of_raw, op_index_of
        )
        if len(match_of_event) == len(pending)
        else {}
    )

    for key in order:
        item = pending[key]
        if key in ambiguous:
            alternative = ambiguous[key]
            unresolved.append(
                (
                    item["position"],
                    item["op_index"],
                    ambiguous_reason(
                        item["row"].get("op_name"),
                        item["start"],
                        item["duration"],
                        item["candidates"],
                        alternative["free_raws"],
                        alternative["partners"],
                        item["row"].get("duplicate_of"),
                    ),
                )
            )
            continue
        if key in match_of_event:
            continue
        # Unmatched, but not because nothing agreed: the matching is maximum, so every
        # candidate this event had is held by another event and no augmenting path is left
        # to free one. `contenders` therefore names who holds them right now, not who could
        # hold nothing else -- the holder may itself have had several candidates, and the
        # reason text must not claim otherwise (see `no_match_reason`).
        contenders = {
            op_index_of[match_of_raw[raw_index]]
            for raw_index in item["candidates"]
            if raw_index in match_of_raw
        }
        # `rejected` and `near` are gathered here rather than in pass 1: both only ever reach a
        # failure message, and computing them for every event means one full same-name scan per
        # event on a path that prints nothing at all. This is the one place the quadratic scan
        # still runs, and it runs once per event that actually failed.
        _candidates, rejected, near = matching_raw_events(
            raw_events,
            by_name,
            set(),
            item["row"].get("op_name"),
            item["start"],
            item["duration"],
            tolerance,
        )
        unresolved.append(
            (
                item["position"],
                item["op_index"],
                no_match_reason(
                    item["row"].get("op_name"),
                    item["start"],
                    item["duration"],
                    rejected,
                    near,
                    item["candidates"],
                    contenders,
                    item["row"].get("duplicate_of"),
                ),
            )
        )

    # Bindings come out in the order the Timeline listed its events, which is what every
    # downstream consumer has always read; only the decision above is order-independent.
    enrich_by_raw_index = {}
    bindings = []
    for key in range(len(pending)):
        if key not in match_of_event:
            continue
        item = pending[key]
        event = item["event"]
        row = item["row"]
        pick = match_of_event[key]
        enrich_by_raw_index[pick] = {
            "layer_index": event.get("layer_index"),
            "owner_node_id": event["owner_node_id"],
            "submodule": event.get("submodule"),
            "op_index": item["op_index"],
            "op_type": row.get("op_type"),
        }
        bindings.append(
            {
                "trace_event_id": event["event_id"],
                "raw_source_event_index": pick,
                "timeline_event_id": event["event_id"],
                "op_index": item["op_index"],
                "node_id": event["owner_node_id"],
                "instance_id": event.get("instance_index"),
                "structure_instance_node_id": event.get("structure_instance_node_id"),
                "submodule": event.get("submodule"),
                "relation": "direct_kernel_owner",
                "mapping_method": row.get("attribution_evidence")
                or "declared_op_indices",
                "confidence": "high",
            }
        )

    if unresolved:
        # Every case is printed, not just the first ten. One root cause (a collective that
        # the CSV wrote twice) fails in pairs across a whole capture, so a truncated list
        # reads as "ten unrelated problems" instead of "one repeated problem", and the cases
        # beyond the cut are the ones that would have shown the pattern.
        #
        # Sorted by op_index rather than emitted in pass order, so the listing is a function
        # of the capture and not of the order the Timeline file listed its events in. Two
        # runs over the same data must be diffable against each other.
        unresolved.sort(key=lambda entry: (entry[1], entry[0]))
        for _position, op_index, reason in unresolved:
            print(f"UNRESOLVED op_index={op_index}: {reason}")
        sidecar = args.out + ".unresolved.json"
        os.makedirs(os.path.dirname(os.path.abspath(sidecar)), exist_ok=True)
        with open(sidecar, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": 1,
                    "unresolved_count": len(unresolved),
                    "unresolved": [
                        {"op_index": op_index, "reason": reason}
                        for _position, op_index, reason in unresolved
                    ],
                },
                handle,
                ensure_ascii=False,
                indent=1,
            )
            handle.write("\n")
        # The sidecar path is named here rather than only in the stdout listing above:
        # run_pipeline.py keeps just the last 800 characters of this failure, which on a
        # long capture is the tail of the UNRESOLVED block, so the pointer to the full
        # machine-readable list has to travel with the exit message.
        raise SystemExit(
            f"{len(unresolved)} Timeline event(s) could not be bound; "
            f"a binding must not be invented. Full list: {sidecar}"
        )

    output = {
        "schema_version": 1,
        "contract": "structure_tree_to_raw_traceview_v1",
        "model_id": timeline["model_id"],
        "report_id": timeline["report_id"],
        "representative_step": timeline.get("representative_step"),
        "sources": {
            "timeline": os.path.basename(args.timeline),
            "raw_trace": os.path.basename(args.trace),
            "attribution": os.path.basename(args.attribution),
        },
        "bindings": bindings,
        "summary": {
            "timeline_events": len(timeline.get("events") or []),
            "bound_events": len(bindings),
            "direct_events": len(bindings),
            "propagated_events": 0,
            "coverage_pct": round(
                100.0 * len(bindings) / max(1, len(timeline.get("events") or [])), 4
            ),
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(f"WROTE {args.out}")
    print(
        f"  bound {len(bindings)}/{len(timeline.get('events') or [])} "
        f"({output['summary']['coverage_pct']}%)"
    )

    if args.enrich_trace:
        # Copy the structure facts into each joined event's `args`, leaving every standard lane
        # field untouched so Chrome-trace viewers still read it. Only `args` gains keys.
        enriched = 0
        with_layer = 0
        for raw_index, facts in enrich_by_raw_index.items():
            event = raw_events[raw_index]
            merged = dict(event.get("args") or {})
            for key, value in facts.items():
                if value is not None:
                    merged[key] = value
            event["args"] = merged
            enriched += 1
            if facts.get("layer_index") is not None:
                with_layer += 1
        payload = (
            raw_events if isinstance(raw, list) else {**raw, "traceEvents": raw_events}
        )
        os.makedirs(os.path.dirname(os.path.abspath(args.enrich_trace)), exist_ok=True)
        with open(args.enrich_trace, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        print(f"WROTE {args.enrich_trace}")
        print(f"  enriched {enriched} X events, {with_layer} carry layer_index")
        if not with_layer:
            print(
                "  NOTE no event carries layer_index: the per-layer pager heat will be "
                "uniform. Check that trace_instances declare model_layer_index."
            )


if __name__ == "__main__":
    main()
