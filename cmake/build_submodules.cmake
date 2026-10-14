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

find_package(Git QUIET)
if (NOT GIT_EXECUTABLE)
    find_program(GIT_EXECUTABLE git)
    if(NOT GIT_EXECUTABLE)
        message(FATAL_ERROR "git not found - required for submodule population")
    endif()
endif()

find_package(Python3 COMPONENTS Interpreter QUIET)
if(NOT Python3_EXECUTABLE)
    find_program(Python3_EXECUTABLE python3)
    if(NOT Python3_EXECUTABLE)
        message(FATAL_ERROR "python3 not found - required for msprof wheel build")
    endif()
endif()

function(oam_populate_submodule NAME GIT_URL RESULT_VAR)
    set(_dest "${OAM_TOOLS_DIR}/submodule/${NAME}")
    # 仅当目录存在且非空时才视为已就绪；空目录（上一轮取源失败留下的残壳）
    # 需重新取源，否则会带着空 submodule 继续、把"取源失败"推迟成更难定位的构建报错。
    if(EXISTS "${_dest}" AND IS_DIRECTORY "${_dest}")
        file(GLOB _dest_entries "${_dest}/*")
        if(_dest_entries)
            message(STATUS "${NAME} submodule already present at ${_dest}")
            set(${RESULT_VAR} "${_dest}" PARENT_SCOPE)
            return()
        endif()
        message(STATUS "${NAME} submodule dir empty, re-populating")
    endif()

    file(MAKE_DIRECTORY "${OAM_TOOLS_DIR}/submodule")

    if(DEFINED CANN_3RD_LIB_PATH AND EXISTS "${CANN_3RD_LIB_PATH}/${NAME}"
        AND IS_DIRECTORY "${CANN_3RD_LIB_PATH}/${NAME}")
        message(STATUS "${NAME} using third_party")
        # copy_directory 失败也要拦截：源目录残缺/权限不足时若不检查返回值，
        # 会得到不完整的 submodule，后续 wheel 构建或 msaccucmp 同步才报错、难定位。
        execute_process(COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CANN_3RD_LIB_PATH}/${NAME}" "${OAM_TOOLS_DIR}/submodule/${NAME}"
            RESULT_VARIABLE _copy_result)
        if(NOT _copy_result EQUAL 0)
            message(FATAL_ERROR
                "copy ${NAME} from ${CANN_3RD_LIB_PATH} failed (${_copy_result})")
        endif()
    else()
        message(STATUS "${NAME} download via git clone")
        execute_process(
            COMMAND ${GIT_EXECUTABLE} clone --depth 1 "${GIT_URL}" "${NAME}"
            WORKING_DIRECTORY "${OAM_TOOLS_DIR}/submodule"
            RESULT_VARIABLE _clone_result
            OUTPUT_VARIABLE _clone_output
            ERROR_VARIABLE _clone_error
        )
        if(NOT _clone_result EQUAL 0)
            message(FATAL_ERROR
                "git clone ${NAME} failed (${_clone_result}):\n${_clone_error}")
        endif()
    endif()

    set(${RESULT_VAR} "${_dest}" PARENT_SCOPE)
endfunction()

# --- msprof analysis：取 profiler run 包，提取 analysis whl 并同步到 msprofbin 源码目录 ---
function(oam_build_msprof_analysis)
    # 1. 获取目标架构：优先 MSPROF_DAILY_ARCH，否则按 host 架构
    if(DEFINED ENV{MSPROF_DAILY_ARCH})
        set(_machine "$ENV{MSPROF_DAILY_ARCH}")
        message(STATUS "msprof analysis: arch overridden by MSPROF_DAILY_ARCH=${_machine}")
    else()
        execute_process(
            COMMAND uname -m
            OUTPUT_VARIABLE _machine
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
    endif()

    # 2. 架构映射。_pkg_arch 用于匹配 run 包名（x86/aarch64），并作为 so 架构
    #    校验的期望值。
    if(_machine STREQUAL "aarch64" OR _machine STREQUAL "arm64")
        set(_pkg_arch "aarch64")
    elseif(_machine STREQUAL "x86_64" OR _machine STREQUAL "amd64")
        set(_pkg_arch "x86")
    else()
        message(FATAL_ERROR "unsupported host arch: ${_machine}")
    endif()

    # 3. 临时目录（每次构建前清理）
    set(_daily_root "${CMAKE_BINARY_DIR}/msprof_analysis_daily")
    set(_pkg_dir "${_daily_root}/package")
    set(_extract_dir "${_daily_root}/extract")
    set(_whl_extract_dir "${_daily_root}/whl_extract")
    file(REMOVE_RECURSE "${_daily_root}")
    file(MAKE_DIRECTORY "${_pkg_dir}")

    # 4~5. 取 run 包：本地包目录存在则用其中的包，否则从每日构建下载。
    #       两条分支都把 run 包落到 ${_pkg_dir}/，之后的解压、取 whl、校验、拷贝链路共用。
    if(EXISTS "${OAM_TOOLS_DIR}/../../build/platform/mindstudio")
        # 匹配到多个无法判定用哪个，直接报错而非随意取一。
        set(_local_pkg_dir "${OAM_TOOLS_DIR}/../../build/platform/mindstudio")
        file(GLOB _local_run_pkgs
            "${_local_pkg_dir}/mindstudio-profiler_*_${_pkg_arch}.run")
        list(LENGTH _local_run_pkgs _local_run_count)
        if(_local_run_count GREATER 1)
            message(FATAL_ERROR
                "msprof analysis: multiple run packages found in ${_local_pkg_dir}, "
                "cannot determine uniquely:\n${_local_run_pkgs}")
        endif()

        # 缺本架构 run 包时打印失败日志后跳过，不阻断构建：msprofbin/CMakeLists.txt
        # 的 if(msprof_whl) 会因目标目录无 whl 而跳过解包与进包声明。必须 return()——
        # 继续往下走会在解压/找 whl 处以 FATAL_ERROR 中止，那就不是"跳过"了。
        if(_local_run_count EQUAL 0)
            message(WARNING
                "msprof analysis: no mindstudio-profiler_*_${_pkg_arch}.run found in "
                "${_local_pkg_dir}, skip msprof analysis whl preparation")
            return()
        endif()

        # 拷进构建目录再改权限：buildplatform 是只读输入，不应在原地 chmod（第 7 步需 755）。
        list(GET _local_run_pkgs 0 _local_run_src)
        message(STATUS "msprof analysis: using local package: ${_local_run_src}")
        file(COPY "${_local_run_src}" DESTINATION "${_pkg_dir}")
        get_filename_component(_run_pkg_name "${_local_run_src}" NAME)
        set(_run_pkg "${_pkg_dir}/${_run_pkg_name}")
    else()
        message(STATUS "msprof analysis: local package dir not found, downloading daily package")
        set(_run_url
            "https://ascend-package.obs.cn-north-4.myhuaweicloud.com/msprof_daily/mindstudio-profiler_1.0.0_${_pkg_arch}.run")
        message(STATUS "msprof analysis: daily package URL: ${_run_url}")
        # 本地文件名从 URL 推导，避免版本号在 URL 和文件名两处硬编码、改一处漏一处。
        get_filename_component(_run_pkg_name "${_run_url}" NAME)
        set(_run_pkg "${_pkg_dir}/${_run_pkg_name}")
        file(DOWNLOAD "${_run_url}" "${_run_pkg}" STATUS _dl_status SHOW_PROGRESS TIMEOUT 600)
        list(GET _dl_status 0 _dl_rc)
        if(NOT _dl_rc EQUAL 0)
            list(GET _dl_status 1 _dl_msg)
            message(FATAL_ERROR "msprof analysis: download failed (rc=${_dl_rc}): ${_dl_msg}")
        endif()
    endif()

    # 6. 校验 run 包存在且大小 > 0
    if(NOT EXISTS "${_run_pkg}")
        message(FATAL_ERROR "msprof analysis: run package not found: ${_run_pkg}")
    endif()
    file(SIZE "${_run_pkg}" _pkg_size)
    if(_pkg_size EQUAL 0)
        message(FATAL_ERROR "msprof analysis: run package size is 0: ${_run_pkg}")
    endif()
    message(STATUS "msprof analysis: run package ${_pkg_size} bytes")

    # 7. 解压 run 包
    execute_process(COMMAND chmod 755 "${_run_pkg}")
    execute_process(
        COMMAND "${_run_pkg}" --noexec --extract=${_extract_dir}
        RESULT_VARIABLE _extract_rc
        OUTPUT_VARIABLE _extract_out
        ERROR_VARIABLE _extract_err
    )
    if(NOT _extract_rc EQUAL 0)
        message(FATAL_ERROR "msprof analysis: run package extract failed (rc=${_extract_rc}):\n${_extract_err}")
    endif()

    # 8. 查找 analysis whl（GLOB_RECURSE 自动递归子目录）
    file(GLOB_RECURSE _whl_candidates "${_extract_dir}/msprof-*-py3-none-any.whl")
    list(LENGTH _whl_candidates _whl_count)
    if(_whl_count EQUAL 0)
        message(FATAL_ERROR "msprof analysis: no msprof-*-py3-none-any.whl found in ${_extract_dir}")
    endif()
    if(_whl_count GREATER 1)
        message(FATAL_ERROR "msprof analysis: multiple whl candidates found, cannot determine uniquely:\n${_whl_candidates}")
    endif()
    list(GET _whl_candidates 0 _whl_src)
    message(STATUS "msprof analysis: found whl: ${_whl_src}")

    # 9. 解压 whl 到临时目录，校验 msprof_analysis.so 存在
    file(MAKE_DIRECTORY "${_whl_extract_dir}")
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -m zipfile -e "${_whl_src}" "${_whl_extract_dir}"
        RESULT_VARIABLE _whl_unzip_rc
    )
    if(NOT _whl_unzip_rc EQUAL 0)
        message(FATAL_ERROR "msprof analysis: whl unzip failed (rc=${_whl_unzip_rc})")
    endif()
    file(GLOB_RECURSE _so_candidates "${_whl_extract_dir}/**/msprof_analysis.so")
    list(LENGTH _so_candidates _so_count)
    if(_so_count EQUAL 0)
        message(FATAL_ERROR "msprof analysis: msprof_analysis.so not found in whl: ${_whl_src}")
    endif()
    list(GET _so_candidates 0 _so_path)
    message(STATUS "msprof analysis: found msprof_analysis.so: ${_so_path}")

    # 10. native so 架构校验
    find_program(FILE_CMD file)
    if(FILE_CMD)
        execute_process(
            COMMAND ${FILE_CMD} "${_so_path}"
            OUTPUT_VARIABLE _so_file_out
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        message(STATUS "msprof analysis: so file type: ${_so_file_out}")
        if(_pkg_arch STREQUAL "aarch64" AND NOT _so_file_out MATCHES "aarch64")
            message(FATAL_ERROR "msprof analysis: msprof_analysis.so arch mismatch (expected aarch64): ${_so_file_out}")
        endif()
        if(_pkg_arch STREQUAL "x86" AND NOT _so_file_out MATCHES "x86-64")
            message(FATAL_ERROR "msprof analysis: msprof_analysis.so arch mismatch (expected x86-64): ${_so_file_out}")
        endif()
    endif()

    # 11. 拷贝 whl 到 msprofbin 源码目录（先删旧 whl，版本字段可变）
    set(_msprof_whl_dst "${OAM_TOOLS_DIR}/src/msprof/collector/dvvp/msprofbin")
    file(GLOB _old_whls "${_msprof_whl_dst}/msprof-*-py3-none-any.whl")
    foreach(_old ${_old_whls})
        file(REMOVE "${_old}")
    endforeach()
    file(COPY "${_whl_src}"
        DESTINATION "${_msprof_whl_dst}"
        FILE_PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ
    )
    message(STATUS "msprof analysis: whl copied to ${_msprof_whl_dst}")
endfunction()

# --- build adump analysis：同步 msaccucmp 到 operator_cmp/msaccucmp/compare ---
# 优先用兄弟目录 mindstudio/msaccucmp，否则填充 submodule/msprobe。
function(oam_build_msaccucmp_analysis)
    if(EXISTS "${OAM_TOOLS_DIR}/../../mindstudio/msaccucmp")
        message(STATUS "msprobe using mindstudio")
        set(_msaccucmp_src
            "${OAM_TOOLS_DIR}/../../mindstudio/msaccucmp/python/msprobe/msaccucmp")
    else()
        oam_populate_submodule("msprobe" "https://gitcode.com/Ascend/msprobe.git"
            _msprobe_dir)
        set(_msaccucmp_src "${_msprobe_dir}/python/msprobe/msaccucmp")
    endif()

    set(_compare_dst "${OAM_TOOLS_DIR}/src/operator_cmp/msaccucmp/compare")
    # file(COPY) 对不存在的源目录会静默跳过，导致 compare/ 变成空目录、operator_cmp
    # 打包内容缺失。显式校验源目录存在再拷。
    if(NOT IS_DIRECTORY "${_msaccucmp_src}")
        message(FATAL_ERROR "msaccucmp source dir not found: ${_msaccucmp_src}")
    endif()
    # 先删后拷 + 规范权限：消除只读源带来的只读产物，保证重复构建可覆盖。
    file(REMOVE_RECURSE "${_compare_dst}")
    file(MAKE_DIRECTORY "${_compare_dst}")
    file(COPY "${_msaccucmp_src}/"
        DESTINATION "${_compare_dst}"
        FILE_PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ
        DIRECTORY_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
                              GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
    )
endfunction()

if(DEFINED PROFILING_ANALYSIS)
    string(TOUPPER "${PROFILING_ANALYSIS}" _profiling_analysis_upper)
endif()
if(DEFINED PROFILING_ANALYSIS AND _profiling_analysis_upper STREQUAL "OFF")
    message(STATUS "msprof analysis: PROFILING_ANALYSIS=OFF, skip msprof analysis whl preparation")
else()
    oam_build_msprof_analysis()
endif()
oam_build_msaccucmp_analysis()
