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


BASEPATH=$(cd "$(dirname $0)"; pwd)
SCRIPT_DIR="${BASEPATH}"
BUILD_RELATIVE_PATH="build"
BUILD_OUT="build_out"
CORE_NUMS=$(cat /proc/cpuinfo| grep "processor"| wc -l)

# print usage message
dotted_line="----------------------------------------------------------------"
usage() {
    echo "Usage:"
    echo ""
    echo "    -h, --help     Print usage"
    echo "    -v, --verbose  Display build command"
    echo "Default Build Pkg Options:"
    echo $dotted_line
    echo "    -j<N>          Set the number of threads used for building oam_tools, default is 8"
    echo "    -O<N>          Compile optimization options, support [O0 O1 O2 O3], default is O2"
    echo "    --make_clean "
    echo "                   Make clean and delete build directory, bundle directory, and version file"
    echo "    --build-type=<TYPE>"
    echo "                   Specify build type (TYPE options: Release/Debug), default is Release"
    echo "    --pkg-type=<TYPE>"
    echo "                   Specify package type (TYPE option: run/rpm/deb/deb,rpm/all), Default: run"
    echo "    --pkg          Alias for --pkg-type=run (build run package; default behavior)"
    echo "    --ascend_install_path=<PATH>"
    echo "                   Set ascend package install path, default /usr/local/Ascend/cann"
    echo "    --cann_3rd_lib_path=<PATH>"
    echo "                   Set ascend third_party package install path, default ./third_party"
    echo "    --bundle_branch=<NAME>"
    echo "                   Set the branch whose closed-source bundle to download (e.g. master, 9.1.0)."
    echo "                   Default: auto-detected from git; falls back to master."
    echo "    --extra-cmake-args=<ARGS>"
    echo "                   Optional CMake variable in NAME=VALUE format, e.g. PROFILING_ANALYSIS=OFF."
    echo "                   May be specified multiple times; applies to the main OAM tools build."
    echo "                   NAME=VALUE may contain only letters, digits, '_', '.', '/', and '-'."
    echo "    --module_extension=<VALUE>"
    echo "                   Set module extension value, default empty"
    echo "    --target=<TARGET>"
    echo "                   Build only the specified profiling target (msprofbin/acp)."
    echo "                   Ignored with a WARNING when --pkg or --pkg-type is specified."
    echo "Test Options:"
    echo $dotted_line
    echo "    -u             Build and run all unit tests"
    echo "    --noexec       Only compile ut, do not execute"
    echo "    --cov          Enable code coverage for unit tests"
    echo "    --component <name>"
    echo "                   Specify component to test:"
    echo "                   host, asys, msaicerr, msprof, install, upgrade, uninstall, all (default: all)"
    echo "    --ut           Run UT tests only (default when -u is specified)"
    echo "    --st           Run ST tests only"
    echo ""
}

# parse and set options
checkopts() {
    VERBOSE=""
    THREAD_NUM=8
    ENABLE_UT="off"
    MAKE_CLEAN_ALL="off"
    EXEC_TEST="off"
    BUILD_TYPE="Release"
    PACKAGE_TYPE="run"
    BUILD_MODE=""
    ENABLE_COVERAGE="off"
    TEST_COMPONENT="all"
    RUN_UT_ONLY="off"
    RUN_ST_ONLY="off"
    # 必须显式清空：否则环境里同名变量会被当成"用户显式指定"透传给 CMake，
    # 既盖掉配置期的 git 探测，又绕过下方 --bundle_branch 解析处的字符校验。
    BUNDLE_BRANCH=""
    EXTRA_CMAKE_ARGS=""
    MODULE_EXT=""
    BUILD_TARGET=""
    PACKAGE_OPTION_SPECIFIED="off"
    EFFECTIVE_BUILD_TARGET=""

    if [[ -n "${ASCEND_HOME_PATH}" ]]; then
        echo "env exists ASCEND_HOME_PATH : ${ASCEND_HOME_PATH}"
    elif [ $UID -eq 0 ]; then
        export ASCEND_HOME_PATH=/usr/local/Ascend/latest
    else
        export ASCEND_HOME_PATH=~/Ascend/latest
    fi
    ASCEND_INSTALL_PATH="${ASCEND_HOME_PATH}"
    CANN_3RD_LIB_PATH="$BASEPATH/third_party"

    # Process the options
    parsed_args=$(getopt -a -o j:hvuO: -l help,verbose,cov,make_clean,build-type:,pkg-type:,noexec,ascend_install_path:,pkg,asan,cann_3rd_lib_path:,bundle_branch:,extra-cmake-args:,target:,component:,ut,st,module_extension: -- "$@") || {
    usage
    exit 1
    }

    eval set -- "$parsed_args"

    while true; do
    case "$1" in
        -h | --help)
        usage
        exit 0
        ;;
        -j)
        THREAD_NUM="$2"
        shift 2
        ;;
        -v | --verbose)
        VERBOSE="VERBOSE=1"
        shift
        ;;
        -u)
        ENABLE_UT="on"
        EXEC_TEST="on"
        shift
        ;;
        -O)
        BUILD_MODE="-O$2"
        shift 2
        ;;
        --cov)
        ENABLE_COVERAGE="on"
        shift
        ;;
        --make_clean)
        MAKE_CLEAN_ALL="on"
        shift
        ;;
        --build-type)
        BUILD_TYPE=$2
        shift 2
        ;;
        --pkg-type)
        PACKAGE_OPTION_SPECIFIED="on"
        # 取值集合与 cann-cmake function/prepare.cmake 的 CPACK_GENERATOR 分支保持一致：
        # run(External) / rpm / deb / deb,rpm(DEB;RPM) / all(DEB;RPM;External)
        case "$2" in
          run|rpm|deb|deb,rpm|all) ;;
          *) usage && echo "Error: Invalid value '$2' for option '$1'" && exit 1 ;;
        esac
        PACKAGE_TYPE="$2"
        shift 2
        ;;
        --noexec)
        EXEC_TEST="off"
        shift
        ;;
        --ascend_install_path)
        ASCEND_HOME_PATH="$(realpath $2)"
        shift 2
        ;;
        --cann_3rd_lib_path)
        CANN_3RD_LIB_PATH="$(realpath $2)"
        shift 2
        ;;
        --bundle_branch)
        BUNDLE_BRANCH="$2"
        # 只允许 git ref 常见字符：CMAKE_ARGS 在 cmake ${cmake_args} .. 处是非引号展开，
        # 分支名若含空格/引号/shell 元字符会被二次解析。此处拒绝而非加引号包裹，
        # 因为包裹后引号会作为字面量传给 CMake（见下方拼装处注释）。
        if [[ ! "${BUNDLE_BRANCH}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
            echo "ERROR: invalid --bundle_branch '${BUNDLE_BRANCH}': only [A-Za-z0-9._/-] allowed."
            exit 1
        fi
        shift 2
        ;;
        --extra-cmake-args)
        if [[ ! "$2" =~ ^[A-Za-z0-9_]+=[A-Za-z0-9._/-]*$ ]]; then
            echo "ERROR: invalid --extra-cmake-args '$2': expected NAME=VALUE without spaces or shell metacharacters."
            exit 1
        fi
        EXTRA_CMAKE_ARGS="${EXTRA_CMAKE_ARGS:+${EXTRA_CMAKE_ARGS} }-D$2"
        shift 2
        ;;
        --module_extension)
        MODULE_EXT="$2"
        # 只允许构建取值常见字符：CMAKE_ARGS 在 cmake_generate_make 里是 cmake ${cmake_args} .. 非引号展开，
        # 取值若含空格/引号/shell 元字符会被二次解析，导致 CMake 收到错误参数甚至引发注入风险，
        # 与 --bundle_branch、--extra-cmake-args 的校验策略保持一致。
        if [[ ! "${MODULE_EXT}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
            echo "ERROR: invalid --module_extension '${MODULE_EXT}': only [A-Za-z0-9._/-] allowed."
            exit 1
        fi
        shift 2
        ;;
        --target)
        case "$2" in
          msprofbin|acp) BUILD_TARGET="$2" ;;
          *) usage && echo "Error: Invalid value '$2' for option '--target'" && exit 1 ;;
        esac
        shift 2
        ;;
        --asan)
        ENABLE_ASAN="on"
        shift
        ;;
        --component)
        TEST_COMPONENT="$2"
        shift 2
        ;;
        --ut)
        RUN_UT_ONLY="on"
        shift
        ;;
        --st)
        RUN_ST_ONLY="on"
        shift
        ;;
        --pkg)
        PACKAGE_OPTION_SPECIFIED="on"
        shift
        ;;
        --)
        shift
        break
        ;;
        *)
        echo "Undefined option: $1"
        usage
        exit 1
        ;;
    esac
    done
}

mk_dir() {
    local create_dir="$1"
    mkdir -pv "${create_dir}"
    echo "created ${create_dir}"
}

# 安全删除目录：非空判断 + 存在性检查 + 恢复写权限后再删除，禁止 rm -rf。
safe_rm_dir() {
    local dir_path="$1"
    if [ -z "${dir_path}" ] || [ ! -d "${dir_path}" ]; then
        return
    fi
    chmod -R u+w "${dir_path}" 2>/dev/null
    rm -r -- "${dir_path}"
}

clean_cpack_staging() {
    local build_path="$1"
    local cpack_path="${build_path%/}/_CPack_Packages"

    if [ -z "${build_path}" ] || [ -z "${cpack_path}" ]; then
        return
    fi

    echo "clear cpack staging directory"
    safe_rm_dir "${cpack_path}"
}

print_success() {
  echo
  echo $dotted_line
  local msg="$1"
  echo -e "${COLOR_GREEN}[SUCCESS] ${msg}${COLOR_RESET}"
  echo $dotted_line
  echo
}

# oam_tools build start
cmake_generate_make() {
    local build_path="$1"
    local cmake_args="$2"
    if [[ "${MAKE_CLEAN_ALL}" == "on" ]];then
        echo "clear all files in build directory"
        safe_rm_dir "${build_path}"
    fi
    mk_dir "${build_path}"
    cd "${build_path}"
    [ -f CMakeCache.txt ] && rm CMakeCache.txt
    [ -f Makefile ] && rm Makefile
    [ -f cmake_install.cmake ] && rm cmake_install.cmake
    [ -d CMakeFiles ] && safe_rm_dir CMakeFiles
    echo "${cmake_args}"
    cmake ${cmake_args} ..
    if [ 0 -ne $? ]; then
        echo "execute command: cmake ${cmake_args} .. failed."
        exit 1
    fi
}

REPOSITORY_NAME="oam"

# create build path
build_oam_tools() {
    echo "ARCH: $(arch)"
    # === 新增判断逻辑 ===
    # 1. 先处理 --make_clean：清理 bundle 目录
    if [[ "${MAKE_CLEAN_ALL}" == "on" ]]; then
        echo "--make_clean: clearing bundle directory"
        safe_rm_dir "bundle"
    fi

    # 2. 处理 --make_clean：清理 submodule 目录（msprof, msprobe）
    if [[ "${MAKE_CLEAN_ALL}" == "on" ]]; then
        echo "--make_clean: clearing submodule directory (msprof, msprobe)"
        safe_rm_dir "submodule"
    fi

    # === 判断逻辑结束 ===
    # bundle 闭源包拉取/解压已迁至 cmake/install_bundle.cmake；
    # msprof wheel 构建与 msaccucmp/compare 同步已迁至 cmake/build_submodules.cmake，
    # 均由 cmake 配置期负责，此处不再调用。
    echo "create build directory and build oam_tools"
    cd "${BASEPATH}"
    ENABLE_BINARY=TRUE
    if [[ "${BUILD_TARGET}" != "" && "${PACKAGE_OPTION_SPECIFIED}" == "off" ]]; then
        EFFECTIVE_BUILD_TARGET="${BUILD_TARGET}"
    else
        EFFECTIVE_BUILD_TARGET=""
    fi
    if [[ "${BUILD_TARGET}" != "" && "${PACKAGE_OPTION_SPECIFIED}" == "on" ]]; then
        echo "WARNING: --target is ignored when packaging is enabled; the full packaging build will be executed."
    fi
    if [[ -n "${EFFECTIVE_BUILD_TARGET}" && ( "${ENABLE_UT}" == "on" || "${ENABLE_COVERAGE}" == "on" ) ]]; then
        echo "WARNING: --ut/--cov are ignored in target build mode; UT/COV configuration and test execution are skipped."
    fi
    BUILD_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}"
    BUILD_OUT_PATH="${BASEPATH}/${BUILD_OUT}"
    ENABLE_PACKAGE="TRUE"
    if [[ -n "${EFFECTIVE_BUILD_TARGET}" ]]; then
        ENABLE_PACKAGE="FALSE"
    fi
    CMAKE_ARGS="\
    -DCMAKE_INSTALL_PREFIX=${BUILD_PATH} \
    -DENABLE_UT=${ENABLE_UT} \
    -DASCEND_INSTALL_PATH=${ASCEND_INSTALL_PATH} \
    -DCANN_3RD_LIB_PATH=${CANN_3RD_LIB_PATH} \
    -DDCMAKE_WGET_FLAGS='--no-check-certificate' \
    -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
    -DBUILD_MODE=${BUILD_MODE} \
    -DENABLE_GCOV=${ENABLE_COVERAGE} \
    -DENABLE_ASAN=${ENABLE_ASAN} \
    -DENABLE_UT=${ENABLE_UT} \
    -DENABLE_SIGN=${ENABLE_SIGN} \
    -DBUILD_OPEN_PROJECT=ON\
    -DENABLE_PACKAGE=${ENABLE_PACKAGE} \
    -DPACKAGE_TYPE=${PACKAGE_TYPE}"
    if [[ -n "${EFFECTIVE_BUILD_TARGET}" ]]; then
        CMAKE_ARGS="${CMAKE_ARGS} -DOAM_BUILD_TARGET=${EFFECTIVE_BUILD_TARGET}"
    fi
    # 仅在用户显式指定 --bundle_branch 时透传；不传则由 cmake 配置期 git 探测决定。
    # 不给取值加引号：CMAKE_ARGS 在 cmake_generate_make 里是 cmake ${cmake_args} .. 非引号展开，
    # 引号会作为字面量进入 CMake（OAM_BUNDLE_BRANCH 变成 "9.1.0" 而非 9.1.0），白名单校验必然失配。
    # 取值合法性已在 --bundle_branch 解析处校验，此处无需再防 shell 元字符。
    if [ -n "${BUNDLE_BRANCH}" ]; then
        CMAKE_ARGS="${CMAKE_ARGS} -DOAM_BUNDLE_BRANCH=${BUNDLE_BRANCH}"
    fi
    if [ -n "${EXTRA_CMAKE_ARGS}" ]; then
        CMAKE_ARGS="${CMAKE_ARGS} ${EXTRA_CMAKE_ARGS}"
    fi
    # --module_extension 透传 MODULE_EXT 给 CMake：需要差异化模块扩展的形态由工程侧构建时使能；
    # 默认空值，不传该参数时行为不变。
    if [ -n "${MODULE_EXT}" ]; then
        CMAKE_ARGS="${CMAKE_ARGS} -DMODULE_EXT=${MODULE_EXT}"
    fi
    cmake_generate_make "${BUILD_PATH}" "${CMAKE_ARGS}"

    if [[ -n "${EFFECTIVE_BUILD_TARGET}" ]]; then
        case "${EFFECTIVE_BUILD_TARGET}" in
            msprofbin) BUILD_TARGETS="msprofbin" ;;
            acp) BUILD_TARGETS="acp profinj" ;;
        esac
        cmake --build "${BUILD_PATH}" --target ${BUILD_TARGETS} --parallel "${THREAD_NUM}"
        return $?
    fi
    # make package 前清理历史产物，避免旧 cann*.run/rpm/deb 被误当本次产物搬走。
    rm -f cann*.run cann*.rpm cann*.deb
    make ${VERBOSE} -j${THREAD_NUM} && clean_cpack_staging "${BUILD_PATH}" && make package
    # make package
    if [ 0 -ne $? ]; then
        echo "execute command: make ${VERBOSE} -j${THREAD_NUM} && make install failed."
        return 1
    fi
    # 只搬本次 ${PACKAGE_TYPE} 对应后缀的产物，不按固定顺序扫描，避免残留旧后缀先命中搬错包。
    # deb,rpm 与 all 一次产出多个包，故按取值展开成后缀列表（all 含 run）。
    case "${PACKAGE_TYPE}" in
      all)     PKG_SUFFIXES="deb rpm run" ;;
      deb,rpm) PKG_SUFFIXES="deb rpm" ;;
      *)       PKG_SUFFIXES="${PACKAGE_TYPE}" ;;
    esac
    moved_any="false"
    for sfx in ${PKG_SUFFIXES}; do
        if compgen -G "cann*.${sfx}" > /dev/null 2>&1; then
            mkdir -pv "$BUILD_OUT_PATH"
            mv cann*.${sfx} "$BUILD_OUT_PATH"
            moved_any="true"
        else
            echo "package oam_tools failed: no cann*.${sfx} artifact found"
            return 1
        fi
    done
    if [ "X${moved_any}" != "Xtrue" ]; then
        echo "package oam_tools failed: no artifact found for PACKAGE_TYPE=${PACKAGE_TYPE}"
        return 1
    fi

    echo "oam_tools build success!"
}

# Python-only components have no compiled artefacts and don't need build_oam_tools.
# When -u is used and the requested component is in this list, skip the heavy
# build (cmake/make/cpack/.run packaging, msprof wheel, msprobe staging, etc.).
is_python_only_component() {
    case "$1" in
        host|asys|msaicerr) return 0 ;;
        *) return 1 ;;
    esac
}

generate_asys_chip_handler() {
    echo "---------------- generating chip_handler.py for asys component ----------------"
    cmake -P "${BASEPATH}/src/asys/asys.cmake" || { echo "generate chip_handler.py failed."; exit 1; }
}

main() {
    cd "${BASEPATH}"
    checkopts "$@"
    if [ "$THREAD_NUM" -gt "$CORE_NUMS" ];then
        echo "compile thread num:$THREAD_NUM over core num:$CORE_NUMS, adjust to core num"
        THREAD_NUM=$CORE_NUMS
    fi

    local skip_build="off"
    if [[ "${ENABLE_UT}" == "on" && "${EXEC_TEST}" == "on" ]] && is_python_only_component "${TEST_COMPONENT}"; then
        skip_build="on"
        echo "---------------- skip oam_tools build for python-only component: ${TEST_COMPONENT} ----------------"
        if [[ "${TEST_COMPONENT}" != "host" ]]; then
            generate_asys_chip_handler
        fi
    fi

    if [[ "${skip_build}" == "off" ]]; then
        g++ -v
        echo "---------------- oam_tools build start ----------------"
        build_oam_tools || { echo "oam_tools build failed."; exit 1; }
        echo "---------------- oam_tools build finished ----------------"
    fi

    if [[ "${ENABLE_UT}" == "on" && "${EXEC_TEST}" == "on" ]];then
        if [[ -f "${ASCEND_HOME_PATH}/bin/setenv.bash" ]]; then
            source "${ASCEND_HOME_PATH}/bin/setenv.bash"
        else
            echo "WARNING: ${ASCEND_HOME_PATH}/bin/setenv.bash not found, skipping source"
        fi
        export LD_LIBRARY_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}"/:$LD_LIBRARY_PATH

        local run_tests_args=()
        if [[ "$TEST_COMPONENT" != "all" ]]; then
            run_tests_args+=("--component" "$TEST_COMPONENT")
        fi
        if [[ "$RUN_UT_ONLY" == "on" ]]; then
            run_tests_args+=("--ut")
        fi
        if [[ "$RUN_ST_ONLY" == "on" ]]; then
            run_tests_args+=("--st")
        fi
        if [[ "$ENABLE_COVERAGE" == "on" ]]; then
            run_tests_args+=("--cov")
        fi

        bash "${BASEPATH}/scripts/run_tests.sh" "${run_tests_args[@]}"
        if [ $? -ne 0 ]; then
            echo "Execute run_tests.sh failed."
            exit 1
        fi
        echo "Execute run_tests.sh successful."
    fi
}

main "$@"
