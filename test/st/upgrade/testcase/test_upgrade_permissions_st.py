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

"""ST: permissions do not drift after a real package upgrade."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "test/st/install/data"
_BASH = shutil.which("bash") or "/bin/bash"
GUARD_DIR = ROOT / "test/st/install/testcase"
if str(GUARD_DIR) not in sys.path:
    sys.path.insert(0, str(GUARD_DIR))

from package_permission_guard import (  # noqa: E402
    assert_tree_matches,
    current_installation_is_private,
)


@pytest.mark.parametrize(
    "first_type,second_type",
    [("--full", "--full"), ("--run", "--full")],
)
def test_upgrade_preserves_structure_and_permissions(
    run_package, install_dir, first_type, second_type
):
    for install_type in (first_type, second_type):
        result = subprocess.run(
            [
                _BASH,
                run_package,
                install_type,
                "--quiet",
                f"--install-path={install_dir}",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    assert_tree_matches(
        Path(install_dir) / "cann",
        DATA_DIR / "installed_tree.tsv",
        mode_column="mode_private"
        if current_installation_is_private()
        else "mode_shared",
    )
