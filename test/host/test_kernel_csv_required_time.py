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
import importlib.util
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(path):
    path = ROOT / path
    spec = importlib.util.spec_from_file_location("host_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = "skills/cann-perf-breakdown/1-perf-breakdown/scripts/analyze_kernels.py"


@pytest.mark.parametrize("value", ["broken", "NaN", "inf", "-1"])
def test_invalid_csv_time_cannot_be_exported_as_measurement(tmp_path, value):
    csv = tmp_path / "kernels.csv"
    csv.write_text(
        "Step Id,Name,Duration(us),Start Time(us),Stream ID\n"
        f"0,Kernel,{value},0,1\n0,Kernel,2,1,1\n"
    )
    module = load_script(SCRIPT)
    with pytest.raises(module.ValidationError, match="Duration"):
        module.analyze_kernels(csv)


def test_zero_and_finite_scientific_times_remain_valid(tmp_path):
    csv = tmp_path / "kernels.csv"
    csv.write_text(
        "Step Id,Name,Duration(us),Start Time(us),Stream ID\n0,Kernel,0,0,1\n0,Kernel,1e-3,1,1\n"
    )
    result, steps = load_script(SCRIPT).analyze_kernels(csv)
    assert steps == ["0"]
    operators = result.get("selected_step_operators", {}).get("operators", [])
    assert [op.get("duration_us") for op in operators] == [0, 0.001]


@pytest.mark.parametrize("value", ["", "N/A", "-", "--", "1e400", "0x10", "NaN", "-1"])
def test_cli_diagnostic_identifies_file_row_and_duration_column(value, tmp_path):
    csv = tmp_path / "kernels.csv"
    output = tmp_path / "raw_ops.json"
    csv.write_text(
        "Step Id,Name,Duration(us),Start Time(us),Stream ID\n"
        f"0,Kernel,1,0,1\n0,Kernel,{value},1,1\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / SCRIPT),
            "--file",
            str(csv),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1
    diagnostic = result.stderr[-500:]
    assert "错误:" in diagnostic
    assert str(csv) in diagnostic
    assert "第 3 行" in diagnostic and "Duration(us)" in diagnostic
    assert repr(value) in diagnostic
    assert "Traceback" not in result.stderr
    assert not output.exists()
