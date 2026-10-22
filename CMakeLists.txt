# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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

# 最低版本依据：cmake/install_bundle.cmake 解压闭源包使用 file(ARCHIVE_EXTRACT)，
# 该子命令自 CMake 3.18 引入；低于 3.18 的 cmake 二进制在首次构建或 --make_clean 后
# （bundle 未就绪、配置期须拉包解压）会报 "file sub-command ARCHIVE_EXTRACT is not
# recognized" 并中断。声明 3.18 可在配置最开始即给出明确的版本要求提示
# （与 docs/zh|en/quick_install.md 前置依赖口径一致）。
cmake_minimum_required(VERSION 3.18)
set(OAM_BUILD_TARGET "" CACHE STRING "Build one profiling target")
set_property(CACHE OAM_BUILD_TARGET PROPERTY STRINGS "" msprofbin acp)
if(NOT OAM_BUILD_TARGET STREQUAL "" AND
   NOT OAM_BUILD_TARGET STREQUAL "msprofbin" AND
   NOT OAM_BUILD_TARGET STREQUAL "acp")
    message(FATAL_ERROR "Invalid OAM_BUILD_TARGET='${OAM_BUILD_TARGET}'. Expected empty, msprofbin, or acp.")
endif()
include(cmake/fetch_cann_cmake.cmake)
set(PKG_NAME oam)
project(Oam-Tools)
if(OAM_BUILD_TARGET STREQUAL "")
    message(STATUS "OAM build mode: full")
else()
    message(STATUS "OAM build mode: target=${OAM_BUILD_TARGET}")
endif()

init_cann_project(PREPEND_MODULE_PATH)
add_cann_target_options()

set(CMAKE_C_FLAGS_RELEASE "")
set(CMAKE_CXX_FLAGS_RELEASE "")

include(cmake/intf_pub.cmake)

# install 参数
# OAM_STAGING_DIR：makeself 暂存绝对路径，供配置期 file() 操作用，不随包类型变化。
set(OAM_STAGING_DIR ${CMAKE_BINARY_DIR}/_CPack_Packages/makeself_staging)
# INSTALL_LIBRARY_DIR 按包类型切换：rpm/deb 用相对路径交 CPACK_PACKAGING_INSTALL_PREFIX 收，run 用绝对 staging。
# 取值集合与 cann-cmake function/prepare.cmake 的 CPACK_GENERATOR 分支一致：除 rpm/deb 外
# 还有 deb,rpm(DEB;RPM) 与 all(DEB;RPM;External)，它们同样产出 rpm/deb 包。只判 STREQUAL
# "rpm"/"deb" 会让这两个取值落进 else，拿到绝对 staging 路径而绕过 CPACK_PACKAGING_INSTALL_PREFIX，
# 结果 tools/* 与 lib64/* 不进包载荷（表现为装完缺目录）。"all" 不含 rpm/deb 子串，须单列。
if(PACKAGE_TYPE MATCHES "rpm|deb" OR PACKAGE_TYPE STREQUAL "all")
    set(INSTALL_LIBRARY_DIR .)
    # tools / lib64 用 bare 相对路径，与本文件既有 install 规则（tools/aml/lib64/*、
    # ${CMAKE_SYSTEM_PROCESSOR}-linux/lib64）保持同一形态，避免同包内出现两个 lib64 目录。
    set(INSTALL_TOOLS_DIR tools)
    set(INSTALL_LIB64_DIR ${CMAKE_SYSTEM_PROCESSOR}-linux/lib64)
else()
    set(INSTALL_LIBRARY_DIR ${OAM_STAGING_DIR})
    # run 包保持原有绝对路径结构
    set(INSTALL_TOOLS_DIR ${OAM_STAGING_DIR}/tools)
    set(INSTALL_LIB64_DIR ${OAM_STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64)
endif()

# Ascend mode
if(DEFINED ENV{ASCEND_HOME_PATH})
  set(ASCEND_DIR $ENV{ASCEND_HOME_PATH})
else()
  if ("$ENV{USER}" STREQUAL "root")
    if(EXISTS /usr/local/Ascend/ascend-toolkit/latest)
      set(ASCEND_DIR /usr/local/Ascend/ascend-toolkit/latest)
    else()
      set(ASCEND_DIR /usr/local/Ascend/latest)
    endif()
  else()
    if(EXISTS $ENV{HOME}/Ascend/ascend-toolkit/latest)
      set(ASCEND_DIR $ENV{HOME}/Ascend/ascend-toolkit/latest)
    else()
      set(ASCEND_DIR $ENV{HOME}/Ascend/latest)
    endif()
  endif()
endif()
set(ASCEND_CANN_PACKAGE_PATH ${ASCEND_DIR})

include(version.cmake)
check_cann_pkg_build_deps("oam-tools")
add_cann_version_info_targets()


set(CMAKE_LIBRARY_PATH ${ASCEND_CANN_PACKAGE_PATH})
link_directories(
    ${ASCEND_CANN_PACKAGE_PATH}
    ${ASCEND_CANN_PACKAGE_PATH}/lib64
    ${ASCEND_CANN_PACKAGE_PATH}/devlib
)
set(CCACHE_PROGRAM "")
find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set(CMAKE_C_COMPILER_LAUNCHER ${CCACHE_PROGRAM})
    set(CMAKE_CXX_COMPILER_LAUNCHER ${CCACHE_PROGRAM})
endif()

if(PROJECT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
  message(STATUS "compile project with library")
  option(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG "Build oam-tools with cann pkg" ON)
else()
  message(STATUS "compile project with src")
  option(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG "Build oam-tools with cann source" OFF)
endif()
set(OAM_TOOLS_DIR ${CMAKE_CURRENT_SOURCE_DIR})

# protobuf — 通过 cann-cmake 的 add_cann_third_party 引入
add_cann_third_party(protobuf)

set(PROTOC_PROGRAM "")
get_target_property(PROTOC_PROGRAM host_protoc IMPORTED_LOCATION)
set(PROTOBUF_HOST_INCLUDE ${PROTOBUF_LIB_CACHE_DIR}/include)
message("PROTOC_PROGRAM: ${PROTOC_PROGRAM}")

include(cmake/dependencies.cmake)
# 外部依赖库及编译选项
include(cmake/third_party/third_party_header_libs.cmake)

set(TOP_DIR "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH "Project top directory")
set(HI_PYTHON "python" CACHE PATH "Python Path")
set(INSTALL_CONFIG_DIR cmake)
set(MSPROF_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src/msprof)
set(PROF_BASIC_DIR "${MSPROF_DIR}/collector/basic")
set(TARGET_SYSTEM_NAME "Linux")
if(OAM_BUILD_TARGET STREQUAL "msprofbin")
    add_subdirectory(src/msprof/collector/dvvp/msprofbin)
elseif(OAM_BUILD_TARGET STREQUAL "acp")
    add_subdirectory(src/msprof/collector/dvvp/acp)
else()
    # 在superbuild模式下，由CMake负责构建msprof wheel 和同步 msaccucmp/compare
    include(cmake/build_submodules.cmake)

    # 拉取并解压闭源包 bundle（原 install_bundle.sh）；须在下方 bundle/ 的 install() 之前。
    include(cmake/install_bundle.cmake)

    add_subdirectory(src/asys)
    add_subdirectory(src/msaicerr)
    add_subdirectory(src/hccl_test)
    add_subdirectory(src/operator_cmp)
    add_subdirectory(src/msprof/collector/dvvp/msprofbin)
    add_subdirectory(src/msprof/collector/dvvp/acp)
endif()

if (OAM_BUILD_TARGET STREQUAL "")
if (ENABLE_COV OR ENABLE_UT)
    set(OAM_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
    include(CMakePrintHelpers)
    add_cann_third_party(boost)
    add_cann_third_party(mockcpp)
    add_cann_third_party(gtest_shared)
    add_dependencies(GTestShared::gtest mockcpp)
    add_subdirectory(test)
endif()

# 拷贝闭源包到指定目录
set(BUNDLE_PKG ${CMAKE_CURRENT_SOURCE_DIR}/bundle)

# 拷贝 aml 目录内容（配置期 file 操作用绝对 OAM_STAGING_DIR，非相对的 INSTALL_LIBRARY_DIR）。
if(EXISTS "${BUNDLE_PKG}/aml")
    # AICore STL 形态目录列表。目录名须与入口 so 里 SOC_PLATFORM_TABLE 的
    # formSubDir 逐字符一致(oam-tools-diag: aml_aicore_stl_platform.cpp)，
    # 形态 so / kernel so / 算子 .o / 算子输入数据(mx.bin)都放这里。
    # 新增形态时在此追加子目录名（与 oam-tools-diag 的 STL_PLATFORM_DIRS 对应）。
    set(_aml_stl_form_subdirs "ascend950_aicore_stl" "ascend960dt_aicore_stl")
    # 已稳定发布的形态：产物不齐（形态目录 / 形态 so / kernel so 缺失）视为打包异常，
    # configure 期拦截。新形态在随 diag 出包前先只留在 _aml_stl_form_subdirs
    # （缺失时跳过并打 STATUS），发布稳定后挪入此列表转为强制校验。
    set(_aml_stl_required_form_subdirs "ascend950_aicore_stl")

    # 形态产物完整性判断：形态目录、host so、kernel so 全部存在才算完整。
    # mx.bin 的 staging 拷贝与 install、形态层打包共用同一口径，避免只看部分
    # 文件时留下无 so 的孤儿数据文件（如仅缺 host so 的形态）。
    # 入参：_form 形态目录名；出参：_aml_stl_form_complete TRUE/FALSE。
    macro(_aml_stl_form_complete_check _form)
        string(REGEX REPLACE "_aicore_stl$" "" _soc "${_form}")
        if(EXISTS "${BUNDLE_PKG}/aml/lib64/${_form}"
            AND EXISTS "${BUNDLE_PKG}/aml/lib64/${_form}/libaml_stl_${_soc}.so"
            AND EXISTS "${BUNDLE_PKG}/aml/lib64/${_form}/libaml_stl_kernel_${_soc}.so")
            set(_aml_stl_form_complete TRUE)
        else()
            set(_aml_stl_form_complete FALSE)
        endif()
    endmacro()

    # [TEMP-STL-COMPAT] 临时兼容旧版 oam-tools-diag 包(无 AICore STL 产物)。
    # 后续改为强制校验时，删除本 set 及下面 3 处 _aml_stl_available 判断即可。
    if(EXISTS "${BUNDLE_PKG}/aml/lib64/libaml_aicore_stl.so")
        set(_aml_stl_available TRUE)
    else()
        set(_aml_stl_available FALSE)
        message(STATUS "AICore STL libs not in bundle, skip packaging them.")
    endif()

    file(COPY "${BUNDLE_PKG}/aml/lib64/plugin" DESTINATION ${OAM_STAGING_DIR}/tools/aml/lib64)
    # 如果 plugin/bin 存在，将其内容移动到 plugin 下并删除 bin
    set(_aml_plugin_bin "${OAM_STAGING_DIR}/tools/aml/lib64/plugin/bin")
    if(EXISTS "${_aml_plugin_bin}" AND IS_DIRECTORY "${_aml_plugin_bin}")
        # 防御性检查：仅删除位于本次构建目录下的 bin，避免 OAM_STAGING_DIR
        # 为空或被异常修改时，rm -rf 落到用户文件系统的真实路径上造成数据丢失
        get_filename_component(_aml_plugin_bin_abs "${_aml_plugin_bin}" REALPATH)
        get_filename_component(_build_dir_abs "${CMAKE_BINARY_DIR}" REALPATH)
        string(FIND "${_aml_plugin_bin_abs}" "${_build_dir_abs}/" _aml_under_build)
        if(NOT OAM_STAGING_DIR OR NOT _aml_under_build EQUAL 0)
            message(FATAL_ERROR
                "Refusing to remove '${_aml_plugin_bin_abs}': path is not under build "
                "directory '${_build_dir_abs}'. Check OAM_STAGING_DIR="
                "'${OAM_STAGING_DIR}'.")
        endif()
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E copy_directory
                "${_aml_plugin_bin}"
                "${OAM_STAGING_DIR}/tools/aml/lib64/plugin"
        )
        # mx.bin 是 AICore STL 的算子输入，须与形态 so 同目录（入口 so 按
        # <自身目录>/<formSubDir>/ 定位数据文件），不能留在被摊平的 plugin/ 下。
        # 上面 copy_directory 会把它一并摊到 plugin/，此处挪到各形态目录并清掉残留
        # （各形态的 mxfp4/mxfp8 算子读同一份 mx.bin，逐形态各放一份；形态产物缺失被
        #   跳过时[TEMP-STL-COMPAT]一并跳过，不留无 so 的孤儿数据文件）。
        if(_aml_stl_available AND EXISTS "${_aml_plugin_bin}/mx.bin")  # [TEMP-STL-COMPAT]
            foreach(_form ${_aml_stl_form_subdirs})
                _aml_stl_form_complete_check("${_form}")
                if(_aml_stl_form_complete)
                    file(COPY "${_aml_plugin_bin}/mx.bin"
                        DESTINATION "${OAM_STAGING_DIR}/tools/aml/lib64/aicore_stl/${_form}")
                endif()
                unset(_aml_stl_form_complete)
                unset(_soc)
            endforeach()
            execute_process(
                COMMAND ${CMAKE_COMMAND} -E rm -f
                    "${OAM_STAGING_DIR}/tools/aml/lib64/plugin/mx.bin"
            )
        endif()
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E rm -rf "${_aml_plugin_bin}"
        )
    endif()
    unset(_aml_plugin_bin)

    # install() commands mirror file(COPY) so CPack's cmake --install step also stages these files
    # Guard: these two libs are required; fail loudly at configure time rather than producing
    # a broken run package that only crashes at runtime.
    foreach(_required_lib
        "${BUNDLE_PKG}/aml/lib64/libascend_ml.so"
        "${BUNDLE_PKG}/aml/lib64/libascend_ml_detect.so"
    )
        if(NOT EXISTS "${_required_lib}")
            message(FATAL_ERROR "Required AML library not found: ${_required_lib}")
        endif()
    endforeach()
    file(GLOB _aml_runtime_libs CONFIGURE_DEPENDS
        "${BUNDLE_PKG}/aml/lib64/libascend_ml*.so"
    )
    install(FILES ${_aml_runtime_libs}
        DESTINATION ${CMAKE_SYSTEM_PROCESSOR}-linux/lib64
        COMPONENT oam-tools
    )
    unset(_aml_runtime_libs)
    install(FILES
        ${BUNDLE_PKG}/aml/lib64/plugin/libascend_mix_test.so
        DESTINATION tools/aml/lib64/plugin
        COMPONENT oam-tools
    )
    if(EXISTS "${BUNDLE_PKG}/aml/lib64/plugin/bin/matmul_input_0.bin")
        install(FILES
            ${BUNDLE_PKG}/aml/lib64/plugin/bin/matmul_input_0.bin
            ${BUNDLE_PKG}/aml/lib64/plugin/bin/matmul_input_1.bin
            DESTINATION tools/aml/lib64/plugin
            COMPONENT oam-tools
        )
    endif()
    # AICore STL(Ascend950/960DT)算子输入数据:与形态 so 同目录，入口 so 按
    # <自身目录>/<formSubDir>/mx.bin 读取。与 bin/ 下的 matmul_input_*.bin 同源。
    # （各形态的 mxfp4/mxfp8 算子读同一份 mx.bin，逐形态各放一份；
    #   形态产物缺失被跳过时[TEMP-STL-COMPAT]一并跳过，不留无 so 的孤儿数据文件）
    if(_aml_stl_available AND EXISTS "${BUNDLE_PKG}/aml/lib64/plugin/bin/mx.bin")  # [TEMP-STL-COMPAT]
        foreach(_form ${_aml_stl_form_subdirs})
            # 与 staging 拷贝、形态层打包同一完整性口径（_aml_stl_form_complete_check）：
            # 形态目录 / host so / kernel so 全部存在才 install，避免留下无 so 的孤儿数据文件。
            _aml_stl_form_complete_check("${_form}")
            if(_aml_stl_form_complete)
                install(FILES
                    ${BUNDLE_PKG}/aml/lib64/plugin/bin/mx.bin
                    DESTINATION tools/aml/lib64/aicore_stl/${_form}
                    COMPONENT oam-tools
                )
            endif()
            unset(_aml_stl_form_complete)
            unset(_soc)
        endforeach()
    endif()
    install(FILES
        ${BUNDLE_PKG}/aml/lib64/plugin_v2/libascend_stress_detect.so
        DESTINATION tools/aml/lib64/plugin_v2
        COMPONENT oam-tools
    )

    # AICore STL 自诊断三层框架(源自 oam-tools-diag，随 bundle 发布到 aml/lib64):
    #   入口 libaml_aicore_stl.so → host libaml_stl_<形态>.so → kernel libaml_stl_kernel_<形态>.so
    # 分级放置以便后续按 SoC 形态扩展:
    #   aicore_stl/                        入口层，平台无关
    #   aicore_stl/<形态>_aicore_stl/      形态相关(host so + kernel so + 算子 .o)
    # 形态子目录名须与入口 so 里 SOC_PLATFORM_TABLE 的 formSubDir 逐字符一致
    # (oam-tools-diag: aml_aicore_stl_platform.cpp)：入口 so 用 dladdr 定位自身目录后
    # 拼 <自身目录>/<formSubDir>/ 加载形态 so，名字不一致会在运行期 dlopen 失败。
    # 新增形态时在 _aml_stl_form_subdirs 追加子目录名即可。
    if(_aml_stl_available)  # [TEMP-STL-COMPAT]
    foreach(_form ${_aml_stl_form_subdirs})
        set(_aml_stl_form_rel "tools/aml/lib64/aicore_stl/${_form}")
        set(_aml_stl_bundle_form_dir "${BUNDLE_PKG}/aml/lib64/${_form}")
        # so 名为 libaml_stl_<soc>.so / libaml_stl_kernel_<soc>.so，<soc> 是形态目录名
        # 去掉 _aicore_stl 后缀（ascend950_aicore_stl -> ascend950），
        # 由 _aml_stl_form_complete_check 顺带求出(_soc)，下方 install 直接使用。
        # [TEMP-STL-COMPAT] 旧版 diag 包可能未带某形态产物（如 960DT 尚未随 diag 出包）：
        # 未发布形态缺失时跳过并打 STATUS；已发布形态（_aml_stl_required_form_subdirs）
        # 缺失视为打包异常，FATAL 拦截，避免产出运行期才崩的残缺包。
        _aml_stl_form_complete_check("${_form}")
        if(NOT _aml_stl_form_complete)
            list(FIND _aml_stl_required_form_subdirs "${_form}" _form_required_idx)
            if(NOT _form_required_idx EQUAL -1)
                message(FATAL_ERROR
                    "Required AICore STL form '${_form}' libs not found in bundle "
                    "(checked ${_aml_stl_bundle_form_dir}).")
            endif()
            message(STATUS "AICore STL form '${_form}' libs not in bundle, skip packaging it.")
            unset(_form_required_idx)
            unset(_soc)
            unset(_aml_stl_form_complete)
            unset(_aml_stl_form_rel)
            unset(_aml_stl_bundle_form_dir)
            continue()
        endif()
        unset(_form_required_idx)
        unset(_aml_stl_form_complete)
        # 形态层:host so + kernel so，放 aicore_stl/<形态>/
        install(FILES
            "${_aml_stl_bundle_form_dir}/libaml_stl_${_soc}.so"
            "${_aml_stl_bundle_form_dir}/libaml_stl_kernel_${_soc}.so"
            DESTINATION ${_aml_stl_form_rel}
            COMPONENT oam-tools
        )
        # 算子 .o(算子目录名生成，随形态增删会变)，用 GLOB 全量纳入。
        # 按形态子目录取，避免把别的形态的 .o 一并捞进本形态目录。
        file(GLOB _stl_kernel_objs CONFIGURE_DEPENDS
            "${_aml_stl_bundle_form_dir}/*.o"
        )
        install(FILES ${_stl_kernel_objs}
            DESTINATION ${_aml_stl_form_rel}
            COMPONENT oam-tools
        )
        unset(_stl_kernel_objs)
        unset(_soc)
        unset(_aml_stl_form_rel)
        unset(_aml_stl_bundle_form_dir)
    endforeach()
    # 入口层:平台无关，放 aicore_stl/
    install(FILES
        ${BUNDLE_PKG}/aml/lib64/libaml_aicore_stl.so
        DESTINATION tools/aml/lib64/aicore_stl
        COMPONENT oam-tools
    )
    endif()  # [TEMP-STL-COMPAT]
    unset(_aml_stl_available)
    unset(_aml_stl_form_subdirs)
    unset(_aml_stl_required_form_subdirs)
endif()

# 拷贝 built-in 目录
# 文件显式 555，与主线 CANN 包对 opp/built-in/op_impl 子树一致；
# 目录不再显式声明，交回 cmake install(DIRECTORY) 默认的 755。
if(EXISTS "${BUNDLE_PKG}/built-in")
    install(DIRECTORY ${BUNDLE_PKG}/built-in/op_impl/ai_core/tbe
        DESTINATION opp/built-in/op_impl/ai_core
        COMPONENT oam-tools
        FILE_PERMISSIONS OWNER_READ OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
        PATTERN "op_api" EXCLUDE
    )
    install(FILES
        ${BUNDLE_PKG}/built-in/op_impl/ai_core/tbe/op_api/lib/linux/${CMAKE_SYSTEM_PROCESSOR}/libopapi_oam.so
        DESTINATION ${CMAKE_SYSTEM_PROCESSOR}-linux/lib64
        COMPONENT oam-tools
    )
endif()

# 创建 bin pkg_inc 目录（配置期用绝对 OAM_STAGING_DIR）。
file(MAKE_DIRECTORY ${OAM_STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/bin)
file(MAKE_DIRECTORY ${OAM_STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/pkg_inc)

# 打run包
include(cmake/package.cmake)
pack_built_in()
endif()
