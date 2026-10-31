//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = await readFile(
  new URL("../assets/report-template/trace-view.js", import.meta.url),
  "utf8",
);
const sandbox = { window: {} };
vm.runInNewContext(source, sandbox, { filename: "trace-view.js" });
const traceView = sandbox.window.DeepSeekTraceView;

// A trace with this many duration events overflows the argument list of
// Math.min(...spread), so it is the smallest scale that pins the single-pass bounds.
const eventCount = 150_000;

function buildEvents() {
  const events = Array.from({ length: eventCount }, (_, index) => ({
    ph: "X",
    pid: 1,
    tid: 1,
    ts: index,
    dur: 1,
    name: "kernel",
  }));
  // Rotate the array so the smallest ts and the largest end land in the middle: an
  // implementation that only reads one end of the array cannot pass the bounds below.
  const rotation = 7;
  const rotated = events.slice(rotation).concat(events.slice(0, rotation));
  const first = rotated[0];
  const last = rotated[eventCount - 1];
  assert.notEqual(first.ts, 0);
  assert.notEqual(first.ts + first.dur, eventCount);
  assert.notEqual(last.ts, 0);
  assert.notEqual(last.ts + last.dur, eventCount);
  return rotated;
}

const parsed = traceView.parseTrace({ traceEvents: buildEvents() });
assert.equal(parsed.durations.length, eventCount);
assert.equal(parsed.minTs, 0);
assert.equal(parsed.maxTs, eventCount);
console.log(`OK   TraceView parses ${eventCount} duration events and returns correct bounds`);

// The rotated fixture keeps both extrema in the middle, so it cannot see a pass that
// skips the ends of the array. A short ascending run puts them at the two ends instead.
const ascending = traceView.parseTrace({
  traceEvents: [
    { ph: "X", pid: 1, tid: 1, ts: 10, dur: 5, name: "a" },
    { ph: "X", pid: 1, tid: 1, ts: 20, dur: 5, name: "b" },
    { ph: "X", pid: 1, tid: 1, ts: 30, dur: 5, name: "c" },
  ],
});
assert.equal(ascending.durations.length, 3);
assert.equal(ascending.minTs, 10);
assert.equal(ascending.maxTs, 35);
console.log("OK   TraceView keeps the first and the last duration event in its bounds");

// Empty input keeps the boundary values it had before the single-pass rewrite, and the
// render entry point still refuses such a trace before it consumes those values.
const empty = traceView.parseTrace({ traceEvents: [] });
assert.equal(empty.durations.length, 0);
assert.equal(empty.minTs, Infinity);
assert.equal(empty.maxTs, -Infinity);
assert.throws(
  () => traceView.createTraceView({}, { traceEvents: [] }, {}),
  /no duration events/,
);
console.log("OK   empty trace keeps its boundary values and is refused by createTraceView");
