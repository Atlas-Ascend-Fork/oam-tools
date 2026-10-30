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
"""Exercise source dataflow extraction through its actual command-line entry."""

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


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(Block() for i in range(0, 24))", 24),
        ("[Block() for i in range(2, 8, 2)]", 3),
        ("(Block() for i in range(8, 2, -2))", 3),
        ("[Block() for i in range(-2, 2)]", 4),
        ("(Block() for i in range(3))", 3),
        ("(Block() for i in range(0))", 0),
        ("(Block() for i in range(n))", None),
        ("[Block(), Block()]", 2),
        # Rejection paths: each of these is a literal range that cannot stand
        # for the ModuleList size, so the size must stay unknown.
        ("[Block() for i in range(4) for j in range(3)]", None),
        ("[Block() for i in range(4) if i]", None),
        ("[Block() for i in range(2, 8, 0)]", None),
        ("[Block() for i in range(1.5)]", None),
        ("[Block() for i in range(4, step=2)]", None),
        # A huge literal is reported as unknown rather than as a real count.
        ("[Block() for i in range(99999999999)]", None),
        ("[Block() for i in range(1000)]", 1000),
    ],
)
def test_module_list_static_range_cardinality(tmp_path, expression, expected):
    source = tmp_path / "model.py"
    source.write_text(
        "class Model:\n    def __init__(self):\n"
        f"        self.layers = ModuleList({expression})\n"
        "    def forward(self, x):\n        return self.head(x)\n",
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
    module = json.loads(result.stdout)["modules"][0]
    assert module["submodules"]["layers"] == expected


def extract(tmp_path, body, parameters="x"):
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
    graph = json.loads(result.stdout)["modules"][0]
    assert graph["unsupported"] == []
    return graph


@pytest.mark.parametrize(
    "declaration", ["x: Tensor", "unused: Tensor", "self.cache: Tensor"]
)
def test_annotation_without_value_does_not_assign(tmp_path, declaration):
    graph = extract(
        tmp_path,
        f"x = self.head(x)\n{declaration}\nreturn self.tail(x)",
    )
    assert [call["symbol"] for call in graph["calls"]] == ["self.head", "self.tail"]
    assert graph["calls"][1]["reads"] == [{"variable": "x", "from_call": 0}]


def test_annotated_assignment_still_records_call(tmp_path):
    graph = extract(tmp_path, "x: Tensor = self.head(x)\nreturn self.tail(x)")
    assert graph["calls"][1]["reads"] == [{"variable": "x", "from_call": 0}]


def test_annotation_does_not_erase_known_none(tmp_path):
    graph = extract(
        tmp_path,
        "residual = None\nresidual: Tensor\nx, residual = self.norm(x, residual)\nreturn x",
    )
    assert graph["merges"] == []
    assert len(graph["residual_initializations"]) == 1


@pytest.mark.parametrize("rhs", ["self.mlp(x)", "self.mlp(hidden_states=x)"])
def test_augmented_add_records_rhs_call_before_merge(tmp_path, rhs):
    graph = extract(tmp_path, f"x = self.head(x)\nx += {rhs}\nreturn self.tail(x)")
    assert [call["symbol"] for call in graph["calls"]] == [
        "self.head",
        "self.mlp",
        "<merge>",
        "self.tail",
    ]
    assert graph["calls"][1]["reads"] == [{"variable": "x", "from_call": 0}]
    assert [item["from_call"] for item in graph["merges"][0]["operands"]] == [0, 1]
    assert graph["merges"][0]["operand_count"] == 2
    assert graph["calls"][3]["reads"] == [{"variable": "x", "from_call": 2}]


def test_augmented_add_keeps_nested_call_order(tmp_path):
    graph = extract(
        tmp_path,
        "x = self.head(x)\nx += self.mlp(self.norm(x))\nreturn x",
    )
    assert [call["symbol"] for call in graph["calls"]] == [
        "self.head",
        "self.norm",
        "self.mlp",
        "<merge>",
    ]
    assert [item["from_call"] for item in graph["merges"][0]["operands"]] == [0, 2]
    assert graph["calls"][2]["reads"][0]["from_call"] == 1
    assert graph["returns"] == [{"variable": "x", "from_call": 3}]


def test_augmented_add_plain_residual_still_records_both_producers(tmp_path):
    graph = extract(
        tmp_path,
        "x = self.head(x)\nresidual = self.skip(x)\nx += residual\nreturn x",
    )
    assert [item["from_call"] for item in graph["merges"][0]["operands"]] == [0, 1]
    assert graph["merges"][0]["kind"] == "in_place_add"


def test_ordinary_add_keeps_nested_rhs_call(tmp_path):
    graph = extract(tmp_path, "x = self.head(x)\nx = x + self.mlp(x)\nreturn x")
    assert [call["symbol"] for call in graph["calls"]] == [
        "self.head",
        "self.mlp",
        "<merge>",
    ]
    assert [item["from_call"] for item in graph["merges"][0]["operands"]] == [0, 1]


@pytest.mark.parametrize(
    "binding", ["left, right = right, left", "[left, right] = [right, left]"]
)
def test_parallel_rebinding_uses_preassignment_writers(tmp_path, binding):
    graph = extract(
        tmp_path,
        f"left = self.left(x)\nright = self.right(x)\n{binding}\nreturn self.join(left, right)",
    )
    assert graph["calls"][2]["reads"] == [
        {"variable": "left", "from_call": 1},
        {"variable": "right", "from_call": 0},
    ]


def test_nested_tuple_rebinding_preserves_producers(tmp_path):
    graph = extract(
        tmp_path,
        "left = self.left(x)\nright = self.right(x)\n(a, (b, c)) = (right, (left, right))\nreturn self.join(a, b, c)",
    )
    assert [item["from_call"] for item in graph["calls"][2]["reads"]] == [1, 0, 1]


def test_tuple_none_initialization_does_not_create_residual_merge(tmp_path):
    graph = extract(
        tmp_path,
        "x = self.head(x)\nx, residual = x, None\nx, residual = self.norm(x, residual)\nreturn x",
    )
    assert graph["merges"] == []
    assert len(graph["residual_initializations"]) == 1


def test_tuple_call_outputs_still_share_call_producer(tmp_path):
    graph = extract(
        tmp_path, "left, right = self.split(x)\nreturn self.join(left, right)"
    )
    assert [item["from_call"] for item in graph["calls"][1]["reads"]] == [0, 0]


def test_tuple_rebinding_clears_overwritten_constant_source(tmp_path):
    graph = extract(
        tmp_path,
        "left = self.left(x)\nright = self.right(x)\nleft, right = 0, left\nreturn self.join(left, right)",
    )
    assert graph["calls"][2]["reads"] == [
        {"variable": "left", "from_call": None},
        {"variable": "right", "from_call": 0},
    ]


def test_chained_tuple_targets_all_read_original_state(tmp_path):
    graph = extract(
        tmp_path,
        "left = self.left(x)\nright = self.right(x)\n(left, right) = (a, b) = (right, left)\nreturn self.join(left, right, a, b)",
    )
    assert [item["from_call"] for item in graph["calls"][2]["reads"]] == [1, 0, 1, 0]


def test_tuple_rebinding_preserves_alternative_branch_sources(tmp_path):
    graph = extract(
        tmp_path,
        "if self.use_fused:\n    x = self.left(x)\nelse:\n    x = self.right(x)\n(alias, unused) = (x, None)\nreturn self.tail(alias)",
    )
    assert graph["calls"][-1]["reads"] == [
        {"variable": "alias", "from_call": 0},
        {"variable": "alias", "from_call": 1},
    ]


def test_repeated_tuple_target_retains_last_assignment(tmp_path):
    graph = extract(
        tmp_path,
        "left = self.left(x)\nright = self.right(x)\nleft, left = right, left\nreturn self.tail(left)",
    )
    assert graph["calls"][2]["reads"] == [{"variable": "left", "from_call": 0}]


def test_nonliteral_unpacking_retains_existing_producer_handling(tmp_path):
    graph = extract(
        tmp_path,
        "values = self.split(x)\nleft, right = values\nreturn self.join(left, right)",
    )
    assert [item["from_call"] for item in graph["calls"][1]["reads"]] == [0, 0]


@pytest.mark.parametrize(
    "assignment",
    ["a, b = x, y", "[a, b] = [x, y]", "a, b = x, y\nc, d = a, b\na, b = c, d"],
)
def test_unpacking_retains_forward_input_edges(tmp_path, assignment):
    graph = extract(tmp_path, assignment + "\nreturn self.head(a, b)", "x, y")
    assert graph["calls"][0]["reads"] == [
        {"variable": "a", "from_call": -1},
        {"variable": "b", "from_call": -1},
    ]
    assert len(graph["edges"]) == 2


@pytest.mark.parametrize(
    "rhs, count", [("x + x", 3), ("x + x + x", 4), ("x + self.mlp(x)", 3)]
)
def test_augmented_add_preserves_each_rhs_operand(tmp_path, rhs, count):
    graph = extract(tmp_path, f"x = self.head(x)\nx += {rhs}\nreturn x")
    explicit = extract(tmp_path, f"x = self.head(x)\nx = x + ({rhs})\nreturn x")
    assert graph["merges"][0]["operand_count"] == count
    assert graph["merges"][0]["operands"] == explicit["merges"][0]["operands"]


@pytest.mark.parametrize("declaration", ["", "x: Tensor\n"])
def test_known_none_parameter_alias_does_not_invent_input(tmp_path, declaration):
    graph = extract(
        tmp_path, "x = None\n" + declaration + "a, b = x, None\nreturn self.head(a, b)"
    )
    assert graph["calls"][0]["reads"] == [
        {"variable": "a", "from_call": None},
        {"variable": "b", "from_call": None},
    ]
    assert graph["edges"] == []


@pytest.mark.parametrize(
    "body",
    [
        "residual = x\nx += residual\nreturn x",
        "x += SCALE\nreturn x",
        "if self.fused:\n    residual = self.left(x)\nelse:\n    residual = self.right(x)\nx += residual\nreturn x",
    ],
)
def test_augmented_operand_count_uses_syntax_not_provenance(tmp_path, body):
    graph = extract(tmp_path, body)
    merge = next(item for item in graph["merges"] if item.get("kind") == "in_place_add")
    assert merge["operand_count"] == 2


def test_augmented_add_constant_operand_keeps_the_syntax_count(tmp_path):
    # A constant contributes no producer, so `operands` holds only the target
    # while operand_count still counts both sides of the statement.
    graph = extract(tmp_path, "x += 1\nreturn self.tail(x)")
    merge = next(item for item in graph["merges"] if item.get("kind") == "in_place_add")
    assert merge["operand_count"] == 2
    assert merge["operands"] == [
        {"variable": "x", "from_call": None, "expression": "x"}
    ]
    assert graph["edges"] == [
        {"from_call": 0, "to_call": 1, "via": "x", "type": "activation"}
    ]


def test_augmented_add_parameter_operand_introduces_no_input_edge(tmp_path):
    # A parameter has no writer, so resolving it yields from_call None and no
    # INPUT edge is added: the merge still reads as a single node feeding tail.
    graph = extract(tmp_path, "x += x\nreturn self.tail(x)")
    merge = next(item for item in graph["merges"] if item.get("kind") == "in_place_add")
    assert merge["operand_count"] == 2
    assert [operand["from_call"] for operand in merge["operands"]] == [None, None]
    assert graph["edges"] == [
        {"from_call": 0, "to_call": 1, "via": "x", "type": "activation"}
    ]


def test_augmented_add_phi_operand_reports_every_producer(tmp_path):
    # A config-gated arm leaves the parameter as one of the phi sources, so the
    # merge genuinely consumes both the call output and the input. Pinned as-is:
    # an INPUT edge here is information, and this is the only shape that makes one.
    graph = extract(
        tmp_path,
        "if self.use_residual:\n    x = self.head(x)\nx += x\nreturn self.tail(x)",
    )
    merge = next(item for item in graph["merges"] if item.get("kind") == "in_place_add")
    assert merge["operand_count"] == 2
    assert {operand["from_call"] for operand in merge["operands"]} == {0, -1}
    assert {"from_call": -1, "to_call": 1, "via": "x", "type": "residual"} in graph[
        "edges"
    ]
    assert {"from_call": 0, "to_call": 1, "via": "x", "type": "residual"} in graph[
        "edges"
    ]


def test_augmented_assign_target_carries_the_statement_location():
    # _aug_assign builds the target node by hand. Without a copied location it
    # has no lineno, and anything that later reports an expression position or
    # walks the node with an AST visitor that reads one raises AttributeError.
    import ast
    import importlib.util

    spec = importlib.util.spec_from_file_location("extract_dataflow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tree = ast.parse("class Model:\n    def forward(self, x):\n        x += x\n")
    func = tree.body[0].body[0]
    statement = func.body[0]
    graph = module.ForwardGraph("Model", func)
    seen = []
    original = graph._resolve_merge_operands

    def record(operands, node):
        seen.extend(operands)
        return original(operands, node)

    graph._resolve_merge_operands = record
    graph._aug_assign(statement)
    synthetic = seen[0]
    assert isinstance(synthetic, ast.Name)
    assert synthetic.lineno == statement.lineno
    assert synthetic.col_offset == statement.col_offset
