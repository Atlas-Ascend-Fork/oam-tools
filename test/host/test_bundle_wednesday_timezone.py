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
"""Exercise the production CMake date function without downloading bundles."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
CMAKE = shutil.which("cmake")
pytestmark = pytest.mark.skipif(CMAKE is None, reason="CMake is required")


@pytest.mark.parametrize("tz", ["UTC0", "UTC-8", "UTC+7"])
@pytest.mark.parametrize(
    "instant",
    [
        "2026-10-21T12:00:00",
        "2026-10-21T20:00:00",
        "2026-10-22T00:00:00",
        "2026-10-21T03:00:00",
        "2026-10-26T01:00:00",
        "2027-01-01T00:00:00",
        "2028-02-29T12:00:00",
        "2026-10-08T12:00:00",
    ],
)
def test_recent_wednesday_uses_one_utc_calendar(tmp_path, instant, tz):
    source = (ROOT / "cmake/install_bundle.cmake").read_text(encoding="utf-8")
    # Isolate the exact production function: including the whole file would
    # invoke the installer and access the network at module scope.
    function = re.search(
        r"^function\(oam_recent_wednesday RESULT_VAR\).*?^endfunction\(\)",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert function is not None
    driver = tmp_path / "date.cmake"
    driver.write_text(
        function.group()
        + '\noam_recent_wednesday(chosen)\nmessage(STATUS "CHOSEN=${chosen}")\n',
        encoding="utf-8",
    )
    moment = datetime.fromisoformat(instant).replace(tzinfo=timezone.utc)
    expected = moment.date() - timedelta(days=(moment.weekday() - 2) % 7)
    env = os.environ.copy()
    env["TZ"] = tz
    env["SOURCE_DATE_EPOCH"] = str(int(moment.timestamp()))
    result = subprocess.run(
        [CMAKE, "-P", str(driver)],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"CHOSEN={expected:%Y%m%d}" in result.stdout, result.stdout
