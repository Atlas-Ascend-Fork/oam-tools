#!/usr/bin/env bash
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
set -euo pipefail

REPO_URL="${TOOL_FAULT_DIAGNOSIS_SKILLS_REPO:-https://gitcode.com/cann/oam-tools.git}"
TMPDIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required command: $1" >&2
    exit 1
  fi
}

need_cmd git
need_cmd python3

has_mode_arg=false
for arg in "$@"; do
  case "$arg" in
    --overwrite|--dry-run|--verify-only)
      has_mode_arg=true
      ;;
  esac
done

if [ "$has_mode_arg" = false ]; then
  set -- "$@" --overwrite
fi

echo "Downloading tool-fault-diagnosis skills..."
git clone --depth 1 "$REPO_URL" "$TMPDIR/skills" >/dev/null

echo "Installing tool-fault-diagnosis skills..."
python3 "$TMPDIR/skills/skills/tool-fault-diagnosis/scripts/install_all_tool_fault_diagnosis_skills.py" "$@"

echo "tool-fault-diagnosis install command finished."
echo "Restart your agent client to load updated skill metadata."
