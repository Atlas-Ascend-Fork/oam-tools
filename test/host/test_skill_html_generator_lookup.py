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
"""Static regression for the HTML generator lookup documented in the perf skill.

The documented command must locate ``generate_html.py`` through the canonical
``SKILL.md`` title instead of assuming the directory name equals that title,
and it must fail explicitly when nothing matches.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = ROOT / "skills/cann-npu-perfanalysis/SKILL.md"
SKILL_TITLE = "# npu-perf-analysis"
GENERATOR_RELPATH = Path("references") / "generate_html.py"
# Directory names the lookup must survive: the current one and the rename
# proposed upstream, neither of which contains the skill title verbatim.
RENAMED_SKILL_DIRS = ("cann-npu-perfanalysis", "cann-perf-analysis")
STEP_C_HEADING = "### 步骤 C：运行 HTML 生成器"


def extract_lookup_script():
    """Return the step-C shell block with the generator invocation stripped."""
    text = SKILL_MD.read_text(encoding="utf-8")
    section = text.split(STEP_C_HEADING, 1)[1]
    block = re.search(r"```bash\n(.*?)```", section, re.DOTALL).group(1)
    lines = [line for line in block.splitlines() if not line.startswith("python3 ")]
    assert lines, "step C documents no lookup logic"
    assert block.count("python3 ") >= 1, "step C no longer invokes the generator"
    return "\n".join(lines + ['printf "%s\\n" "$generate_html"'])


def run_lookup(script, cwd):
    return subprocess.run(
        ["bash", "-c", script],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def lookup_script():
    return extract_lookup_script()


def test_documented_lookup_is_title_based(lookup_script):
    assert SKILL_TITLE in lookup_script, "lookup no longer keys off the skill title"
    assert "grep npu-perf-analysis" not in lookup_script, (
        "lookup still filters SKILL.md paths by a name the directory does not contain"
    )


def test_lookup_resolves_from_repo_root(lookup_script):
    result = run_lookup(lookup_script, ROOT)
    assert result.returncode == 0, result.stderr
    # The lookup runs with cwd=ROOT, so resolve its relative output against ROOT
    # instead of the pytest process cwd. An absolute output keeps working: Path
    # discards the left operand when the right one is absolute.
    resolved = (ROOT / result.stdout.strip()).resolve()
    assert resolved.is_file(), f"documented generator path does not exist: {resolved}"
    assert resolved.name == "generate_html.py"


def test_lookup_fails_without_matching_skill(lookup_script, tmp_path):
    (tmp_path / "skills" / "unrelated").mkdir(parents=True)
    (tmp_path / "skills" / "unrelated" / "SKILL.md").write_text(
        "# some-other-skill\n", encoding="utf-8"
    )
    result = run_lookup(lookup_script, tmp_path)
    assert result.returncode != 0, "unmatched lookup must exit non-zero"
    assert result.stderr.strip(), "unmatched lookup must report why it failed"


@pytest.mark.parametrize("skill_dir", RENAMED_SKILL_DIRS)
def test_lookup_is_directory_name_agnostic(lookup_script, tmp_path, skill_dir):
    destination = tmp_path / "skills" / skill_dir
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_MD.parent, destination)
    result = run_lookup(lookup_script, tmp_path)
    assert result.returncode == 0, result.stderr
    resolved = (tmp_path / result.stdout.strip()).resolve()
    assert resolved == (destination / GENERATOR_RELPATH).resolve()
