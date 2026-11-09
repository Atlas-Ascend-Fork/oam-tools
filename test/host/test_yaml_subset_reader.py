# ----------------------------------------------------------------------------
# YAML adapter contract tests
#
# These tests pin the contract of breakdown_common's YAML adapter (PyYAML behind
# a thin layer):
#
#  1. Consumer shapes: every way a real runtime config spells model_path / tp_size /
#     pipeline_stage reads exactly as PyYAML reads it.
#  2. The two value-domain deviations are pinned as *deviations*: implicit octal and
#     sexagesimal stay strings, implicit timestamps stay strings in every position;
#     an explicit `!!timestamp` builds a date/datetime and is refused at the
#     walkability boundary.
#  3. Failure boundary: every refusal raises YamlSubsetError (never a bare
#     ValueError/KeyError/IndexError from PyYAML's constructors, never a traceback),
#     and every value the boundary lets through is walkable downstream (no cycles,
#     no exotic constructions).
#  4. Multi-document streams stay refused: a single answer from one stream, or none.
#
# Deliberately NOT pinned: parser-internal line numbers, error wording, or
# "shape X is outside the grammar" refusals -- PyYAML's verdict on those is the
# specification, and re-pinning it would re-implement PyYAML's own test suite.
# The loader is built lazily, so collecting this file works even in an
# environment without PyYAML; the parsing tests are skipped there.
# ----------------------------------------------------------------------------
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/cann-perf-breakdown/1-perf-breakdown/scripts"
sys.path.insert(0, str(SCRIPTS))
import breakdown_common as bc  # noqa: E402

try:
    import yaml as _reference_yaml
except ImportError:  # pragma: no cover
    _reference_yaml = None


@pytest.fixture
def reader():
    return bc


# ---------------------------------------------------------------------------
# 1. consumer shapes
# ---------------------------------------------------------------------------

CONSUMER_SHAPES = [
    pytest.param("model_path: /T/w\n", {"model_path": "/T/w"}, id="plain"),
    pytest.param("train:\n  tp_size: 8\n", {"train": {"tp_size": 8}}, id="nested"),
    pytest.param(
        "parallel_config: [{tp_size: 8, ep_size: 1}]\n",
        {"parallel_config": [{"tp_size": 8, "ep_size": 1}]},
        id="flow_of_mappings",
    ),
    pytest.param(
        "cmd: |\n  run.sh --tp_size 8 --model_path /T/w\n",
        {"cmd": "run.sh --tp_size 8 --model_path /T/w\n"},
        id="block_scalar_body_is_text",
    ),
    pytest.param(
        "a: &x {tp_size: 8}\ninfer: *x\n",
        {"a": {"tp_size": 8}, "infer": {"tp_size": 8}},
        id="alias",
    ),
    pytest.param(
        "base: &b\n  tp_size: 8\nk:\n  <<: *b\n  ep_size: 2\n",
        {"base": {"tp_size": 8}, "k": {"tp_size": 8, "ep_size": 2}},
        id="merge_key",
    ),
    pytest.param("desc: >\n  one\n  two\n", {"desc": "one two\n"}, id="folded"),
    pytest.param(
        "model_path: /T/a\nmodel_path: /T/b\n",
        {"model_path": "/T/b"},
        id="duplicate_later_wins",
    ),
    pytest.param(
        "# c\n---\nmodel_path: /T/w\n...\n", {"model_path": "/T/w"}, id="markers"
    ),
    pytest.param('k: "a \\" b"\n', {"k": 'a " b'}, id="escaped_quote"),
    pytest.param("k: 'it''s'\n", {"k": "it's"}, id="single_quote_escape"),
    pytest.param("x: 1\n\n  two\n", {"x": "1\ntwo"}, id="fold_blank_line"),
    pytest.param("layers: !!int 61\n", {"layers": 61}, id="explicit_int_tag"),
    pytest.param("name: !!str true\n", {"name": "true"}, id="explicit_str_tag"),
    pytest.param("? explicit\n: value\n", {"explicit": "value"}, id="explicit_key"),
    pytest.param("k: 61\n", {"k": 61}, id="plain_int"),
    pytest.param("ratio: 0.5\n", {"ratio": 0.5}, id="plain_float"),
    pytest.param("flag: true\n", {"flag": True}, id="plain_bool"),
    pytest.param("k: null\n", {"k": None}, id="plain_null"),
]


@pytest.mark.parametrize("text,expected", CONSUMER_SHAPES)
def test_consumer_shapes_read_exactly_as_expected(reader, text, expected):
    assert reader.load_yaml_subset(text, "case") == expected


@pytest.mark.skipif(
    _reference_yaml is None, reason="PyYAML is the parser; oracle is the same package"
)
@pytest.mark.parametrize("text,expected", CONSUMER_SHAPES)
def test_consumer_shapes_read_exactly_as_pyyaml(reader, text, expected):
    assert reader.load_yaml_subset(text, "case") == _reference_yaml.safe_load(text)


@pytest.mark.parametrize(
    "text",
    [
        "desc: |\n  model_path: /not/a/declaration\n",
        "desc: >\n  model_path: /not/a/declaration\n",
    ],
    ids=["literal_decoy", "folded_decoy"],
)
def test_block_scalar_bodies_declare_nothing(reader, text):
    """Text inside a block scalar is content, never a declaration."""
    tree = reader.load_yaml_subset(text, "case")
    assert reader.collect_yaml_values(tree, "model_path") == []


def test_a_declaration_after_a_block_scalar_still_declares(reader):
    """The decoy inside the block scalar is inert; the real key on its own line is not."""
    text = "cmd: |\n  run.sh --tp_size 8\nmodel_path: /T/w\n"
    tree = reader.load_yaml_subset(text, "case")
    assert reader.collect_yaml_values(tree, "model_path") == ["/T/w"]


def test_reader_resolves_the_declared_path(reader, tmp_path):
    """End-to-end: a discovered YAML's model_path reaches collect_yaml_values intact."""
    cfg = tmp_path / "runtime.yaml"
    cfg.write_text("model_path: /T/w\n", encoding="utf-8")
    tree = reader.load_yaml_subset_file(str(cfg))
    assert reader.collect_yaml_values(tree, "model_path") == ["/T/w"]


# ---------------------------------------------------------------------------
# 2. the two value-domain deviations
# ---------------------------------------------------------------------------

DEVIATION_CASES = [
    pytest.param("k: 0123\n", {"k": "0123"}, id="implicit_octal_stays_a_string"),
    pytest.param("k: 1:30\n", {"k": "1:30"}, id="implicit_sexagesimal_stays_a_string"),
    pytest.param(
        "k: 1:30:00\n", {"k": "1:30:00"}, id="long_sexagesimal_stays_a_string"
    ),
    pytest.param("k: -0123\n", {"k": "-0123"}, id="signed_octal_stays_a_string"),
    pytest.param("k: 2024-01-02\n", {"k": "2024-01-02"}, id="a_date_stays_a_string"),
    pytest.param(
        "k: 2024-01-02T03:04:05Z\n",
        {"k": "2024-01-02T03:04:05Z"},
        id="a_timestamp_stays_a_string",
    ),
    pytest.param(
        "model_path: 0123\n",
        {"model_path": "0123"},
        id="a_path_shaped_octal_stays_a_string",
    ),
    pytest.param(
        "tp_size: 0123\n", {"tp_size": "0123"}, id="a_sized_octal_stays_a_string"
    ),
    pytest.param("k: !!int 0123\n", {"k": 83}, id="explicit_int_constructs_octal"),
    pytest.param(
        "k: !!int 1:30\n", {"k": 90}, id="explicit_int_constructs_sexagesimal"
    ),
    pytest.param("k: 0x1f\n", {"k": 31}, id="hex_constructs"),
    pytest.param("k: 0b101\n", {"k": 5}, id="binary_constructs"),
    pytest.param("k: 1_000\n", {"k": 1000}, id="underscores_construct"),
    pytest.param("k: 61\n", {"k": 61}, id="decimal_constructs"),
    pytest.param("k: 0\n", {"k": 0}, id="zero_constructs"),
]


@pytest.mark.parametrize("text,expected", DEVIATION_CASES)
def test_the_two_value_domain_deviations(reader, text, expected):
    """Path-shaped and date-shaped scalars stay the strings they look like.

    These are the two deviations PyYAML-the-package does not ship with: the report
    probes `model_path` strings for reachability, and a date object or the number 83
    in that position is a value the file never wrote.
    """


@pytest.mark.parametrize("text,expected", DEVIATION_CASES)
def test_the_two_value_domain_deviations_are_pinned_by_value(reader, text, expected):
    assert reader.load_yaml_subset(text, "case") == expected


# ---------------------------------------------------------------------------
# 3. failure boundary
# ---------------------------------------------------------------------------

REFUSALS = [
    pytest.param("---\na: 1\n---\nb: 2\n", id="two_documents"),
    pytest.param("a: 1\n---\nb: 2\n", id="document_marker_inside"),
    pytest.param("k: [1,\n", id="unterminated_flow"),
    pytest.param('k: "unterminated\n', id="unterminated_quote"),
    pytest.param("a: &\n", id="anchor_with_no_name"),
    pytest.param("a: &x 1\nb: &x 2\nc: *x\n", id="duplicate_anchor"),
    pytest.param("x: *undefined\n", id="undefined_alias"),
    pytest.param("k: !!int abc\n", id="int_tag_on_non_number"),
    pytest.param("k: !!bool maybe\n", id="bool_tag_on_non_bool"),
    pytest.param("k: !!int .inf\n", id="int_tag_on_infinity"),
    pytest.param("x: [!!int ]\n", id="empty_tagged_node_in_flow"),
    pytest.param("k: [1, 2", id="flow_never_closes"),
]


@pytest.mark.parametrize(
    "text", [p.values[0] for p in REFUSALS], ids=[p.id for p in REFUSALS]
)
def test_refusals_raise_yamlsubseterror_only(reader, text):
    """Every refusal exits through YamlSubsetError -- never a bare exception type.

    PyYAML's constructors raise ValueError/KeyError/IndexError outside the YAMLError
    hierarchy for construction failures; the adapter's boundary converts all of them.
    """
    with pytest.raises(bc.YamlSubsetError):
        reader.load_yaml_subset(text, "case")


CYCLIC_DOCUMENTS = [
    pytest.param(t, id=i)
    for t, i in [
        ("a: &x {k: *x}\n", "a_mapping_key_pointing_back"),
        ("a: &x [*x]\n", "a_sequence_item_pointing_back"),
        ("- &x\n  - *x\n", "a_block_sequence_item_pointing_back"),
        ("a: &x {k: &y {j: *x}}\n", "a_cycle_through_two_anchors"),
    ]
]


@pytest.mark.parametrize("text", CYCLIC_DOCUMENTS)
def test_a_self_referential_alias_is_refused_not_constructed(reader, text):
    """A cyclic document is refused at the boundary, never handed to a walker.

    PyYAML constructs recursive values by design (two-phase constructors), and the
    YAML spec allows them; this reader refuses them because every downstream walk
    ("all model_path values in the document") on a cycle is an infinite set.
    """
    with pytest.raises(bc.YamlSubsetError, match="cycle"):
        reader.load_yaml_subset(text, "case")


@pytest.mark.parametrize(
    "text",
    [
        "a: &x {tp_size: 8}\ninfer: *x\n",
        "a: &x 1\nb: *x\n",
        "k:\n  <<: &b {a: 1}\n  c: 2\nz: *b\n",
        "a: &x [1, 2]\nb: *x\nc: *x\n",
        "b: &a |\n  x\ny: *a\n",
    ],
    ids=[
        "shared_mapping",
        "shared_scalar",
        "merge_key_source",
        "diamond",
        "block_scalar",
    ],
)
def test_a_shared_anchor_is_not_a_cycle(reader, text):
    """Aliasing one node twice is a diamond, not a cycle: the walk keeps an
    on-stack set beside the finished set, so revisiting a *completed* node is
    fine. Refusing these would cut the anchors/merge half of the grammar."""
    tree = reader.load_yaml_subset(text, "case")
    assert tree is not None


@pytest.mark.parametrize(
    "text",
    [
        "a: &a [x,x,x,x,x,x,x,x]\nb: &b [*a,*a,*a,*a,*a,*a,*a,*a]\n"
        "c: &c [*b,*b,*b,*b,*b,*b,*b,*b]\nd: &d [*c,*c,*c,*c,*c,*c,*c,*c]\n",
        "a: &a [1, 2]\nb: &b [*a, *a, *a, *a]\nc: [*b, *b, *b, *b]\n",
    ],
    ids=["deep_alias_fanout", "two_level_fanout"],
)
def test_a_deeply_shared_document_is_walked_linearly(reader, text):
    """Aliases share *references*; the walk must not treat every reference as a copy.

    Without a visited set the visit count multiplies by the fan-out at each level
    (a ten-line file, ten minutes); with it every node is walked exactly once.
    Both documents finish instantly and still find the declared keys.
    """
    tree = reader.load_yaml_subset(text, "case")
    assert reader.collect_yaml_values(tree, "nope") == []


def test_a_shared_anchor_collects_from_every_reference_site(reader):
    """The visited set deduplicates *walks*, not findings.

    `a: &x {tp_size: 8}` aliased by two keys is one shared node, but the value
    under `tp_size` is still collectible -- once is enough, and
    `resolve_declared_paths` works on distinct values anyway.
    """
    tree = reader.load_yaml_subset("a: &x {tp_size: 8}\ninfer: *x\n", "case")
    assert reader.collect_yaml_values(tree, "tp_size") == [8]


EXOTIC_DOCUMENTS = [
    pytest.param(t, id=i)
    for t, i in [
        ("k: !!omap\n  - model_path: /T/w\n", "omap_tuples"),
        ("k: !!pairs\n  - a: 1\n", "pairs_tuples"),
        ("k: !!set\n  ? a\n", "set_members"),
        ("k: !!binary aGVsbG8=\n", "binary_bytes"),
        ("k: !!timestamp 2024-01-02\n", "explicit_timestamp_datetime"),
        ("? !!binary bW9kZWxfcGF0aA==\n: /T/w\n", "binary_in_key_position"),
        ("? !!timestamp 2024-01-02\n: v\n", "timestamp_in_key_position"),
    ]
]


@pytest.mark.parametrize("text", EXOTIC_DOCUMENTS)
def test_an_exotic_construction_is_refused_not_half_read(reader, text):
    """`!!omap`/`!!pairs`/`!!set`/`!!binary`/`!!timestamp` build types the walks skip.

    `collect_yaml_values` walks dict and list only, so a `model_path` under an
    `!!omap` would be lost silently -- a declaration vanishing with exit code 0.
    The boundary refuses the document so the caller's refusal path names it
    instead (hard error for a named file, evidence gap for a discovered one).
    """
    with pytest.raises(bc.YamlSubsetError, match="value type"):
        reader.load_yaml_subset(text, "case")


@pytest.mark.parametrize(
    "text",
    [
        "model_path: /T/w\n",
        "k: 1.5\n",
        "k: true\n",
        "k: null\n",
        "k: 61\n",
        "a: &x {tp_size: 8}\ninfer: *x\n",
        "cmd: |\n  x\n",
        "k: !!str true\n",
        "k: !!int 8\n",
    ],
    ids=[
        "path",
        "float",
        "bool",
        "null",
        "int",
        "alias",
        "block",
        "str_tag",
        "int_tag",
    ],
)
def test_plain_and_tagged_scalars_stay_readerable(reader, text):
    """The exotic check refuses tuples/sets/bytes only; every scalar type the
    corpus actually uses -- including explicitly tagged ones -- passes."""
    tree = reader.load_yaml_subset(text, "case")
    assert tree is not None


def test_the_loader_is_built_lazily_not_at_import(tmp_path):
    """Importing this module must not require PyYAML.

    Seventeen scripts that never read YAML import `breakdown_common` for its
    other helpers; an eager loader build would turn every one of their `--help`
    invocations into a traceback in a PyYAML-less environment, and the
    `--checkpoint-config` escape the import error names would be unreachable
    because the crash happens before argparse runs. The build happens on the
    first parse call instead -- verified in a fresh interpreter, because this
    suite's own parse calls may have built it already.
    """
    probe = (
        "import sys; sys.path.insert(0, %r); "
        "import breakdown_common as bc; "
        "assert bc._YAML_DEPS is None, 'loader built at import time'"
    ) % str(SCRIPTS)
    subprocess.run([sys.executable, "-c", probe], check=True)


def test_a_construction_failure_never_escapes_the_module(reader):
    """The R10/R13 lesson, kept: enumerating exception types loses; convert at the edge."""
    for text in [
        "k: !!int 1e999\n",
        "k: !!int .inf\n",
        "k: !!int .nan\n",
        "k: !!float abc\n",
        "k: !!bool maybe\n",
        "k: [!!int ]\n",
        "? !!int \n: w\n",
    ]:
        with pytest.raises(bc.YamlSubsetError):
            reader.load_yaml_subset(text, "case")


def test_non_utf8_file_is_refused_without_replacement_characters(reader, tmp_path):
    """GBK bytes must refuse, not decode to U+FFFD paths that cannot exist."""
    cfg = tmp_path / "runtime.yaml"
    cfg.write_bytes("model_path: /权重目录\n".encode("gbk"))
    with pytest.raises(bc.YamlSubsetError):
        reader.load_yaml_subset_file(str(cfg))


def test_leading_bom_is_consumed_but_an_interior_one_is_content(reader, tmp_path):
    cfg = tmp_path / "runtime.yaml"
    cfg.write_bytes(b"\xef\xbb\xbfmodel_path: /T/w\n")
    tree = reader.load_yaml_subset_file(str(cfg))
    assert reader.collect_yaml_values(tree, "model_path") == ["/T/w"]


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
def test_line_endings_do_not_change_the_value(reader, newline):
    tree = reader.load_yaml_subset(f"model_path: /T/w{newline}", "case")
    assert reader.collect_yaml_values(tree, "model_path") == ["/T/w"]


# ---------------------------------------------------------------------------
# 4. collect_yaml_values + resolve_declared_paths (consumer invariants)
# ---------------------------------------------------------------------------


def test_collect_yaml_values_finds_every_depth(reader):
    tree = reader.load_yaml_subset(
        "a:\n  b:\n    model_path: /deep\nmodel_path: /flat\n", "case"
    )
    assert sorted(reader.collect_yaml_values(tree, "model_path")) == ["/deep", "/flat"]


def test_collect_yaml_values_ignores_block_scalar_text(reader):
    tree = reader.load_yaml_subset("desc: |\n  model_path: /decoy\n", "case")
    assert reader.collect_yaml_values(tree, "model_path") == []


def test_resolve_declared_paths_refuses_to_choose_between_two_reachable(
    reader, tmp_path
):
    for name, value in [("a.yaml", "/one"), ("b.yaml", "/two")]:
        (tmp_path / name).write_text(f"model_path: {value}\n", encoding="utf-8")
    declared = []
    for name in ("a.yaml", "b.yaml"):
        tree = reader.load_yaml_subset_file(str(tmp_path / name))
        declared.extend(
            (name, v) for v in reader.collect_yaml_values(tree, "model_path")
        )
    resolved, chosen, conflict = reader.resolve_declared_paths(declared, lambda v: True)
    assert resolved is None and conflict is not None


def test_resolve_declared_paths_accepts_one_reachable_declaration(reader):
    resolved, chosen, conflict = reader.resolve_declared_paths(
        [("a.yaml", "/one")], lambda v: True
    )
    assert resolved == "/one" and conflict is None


def test_a_path_holding_a_number_is_reported_not_guessed(reader):
    """The value-domain deviation surfaces to the caller as a reportable odd value."""
    resolved, chosen, conflict = reader.resolve_declared_paths(
        [("a.yaml", 83)], lambda v: False
    )
    assert resolved is None
    assert conflict is not None and "not a path" in conflict


# ---------------------------------------------------------------------------
# 5. golden set: the runtime-config grammar, one document at a time
# ---------------------------------------------------------------------------

SUPPORTED_GRAMMAR_DOCUMENTS = [
    # 1. block mappings and sequences, nested
    "train:\n  tp_size: 8\n  ep_size: 16\ncmds:\n  - echo it's fine\n  - --flag=1\n",
    # 2. plain and quoted scalars, folding
    "model_path: /T/weights\nlayers: 61\nratio: 0.5\nnote: first\n  continued\n"
    "blank_line: one\n\n  two\nquoted: \"a \\\" b \\t c\"\nsingle: 'it''s'\n",
    # 3. block scalars
    "description: |\n  body line\n    deeper line\n  model_path: /not/a/declaration\n"
    "folded: >\n  one\n  two\nchomped: |-\n  no trailing newline\n"
    "keep: |+\n  kept\nexplicit: |2\n  indented two\n",
    # 4. flow collections
    "parallel_config: [{tp_size: 8, ep_size: 1}]\nkv: {a: 1, b: two}\n"
    "multi: [\n  # comment inside\n  1,\n  2\n]\n",
    # 5. anchors, aliases, merge
    "base: &b\n  tp_size: 8\ninfer: *b\nmerged:\n  <<: *b\n  ep_size: 2\nflow_merge:\n  <<: [*b]\n",
    # 6. tags and explicit keys
    "layers: !!int 61\nname: !!str true\nflag: !!bool true\nnothing: !!null\n"
    "? explicit_key\n: explicit_value\n",
    # 7. comments, document markers, duplicates
    "# leading comment\n---\nmodel_path: /T/first\nmodel_path: /T/second\n...\n",
]

pytestmark_pyyaml = pytest.mark.skipif(
    _reference_yaml is None, reason="PyYAML is the parser; oracle is the same package"
)


@pytest.mark.parametrize(
    "document",
    SUPPORTED_GRAMMAR_DOCUMENTS,
    ids=[
        "block_mappings_and_sequences",
        "plain_and_quoted_scalars",
        "block_scalars",
        "flow_collections",
        "anchors_aliases_merge",
        "tags_and_explicit_keys",
        "comments_markers_duplicates",
    ],
)
def test_supported_grammar_reads_exactly_as_pyyaml(reader, document):
    """The grammar the corpus actually carries, now delegated to PyYAML.

    With PyYAML as the engine this test is a tautology by construction -- which is
    the point: the 7-group grammar existed to bound a hand-built implementation,
    and pinning it again here would re-implement PyYAML's own test suite. It stays
    as a tripwire: if the adapter's deviations ever leak into these documents, or
    PyYAML's semantics change under a major upgrade, this catches it.
    """
    assert reader.load_yaml_subset(document, "golden") == _reference_yaml.safe_load(
        document
    )
