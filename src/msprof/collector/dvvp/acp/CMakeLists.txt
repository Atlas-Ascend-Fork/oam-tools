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

####################### acp #######################
set(acpBinHeader
    ${MSPROF_DIR}/inc/toolchain
    include
    ../
    ../app
    ../common
    ../common/argparse
    ../common/cmd_log
    ../common/utils
    ../common/errno
    ../common/logger
    ../common/config
    ../common/singleton
    ../common/platform
    ../common/validation
    ../profimpl/platform
    ../profimpl/adapter/inc
    ../profimpl/collect/job_wrapper/include
    ../depend/include/stub
    ../msprof/dynamic_profiling/include/
    ../driver/inc
    ../transport
    ../task_handle/include
    ../profapi/inc
    ${PROF_BASIC_DIR}/osal
)

set(acpBinCpp
    src/acp_bin_tool.cpp
    src/acp_command.cpp
    src/acp_pipe_transfer_tool.cpp
    ../app/application_tool.cpp
    ../app/env_manager_tool.cpp
    ../common/argparse/argparser_tool.cpp
    ../common/utils/utils_tool.cpp
    ../common/cmd_log/cmd_log_tool.cpp
    ../common/config/config_manager_tool.cpp
    ../common/validation/param_validation_tool.cpp
    ../common/thread/thread_tool.cpp
    ../common/thread/thread_pool_tool.cpp
    ../common/socket/local_socket_tool.cpp
    ../common/json/json_tool.cpp
    ../common/platform/platform.cpp
    ../common/statistics/perf_count_tool.cpp
    ../driver/devmgmt/ai_drv_dev_api.cpp
    ../driver/channel/ai_drv_prof_api_tool.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ../msprof/dynamic_profiling/src/dyn_prof_client_tool.cpp
    ../task_handle/src/task_relationship_mgr_tool.cpp
    ../profimpl/adapter/src/json_parser.cpp
    ../profimpl/platform/platform_interface.cpp
    ../profimpl/platform/cloud_v2_platform.cpp
        ../profimpl/platform/david_platform.cpp
        ../profimpl/platform/david_lite_platform.cpp
        ../profimpl/platform/david_v121_platform.cpp
    ../profimpl/platform/base_analyzer_tool.cpp
    ../profimpl/collect/job_wrapper/src/collection_job_tool.cpp
    ../profimpl/collect/job_wrapper/src/collection_register_tool.cpp
    ../profimpl/collect/job_wrapper/src/prof_comm_job_tool.cpp
    ../profimpl/collect/job_wrapper/src/prof_channel_manager_tool.cpp
    ../profimpl/collect/job_wrapper/src/prof_stars_job_tool.cpp
    ../transport/prof_channel_tool.cpp
    ../transport/uploader_mgr_tool.cpp
    ../transport/uploader_tool.cpp
    ${PROF_BASIC_DIR}/osal/osal.c
)

add_executable(acp
    ${acpBinCpp}
)

target_include_directories(acp PRIVATE
    ${acpBinHeader}
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_compile_options(acp PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    $<$<CONFIG:Release>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<CONFIG:Debug>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wfloat-equal>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wextra>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-unused-parameter>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-missing-field-initializers>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Werror>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_compile_definitions(acp PRIVATE
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
)

target_link_options(acp PRIVATE
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    -Wl,--start-group
    -ldl
)

target_link_libraries(acp PRIVATE
    $<BUILD_INTERFACE:oam_intf_pub>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    runtime_inc_headers
    stub_adcore_headers
    error_manager_headers
    c_sec
    unified_dlog
    mmpa
    ascend_hal
)

set_target_properties(acp
    PROPERTIES
    OUTPUT_NAME acp
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

install(TARGETS acp ${INSTALL_OPTIONAL}
    RUNTIME DESTINATION ${INSTALL_TOOLS_DIR}/profiler/bin
    # 须带 OWNER_WRITE：acp 是 ELF，CMake 在 install 期就地改写 RPATH，无写位会导致
    # "RPATH_CHANGE could not write new RPATH / Error opening file for update" 使
    # rpm 打包失败。包内写位不影响安装后权限——运行期由 XML install_mod 收口。
    PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
    COMPONENT oam-tools
)

####################### acp end #######################

####################### libascend_profinj.so #######################
set(profinjCpp
    ${PROF_BASIC_DIR}/osal/osal.c
    src/acp_command.cpp
    src/acp_pipe_transfer_tool.cpp
    src/acp_runtime_api_tool.cpp
    src/acp_manager_tool.cpp
    src/acp_api_plugin.cpp
    src/acp_compute_device_job_tool.cpp
    src/op_transport_tool.cpp
    src/op_data_manager_tool.cpp
    src/op_analyzer_tool.cpp
    src/op_analyzer_base_tool.cpp
    src/op_analyzer_pmu_tool.cpp
    src/op_analyzer_biu_tool.cpp
    src/op_analyzer_pc_sampling_tool.cpp
    ../transport/uploader_tool.cpp
    ../transport/uploader_mgr_tool.cpp
    ../transport/prof_channel_tool.cpp
    ../profimpl/platform/platform_interface.cpp
    ../profimpl/platform/cloud_v2_platform.cpp
        ../profimpl/platform/david_platform.cpp
        ../profimpl/platform/david_lite_platform.cpp
        ../profimpl/platform/david_v121_platform.cpp
    ../profimpl/platform/base_analyzer_tool.cpp
    ../profimpl/adapter/src/json_parser.cpp
    ../profimpl/collect/job_wrapper/src/collection_job_tool.cpp
    ../profimpl/collect/job_wrapper/src/collection_register_tool.cpp
    ../profimpl/collect/job_wrapper/src/prof_comm_job_tool.cpp
    ../profimpl/collect/job_wrapper/src/prof_channel_manager_tool.cpp
    ../profimpl/collect/job_wrapper/src/prof_stars_job_tool.cpp
    ../profimpl/collect/job_wrapper/src/prof_biu_perf_job_tool.cpp
    ../common/platform/platform.cpp
    ../common/utils/utils_tool.cpp
    ../common/config/config_manager_tool.cpp
    ../common/statistics/perf_count_tool.cpp
    ../common/json/json_tool.cpp
    ../common/cmd_log/cmd_log_tool.cpp
    ../common/validation/param_validation_tool.cpp
    ../common/thread/thread_tool.cpp
    ../common/thread/thread_pool_tool.cpp
    ../common/socket/local_socket_tool.cpp
    ../common/argparse/argparser_tool.cpp
    ../driver/devmgmt/ai_drv_dev_api.cpp
    ../driver/channel/ai_drv_prof_api_tool.cpp
    ../driver/devmgmt/ai_drv_dsmi_api_tool.cpp
    ../app/application_tool.cpp
    ../app/env_manager_tool.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ../msprof/dynamic_profiling/src/dyn_prof_client_tool.cpp
    ../task_handle/src/task_relationship_mgr_tool.cpp
)

add_library(profinj SHARED
    ${profinjCpp}
)

target_include_directories(profinj PRIVATE
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime/runtime
    ${MSPROF_DIR}/inc/toolchain
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${PROF_BASIC_DIR}/osal
    include/
    ../
    ../depend/include/stub
    ../transport/
    ../common/
    ../common/logger
    ../common/statistics
    ../common/utils
    ../common/validation
    ../common/queue
    ../common/json
    ../common/config
    ../common/singleton
    ../analyze/inc
    ../profimpl/platform
    ../profimpl/adapter/inc
    ../driver/inc
    ../message
    ../profimpl/collect/job_wrapper/include/
    ../profapi/inc/
    ../app
    ../common/
    ../common/argparse/
    ../common/cmd_log
    ../common/errno
    ../msprof/dynamic_profiling/include/
    ../task_handle/include
)

set_target_properties(profinj
    PROPERTIES
    OUTPUT_NAME $<IF:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,libascend_profinj,ascend_profinj>
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

target_compile_options(profinj PRIVATE
    -fPIC
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    -Wfloat-equal
    -Wextra
    -Wall
    -Werror
    $<$<CONFIG:Release>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<CONFIG:Debug>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

string(PREPEND CMAKE_CXX_FLAGS "-std=c++17 ")
string(PREPEND CMAKE_C_FLAGS "-std=c11 ")

target_compile_definitions(profinj PRIVATE
    MSPROF_LIB
)

target_link_options(profinj PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

target_link_libraries(profinj PRIVATE
    $<BUILD_INTERFACE:oam_intf_pub>
    $<BUILD_INTERFACE:slog_headers>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    runtime_inc_headers
    stub_adcore_headers
    error_manager_headers
    c_sec
    mmpa
    unified_dlog
    ascend_hal
)

install(TARGETS profinj ${INSTALL_OPTIONAL}
    LIBRARY DESTINATION ${INSTALL_TOOLS_DIR}/profiler/lib64
    COMPONENT oam-tools
)

####################### libascend_profinj.so ###########################
