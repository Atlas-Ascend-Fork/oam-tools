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
"""Drive the real dataflow CLI over `async` spellings and loop `else:` clauses.

Both families were silent holes of exactly the kind issue #330 is about: submodule
calls that vanished while the report still claimed `unsupported` was empty.

* `async for` / `async with` / `async def forward`. `await` says *when* a call may
  suspend, not whether it happens, so the async spellings must classify like their sync
  ones. They used to be missed outright -- `extract_file` only collected
  `ast.FunctionDef`, so an `async def forward` matched no method and the file reported
  `module_count: 0` -- or sent to the unrecognised-statement fallback, which saw no
  `self.` callee in `x = await layer(x)` and dropped the whole repeated block.
* a loop's `else:` clause, which `_loop` skipped along with everything that was not
  `body`: `for i in range(3): pass` + `else: x = self.fallback(x)` produced
  `calls=[]`, `unsupported=[]`, `blocking_unsupported=0`.

Every case here runs the complete command-line entry point on a real temporary source
file and reads the JSON report back; nothing is imported, stubbed or simulated.
"""

import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "skills/cann-perf-breakdown/1-perf-breakdown/scripts/extract_dataflow.py"
)
requires_try_star = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="except* source requires Python 3.11+"
)


def load_script_module():
    spec = importlib.util.spec_from_file_location("extract_dataflow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(tmp_path, source):
    """Run the CLI on a whole source file and return the parsed report."""
    path = tmp_path / "model.py"
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def report_for(tmp_path, body, parameters="x", keyword="def"):
    """Run the CLI on `class Model.<keyword> forward` whose body is `body`."""
    return run_cli(
        tmp_path,
        f"class Model:\n    {keyword} forward(self, {parameters}):\n"
        + textwrap.indent(textwrap.dedent(body).strip() + "\n", "        "),
    )


def single(report):
    return report["modules"][0]


def blocking(report):
    """The blocking entries of the one module under test."""
    return [
        entry
        for entry in single(report)["unsupported"]
        if entry["severity"] in ("data_dependent", "unparsable")
    ]


def symbols(module):
    return [call["symbol"] for call in module["calls"]]


def loop_ids(module):
    """The loop each call was tagged with, in call order; None means main path."""
    return [
        call["loop"]["loop_id"] if "loop" in call else None for call in module["calls"]
    ]


# --------------------------------------------------------------------------------------
# `async def forward` is a forward at all
# --------------------------------------------------------------------------------------


def test_async_forward_is_scanned_like_a_sync_one(tmp_path):
    """An `async def forward` used to match no method, so the file looked model-free.

    `module_count: 0` is indistinguishable from "no model in this file", so every call
    in the method was invisible to the downstream gate rather than reported.
    """
    report = report_for(
        tmp_path,
        """
        x = await self.pre(x)
        x = self.post(x)
        return x
        """,
        keyword="async def",
    )
    assert report["module_count"] == 1
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.pre", "self.post"]
    # `await` is transparent to the data dependency, not just to the call itself.
    assert module["calls"][1]["reads"] == [{"variable": "x", "from_call": 0}]
    assert module["returns"] == [{"variable": "x", "from_call": 1}]


@pytest.mark.parametrize("spelling", ["await self.head(x)", "self.head(x)"])
def test_awaited_call_binds_exactly_like_the_sync_call(tmp_path, spelling):
    """`x = await self.head(x)` writes `x` from the same call as the unawaited form."""
    report = report_for(tmp_path, f"x = {spelling}\nreturn x", keyword="async def")
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.head"]
    assert module["returns"] == [{"variable": "x", "from_call": 0}]


def test_bare_await_expression_statement_is_not_dropped(tmp_path):
    report = report_for(
        tmp_path,
        """
        await self.side(x)
        x = self.pre(x)
        return x
        """,
        keyword="async def",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.side", "self.pre"]


def test_return_await_is_recorded_as_the_returned_call(tmp_path):
    report = report_for(
        tmp_path,
        """
        x = self.pre(x)
        return await self.head(x)
        """,
        keyword="async def",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert symbols(module) == ["self.pre", "self.head"]
    assert module["returns"] == [{"variable": None, "from_call": 1}]


def test_nested_awaits_record_each_call_once(tmp_path):
    """Seeing through `await` must not double-count the inner call."""
    report = report_for(
        tmp_path,
        """
        x = await self.route(await self.pre(x))
        return x
        """,
        keyword="async def",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert symbols(module) == ["self.pre", "self.route"]
    assert module["calls"][1]["reads"] == [
        {"variable": "__call_0_result", "from_call": 0}
    ]
    assert module["returns"] == [{"variable": "x", "from_call": 1}]


# --------------------------------------------------------------------------------------
# `async for` is the same repeated block as `for`
# --------------------------------------------------------------------------------------


def test_async_for_over_submodules_is_the_repeated_block(tmp_path):
    """The decoder shape, spelled asynchronously: `async for layer in self.layers`.

    The loop calls the *loop variable* through `await`, so a callee test that stops at
    the `Await` node sees no call at all and the whole repeated block disappeared while
    `unsupported` stayed empty.
    """
    report = report_for(
        tmp_path,
        """
        async for layer in self.layers:
            x = await layer(x)
        return x
        """,
        keyword="async def",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer"]
    assert loop_ids(module) == [0]
    (loop,) = module["loops"]
    assert loop["construct"] == "AsyncFor"
    assert loop["iterates_over"] == "self.layers"
    assert loop["call_ids"] == [0]


@pytest.mark.parametrize(
    "spelling,construct", [("for", "For"), ("async for", "AsyncFor")]
)
def test_async_for_and_for_classify_identically(tmp_path, spelling, construct):
    """The `self.<name>` shape fujun19 used as the control case, in both spellings.

    Before, only the sync one reached `_control_flow`; the async one fell through to
    `_unrecognized` and was reported as an unparsable construct instead of reduced as
    the loop it is.
    """
    report = report_for(
        tmp_path,
        f"{spelling} item in self.items:\n    x = self.proc(x)\nreturn x",
        keyword="async def",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.proc"]
    (loop,) = module["loops"]
    assert loop["construct"] == construct
    assert loop["iterates_over"] == "self.items"
    assert loop["call_ids"] == [0]


def test_async_for_in_a_sync_method_is_still_classified(tmp_path):
    """The reducer works on the parse tree, so the enclosing method kind cannot matter.

    This is the exact source fujun19 measured as silently dropped. `compile()` rejects
    an `async for` inside a plain `def`, but `ast.parse()` -- which is all this script
    does -- accepts it, so the shape is reachable by the CLI and must be classified
    rather than dropped.
    """
    report = report_for(
        tmp_path,
        """
        async for layer in self.layers:
            x = await layer(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer"]
    (loop,) = module["loops"]
    assert loop["construct"] == "AsyncFor"


def test_async_for_nested_in_a_for_does_not_make_it_look_call_free(tmp_path):
    """`_nested_loop_targets` must bind `async for` targets too.

    The outer loop only ever calls `layer(...)`, bound by the inner `async for`. Without
    that binding the outer loop looks call-free, takes the call-free path, and the entire
    body vanishes -- the same hole one level up.
    """
    report = report_for(
        tmp_path,
        """
        for block in self.blocks:
            async for layer in block.layers:
                x = layer(x)
        return x
        """,
        keyword="async def",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer"]
    (loop,) = module["loops"]
    assert loop["construct"] == "AsyncFor"
    assert loop["iterates_over"] == "block.layers"


@pytest.mark.parametrize(
    "spelling,construct", [("with", "With"), ("async with", "AsyncWith")]
)
def test_async_with_is_reported_like_with(tmp_path, spelling, construct):
    """`async with` opens its body like `with`, so it reports like `with` -- one shape.

    Unlike `async for` this stays blocking: a context manager may run its body zero or
    more times, which is a runtime fact the graph must not guess. What changed is only
    *which* code path reports it, so both spellings now share one wording.
    """
    report = report_for(
        tmp_path,
        f"{spelling} self.ctx as c:\n    x = self.proc(x)\nreturn x",
        keyword="async def",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 1
    (entry,) = module["unsupported"]
    assert entry["construct"] == construct
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == ["self.proc"]
    assert module["calls"] == []
    assert entry["reason"] == (
        f"{construct} 包含 submodule 调用，此 reducer 无法确定其执行语义；"
        f"需要显式 deviation 声明"
    )


def test_async_constructs_are_in_the_control_flow_node_set():
    """The set is the dispatch gate; an async node missing from it is a silent hole."""
    module = load_script_module()
    nodes = module.CONTROL_FLOW_NODES
    names = {node.__name__ for node in nodes}
    assert all(isinstance(node, type) for node in nodes)
    assert len(set(nodes)) == len(nodes)
    assert {"AsyncFor", "AsyncWith"} <= names
    # Every "does this loop bind a target" test branches on one tuple, so the async
    # form cannot drift away from the sync one.
    assert set(module.LOOP_NODES) == {ast.For, ast.AsyncFor}
    assert set(module.ITERATIVE_NODES) == set(module.LOOP_NODES) | {ast.While}


def test_unrecognised_fallback_no_longer_claims_async_for_as_an_example():
    """The docstring's example list is a claim, and one entry was measured false.

    It named `an async for over submodules` as a statement the fallback reports. It did
    not report it: the loop variable is the callee, so no `self.` was ever seen and the
    statement vanished. The remaining examples are both measured.
    """
    text = load_script_module().ForwardGraph._unrecognized.__doc__
    # Compare with markup and line wrapping stripped, so the claim is tested and not
    # the exact way it happens to be spelled or broken across lines.
    plain = " ".join(text.replace("`", " ").split())
    examples = plain.split("Both examples")[0]
    assert "an async for over submodules" not in examples
    assert "a raise or assert carrying a submodule call" in examples
    # And the docstring says where async constructs are classified instead.
    assert "_control_flow" in plain


# --------------------------------------------------------------------------------------
# a loop's `else:` clause
# --------------------------------------------------------------------------------------


def test_break_free_else_lands_on_the_main_path(tmp_path):
    """No `break` in the body means the clause always runs, so it is main-path code.

    It must not be tagged with the loop's id: the loop body runs once per iteration,
    the clause runs once in total.
    """
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            x = layer(x)
        else:
            x = self.fallback(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer", "self.fallback"]
    assert loop_ids(module) == [0, None]
    (loop,) = module["loops"]
    assert loop["call_ids"] == [0]
    assert module["returns"] == [{"variable": "x", "from_call": 1}]


def test_call_only_in_a_break_free_else_is_not_dropped(tmp_path):
    """The measured hole: a submodule call with nothing reported about it at all."""
    report = report_for(
        tmp_path,
        """
        for i in range(3):
            pass
        else:
            x = self.fallback(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.fallback"]
    assert loop_ids(module) == [None]
    # The body calls nothing, so there is no repeated block to book.
    assert module["loops"] == []
    assert module["returns"] == [{"variable": "x", "from_call": 0}]


def test_loop_variable_is_still_bound_in_a_break_free_else(tmp_path):
    """The target survives the loop, so `layer(x)` in the clause is still a call."""
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            pass
        else:
            x = layer(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer"]
    assert loop_ids(module) == [None]


def test_break_free_else_writing_a_residual_is_not_a_guess(tmp_path):
    """An *unreachable-state* None write is rejected; here the state is known.

    The clause always runs, so the residual really is reset on the main path and the
    reducer may carry it instead of reporting a blocker.
    """
    report = report_for(
        tmp_path,
        """
        residual = None
        for layer in self.layers:
            x = layer(x)
        else:
            residual = None
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer"]
    assert loop_ids(module) == [0]


@pytest.mark.parametrize(
    "keyword,body,construct,kept,clause_range",
    [
        (
            "def",
            """
            for layer in self.layers:
                x = layer(x)
                if self.limit:
                    break
            else:
                x = self.fallback(x)
            return x
            """,
            "ForElse",
            ["layer"],
            (8, 8),
        ),
        (
            "def",
            """
            while self.cond:
                x = self.step(x)
                if self.limit:
                    break
            else:
                x = self.fallback(x)
            return x
            """,
            "WhileElse",
            ["self.step"],
            (8, 8),
        ),
        (
            "async def",
            """
            async for layer in self.layers:
                x = await layer(x)
                if self.limit:
                    break
            else:
                x = await self.fallback(x)
            return x
            """,
            "AsyncForElse",
            ["layer"],
            (8, 8),
        ),
    ],
)
def test_else_after_a_breakable_loop_is_reported(
    tmp_path, keyword, body, construct, kept, clause_range
):
    """Whether the clause ran is a runtime fact, so report it instead of placing it.

    All three loop spellings have an `orelse`; handling only `for` would leave the
    async one silently dropped again.
    """
    report = report_for(tmp_path, body, keyword=keyword)
    module = single(report)
    assert report["blocking_unsupported"] == 1
    (entry,) = blocking(report)
    assert entry["construct"] == construct
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == ["self.fallback"]
    assert [site["symbol"] for site in entry["call_sites"]] == ["self.fallback"]
    # The entry names the clause, not the loop: `lineno` is `clause[0].lineno` (8), not
    # `statement.lineno` (3). Both fields are the keys a declared deviation is matched on
    # downstream (D5 -> `_source_ref_covers`), so pointing at the loop would make the user
    # declare a range that does not identify the construct the report is about.
    assert (entry["lineno"], entry["end_lineno"]) == clause_range
    # The loop body itself is still extracted as the repeated block.
    assert symbols(module) == kept
    assert loop_ids(module) == [0]


def test_break_in_a_nested_loop_also_blocks_the_else(tmp_path):
    """Deliberately conservative: this `break` cannot exit the outer loop.

    Telling the two apart needs the control-flow analysis this reducer does not do, and
    over-reporting one blocking construct is the cheap direction -- the same trade the
    `_unrecognized` fallback makes.
    """
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            for i in range(3):
                if self.limit:
                    break
            x = layer(x)
        else:
            x = self.fallback(x)
        return x
        """,
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "ForElse"
    assert entry["call_symbols"] == ["self.fallback"]


def test_call_free_else_that_keeps_the_residual_none_is_not_a_guess(tmp_path):
    """Both arms agree the residual is None, so merging them is not a guess at all.

    This shape used to be reported once for the whole loop under the label `For`: the
    call-free path asked only "does anything here write ``None``", and it did. But the
    answer to the question that actually matters -- can a later fused call tell which
    topology the residual is in -- is no, it cannot be fooled here, because the residual
    was already None before the loop and the clause writes None again. Merging the two
    arms finds them in agreement and books nothing, which is strictly more accurate than
    the old blocker and matches what the same clause does after a loop that *does* call.
    """
    report = report_for(
        tmp_path,
        """
        residual = None
        for layer in self.layers:
            if self.limit:
                break
        else:
            residual = None
        return x
        """,
    )
    assert report["blocking_unsupported"] == 0
    assert single(report)["unsupported"] == []


def test_call_free_else_that_resets_a_bound_residual_reports_the_clause(tmp_path):
    """The rejection survives -- and now names the clause, not the loop.

    Here the residual really is a tensor before the loop, so whether the clause reset it to
    None is unknown and the merge cannot be represented. It escalates under the clause's own
    label and range, which is what the same clause reports when the loop body holds calls
    (`test_call_free_clause_escalation_keeps_the_clause_label_and_range`). Before the clause
    was reduced through the two-arm merge it was reported as `For` spanning the whole loop,
    so one source fact carried two different labels depending on the loop body -- and
    `construct` plus the line range are exactly what a declared deviation is matched on
    (D5 -> `_source_ref_covers`).
    """
    report = report_for(
        tmp_path,
        """
        residual = self.prep(x)
        for i in range(3):
            if self.limit:
                break
        else:
            residual = None
        return residual
        """,
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "ForElse"
    assert (entry["lineno"], entry["end_lineno"]) == (8, 8)
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == []
    assert entry["call_sites"] == []
    assert "condition" not in entry
    assert symbols(single(report)) == ["self.prep"]


def test_call_free_clause_after_a_calling_loop_is_reported_once_for_the_clause(
    tmp_path,
):
    """One source fact, one entry -- whatever the loop body happened to contain.

    The clause below holds no submodule call, so nothing can be placed; what it can still
    do is rebind the residual to ``None``. Reporting that per statement produced two
    `Assign` entries for one clause and made the count depend on whether the *body* called
    a submodule, while `construct` and the line range are exactly what a declared deviation
    is matched on (D5 -> `_source_ref_covers`). So the clause is reported once, under the
    same `*Else` label and the same range as a clause that does hold calls.
    """
    report = report_for(
        tmp_path,
        """
        residual = None
        for layer in self.layers:
            if self.limit:
                break
            x = layer(x)
        else:
            residual = None
            carry = None
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 1
    (entry,) = module["unsupported"]
    assert entry["construct"] == "ForElse"
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == []
    assert entry["call_sites"] == []
    # The clause spans lines 9-10; one entry for the pair, not one per `= None`.
    assert (entry["lineno"], entry["end_lineno"]) == (9, 10)
    # The loop body is unaffected: still booked as the repeated block.
    assert symbols(module) == ["layer"]
    assert loop_ids(module) == [0]


def test_break_free_else_with_a_conditional_call_still_sees_the_loop_variable(tmp_path):
    """The clause is reduced with the loop variables still in scope.

    `_loop_else` pushes the loop's targets for the duration of the clause, so `layer(x)`
    under `else:` is the submodule call it is everywhere else. Without that frame the
    conditional call is not recognised as a call at all, and it lands on the main path as
    an unconditional edge -- a `returns` with two writers for `x` instead of one, and
    nothing reported.
    """
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            x = layer(x)
        else:
            if self.flag:
                x = layer(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 1
    (entry,) = blocking(report)
    assert entry["construct"] == "If"
    assert entry["severity"] == "data_dependent"
    assert entry["condition"] == "self.flag"
    assert (entry["lineno"], entry["end_lineno"]) == (6, 7)
    assert entry["call_symbols"] == ["layer"]
    assert [site["lineno"] for site in entry["call_sites"]] == [7]
    # Only the loop body's call is placed; the conditional one is reported, not booked.
    assert symbols(module) == ["layer"]
    assert loop_ids(module) == [0]
    assert [loop["call_ids"] for loop in module["loops"]] == [[0]]
    assert module["returns"] == [{"variable": "x", "from_call": 0}]


def test_break_free_else_with_a_nested_loop_still_sees_the_loop_variable(tmp_path):
    """A `while` in a break-free clause is a repeated block of its own, not a hole.

    The clause always runs, so its nested loop is reduced in place and books its own
    `loop_id`. Without the pushed frame `layer(x)` inside the `while` looks call-free and
    the whole nested loop disappears: no second call, no second loop, and `returns` points
    back at the outer loop's call.
    """
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            x = layer(x)
        else:
            while self.cond:
                x = layer(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer", "layer"]
    assert loop_ids(module) == [0, 1]
    assert [
        (
            loop["loop_id"],
            loop["construct"],
            loop["lineno"],
            loop["iterates_over"],
            loop["call_ids"],
        )
        for loop in module["loops"]
    ] == [(0, "For", 3, "self.layers", [0]), (1, "While", 6, "self.cond", [1])]
    assert module["returns"] == [{"variable": "x", "from_call": 1}]


def test_break_free_else_with_a_nested_for_over_the_loop_variable(tmp_path):
    """Same frame, third spelling: `for sub in layer.subs:` inside the clause.

    The inner iterable is spelled with the *outer* loop variable, so recognising `sub(x)`
    as a submodule call needs the pushed frame twice over -- for the iterable's root and
    for the inner loop's own target.
    """
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            x = layer(x)
        else:
            for sub in layer.subs:
                x = sub(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer", "sub"]
    assert loop_ids(module) == [0, 1]
    assert [loop["iterates_over"] for loop in module["loops"]] == [
        "self.layers",
        "layer.subs",
    ]
    assert module["returns"] == [{"variable": "x", "from_call": 1}]


def test_loop_without_an_else_clause_is_unchanged(tmp_path):
    """Regression guard: the new clause handling must not touch the ordinary shape."""
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            x = layer(x)
        return x
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["layer"]
    assert loop_ids(module) == [0]
    assert [loop["call_ids"] for loop in module["loops"]] == [[0]]


def test_call_free_clause_that_rebinds_a_name_is_merged_not_dropped(tmp_path):
    """A clause with no call still rebinds, so the next read must name both producers.

    The clause holds no submodule call, so there is nothing to place -- but returning early
    left the pre-clause writer in place and the graph then claimed a producer the clause may
    have overwritten: `self.out` read `x` as `layer`'s output only, with `unsupported=[]` and
    `blocking_unsupported=0`, i.e. nothing anywhere said the clause had been dropped. That is
    the same lie as dropping the calls, and it disagreed with the break-free branch above,
    which reduces this very clause in place. Merging the clause against "the loop broke, so
    it never ran" records both producers instead of inventing a choice between them.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        for layer in self.layers:
            if self.limit:
                break
            x = layer(x)
        else:
            x = y
        return self.out(x)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.prep", "self.other", "layer", "self.out"]
    assert loop_ids(module) == [None, None, 0, None]
    # Both possible producers of `x`: `self.other` (the clause ran) and `layer` (it did not).
    assert module["calls"][3]["reads"] == [
        {"variable": "x", "from_call": 1},
        {"variable": "x", "from_call": 2},
    ]
    assert module["returns"] == [{"variable": None, "from_call": 3}]
    # Whether the loop broke is not the profile's choice, so no named variant is emitted,
    # and no `<merge>` node is invented for a clause that wrote no expression.
    assert report["config_gated_variants"] == 0
    assert module["variants"] == []
    assert module["merges"] == []


def test_call_free_clause_merges_like_the_same_rebinding_in_an_if(tmp_path):
    """The clause and the `if` that means the same thing must produce the same graph.

    `else: x = y` after a breakable loop and `if self.flag: x = y` are the same claim --
    maybe `x` was rebound to `y`, maybe not -- so one cannot name two producers while the
    other names one. This is the asymmetry the merge above removes, pinned as a pair so a
    future change to either path has to move both.
    """
    bodies = [
        """
        x = self.prep(x)
        y = self.other(x)
        for layer in self.layers:
            if self.limit:
                break
            x = layer(x)
        else:
            x = y
        return self.out(x)
        """,
        """
        x = self.prep(x)
        y = self.other(x)
        for layer in self.layers:
            if self.limit:
                break
            x = layer(x)
        if self.flag:
            x = y
        return self.out(x)
        """,
    ]
    # `report_for` rewrites the one source file under `tmp_path`, so the two shapes are
    # extracted one after the other from the same directory.
    reports = [report_for(tmp_path, body) for body in bodies]
    assert reports[0]["blocking_unsupported"] == reports[1]["blocking_unsupported"] == 0
    assert [single(r)["unsupported"] for r in reports] == [[], []]
    reads = [
        [call["reads"] for call in single(r)["calls"] if call["symbol"] == "self.out"]
        for r in reports
    ]
    assert reads[0] == reads[1]
    assert reads[0] == [
        [{"variable": "x", "from_call": 1}, {"variable": "x", "from_call": 2}]
    ]


@pytest.mark.parametrize(
    "keyword,body,clause_producer",
    [
        (
            "def",
            """
            x = self.prep(x)
            y = self.other(x)
            while self.cond:
                if self.limit:
                    break
                x = self.step(x)
            else:
                x = y
            return self.out(x)
            """,
            1,
        ),
        (
            "async def",
            """
            x = self.prep(x)
            y = self.other(x)
            async for layer in self.layers:
                if self.limit:
                    break
                x = await layer(x)
            else:
                x = y
            return self.out(x)
            """,
            1,
        ),
    ],
)
def test_call_free_clause_of_every_loop_spelling_merges(
    tmp_path, keyword, body, clause_producer
):
    """`while ... else:` and `async for ... else:` share `_loop_else`, so both must merge.

    Fixing only the `for` spelling would leave the same dropped rebind reachable through the
    other two, which is how the async shapes were missed in the first place.
    """
    report = report_for(tmp_path, body, keyword=keyword)
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert loop_ids(module) == [None, None, 0, None]
    reads = module["calls"][3]["reads"]
    assert {read["from_call"] for read in reads} == {clause_producer, 2}
    assert module["variants"] == []


def test_call_free_clause_escalation_keeps_the_clause_label_and_range(tmp_path):
    """The merge escalates against the *clause*, not the loop, and adds no `condition`.

    `_extract_variants` reports an unrepresentable merge against `statement` by default,
    which for a loop is `For` and the loop's whole range -- a different construct and a
    different line range than the clause-holds-a-call path reports for the same clause. Both
    fields are what a declared deviation is matched on (D5 -> `_source_ref_covers`), so the
    clause passes its own label and range down. There is also no selector expression to name
    (the clause is gated on "the loop was not broken"), so `condition` is omitted rather than
    recorded as null and D5 falls back to `construct`.
    """
    report = report_for(
        tmp_path,
        """
        residual = None
        for layer in self.layers:
            if self.limit:
                break
            x = layer(x)
        else:
            residual = None
            carry = None
        return x
        """,
    )
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "ForElse"
    assert (entry["lineno"], entry["end_lineno"]) == (9, 10)
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == []
    assert entry["call_sites"] == []
    assert "condition" not in entry


# --------------------------------------------------------------------------------------
# A call-free construct is reduced, not skipped -- the hole the loop `else:` clause was
# only the first instance of. `_call_free` asked one question ("does anything here write
# ``None``?") of constructs that differ in *execution semantics*, so a call-free loop,
# `with` and `try` all dropped every rebinding they held while the report still claimed
# `unsupported == []` and `blocking_unsupported == 0`. Nothing anywhere said they had been
# skipped, which is the same lie as dropping the calls.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("loop_head", ["for i in range(3)", "while self.cond"])
def test_call_free_loop_clause_merges_like_the_same_rebinding_in_an_if(
    tmp_path, loop_head
):
    """A call-free loop's `else:` clause means the same thing as an `if` with no `else`.

    The loop holds no submodule call at all here, so before this there was nothing to place
    and the whole statement -- clause included -- was skipped. But `else: x = y` after a
    breakable loop and `if self.flag: x = y` are the same claim: maybe `x` was rebound to
    `y`, maybe not. One cannot name two producers while the other names one, so the pair is
    pinned together and a future change to either path has to move both.
    """
    head = f"""
        x = self.prep(x)
        y = self.other(x)
        {loop_head}:
            if self.limit:
                break
    """
    bodies = [
        head
        + f"""
        {tail}
            x = y
        return self.out(x)
        """
        for tail in ("else:", "if self.flag:")
    ]
    # `report_for` rewrites the one source file under `tmp_path`, so the two shapes are
    # extracted one after the other from the same directory.
    reports = [report_for(tmp_path, body) for body in bodies]
    assert [r["blocking_unsupported"] for r in reports] == [0, 0]
    assert [single(r)["unsupported"] for r in reports] == [[], []]
    reads = [
        [call["reads"] for call in single(r)["calls"] if call["symbol"] == "self.out"]
        for r in reports
    ]
    assert reads[0] == reads[1]
    assert reads[0] == [
        [{"variable": "x", "from_call": 1}, {"variable": "x", "from_call": 0}]
    ]
    for report in reports:
        module = single(report)
        assert symbols(module) == ["self.prep", "self.other", "self.out"]
        # No named variant: whether the loop broke is not the profile's choice.
        assert report["config_gated_variants"] == 0
        assert module["variants"] == []
        assert module["merges"] == []


def test_call_free_loop_body_rebinding_is_not_dropped(tmp_path):
    """The body of a call-free loop rebinds too, so the next read must see it.

    `for i in range(3): x = y` holds no submodule call, so it was skipped whole and `self.out`
    read `x` as `self.prep`'s output -- a producer the loop body had already overwritten. The
    body belongs on the main path exactly as it does when the loop *does* call submodules.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        for i in range(3):
            x = y
        return self.out(x)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.prep", "self.other", "self.out"]
    assert module["calls"][2]["reads"] == [{"variable": "x", "from_call": 1}]
    # Still no repeated block to book: nothing inside was placed as a call.
    assert module["loops"] == []


@pytest.mark.parametrize(
    "keyword,spelling",
    [("def", "with self.ctx"), ("async def", "async with self.ctx")],
)
def test_call_free_with_body_reduces_like_a_plain_rebinding(
    tmp_path, keyword, spelling
):
    """A call-free `with` opens no alternative path, so its body reduces in place.

    Either `__enter__` succeeds and every statement in the body runs, or it raises and
    control leaves the construct -- there is no "the body maybe ran" to merge. Skipping it
    left the pre-`with` writer in place, so `self.out` named `self.prep` as `x`'s producer
    after `x = y` had already overwritten it. The equivalent bare assignment is the control
    group for this one: both must produce the same graph.
    """
    bodies = [
        f"""
        x = self.prep(x)
        y = self.other(x)
        {spelling}:
            x = y
        return self.out(x)
        """,
        """
        x = self.prep(x)
        y = self.other(x)
        x = y
        return self.out(x)
        """,
    ]
    keywords = [keyword, "def"]
    reports = [
        report_for(tmp_path, body, keyword=kw) for body, kw in zip(bodies, keywords)
    ]
    assert [r["blocking_unsupported"] for r in reports] == [0, 0]
    assert [single(r)["unsupported"] for r in reports] == [[], []]
    reads = [
        [call["reads"] for call in single(r)["calls"] if call["symbol"] == "self.out"]
        for r in reports
    ]
    assert reads[0] == reads[1] == [[{"variable": "x", "from_call": 1}]]


def test_call_free_with_as_target_keeps_no_stale_producer(tmp_path):
    """An `as` target is a rebinding whose producer this reducer cannot see.

    `with self.ctx as x:` binds `x` to whatever `__enter__` returned. Leaving the previous
    writer in place would be the stale-producer lie again, and inventing one would be worse,
    so the name is recorded as rebound with no known producer -- and unlike an invented
    `self.ctx` call an `as` target correctly books nothing.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        with self.ctx as x:
            pass
        return self.out(x)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    # A context manager expression is not a call, so nothing is placed for `self.ctx`.
    assert symbols(module) == ["self.prep", "self.out"]
    assert module["calls"][1]["reads"] == [{"variable": "x", "from_call": None}]
    assert module["returns"] == [{"variable": None, "from_call": 1}]


def test_call_free_with_as_target_is_popped_before_the_body_reduces(tmp_path):
    """The `as` pop precedes the body, and that order is observable.

    A body statement reading the target propagates whatever `last_writer` holds when it is
    reduced, so `with open('f') as x:` / `y = x` must book `y` as coming from an unknown
    producer. Popping after the body keeps every existing test green while handing `y` the
    pre-`with` producer `self.prep` -- the stale-producer lie. The `pass` body above cannot
    see the difference.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        with open('f') as x:
            y = x
        return self.out(y)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert symbols(module) == ["self.prep", "self.out"]
    assert module["calls"][1]["reads"] == [{"variable": "y", "from_call": None}]


def test_call_free_with_several_as_targets_pops_them_all_before_the_body(tmp_path):
    """Every item of a multi-item `with` is popped, not just the first.

    `with open('f') as x, open('g') as y:` binds two targets in one statement; a body that
    reads both must see neither pre-`with` writer.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        with open('f') as x, open('g') as y:
            z = x
            w = y
        return self.out(z, w)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert module["calls"][2]["reads"] == [
        {"variable": "z", "from_call": None},
        {"variable": "w", "from_call": None},
    ]


def test_with_docstring_no_longer_cites_assign_as_the_as_target_analogy():
    """The docstring's analogy was measured false, so the reference is gone.

    It called the `as` target "the same treatment `_assign` gives `x = <opaque
    expression>`". The real CLI says the opposite: `x = self.prep(x)` / `x = [1, 2]` keeps
    `self.prep` as the producer of the next read, while `with open('f') as x: pass` books no
    producer at all. Same standard as `_unrecognized`'s withdrawn `async for` example.
    """
    text = load_script_module().ForwardGraph._with.__doc__
    plain = " ".join(text.replace("`", " ").split())
    assert "_assign" not in plain
    # And the ordering requirement the pop carries is stated where it is implemented.
    assert "before" in plain


def test_call_free_try_merges_body_against_handlers(tmp_path):
    """A call-free `try` has alternative outcomes, so its arms merge like an `if`.

    Reaching the statement after the `try` means either the body ran to the end or an
    exception diverted into exactly one handler, and which one is a runtime fact. Skipping
    the construct left the pre-`try` writer in place, so `self.out` named only `self.prep`
    while `x = y` inside the body may well have overwritten it. No variant is emitted:
    `selected_by: execution_profile` would claim the profile decides whether an exception was
    raised, which it does not.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        try:
            x = y
        except ValueError:
            pass
        return self.out(x)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert module["calls"][2]["reads"] == [
        {"variable": "x", "from_call": 1},
        {"variable": "x", "from_call": 0},
    ]
    assert report["config_gated_variants"] == 0
    assert module["variants"] == []
    assert module["merges"] == []


def test_call_free_try_finally_reduces_in_place(tmp_path):
    """`finally:` runs on every outcome, so it is reduced in place after the merge.

    Treating it as one more arm would claim the body and the cleanup are alternatives, and
    reporting it would book a blocker for a path that always runs. Here it is the only
    writer of `x` that survives, exactly as a bare `x = y` at the same place would be.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        try:
            pass
        finally:
            x = y
        return self.out(x)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert module["calls"][2]["reads"] == [{"variable": "x", "from_call": 1}]
    assert module["merges"] == []


def test_call_free_try_arms_that_agree_produce_no_phi(tmp_path):
    """Merging is a fact about the arms, not a `<merge>` node invented on principle.

    `except:` and `else:` both write `x` from the same producer, so there is exactly one
    possible writer and nothing to disambiguate. A merge that always produced a phi would
    have padded the graph with a node no execution corresponds to.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        try:
            pass
        except ValueError:
            x = y
        else:
            x = y
        return self.out(x)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert module["calls"][2]["reads"] == [{"variable": "x", "from_call": 1}]
    assert report["merge_count"] == 0
    assert module["merges"] == []


def test_call_free_try_escalates_under_its_own_label_and_range(tmp_path):
    """Arms that disagree on the residual are escalated once, as `Try` over the `try`.

    The body writes `None` and the handler does not, so no later fused call can be told
    which topology the residual is in and the merge cannot be represented at all. The entry
    names the construct that actually holds the disagreement, with no `condition`: there is
    no selector expression to classify, and `construct` plus the line range are what a
    declared deviation is matched on (D5 -> `_source_ref_covers`).
    """
    report = report_for(
        tmp_path,
        """
        residual = self.prep(x)
        try:
            residual = None
        except ValueError:
            pass
        return residual
        """,
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "Try"
    assert (entry["lineno"], entry["end_lineno"]) == (4, 7)
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == []
    assert entry["call_sites"] == []
    assert "condition" not in entry


def test_call_free_try_with_a_nested_with_merges(tmp_path):
    """The nested construct reduces inside its arm instead of being skipped with it.

    A call-free `try` whose body holds a call-free `with` used to lose both: the outer
    construct was skipped whole, so the inner one was never visited. The `with` body runs
    whenever the `try` arm runs, so the arm's writer is `y`'s producer and the handler's is
    the pre-`try` one -- two producers, neither invented.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        try:
            with self.ctx:
                x = y
        except ValueError:
            pass
        return self.out(x)
        """,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert module["calls"][2]["reads"] == [
        {"variable": "x", "from_call": 1},
        {"variable": "x", "from_call": 0},
    ]


@requires_try_star
@pytest.mark.parametrize(
    "tail,expected_reads",
    [
        (
            """
        try:
            x = y
        except* ValueError:
            pass
        return self.out(x)
        """,
            [{"variable": "x", "from_call": 1}, {"variable": "x", "from_call": 0}],
        ),
        (
            """
        try:
            pass
        except* ValueError:
            pass
        finally:
            x = y
        return self.out(x)
        """,
            [{"variable": "x", "from_call": 1}],
        ),
    ],
)
def test_call_free_except_star_reduces_like_except(tmp_path, tail, expected_reads):
    """`try*` is in `TRY_NODES`, so it merges its arms and reduces its `finally:` too.

    A call-having `try*` is reported as `TryStar` because exception groups change which
    handlers run; a call-free one has nothing to place and the same arm structure, so it
    reduces through the one path rather than being skipped by a spelling check.
    """
    report = report_for(
        tmp_path,
        """
        x = self.prep(x)
        y = self.other(x)
        """
        + tail,
    )
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert module["calls"][2]["reads"] == expected_reads


def test_every_control_flow_node_has_a_dispatch_branch():
    """`_unhandled_control_flow` must stay unreachable -- and the skip path must stay gone.

    The dispatch is the thing that decides whether a construct is reduced or booked. A node
    added to `CONTROL_FLOW_NODES` without a branch used to land in a call-free path that
    reduced nothing and reported only a `= None` write, so the construct vanished while the
    report still claimed nothing was unsupported. The structural guard below fails at the
    moment such a node is added; the runtime backstop reports it either way.
    """
    module = load_script_module()
    handled = (
        set(module.ITERATIVE_NODES)
        | {ast.If}
        | set(module.WITH_NODES)
        | set(module.TRY_NODES)
    )
    if module.MATCH_NODE is not None:
        handled.add(module.MATCH_NODE)
    assert set(module.CONTROL_FLOW_NODES) <= handled
    assert set(module.WITH_NODES) == {ast.With, ast.AsyncWith}
    assert ast.Try in module.TRY_NODES
    # The skip path itself is deleted, not merely unreached: a resurrected `_call_free`
    # would bring back the "holds no call, so nothing to do" assumption with it.
    assert not hasattr(module, "_writes_none")
    assert not hasattr(module.ForwardGraph, "_call_free")
    assert not hasattr(module.ForwardGraph, "_stale_residual")
    assert hasattr(module.ForwardGraph, "_unhandled_control_flow")


@pytest.mark.parametrize(
    "body,expected_symbols",
    [("pass", []), ("x = self.step(x)", ["self.step"])],
)
def test_unhandled_control_flow_reports_whether_or_not_it_holds_a_call(
    body, expected_symbols
):
    """The backstop books the construct either way -- that is the whole point of it.

    `_control_flow` names every member of `CONTROL_FLOW_NODES` today, so no source shape
    reaches this method; the structural guard above is what keeps it that way. It is driven
    directly here because the failure it exists to prevent is silence: the call-free path it
    replaces reduced nothing and reported only a `= None` write, so a construct that lost its
    dispatch branch vanished from the graph while `unsupported` stayed empty and the report
    read as "nothing to see here". Reporting a construct that *does* hold a call is what the
    sibling branch one statement over already does, so the two cannot disagree about whether
    a missing branch is an error.
    """
    module = load_script_module()
    source = f"class Model:\n    def forward(self, x):\n        with self.ctx:\n            {body}\n"
    func = ast.parse(source).body[0].body[0]
    statement = func.body[0]
    graph = module.ForwardGraph("Model", func)
    graph._unhandled_control_flow(statement)
    (entry,) = graph.unsupported
    assert entry["construct"] == "With"
    assert entry["severity"] == "unparsable"
    assert (entry["lineno"], entry["end_lineno"]) == (
        statement.lineno,
        statement.end_lineno,
    )
    assert entry["call_symbols"] == expected_symbols
    assert [site["symbol"] for site in entry["call_sites"]] == expected_symbols
