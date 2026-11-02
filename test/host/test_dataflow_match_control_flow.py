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
"""Drive the real dataflow CLI over control flow it used to drop silently.

Every case here runs the complete command-line entry point on a real temporary source
file and reads the JSON report back; nothing is imported, stubbed or simulated. The
contract under test is the one the script's own docstring states: a construct whose
execution path cannot be read from source order is classified -- extracted as a named
variant when a deployment fixes it, reported as blocking otherwise -- and is never
dropped on the floor while the report claims nothing is unsupported.
"""

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
requires_match = pytest.mark.skipif(
    sys.version_info < (3, 10), reason="match source requires Python 3.10+"
)
requires_try_star = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="except* source requires Python 3.11+"
)


def load_script_module():
    spec = importlib.util.spec_from_file_location("extract_dataflow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report_for(tmp_path, body, parameters="x"):
    """Run the CLI on `class Model.forward` whose body is `body`, return the report."""
    source = tmp_path / "model.py"
    source.write_text(
        f"class Model:\n    def forward(self, {parameters}):\n"
        + textwrap.indent(textwrap.dedent(body).strip() + "\n", "        "),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def single(report):
    return report["modules"][0]


def blocking(report):
    """The blocking entries of the one module under test."""
    return [
        entry
        for entry in single(report)["unsupported"]
        if entry["severity"] in ("data_dependent", "unparsable")
    ]


@requires_match
def test_issue_330_match_branch_calls_are_reported_and_block(tmp_path):
    """The exact source from issue #330: two dropped calls and a clean-looking report."""
    report = report_for(
        tmp_path,
        """
        match mode:
            case 0:
                x = self.first(x)
            case _:
                x = self.second(x)
        return x
        """,
        parameters="x, mode",
    )
    assert report["blocking_unsupported"] == 1
    module = single(report)
    assert [call["symbol"] for call in module["calls"]] == []
    (entry,) = module["unsupported"]
    assert entry["construct"] == "Match"
    assert entry["severity"] == "data_dependent"
    assert entry["condition"] == "mode"
    assert entry["call_symbols"] == ["self.first", "self.second"]
    assert [site["symbol"] for site in entry["call_sites"]] == [
        "self.first",
        "self.second",
    ]
    # Line numbers point at the calls themselves, not at the `match` keyword.
    assert [site["lineno"] for site in entry["call_sites"]] == [5, 7]


@requires_match
def test_config_gated_match_extracts_variants_like_config_gated_if(tmp_path):
    """A selector fixed at construction time is extracted, not rejected.

    `if self.quant_mode:` has always produced two named variants; the same selector
    written as a `match` must not degrade into a blocking deviation, which is what
    made every real model report its main compute as unextractable.
    """
    bodies = {
        "if": """
            if self.quant_mode:
                x = self.first(x)
            else:
                x = self.second(x)
            return x
            """,
        "match": """
            match self.quant_mode:
                case True:
                    x = self.first(x)
                case _:
                    x = self.second(x)
            return x
            """,
    }
    reports = {name: report_for(tmp_path, body) for name, body in bodies.items()}
    for report in reports.values():
        assert report["blocking_unsupported"] == 0
        assert report["config_gated_variants"] == 2
        assert [call["symbol"] for call in single(report)["calls"]] == [
            "self.first",
            "self.second",
        ]
    assert [variant["arm"] for variant in single(reports["if"])["variants"]] == [
        "then",
        "else",
    ]
    assert [variant["arm"] for variant in single(reports["match"])["variants"]] == [
        "case[0]",
        "case[1]",
    ]


@requires_match
def test_config_gated_match_keeps_every_arm_and_the_wildcard(tmp_path):
    report = report_for(
        tmp_path,
        """
        match self.quant_mode:
            case 0:
                x = self.w4(x)
            case 1:
                x = self.w8(x)
            case _:
                x = self.w16(x)
        return x
        """,
    )
    assert report["blocking_unsupported"] == 0
    assert report["config_gated_variants"] == 3
    assert [call["symbol"] for call in single(report)["calls"]] == [
        "self.w4",
        "self.w8",
        "self.w16",
    ]


@requires_match
def test_match_without_wildcard_has_no_phantom_passthrough_arm(tmp_path):
    """A match that matches nothing raises MatchError; "ran nothing" is not an outcome.

    Unlike `if` without `else`, a `match` has no fall-through arm. Granting it one invented an
    execution that cannot happen and made `return x` claim the pre-match value as well, so
    `returns` carried a `from_call: -1` for a path that never reaches the `return`.
    """
    report = report_for(
        tmp_path,
        """
        match self.quant_mode:
            case True:
                x = self.first(x)
        return x
        """,
    )
    assert report["blocking_unsupported"] == 0
    module = single(report)
    assert [variant["arm"] for variant in module["variants"]] == ["case[0]"]
    assert [call["symbol"] for call in module["calls"]] == ["self.first"]
    # The only way to reach the `return` is through the case body.
    assert module["returns"] == [{"variable": "x", "from_call": 0}]


@requires_match
@pytest.mark.parametrize("pattern", ["object()", "object() as o"], ids=["object", "as"])
def test_catch_all_pattern_gets_no_phantom_passthrough_arm(tmp_path, pattern):
    """`case object():` matches every object, exactly like a bare `case _:`.

    The exhaustiveness gate recognised only the bare spelling, so this match was granted a
    "ran nothing" arm as well. That arm cannot execute -- matching no case raises
    MatchError -- yet it made `return x` claim the pre-match value too, putting a
    `from_call: -1` in `returns` next to the two arms that really produce it.
    """
    report = report_for(
        tmp_path,
        f"""
        match self.quant_mode:
            case 0:
                x = self.first(x)
            case {pattern}:
                x = self.second(x)
        return x
        """,
    )
    assert report["blocking_unsupported"] == 0
    module = single(report)
    assert [variant["arm"] for variant in module["variants"]] == ["case[0]", "case[1]"]
    assert [call["symbol"] for call in module["calls"]] == ["self.first", "self.second"]
    assert module["returns"] == [
        {"variable": "x", "from_call": 0},
        {"variable": "x", "from_call": 1},
    ]


@requires_match
def test_match_subject_call_stays_on_the_main_path(tmp_path):
    """The subject runs whichever arm wins, so it is a call, not a branch call."""
    report = report_for(
        tmp_path,
        """
        match self.route(x):
            case 0:
                x = self.first(x)
            case _:
                x = self.second(x)
        return x
        """,
        parameters="x, mode",
    )
    module = single(report)
    assert [call["symbol"] for call in module["calls"]] == ["self.route"]
    assert report["blocking_unsupported"] == 1
    (entry,) = module["unsupported"]
    assert entry["construct"] == "Match"
    # The unconditional subject must not be reported as an arm-dependent call.
    assert entry["call_symbols"] == ["self.first", "self.second"]


@requires_match
def test_nested_match_subject_records_each_call_once(tmp_path):
    """`self.route(self.pre(x))` is two steps of the graph, not three, and forks nothing.

    The subject is scanned by a walk, which yields both halves of a nested call, while the
    call-tree builder descends into arguments on its own. Handing it both halves recorded
    `self.pre` a second time as a stand-alone step and hung a fork on `x` that the source
    does not contain.
    """
    report = report_for(
        tmp_path,
        """
        match self.route(self.pre(x)):
            case 0:
                x = self.first(x)
            case _:
                x = self.second(x)
        return x
        """,
    )
    module = single(report)
    assert [call["symbol"] for call in module["calls"]] == ["self.pre", "self.route"]
    # The inner call is the nested source of the outer one, and nothing else.
    assert module["edges"] == [
        {"from_call": 0, "to_call": 1, "via": "__call_0_result", "type": "activation"}
    ]
    # `x` has exactly one reader, so no fork may be invented for it.
    assert module["forks"] == []
    assert report["blocking_unsupported"] == 1
    (entry,) = module["unsupported"]
    assert entry["construct"] == "Match"
    assert entry["call_symbols"] == ["self.first", "self.second"]


@requires_match
def test_match_with_only_a_subject_call_is_not_a_blocker(tmp_path):
    """Call-free arms plus an unconditional subject call are fully extractable.

    Reporting this as blocking would make the graph depend on which of two equivalent
    spellings the model author happened to choose. The arms still rebind `x`, so they are
    reduced and their writers merged -- skipping the construct left the graph claiming the
    pre-match producer of `x`.
    """
    report = report_for(
        tmp_path,
        """
        match self.route(x):
            case 0:
                x = x + 1
            case _:
                x = x * 2
        return x
        """,
    )
    assert report["blocking_unsupported"] == 0
    module = single(report)
    assert module["unsupported"] == []
    # `self.route` on the main path, plus the in-place add the first arm performs.
    assert [call["symbol"] for call in module["calls"]] == ["self.route", "<merge>"]
    # The selector is a runtime value, so no arm may claim to be the deployed one.
    assert module["variants"] == []
    (merge,) = module["merges"]
    assert merge["writes"] == ["x"]
    assert merge["lineno"] == 5


@requires_match
def test_call_free_match_does_not_invent_a_blocker(tmp_path):
    report = report_for(
        tmp_path,
        """
        match mode:
            case 0:
                pass
        return x
        """,
        parameters="x, mode",
    )
    assert report["blocking_unsupported"] == 0
    assert single(report)["unsupported"] == []


@requires_match
def test_match_guard_expression_is_not_a_submodule_call(tmp_path):
    """`x.sum()` in a guard is a tensor query, not a submodule, and must not be listed."""
    report = report_for(
        tmp_path,
        """
        match mode:
            case 0 if x.sum():
                x = self.first(x)
            case _:
                pass
        return x
        """,
        parameters="x, mode",
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["call_symbols"] == ["self.first"]


@requires_match
def test_match_guard_makes_the_selector_data_dependent(tmp_path):
    """A guard is part of the selector, so it decides the arm just like the subject does.

    Classifying the subject alone read `match self.quant_mode:` as construction-time config
    and published `selected_by: execution_profile` for arms that a tensor value picks at
    runtime. The reported `condition` must name the guard too: it is what a reader of the
    report uses to work out which deviation to declare.
    """
    report = report_for(
        tmp_path,
        """
        match self.quant_mode:
            case 0 if x.sum():
                x = self.first(x)
            case _:
                x = self.second(x)
        return x
        """,
    )
    assert report["blocking_unsupported"] == 1
    module = single(report)
    # No arm may claim to be the deployed one when a tensor chooses it.
    assert module["variants"] == []
    (entry,) = module["unsupported"]
    assert entry["construct"] == "Match"
    assert entry["severity"] == "data_dependent"
    assert entry["condition"] == "self.quant_mode | case 0 if x.sum()"
    assert entry["call_symbols"] == ["self.first", "self.second"]


@requires_match
def test_submodule_call_inside_a_guard_is_not_lost(tmp_path):
    """Arm extraction only walks `case.body`, so a guard call needs its own route in.

    `self.check(x)` provably appears in the source; a report that omits it is the same
    failure mode issue #330 describes, one clause to the left.
    """
    report = report_for(
        tmp_path,
        """
        match self.quant_mode:
            case 0 if self.check(x):
                x = self.first(x)
            case _:
                x = self.second(x)
        return x
        """,
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["call_symbols"] == ["self.check", "self.first", "self.second"]
    assert [site["symbol"] for site in entry["call_sites"]] == [
        "self.check",
        "self.first",
        "self.second",
    ]
    assert [site["lineno"] for site in entry["call_sites"]] == [4, 5, 7]


@requires_match
def test_match_pattern_capture_is_not_a_submodule_call(tmp_path):
    report = report_for(
        tmp_path,
        """
        match mode:
            case {"kind": kind}:
                x = self.first(x)
            case _:
                pass
        return x
        """,
        parameters="x, mode",
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["call_symbols"] == ["self.first"]


@requires_match
def test_match_that_resets_a_residual_is_rejected_explicitly(tmp_path):
    """Call-free arms still change provenance, so they cannot pass silently."""
    report = report_for(
        tmp_path,
        """
        match mode:
            case 0:
                residual = None
            case _:
                residual = x
        return x
        """,
        parameters="x, mode",
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "Match"
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == []


@pytest.mark.parametrize(
    "branch",
    [
        pytest.param(["if self.quant_mode:", "    x = y"], id="if"),
        pytest.param(
            [
                "match self.quant_mode:",
                "    case 0:",
                "        x = y",
                "    case _:",
                "        pass",
            ],
            id="match",
            marks=requires_match,
        ),
    ],
)
def test_call_free_branch_still_feeds_the_next_read(tmp_path, branch):
    """An arm that calls no submodule still rebinds names, so it cannot be skipped.

    The construct used to return early when no arm held a call, leaving the pre-branch
    writer in place: `self.first(x)` then read `x` from a producer the source contradicts,
    which is the same lie as dropping the calls. Reducing the arms and merging their
    writers keeps every possible producer instead.
    """
    report = report_for(
        tmp_path,
        "\n".join(["y = self.prep(y)", *branch, "x = self.first(x)", "return x"]),
        parameters="x, y",
    )
    assert report["blocking_unsupported"] == 0
    module = single(report)
    assert [call["symbol"] for call in module["calls"]] == ["self.prep", "self.first"]
    # `x` can come from the branch or from the input, and both are recorded.
    assert module["calls"][1]["reads"] == [
        {"variable": "x", "from_call": 0},
        {"variable": "x", "from_call": -1},
    ]
    assert {edge["from_call"] for edge in module["edges"]} == {0, -1}
    assert all(edge["to_call"] == 1 for edge in module["edges"])
    # The selector is config, but no arm calls anything, so there is no variant to bind.
    assert module["variants"] == []


@pytest.mark.parametrize(
    "branch",
    [
        pytest.param(
            ["if mode:", "    x = y", "else:", "    x = z"],
            id="if",
        ),
        pytest.param(
            [
                "match mode:",
                "    case 0:",
                "        x = y",
                "    case _:",
                "        x = z",
            ],
            id="match",
            marks=requires_match,
        ),
    ],
)
def test_runtime_selector_with_call_free_arms_merges_writers(tmp_path, branch):
    """A runtime selector with call-free arms is not blocking, but it is not ignored either.

    Reporting it as `data_dependent` would block on a branch that calls nothing -- the
    common `if past_key_value is not None: key_states = torch.cat([...])` shape -- while
    dropping it would claim a single producer for a value two arms can write. Merging into
    a phi is the honest middle: every possible producer, none invented, no variant
    published for a choice the deployment profile cannot make.
    """
    report = report_for(
        tmp_path,
        "\n".join(
            [
                "y = self.prep(y)",
                "z = self.post(z)",
                *branch,
                "x = self.first(x)",
                "return x",
            ]
        ),
        parameters="x, y, z, mode",
    )
    assert report["blocking_unsupported"] == 0
    module = single(report)
    assert module["unsupported"] == []
    assert module["variants"] == []
    assert [call["symbol"] for call in module["calls"]] == [
        "self.prep",
        "self.post",
        "self.first",
    ]
    assert module["calls"][2]["reads"] == [
        {"variable": "x", "from_call": 0},
        {"variable": "x", "from_call": 1},
    ]


@requires_match
def test_match_nested_in_a_module_list_loop_is_reported(tmp_path):
    """The decoder-layer shape: `match` inside `for layer in self.layers`.

    The loop calls the *loop variable*, so a gate that only recognises `self.<name>`
    sees no call here and the whole body disappears -- which is the failure issue #330
    describes, one level down.
    """
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            match mode:
                case 0:
                    x = layer.first(x)
                case _:
                    x = layer.second(x)
            x = layer.post(x)
        return x
        """,
        parameters="x, mode",
    )
    module = single(report)
    assert report["blocking_unsupported"] == 1
    (entry,) = module["unsupported"]
    assert entry["construct"] == "Match"
    assert entry["call_symbols"] == ["layer.first", "layer.second"]
    # The unconditional call in the loop body is still extracted as the repeated block.
    assert [call["symbol"] for call in module["calls"]] == ["layer.post"]
    assert len(module["loops"]) == 1


@requires_match
def test_match_nested_in_two_loops_is_reported(tmp_path):
    report = report_for(
        tmp_path,
        """
        for block in self.blocks:
            for layer in block.layers:
                match mode:
                    case 0:
                        x = layer.first(x)
                    case _:
                        x = layer.second(x)
        return x
        """,
        parameters="x, mode",
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "Match"
    assert entry["call_symbols"] == ["layer.first", "layer.second"]


def test_if_nested_in_a_module_list_loop_is_reported(tmp_path):
    """The same gate hole affects `if`; it is closed by the same loop-target stack."""
    report = report_for(
        tmp_path,
        """
        for layer in self.layers:
            if flag:
                x = layer.first(x)
        return x
        """,
        parameters="x, flag",
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "If"
    assert entry["call_symbols"] == ["layer.first"]


def test_if_containing_a_module_list_loop_is_not_dropped(tmp_path):
    report = report_for(
        tmp_path,
        """
        if flag:
            for layer in self.layers:
                x = layer(x)
        return x
        """,
        parameters="x, flag",
    )
    assert report["blocking_unsupported"] == 1
    (entry,) = single(report)["unsupported"]
    assert entry["construct"] == "If"
    assert entry["call_symbols"] == ["layer"]


@requires_try_star
def test_except_star_calls_are_reported_and_block(tmp_path):
    report = report_for(
        tmp_path,
        """
        try:
            x = self.first(x)
        except* ValueError:
            x = self.second(x)
        return x
        """,
    )
    assert report["blocking_unsupported"] == 1
    module = single(report)
    (entry,) = module["unsupported"]
    assert entry["construct"] == "TryStar"
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == ["self.first", "self.second"]
    assert [site["symbol"] for site in entry["call_sites"]] == [
        "self.first",
        "self.second",
    ]
    assert module["calls"] == []


@requires_try_star
def test_call_free_except_star_does_not_invent_a_blocker(tmp_path):
    report = report_for(
        tmp_path,
        """
        try:
            pass
        except* ValueError:
            pass
        return x
        """,
    )
    assert report["blocking_unsupported"] == 0
    assert single(report)["unsupported"] == []


@pytest.mark.parametrize(
    "statement,construct,symbol",
    [
        ("raise self.make_error(x)", "Raise", "self.make_error"),
        ("assert self.check(x)", "Assert", "self.check"),
    ],
)
def test_unrecognised_statement_carrying_a_call_is_not_dropped(
    tmp_path, statement, construct, symbol
):
    """The dispatch list is hardcoded; anything off it must still be reported.

    Without a fallback these statements reach the implicit `return None` and vanish, and
    because the downstream gate is driven by the `unsupported` list it never fires.
    """
    report = report_for(tmp_path, f"{statement}\nx = self.first(x)\nreturn x")
    module = single(report)
    assert report["blocking_unsupported"] == 1
    (entry,) = module["unsupported"]
    assert entry["construct"] == construct
    assert entry["severity"] == "unparsable"
    assert entry["call_symbols"] == [symbol]
    # The rest of the method is still extracted normally.
    assert [call["symbol"] for call in module["calls"]] == ["self.first"]


def test_unrecognised_statement_without_a_call_stays_quiet(tmp_path):
    report = report_for(tmp_path, "assert x is not None\nx = self.first(x)\nreturn x")
    assert report["blocking_unsupported"] == 0
    assert single(report)["unsupported"] == []


def test_plain_module_list_loop_is_still_a_loop(tmp_path):
    """Regression guard: the loop-target stack must not change the ordinary shape."""
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
    assert [call["symbol"] for call in module["calls"]] == ["layer"]
    assert [loop["call_ids"] for loop in module["loops"]] == [[0]]


def test_straight_line_extraction_is_unchanged(tmp_path):
    report = report_for(tmp_path, "x = self.first(x)\nreturn self.second(x)")
    module = single(report)
    assert report["blocking_unsupported"] == 0
    assert module["unsupported"] == []
    assert [call["symbol"] for call in module["calls"]] == ["self.first", "self.second"]
    assert module["calls"][1]["reads"] == [{"variable": "x", "from_call": 0}]


def test_control_flow_node_set_has_no_placeholders():
    """Version fallbacks must drop absent nodes, not substitute a lookalike type.

    `getattr(ast, "Match", ast.If)` would leave `ast.If` in the tuple twice and read as
    a claim that a `match` is an `if`. Filtering keeps the set exactly right per
    interpreter.
    """
    module = load_script_module()
    nodes = module.CONTROL_FLOW_NODES
    assert all(isinstance(node, type) for node in nodes)
    assert len(set(nodes)) == len(nodes)
    assert {ast_name for ast_name in ("If", "For", "While", "With", "Try")} <= {
        node.__name__ for node in nodes
    }
    # Present exactly when the running interpreter has the construct at all.
    for name in ("Match", "TryStar"):
        assert (getattr(__import__("ast"), name, None) is not None) == (
            name in {node.__name__ for node in nodes}
        )
