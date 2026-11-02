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
"""The one-shot pipeline consumes a completed Skill 1 bundle."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_pipeline.py"
JOIN = Path(__file__).parents[1] / "scripts" / "build_trace_bindings.py"


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("run_pipeline_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_join_module():
    spec = importlib.util.spec_from_file_location("build_trace_bindings_under_test", JOIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pipeline_resolves_peer_skills_from_its_own_collection():
    module = load_pipeline_module()
    collection = SCRIPT.parents[2].resolve()

    assert Path(module.STAGE1).parent.resolve() == collection
    assert Path(module.STAGE3).parent.resolve() == collection
    assert "name: cann-perf-breakdown" in (Path(module.STAGE1) / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "name: cann-perf-ui-json-report" in (Path(module.STAGE3) / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_peer_skill_resolution_parses_frontmatter_and_rejects_external_symlinks(tmp_path):
    module = load_pipeline_module()
    collection = tmp_path / "skills"
    collection.mkdir()
    quoted = collection / "quoted"
    quoted.mkdir()
    (quoted / "SKILL.md").write_text(
        '---\nname: "quoted-skill"\ndescription: valid\n---\n', encoding="utf-8"
    )
    decoy = collection / "decoy"
    decoy.mkdir()
    (decoy / "SKILL.md").write_text(
        "---\nname: other\ndescription: 'name: quoted-skill'\n---\n", encoding="utf-8"
    )

    assert Path(module.find_peer_skill("quoted-skill", collection)) == quoted

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text(
        "---\nname: external-skill\ndescription: outside\n---\n", encoding="utf-8"
    )
    (collection / "external-link").symlink_to(outside, target_is_directory=True)

    try:
        module.find_peer_skill("external-skill", collection)
    except RuntimeError as error:
        assert "found []" in str(error)
    else:
        raise AssertionError("external symlink must not be accepted as a peer skill")


def test_help_exposes_breakdown_input_and_no_semantic_review_option():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--breakdown" in proc.stdout
    assert "--semantic-review" not in proc.stdout


def test_help_works_without_third_party_python_packages():
    proc = subprocess.run(
        [sys.executable, "-S", str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--breakdown" in proc.stdout


def test_pipeline_checks_readiness_before_auxiliary_conversion_inputs(tmp_path):
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    out = tmp_path / "out"

    proc = subprocess.run([
        sys.executable,
        str(SCRIPT),
        "--breakdown", str(breakdown),
        "--model-id", "fixture-model",
        "--out", str(out),
    ], capture_output=True, text=True)

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["status"] == "failed"
    assert result["stage"] == "readiness"
    assert not (out / "ai_mapping_request.json").exists()


def test_removed_legacy_semantic_review_flow_is_not_referenced():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "prepare_semantic_review.py" not in source
    assert "--semantic-review" not in source
    assert "awaiting_semantic_review" not in source


def test_completed_status_does_not_reference_removed_stage1_report_variable():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"breakdown_report": html' not in source


def test_pipeline_uses_formal_skill3_generator_and_stops_at_manual_gate():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"scripts/generate-report.mjs"' in source or '"generate-report.mjs"' in source
    assert '"status": "pending_manual_validation"' in source
    assert '"status": "completed"' not in source


@pytest.mark.parametrize("bad", ["0", "-1", "nan", "inf", "-inf", "abc", ""])
def test_time_tolerance_is_a_pipeline_flag_and_refuses_nonsense_at_parse_time(bad, tmp_path):
    """Widening the raw join is reachable from the documented entry point, and validated early.

    `build_trace_bindings.py` owns `--time-tolerance-us`, but README's quick start and
    `MODEL_BREAKDOWN_TO_UI_WORKFLOW.md` both drive this script, so a flag that stops here is a
    flag no operator has. Without the passthrough a capture whose two exports disagree by more
    than the 2e-3 us default ends in `die("failed", "bindings", ...)`: exit 1, empty report,
    and no supported way to widen the join.

    Refusal happens at parse time rather than in the child because bindings is the *last*
    stage -- a bad number caught there costs a whole pipeline run to discover.
    """
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    out = tmp_path / "out"

    helped = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--time-tolerance-us" in helped.stdout

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--breakdown",
            str(breakdown),
            "--model-id",
            "fixture-model",
            "--out",
            str(out),
            "--time-tolerance-us",
            bad,
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "argument --time-tolerance-us" in proc.stderr
    # argparse rejected it before main() created anything, so a typo leaves no half-built tree.
    assert not out.exists()


def test_bindings_stage_hands_the_tolerance_to_the_join():
    """The flag has to reach the child, not just be accepted here.

    Asserted on the source of the bindings invocation rather than end to end: reaching that
    call needs a complete Skill 1 bundle (readiness, node index, attribution, facts, overlay),
    and the two things that can silently break -- the flag missing from the argv, or a second
    default drifting away from the join's -- are both visible here.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index('"build_trace_bindings.py"')
    call = source[start : source.index('die("failed", "bindings"', start)]

    assert '"--time-tolerance-us"' in call
    assert "args.time_tolerance_us" in call
    # Always passed, default included, so the echoed `$ ...` line records the slack the report
    # was actually built with instead of leaving it implied by whichever script is on disk.
    assert "if args.time_tolerance_us" not in call


def test_pipeline_and_join_share_one_tolerance_default_and_validator():
    """One source of truth: the pipeline must not be able to accept what the join refuses.

    Redeclaring either the default or the validator here would let the two disagree -- a
    pipeline default of, say, 1e-3 would silently narrow the join back to the open-boundary
    failure the 2e-3 default exists to avoid, and a looser local validator would accept a
    tolerance the child then rejects at the last stage.

    Compared against the module the pipeline actually imported, not a second copy loaded
    here: `load_join_module()` executes the file again under its own name, so its function
    objects are distinct by construction and identity against them would always fail.
    """
    pipeline = load_pipeline_module()
    join = sys.modules["build_trace_bindings"]

    assert pipeline.DEFAULT_TIME_MATCH_TOLERANCE_US == join.DEFAULT_TIME_MATCH_TOLERANCE_US
    assert pipeline.positive_float is join.positive_float
    assert "DEFAULT_TIME_MATCH_TOLERANCE_US =" not in SCRIPT.read_text(encoding="utf-8")


@pytest.mark.parametrize("value", ["2e-3", "1e-05", "0.5", "123.456", "1e10"])
def test_tolerance_survives_the_argv_round_trip(value):
    """`run()` stringifies every argv element, so the value must survive float -> str -> float.

    The flag is always passed, including the default, which makes the child's parse of
    `str(float)` part of the contract rather than an accident of the operator typing a value.
    """
    join = load_join_module()

    expected = join.positive_float(value)
    assert join.positive_float(str(expected)) == expected
