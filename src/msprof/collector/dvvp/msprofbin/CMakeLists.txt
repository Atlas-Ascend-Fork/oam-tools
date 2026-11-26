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

# device 侧联编守卫：本目录可能被单独作为入口联编，补齐缺失的 INTERFACE 目标
include(${CMAKE_CURRENT_LIST_DIR}/../msprof_intf_pub_cxx.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../msprof_find_target.cmake)
set(msprofBinHeader
    ${SOURCE_DIR}/src
    ${TOP_DIR}/inc
    ${TOP_DIR}/inc/driver
    ${TOP_DIR}/inc/aicpu
    ${MSPROF_DIR}/inc/toolchain
    include
    ../
    ../app
    ../common/utils
    ../msprof/engine/include
    ../host/include/
    ../message/
    ../common
    ../common/json
    ../common/logger
    ../common/queue
    ../common/statistics
    ../common/validation
    ../common/platform
    ../common/json
    ../common/config
    ../../basic/osal
    ../common/errno
    ../depend/include/stub
    ../msprof/common/include/
    ../msprof/dynamic_profiling/include/
    ../profimpl/adapter/inc
    ../profimpl/platform
    ../profimpl/collect/job_wrapper/include
    ../profimpl/inc
    ../msprof/msproftx/mstx/inc
    ../profhal/adx/inc
    ../profhal/halinc
    ../driver/inc
    ../task_handle/include
    ../transport
    ../profhal/adx/inc
)

set(hdcCpp
    ../profhal/adx/stub/adx_prof_api_tool.cpp
    ../profhal/adx/wrapper/hdc_api.cpp
    ../profhal/adx/wrapper/memory_utils.cpp
)

set(msprofbinCpp
    src/msprof_bin_tool.cpp
    src/msopprof_manager_tool.cpp
    src/msprof_manager_tool.cpp
    src/msprof_params_adapter_tool.cpp
    src/input_parser_tool.cpp
    src/running_mode_tool.cpp
    src/prof_api_loader.cpp
    ../app/application_tool.cpp
    ../app/env_manager_tool.cpp
    ../common/cmd_log/cmd_log_tool.cpp
    ../common/utils/utils_tool.cpp
    ../common/json/json_tool.cpp
    ../../basic/osal/osal.c
    ../common/config/config_manager_tool.cpp
    ../common/memory/chunk_pool_tool.cpp
    ../common/thread/thread_tool.cpp
    ../common/thread/thread_pool_tool.cpp
    ../common/socket/local_socket_tool.cpp
    ../common/statistics/perf_count_tool.cpp
    ../common/validation/param_validation_tool.cpp
    ../common/platform/platform.cpp
    ../driver/devmgmt/ai_drv_dev_api.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ../driver/devmgmt/ai_drv_dsmi_api_tool.cpp
    ../driver/channel/ai_drv_prof_api_tool.cpp
    ../profimpl/adapter/src/json_parser.cpp
    ../profimpl/platform/platform_interface.cpp
    ../profimpl/platform/base_analyzer_tool.cpp
    ../profimpl/platform/modena_platform.cpp
    ../profimpl/platform/mini_platform.cpp
    ../profimpl/platform/cloud_v2_platform.cpp
    ../profimpl/platform/david_platform.cpp
    ../profimpl/platform/david_lite_platform.cpp
    ../profimpl/platform/david_v121_platform.cpp
    ../profimpl/platform/cloud_platform.cpp
    ../profimpl/platform/dc_platform.cpp
    ../profimpl/platform/mini_v3_platform.cpp
    ../msprof/dynamic_profiling/src/dyn_prof_client_tool.cpp
    ../transport/pipe_transport_tool.cpp
    ${hdcCpp}
)

# 扩展平台（module ext）源文件隔离：仅MODULE_EXT使能时编入
set(ENABLE_MODULE_EXT OFF)
if(DEFINED MODULE_EXT AND NOT (MODULE_EXT STREQUAL "") AND
    NOT (MODULE_EXT STREQUAL "False") AND NOT (MODULE_EXT STREQUAL "false") AND
    NOT (MODULE_EXT STREQUAL "OFF") AND NOT (MODULE_EXT STREQUAL "0"))
    set(ENABLE_MODULE_EXT ON)
    if(NOT DEFINED MSPROF_MODULE_EXT_ROOT)
        get_filename_component(MSPROF_MODULE_EXT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../../../modext/runtime_modext" ABSOLUTE)
    endif()
    set(MSPROF_MODULE_EXT_CMAKE
        "${MSPROF_MODULE_EXT_ROOT}/src/dfx/msprof/collector/dvvp/cmake/msprof_module_ext.cmake")
    if(NOT EXISTS "${MSPROF_MODULE_EXT_CMAKE}")
        message(FATAL_ERROR "Profiling module ext cmake not found: ${MSPROF_MODULE_EXT_CMAKE}")
    endif()
    include("${MSPROF_MODULE_EXT_CMAKE}")
    list(APPEND msprofbinCpp ${MSPROF_MODULE_EXT_PLATFORM_CPP})
endif()

if(${TARGET_SYSTEM_NAME} STREQUAL "Windows")
set(msprofbinCpp
    src/win/msprof_bin_tool.cpp
)
endif()
add_executable(msprofbin
    ${msprofbinCpp}
)

link_directories(
    ${INSTALL_LIBRARY_DIR}/stub
)

target_include_directories(msprofbin PRIVATE
    $<$<BOOL:${ENABLE_MODULE_EXT}>:${MSPROF_MODULE_EXT_PLATFORM_INC}>
    ${msprofBinHeader}
    ${CMAKE_CURRENT_SOURCE_DIR}
)


target_compile_options(msprofbin PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    # PRODUCT_SIDE 已从 build.sh 中移除（仓内仅此处引用，业务上无 host/device
    # 双侧需求），原本传 device 时本行 generator expression 永远求值为空，
    # 即"死代码"；保留本行以备后续如需启用旧 ABI 时取消注释。
    # $<$<STREQUAL:${PRODUCT_SIDE},host>:-D_GLIBCXX_USE_CXX11_ABI=0>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wfloat-equal>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wextra>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-unused-parameter>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-missing-field-initializers>
    #$<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Werror>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_compile_definitions(msprofbin PRIVATE
    SECUREC_USING_STD_SECURE_LIB=0
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
    $<$<BOOL:${ENABLE_MODULE_EXT}>:${MSPROF_MODULE_EXT_COMPILE_DEFINITIONS}>
)

target_link_options(msprofbin PRIVATE
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    -ldl
)

target_link_libraries(msprofbin PRIVATE
    $<BUILD_INTERFACE:oam_intf_pub>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    $<BUILD_INTERFACE:msprofbinOnetrack_pub>
    runtime_inc_headers
    stub_adcore_headers
    error_manager_headers
)

set_target_properties(msprofbin
    PROPERTIES
    OUTPUT_NAME msprof
    LIBRARY_OUTPUT_DIRECTORY ${INSTALL_LIBRARY_DIR}/msprof
)

if (DEFINED PKG_NAME AND PKG_NAME STREQUAL "oam")
    install(TARGETS msprofbin ${INSTALL_OPTIONAL}
        RUNTIME DESTINATION ${INSTALL_TOOLS_DIR}/profiler/bin
        # 须带 OWNER_WRITE：msprof 是 ELF，CMake 在 install 期就地改写 RPATH，
        # 无写位会导致 "RPATH_CHANGE could not write new RPATH / Error opening
        # file for update" 使 rpm 打包失败。包内写位不影响安装后权限——运行期由
        # XML install_mod 收口（rpm/deb postinst chmod 555、run 走 entity 递归 550）。
        PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
        COMPONENT oam-tools
    )
else()
    install(TARGETS msprofbin ${INSTALL_OPTIONAL}
        RUNTIME DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/bin
        COMPONENT oam-tools
    )

    install(TARGETS msprofbin ${INSTALL_OPTIONAL}
        LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/bin
        COMPONENT oam-tools
    )
endif()

### onetrack target interface

add_library(msprofbinOnetrack_pub INTERFACE)

target_link_libraries(msprofbinOnetrack_pub INTERFACE
    $<BUILD_INTERFACE:oam_intf_pub>
    c_sec
    alog
    mmpa
    ascend_hal
    -lpthread
    -ldl
)
