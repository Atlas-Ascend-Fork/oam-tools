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

is_for_all="${is_for_all:-n}"
is_quiet="${is_quiet:-n}"


if [ "$(id -u)" != "0" ]; then
    _LOG_PATH=$(echo "${HOME}")"/var/log/ascend_seclog"
    _INSTALL_LOG_FILE="${_LOG_PATH}/ascend_install.log"
    _OPERATE_LOG_FILE="${_LOG_PATH}/operation.log"
else
    _LOG_PATH="/var/log/ascend_seclog"
    _INSTALL_LOG_FILE="${_LOG_PATH}/ascend_install.log"
    _OPERATE_LOG_FILE="${_LOG_PATH}/operation.log"
fi

# The common logging functions can be called immediately after this file is
# sourced, before the caller has performed its own log setup.
mkdir -p "${_LOG_PATH}" 2>/dev/null
touch "${_INSTALL_LOG_FILE}" "${_OPERATE_LOG_FILE}" 2>/dev/null

# log functions
getdate() {
    _cur_date=$(date +"%Y-%m-%d %H:%M:%S")
    echo "${_cur_date}"
}

logandprint() {
    is_error_level=$(echo $1 | grep -E 'ERROR|WARN|INFO')
    if [ "${is_quiet}" != "y" ] || [ "${is_error_level}" != "" ]; then
        echo "[Oam-Tools] [$(getdate)] ""$1"
    fi
    echo "[Oam-Tools] [$(getdate)] ""$1" >> "${_INSTALL_LOG_FILE}"
}

# create opapi soft link
createrelativelysoftlink() {
    local src_path_="$1"
    local dst_path_="$2"
    local dst_parent_path_=$(dirname ${dst_path_})
    # echo "dst_parent_path_: ${dst_parent_path_}"
    local relative_path_=$(realpath --relative-to="$dst_parent_path_" "$src_path_")
    # echo "relative_path_: ${relative_path_}"
    if [ -L "$2" ]; then
        return 0
    fi
    ln -s "${relative_path_}" "${dst_path_}" 2> /dev/null
    if [ "$?" != "0" ]; then
        return 1
    else
        return 0
    fi
}

change_mode() {
    local _mode=$1
    local _path=$2
    local _type=$3
    if [ ! x"${is_for_all}" = "x" ] && [ ${is_for_all} = y ]; then
        _mode="$(expr substr $_mode 1 2)$(expr substr $_mode 2 1)"
    fi
    if [ "${_type}" = "dir" ]; then
        find "${_path}" -type d -exec chmod ${_mode} {} \; 2> /dev/null
    elif [ "${_type}" = "file" ]; then
        find "${_path}" -type f -exec chmod ${_mode} {} \; 2> /dev/null
    fi
}

change_file_mode() {
    local _mode=$1
    local _path=$2
    change_mode ${_mode} "${_path}" "file"
}

change_dir_mode() {
    local _mode=$1
    local _path=$2
    change_mode ${_mode} "${_path}" "dir"
}
