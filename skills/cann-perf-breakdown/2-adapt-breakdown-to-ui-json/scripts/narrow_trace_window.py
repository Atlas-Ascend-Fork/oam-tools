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
"""Narrow a raw Chrome-trace to the representative step's time window.

A full msprof capture covers the whole run (here ~55 s / 5.7 M events / 1 GB) while the
report only ever renders the representative step (~28 ms). Stage 3 must inline the trace
into one JS string via `JSON.stringify`, so an unnarrowed capture fails outright with
Node's `RangeError: Invalid string length` -- and even if it fit, shipping a gigabyte of
out-of-window events into a standalone HTML would be pointless.

The window comes from raw_ops.json (the representative step's own kernels), never from a
hardcoded constant, so this stays correct for any capture and any selected step.

Kept: every metadata event (`ph: M`, the process/thread names the lanes are labelled from),
and every timed event overlapping the window. Flow events (`s`/`t`/`f`) are kept
as complete chains, keyed by category, name and id. Events without an id are
discarded and counted in the JSON summary.
"""
import argparse
import json


def event_start(event):
    try:
        return float(event.get("ts"))
    except (TypeError, ValueError):
        return None


def flow_key(event):
    identity = event.get("id")
    if identity is None:
        return None
    return event.get("cat"), event.get("name"), identity


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, help="raw Chrome-trace JSON")
    ap.add_argument("--raw-ops", required=True, help="raw_ops.json of the representative step")
    ap.add_argument("--output", required=True)
    ap.add_argument("--pad-us", type=float, default=2000.0,
                    help="context kept on each side, so a counter sampled just outside the "
                         "step still renders at the window edge")
    args = ap.parse_args()

    with open(args.raw_ops, encoding="utf-8") as fh:
        ops = json.load(fh)["operators"]
    start = min(o["start_time_us"] for o in ops) - args.pad_us
    end = max(o["start_time_us"] + o["duration_us"] for o in ops) + args.pad_us

    with open(args.trace, encoding="utf-8") as fh:
        events = json.load(fh)

    # Pass 1: complete flow keys touching the window at any phase.
    live_flow_ids = set()
    for event in events:
        if event.get("ph") in ("s", "t", "f"):
            ts = event_start(event)
            key = flow_key(event)
            if key is not None and ts is not None and start <= ts <= end:
                live_flow_ids.add(key)

    kept, meta, flows = [], 0, 0
    for event in events:
        phase = event.get("ph")
        if phase == "M":
            kept.append(event)
            meta += 1
            continue
        if phase in ("s", "t", "f"):
            if flow_key(event) is not None and flow_key(event) in live_flow_ids:
                kept.append(event)
                flows += 1
            continue
        ts = event_start(event)
        if ts is None:
            continue
        # `X` carries a duration, so it counts as in-window if it overlaps at all.
        finish = ts + float(event.get("dur") or 0)
        if finish >= start and ts <= end:
            kept.append(event)

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(kept, fh)

    print(json.dumps({
        "output": args.output,
        "window_us": [start, end],
        "events_in": len(events),
        "events_kept": len(kept),
        "metadata_kept": meta,
        "flow_events_kept": flows,
        "flow_events_missing_id": sum(1 for e in events
                                      if e.get("ph") in ("s", "t", "f")
                                      and flow_key(e) is None),
    }, indent=1))


if __name__ == "__main__":
    main()
