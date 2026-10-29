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

"""ST: a permission-hardened install remains uninstallable."""

from pathlib import Path
import shutil
import subprocess


_BASH = shutil.which("bash") or "/bin/bash"


def test_uninstall_removes_package_tree(run_package, install_dir):
    install = subprocess.run(
        [
            _BASH,
            run_package,
            "--full",
            "--quiet",
            f"--install-path={install_dir}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    uninstall = subprocess.run(
        [
            _BASH,
            run_package,
            "--uninstall",
            "--quiet",
            f"--install-path={install_dir}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert uninstall.returncode == 0, uninstall.stdout + uninstall.stderr
    assert not (Path(install_dir) / "cann").exists()
