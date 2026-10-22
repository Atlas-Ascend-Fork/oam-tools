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

# 本脚本为安装包 <cleanup> 生命周期钩子，包管理器在卸载/升级时以解压临时目录
# 为当前目录执行它。删除前校验目标路径（拒绝空路径与根目录），避免脚本在错误
# 目录（家目录、/ 等）执行时递归删除该目录下全部内容。
script_path="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
target_dir="$(pwd -P)"
if [ -z "${target_dir}" ] || [ "${target_dir}" = "/" ] || [ "${target_dir}" = "//" ] || [ "${script_path}" != "${target_dir}/share/info/oam_tools/script" ]; then
    echo "[ERROR]: Refuse unsafe cleanup path: ${target_dir:-<empty>}; lifecycle path: ${script_path}" >&2
    exit 1
fi

echo "[INFO]: Cleanup temp directory: ${target_dir}"

# 解压临时目录中的子目录权限可能为 550（与正式安装路径对齐），需要先恢复 owner
# 写位，否则 rm 无法删除目录中的文件条目，会输出大量 "Permission denied"。
chmod -R u+w "${target_dir}" 2>/dev/null || true
rm -rf -- "${target_dir}"
