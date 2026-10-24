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

_CURR_OPERATE_USER="$(id -nu 2> /dev/null)"
_CURR_OPERATE_GROUP="$(id -ng 2> /dev/null)"
_DEFAULT_INSTALL_PATH=/usr/local/Ascend
# defaults for general user
if [ "$(id -u)" != "0" ]; then
    _DEFAULT_USERNAME="${_CURR_OPERATE_USER}"
    _DEFAULT_USERGROUP="${_CURR_OPERATE_GROUP}"
    _DEFAULT_INSTALL_PATH="${HOME}/Ascend"
fi

# run package's files info
_CURR_PATH=$(dirname $(readlink -f $0))
_VERSION_INFO_FILE="${_CURR_PATH}""/../version.info"
_FILELIST_FILE="${_CURR_PATH}""/filelist.csv"
_COMMON_PARSER_FILE="${_CURR_PATH}""/install_common_parser.sh"
SCENE_FILE="${_CURR_PATH}""/../scene.info"
platform_data=$(grep -e "arch" "$SCENE_FILE" | cut --only-delimited -d"=" -f2-)
ops_base_platform_old_dir=oam-tools_$platform_data-linux
ops_base_platform_dir=oam_tools
upper_ops_base_platform=$(echo "${ops_base_platform_dir}" | tr 'a-z' 'A-Z')


_INSTALL_INFO_SUFFIX="${ops_base_platform_dir}/ascend_install.info"
_VERSION_INFO_SUFFIX="${ops_base_platform_dir}/version.info"

_COMMON_INC_FILE="${_CURR_PATH}/common_func.inc"
COMMON_FUNC_V2_PATH="${_CURR_PATH}/common_func_v2.inc"
VERSION_CFG="${_CURR_PATH}/version_cfg.inc"
_OPP_COMMON_FILE="${_CURR_PATH}/oam_common.sh"
. "${_COMMON_INC_FILE}"
. "${COMMON_FUNC_V2_PATH}"
. "${VERSION_CFG}"
. "${_OPP_COMMON_FILE}"

PARAM_INVALID="0x0002"
INSTALL_FAILED="0x0000"
INSTALL_FAILED_DES="Update successfully."
FILE_READ_FAILED="0x0082"
FILE_READ_FAILED_DES="File read failed."
FILE_WRITE_FAILED="0x0081"
FILE_WRITE_FAILED_DES="File write failed."
PERM_DENIED="0x0093"
PERM_DENIED_DES="Permission denied."

logwitherrorlevel() {
    _ret_status="$1"
    _level="$2"
    _msg="$3"
    if [ "${_ret_status}" != 0 ]; then
        if [ "${_level}" = "error" ]; then
            logandprint "${_msg}"
            exit 1
        else
            logandprint "${_msg}"
        fi
    fi
}

#check ascend_install.info for the change in code warning
checkascendinfo() {
    file_param="${version_install_dir}/${_INSTALL_INFO_SUFFIX}"
    if [ -f "${file_param}" ]; then
        inst_type=$(cat ${file_param} | grep "Opp_Install_Type" | awk -F = '{print $2}')
        uname_param=$(cat ${file_param} | grep "UserName" | awk -F = '{print $2}')
        ugroup_param=$(cat ${file_param} | grep "UserGroup" | awk -F = '{print $2}')
        path_param=$(cat ${file_param} | grep "Opp_Install_path_Param" | awk -F = '{print $2}')
        path_params=$(cat ${file_param} | grep "Opp_Install_Path_Param" | awk -F = '{print $2}')
        version_param=$(cat ${file_param} | grep "Opp_Version" | awk -F = '{print $2}')
        if [ "$inst_type" != "" ]; then
            echo "${upper_ops_base_platform}_INSTALL_TYPE=${inst_type}" >> ${file_param}
        fi
        if [ "$uname_param" != "" ]; then
            echo "USERNAME=${uname_param}" >> ${file_param}
        fi
        if [ "$ugroup_param" != "" ]; then
            echo "USERGROUP=${ugroup_param}" >> ${file_param}
        fi
        if [ "$path_param" != "" ]; then
		echo "${upper_ops_base_platform}_INSTALL_PATH_VAL=${path_param}" >> ${file_param}
        fi
        if [ "$path_params" != "" ]; then
            echo "${upper_ops_base_platform}_INSTALL_PATH_PARAM=${path_params}" >> ${file_param}
        fi

        if [ "$version_param" != "" ]; then
            echo "${upper_ops_base_platform}_VERSION=${version_param}" >> ${file_param}
        fi
    fi
}

# keys of infos in ascend_install.info
KEY_INSTALLED_UNAME="USERNAME"
KEY_INSTALLED_UGROUP="USERGROUP"
KEY_INSTALLED_TYPE="${upper_ops_base_platform}_INSTALL_TYPE"
KEY_INSTALLED_FEATURE="${upper_ops_base_platform}_Install_Feature"
KEY_INSTALLED_CHIP="${upper_ops_base_platform}_INSTALL_CHIP"
KEY_INSTALLED_PATH="${upper_ops_base_platform}_INSTALL_PATH_VAL"
KEY_INSTALLED_VERSION="${upper_ops_base_platform}_VERSION"
getinstalledinfo() {
    _key="$1"
    _res=""
    if [ -f "${_INSTALL_INFO_FILE}" ]; then
        chmod 644 "${_INSTALL_INFO_FILE}"> /dev/null 2>&1
        checkascendinfo
        case "${_key}" in
        USERNAME)
            res=$(cat ${_INSTALL_INFO_FILE} | grep "USERNAME" | awk -F = '{print $2}')
            ;;
        USERGROUP)
            res=$(cat ${_INSTALL_INFO_FILE} | grep "USERGROUP" | awk -F = '{print $2}')
            ;;
        ${upper_ops_base_platform}_INSTALL_TYPE)
            type="INSTALL_TYPE"
            res=$(cat ${_INSTALL_INFO_FILE} | grep "${type}" | awk -F = '{print $2}')
            ;;
        ${upper_ops_base_platform}_INSTALL_PATH_VAL)
            val="INSTALL_PATH_VAL"
            res=$(cat ${_INSTALL_INFO_FILE} | grep ${val} | awk -F = '{print $2}')
            ;;
        ${upper_ops_base_platform}_VERSION)
            version="VERSION"
	        res=$(cat ${_INSTALL_INFO_FILE} | grep ${version} | awk -F = '{print $2}')
            ;;
        ${upper_ops_base_platform}_INSTALL_PATH_PARAM)
            tmp_path_param="INSTALL_PATH_PARAM"
	        res=$(cat ${_INSTALL_INFO_FILE} | grep ${tmp_path_param} | awk -F = '{print $2}')
            ;;
        esac
    fi
    echo "${res}"
}

# keys of infos in run package
KEY_RUNPKG_VERSION="Version"
getrunpkginfo() {
    local _key_param="$1"
    if [ "${_key_param}" = "Version" ] && [ -f "${_VERSION_INFO_FILE}" ]; then
        local _run_pkg_version
        get_version "_run_pkg_version" "${_VERSION_INFO_FILE}"
        echo "${_run_pkg_version}"
    fi
}

updateinstallinfo() {
    _key_val="$1"
    _val="$2"
    _is_new_gen="$3"
    _old_val=$(getinstalledinfo "${_key_val}")
    _target_install_info="${version_install_dir}/$4"
    if [ -f "${_target_install_info}" ]; then
        chmod 644 "${_target_install_info}"
        if [ "${_old_val}"x = ""x ] || [ "${_is_new_gen}" = "true" ]; then
            echo "${_key_val}=${_val}" >> "${_target_install_info}"
        else
            sed -i "/${_key_val}/c ${_key_val}=${_val}" "${_target_install_info}"
        fi
    else
        echo "${_key_val}=${_val}" > "${_target_install_info}"
    fi
}

updatefeatureandchipinfo() {
    _key_val="$1"
    _val="$2"
    _old_val=$(getinstalledinfo "${_key_val}")
    _is_new_gen="$3"
    _target_install_info="${version_install_dir}/$4"
    if [ -f "${_target_install_info}" ]; then
        chmod 644 "${_target_install_info}"
        if [ "${_is_new_gen}" = "true" ]; then
            echo "${_key_val}=${_val}" >> "${_target_install_info}"
        else
            grep_res=$(cat ${_target_install_info} | grep "$_key_val")
            if [ "${grep_res}x" = "x" ]; then
                echo "${_key_val}=${_val}" >> "${_target_install_info}"
            else
                sed -i "/${_key_val}/c ${_key_val}=${_val}" "${_target_install_info}"
            fi
        fi
    else
        echo "${_key_val}=${_val}" > "${_target_install_info}"
    fi
}

updateinstallinfos() {
    _uname="$1"
    _ugroup="$2"
    _type="$3"
    _path="$4"
    in_feature_new="$5"
    chip_type_new="$6"
    _version=$(getrunpkginfo "${KEY_RUNPKG_VERSION}")
    _target_install_dir="${version_install_dir}/${_INSTALL_INFO_SUFFIX}"
    _is_new_gen_param="false"
    if [ ! -f "${_target_install_dir}" ]; then
        _is_new_gen_param="true"
    fi
    updateinstallinfo "${KEY_INSTALLED_UNAME}" "${_uname}" "${_is_new_gen_param}" "${_INSTALL_INFO_SUFFIX}"
    updateinstallinfo "${KEY_INSTALLED_UGROUP}" "${_ugroup}" "${_is_new_gen_param}" "${_INSTALL_INFO_SUFFIX}"
    updateinstallinfo "${KEY_INSTALLED_TYPE}" "${_type}" "${_is_new_gen_param}" "${_INSTALL_INFO_SUFFIX}"
    updatefeatureandchipinfo "${KEY_INSTALLED_FEATURE}" "${in_feature_new}" "${_is_new_gen_param}" "${_INSTALL_INFO_SUFFIX}"
    updateinstallinfo "${KEY_INSTALLED_PATH}" "${_path}" "${_is_new_gen_param}" "${_INSTALL_INFO_SUFFIX}"
    updateinstallinfo "${KEY_INSTALLED_VERSION}" "${_version}" "${_is_new_gen_param}" "${_INSTALL_INFO_SUFFIX}"
    updatefeatureandchipinfo "${KEY_INSTALLED_CHIP}" "${chip_type_new}" "${_is_new_gen_param}" "${_INSTALL_INFO_SUFFIX}"
}

checkfileexist() {
    _path_val="$1"
    if [ ! -f "${_path_val}" ];then
        logandprint "[ERROR]: ERR_NO:${FILE_READ_FAILED};ERR_DES:The file (${_path_val}) does not existed, install failed."
        return 1
    fi
    return 0
}

createsoftlink() {
    _src_path="$1"
    _dst_path="$2"
    if [ -L "$2" ]; then
        logandprint "[WARNING]: Soft link for ops is existed. Cannot create new soft link."
        return 0
    fi
    ln -s "${_src_path}" "${_dst_path}" 2> /dev/null
    if [ "$?" != "0" ]; then
        return 1
    else
        return 0
    fi
}

getinstallpath() {
    docker_root_tmp="$(echo "${docker_root}" | sed "s#/\+\$##g")"
    docker_root_regex="$(echo "${docker_root_tmp}" | sed "s#\/#\\\/#g")"
    relative_path=$(echo "${version_install_dir}" | sed "s/^${docker_root_regex}//g" | sed "s/\/\+\$//g")
    return
}

setenv() {
    logandprint "[INFO]: Set the environment path."
    if [ "${is_docker_install}" = y ] ; then
         install_option="--docker-root=${docker_root}"
    else
        install_option=""
    fi
    if [ "${is_setenv}" = "y" ];then
        install_option="${install_option} --setenv"
    fi
}

# init installation parameters
_TARGET_INSTALL_PATH="$1"
_TARGET_USERNAME="$2"
_TARGET_USERGROUP="$3"
_CHIP_TYPE="$4"
install_type="$5"
is_quiet="$6"
_FIRST_NOT_EXIST_DIR="$7"
is_the_last_dir_opp="$8"
is_for_all="$9"
is_setenv="${10}"
is_docker_install="${11}"
docker_root="${12}"
is_install_path="${13}"
in_feature_new="${14}"
chip_type_new="${15}"
pkg_version_dir="${16}"
#getinstallpath
#relative_path_val=${relative_path}

logandprint "[INFO]: Command oam-tools_install"

in_install_for_all=""
if [ "${is_for_all}" = y ] ; then
    in_install_for_all="--install_for_all"
fi

if [ "${_TARGET_INSTALL_PATH}" = "" ] || [ "${_TARGET_USERNAME}" = "" ] ||
[ "${_TARGET_USERGROUP}" = "" ] || [ "${install_type}" = "" ] ||
[ "${is_quiet}" = "" ]; then
    logandprint "[ERROR]: ERR_NO:${PARAM_INVALID};ERR_DES:Empty parameters is invalid for install."
    exit 1
fi

get_version "pkg_version" "$_VERSION_INFO_FILE"
get_package_upgrade_version_dir "upgrade_version_dir" "$_TARGET_INSTALL_PATH" "${ops_base_platform_dir}"
get_package_upgrade_version_dir "upgrade_old_version_dir" "$_TARGET_INSTALL_PATH" "${ops_base_platform_old_dir}"
get_package_last_installed_version "last_installed" "$_TARGET_INSTALL_PATH" "${ops_base_platform_dir}"
get_package_last_installed_version "last_installed_old" "$_TARGET_INSTALL_PATH" "${ops_base_platform_old_dir}"
last_installed_version=$(echo ${last_installed} | cut --only-delimited -d":" -f2-)
last_installed_old_version=$(echo ${last_installed} | cut --only-delimited -d":" -f2-)

is_multi_version_pkg "pkg_is_multi_version" "$_VERSION_INFO_FILE"
if [ "$pkg_is_multi_version" = "true" ]; then
    version_install_dir=${_TARGET_INSTALL_PATH}/${pkg_version_dir}/share/info
else
    version_install_dir=${_TARGET_INSTALL_PATH}
fi
getinstallpath
relative_path_val=${relative_path}

#Last Installed Version
install_lower_dir=$(ls "${_TARGET_INSTALL_PATH}" 2> /dev/null)
last_version_data=$(echo $install_lower_dir | awk -F ' ' '{print $1}')

# init log file path
_INSTALL_INFO_FILE="${version_install_dir}/${_INSTALL_INFO_SUFFIX}"
if [ ! -f "${_INSTALL_INFO_FILE}" ]; then
    _INSTALL_INFO_FILE="/etc/ascend_install.info"
fi

if [ "$(id -u)" != "0" ]; then
    _LOG_PATH_PERM="740"
    _LOG_FILE_PERM="640"
    _INSTALL_INFO_PERM="600"
    _LOG_PATH_AND_FILE_GROUP="root"
else
    _LOG_PATH_PERM="750"
    _LOG_FILE_PERM="640"
    _INSTALL_INFO_PERM="644"
fi

logandprint "[INFO]: Begin install oam-tools module."
checkfileexist "${_FILELIST_FILE}"
if [ "$?" != 0 ]; then
    exit 1
fi

checkfileexist "${_COMMON_PARSER_FILE}"
if [ "$?" != 0 ]; then
    exit 1
fi

_BUILTIN_PERM="550"
_CUSTOM_PERM="750"
_CREATE_DIR_PERM="750"
_CREATE_FIRST_ASCEND_DIR_PERM="755"
_ONLYREAD_PERM="440"
if [ "${is_for_all}" = y ]; then
    _BUILTIN_PERM="555"
    _CUSTOM_PERM="755"
    _CREATE_DIR_PERM="755"
    _CREATE_FIRST_ASCEND_DIR_PERM="755"
    _ONLYREAD_PERM="444"
fi
if [ "${_FIRST_NOT_EXIST_DIR}" != "" ]; then
    mkdir -p "${version_install_dir}/${ops_base_platform_dir}" 2> /dev/null
    chmod -R "${_CREATE_DIR_PERM}" "${_FIRST_NOT_EXIST_DIR}" 2> /dev/null
    chown -R "${_TARGET_USERNAME}":"${_TARGET_USERGROUP}" "${_FIRST_NOT_EXIST_DIR}" 2> /dev/null
    if [ "$(id -u)" = "0" ] && [ "${is_the_last_dir_opp}" = "0" ]; then
        chmod -R "${_CREATE_FIRST_ASCEND_DIR_PERM}" "${_FIRST_NOT_EXIST_DIR}" 2> /dev/null
        chown -R "root":"root" "${_FIRST_NOT_EXIST_DIR}" 2> /dev/null
    fi
fi
# make the ops_base and the upper folder can write files
is_change_dir_mode="false"
if [ "$(id -u)" != 0 ] && [ ! -w "${version_install_dir}" ]; then
    chmod u+w "${version_install_dir}" 2> /dev/null
    is_change_dir_mode="true"
fi

logandprint "[INFO]: upgradePercentage:30%"

setenv

logandprint "[INFO]: Update the oam-tools install info."

if [ "${in_feature_new}" = "" ]; then
    in_feature_1="--feature=all"
else
    in_feature_1="--feature=${in_feature_new}"
fi

if [ "${chip_type_new}" = "" ]; then
    chip_type_1="--chip=all"
else
    chip_type_1="--chip=${chip_type_new}"
fi

updateinstallinfos "${_TARGET_USERNAME}" "${_TARGET_USERGROUP}" "${install_type}" "${relative_path_val}" "${in_feature_new}" "${chip_type_new}"
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${INSTALL_FAILED};ERR_DES:Update oam-tools install info failed."

# Pre-chmod: restore write access on directories that a prior install may have locked (e.g. 555).
# Required because --copy_all uses "cp -af *" and cannot write into non-writable directories.
_arch_dir=$(uname -m)
if [ -n "${pkg_version_dir}" ]; then
    _copy_root="${_TARGET_INSTALL_PATH}/${pkg_version_dir}"
else
    _copy_root="${_TARGET_INSTALL_PATH}"
fi
if [ -d "${_copy_root}/${_arch_dir}-linux" ]; then
    find "${_copy_root}/${_arch_dir}-linux" -type d ! -perm -u+w -exec chmod u+w {} + 2>/dev/null || true
fi
if [ -d "${_copy_root}/opp" ]; then
    find "${_copy_root}/opp" -type d ! -perm -u+w -exec chmod u+w {} + 2>/dev/null || true
fi

sh "${_COMMON_PARSER_FILE}" --copy_all --package="${ops_base_platform_dir}" --install --username="${_TARGET_USERNAME}" --usergroup="${_TARGET_USERGROUP}" --set-cann-uninstall \
    --version=$pkg_version --version-dir=$pkg_version_dir $install_option  --use-share-info ${in_install_for_all} ${in_feature_1} ${chip_type_1}  "${install_type}" "${_TARGET_INSTALL_PATH}" "${_FILELIST_FILE}"
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${INSTALL_FAILED};ERR_DES:Install oam-tools module files failed."
logandprint "[INFO]: upgradePercentage:50%"

# change installed folder's owner and group except aicpu
subdirs=$(ls "${version_install_dir}/${ops_base_platform_dir}" 2> /dev/null)
chown "${_TARGET_USERNAME}":"${_TARGET_USERGROUP}" "${version_install_dir}/${ops_base_platform_dir}" 2> /dev/null
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${INSTALL_FAILED};ERR_DES:Change oam-tools ownership failed.."

logandprint "[INFO]: upgradePercentage:100%"

logandprint "[INFO]: Installation information listed below:"
logandprint "[INFO]: Install path: (${version_install_dir}/${ops_base_platform_dir})"
logandprint "[INFO]: Install log file path: (${_INSTALL_LOG_FILE})"
logandprint "[INFO]: Operation log file path: (${_OPERATE_LOG_FILE})"

logandprint "[INFO]: Oam-Tools package installed successfully! The new version takes effect immediately."
exit 0
