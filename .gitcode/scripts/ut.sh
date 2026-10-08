#!/bin/bash
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

set -x
echo $(grep -E "^VERSION_ID=" /etc/os-release | cut -d'"' -f2)
if sudo update-alternatives --set gcc /usr/bin/gcc-16 2>/dev/null; then
    echo "Switched to gcc-16"
elif sudo update-alternatives --set gcc /usr/bin/gcc-15 2>/dev/null; then
    echo "Switched to gcc-15"
elif sudo update-alternatives --set gcc /usr/bin/gcc-14 2>/dev/null; then
    echo "gcc-16/15 not available, fell back to gcc-14"
fi

if gcc --version | head -n1 | grep -q "15\."; then
    rm -rf /home/jenkins/opensource/lib_cache
    if [ -d /home/jenkins/opensource/gcc15 ]; then
        rm -rf /home/jenkins/opensource/gcc15/lib_cache/abseil-cpp
        rm -rf /home/jenkins/opensource/gcc15/lib_cache/device/abseil-cpp
        ln -s /home/jenkins/opensource/gcc15/lib_cache/ /home/jenkins/opensource/lib_cache
    elif [ -d /home/jenkins/opensource/gcc15x86 ]; then
        rm -rf /home/jenkins/opensource/gcc15x86/lib_cache/abseil-cpp
        rm -rf /home/jenkins/opensource/gcc15x86/lib_cache/device/abseil-cpp
        ln -s /home/jenkins/opensource/gcc15x86/lib_cache/ /home/jenkins/opensource/lib_cache
    fi
elif gcc --version | head -n1 | grep -q "14\."; then
    gcc --version
else
    gcc --version
    rm -rf /home/jenkins/opensource/lib_cache
    ln -s /home/jenkins/opensource/ubuntu20/lib_cache /home/jenkins/opensource/lib_cache
fi
gcc --version
source /home/jenkins/Ascend/cann/bin/setenv.bash
set +e

CANN_3RD_LIB_PATH="${CANN_3RD_LIB_PATH:-/home/jenkins/opensource}"
UT_ALLOWED_BRANCHES="master 9.2.0"

if [ -n "${TARGET_BRANCH}" ] && echo " ${UT_ALLOWED_BRANCHES} " | grep -q " ${TARGET_BRANCH} "; then
    case "${ut_type}" in
        asys)
            bash build.sh -u --component asys --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}" --cov
            ret=$?
            coverage_save="true"
            ;;
        msaicerr)
            bash build.sh -u --component msaicerr --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}" --cov
            ret=$?
            coverage_save="true"
            ;;
        msprof)
            bash build.sh -u --component msprof --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}" --cov
            ret=$?
            coverage_save="true"
            ;;
        ut_package)
            bash build.sh --make_clean --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}"
            ret=$?
            if [ $ret -eq 0 ]; then
                bash scripts/run_tests.sh --component install --st
                test_ret=$?
                [ $test_ret -eq 0 ] || ret=$test_ret
                bash scripts/run_tests.sh --component upgrade --st
                test_ret=$?
                [ $test_ret -eq 0 ] || ret=$test_ret
                bash scripts/run_tests.sh --component uninstall --st
                test_ret=$?
                [ $test_ret -eq 0 ] || ret=$test_ret
            fi
            coverage_save="false"
            ;;
        *)
            echo "Skip UT test execution for ${ut_type} on ${TARGET_BRANCH} branch"
            exit 0
            ;;
    esac
else
    bash build.sh --make_clean -u --cann_3rd_lib_path="${CANN_3RD_LIB_PATH}"
    ret=$?
    coverage_save="false"
fi

if [ $ret -ne 200 ] && [ $ret -ne 0 ]; then
    echo "run ut fail"
    exit 1
fi
if [ $ret -eq 0 ]; then
    if [ "$coverage_save" = "true" ];then
    echo "ut_process=coverage" >> $ATOMGIT_OUTPUT
    else
    echo "ut_process=ut_cov" >> $ATOMGIT_OUTPUT
    fi
fi
exit 0
