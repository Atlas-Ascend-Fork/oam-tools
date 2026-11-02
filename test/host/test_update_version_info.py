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
"""update_version_info.sh 的参数校验、路径边界与 tagInfo 回退行为回归。"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/update_version_info/update_version_info.sh"
TIMESTAMP_LINE = re.compile(r"^timestamp=\d{8}_\d{9}$")
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not available")


def _run(tmp_path, args, tag_info=None):
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("tagInfo", "TIME_STAMP_ENV")
    }
    env["PATH"] = "/usr/bin:/bin"
    if tag_info is not None:
        env["tagInfo"] = tag_info
    return subprocess.run(
        [str(BASH), str(SCRIPT), *args],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _timestamp_line(content):
    lines = content.splitlines()
    assert lines, content
    assert TIMESTAMP_LINE.match(lines[-1]), content
    return lines[-1]


def test_wrong_arg_count_prints_usage_and_exits_1(tmp_path):
    for args in ([], ["only-input"], ["a.txt", "b.txt", "c.txt"]):
        result = _run(tmp_path, args)
        assert result.returncode == 1, args
        assert "Usage" in result.stderr, args
        assert list(tmp_path.iterdir()) == [], args


def test_spaced_paths_are_copied_and_timestamped(tmp_path):
    in_dir = tmp_path / "in put dir"
    in_dir.mkdir()
    input_file = in_dir / "in put.txt"
    input_file.write_text("version=1\n", encoding="utf-8")
    output_file = tmp_path / "out put dir" / "out put.txt"

    result = _run(tmp_path, [str(input_file), str(output_file)])

    assert result.returncode == 0
    assert result.stderr == ""
    content = output_file.read_text(encoding="utf-8")
    assert content.splitlines()[0] == "version=1"
    _timestamp_line(content)


def test_leading_dash_paths_succeed(tmp_path):
    (tmp_path / "-input").write_text(
        "version=1\ntimestamp=20250102_030405006\n", encoding="utf-8"
    )

    result = _run(tmp_path, ["-input", "-sub/-out"])

    assert result.returncode == 0
    content = (tmp_path / "-sub" / "-out").read_text(encoding="utf-8")
    assert content.splitlines()[0] == "version=1"
    _timestamp_line(content)
    assert "20250102_030405006" not in content


def test_taginfo_without_timestamp_warns_with_value_and_falls_back(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("version=1\n", encoding="utf-8")

    result = _run(
        tmp_path,
        [str(input_file), str(tmp_path / "output.txt")],
        tag_info="release_without_timestamp",
    )

    assert result.returncode == 0
    assert "WARNING: tagInfo='release_without_timestamp'" in result.stderr
    assert "falling back to current time" in result.stderr
    content = (tmp_path / "output.txt").read_text(encoding="utf-8")
    assert content.splitlines()[0] == "version=1"
    _timestamp_line(content)


def test_taginfo_timestamp_is_extracted_and_used(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("version=1\n", encoding="utf-8")

    result = _run(
        tmp_path,
        [str(input_file), str(tmp_path / "output.txt")],
        tag_info="release_20250102_030405006",
    )

    assert result.returncode == 0
    assert result.stderr == ""
    content = (tmp_path / "output.txt").read_text(encoding="utf-8")
    assert content.splitlines()[-1] == "timestamp=20250102_030405006"


def test_timestamp_appended_to_input_without_trailing_newline(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("version=1", encoding="utf-8")

    result = _run(tmp_path, [str(input_file), str(tmp_path / "output.txt")])

    assert result.returncode == 0
    content = (tmp_path / "output.txt").read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines[0] == "version=1"
    assert len(lines) == 2
    _timestamp_line(content)


def test_leading_dash_paths_without_trailing_newline_separate_lines(tmp_path):
    (tmp_path / "-input").write_text("version=1", encoding="utf-8")

    result = _run(tmp_path, ["-input", "-sub/-out"])

    assert result.returncode == 0
    content = (tmp_path / "-sub" / "-out").read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines[0] == "version=1"
    assert len(lines) == 2
    _timestamp_line(content)


def test_empty_input_yields_only_timestamp_line(tmp_path):
    input_file = tmp_path / "input.txt"
    input_file.write_text("", encoding="utf-8")

    result = _run(tmp_path, [str(input_file), str(tmp_path / "output.txt")])

    assert result.returncode == 0
    content = (tmp_path / "output.txt").read_text(encoding="utf-8")
    lines = content.splitlines()
    assert len(lines) == 1
    assert TIMESTAMP_LINE.match(lines[0]), content
