#!/bin/bash
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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

set -e
CANN_ROOT="${ASCEND_INSTALL_PATH:-${ASCEND_HOME_PATH:-/usr/local/Ascend/cann}}"
SETENV="$CANN_ROOT/bin/setenv.bash"
# shellcheck source=/dev/null
[ -f "$SETENV" ] && source "$SETENV"
OUTPUT_DIR="./msprof_output"
mkdir -p "$OUTPUT_DIR"
"$CANN_ROOT/tools/profiler/bin/msprof" --output="$OUTPUT_DIR" --sys-devices=0 --sys-period=5 --ai-core=on --host-sys-usage=cpu,mem
