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
set(MSPROF_SOURCE_DIR ${TOP_DIR}/src/msprof/collector)



set(testSrc
    testcase/main.cpp
    testcase/acp_bin_utest.cpp
    testcase/acp_manager_utest.cpp
    testcase/op_data_manager_utest.cpp
    testcase/op_analyzer_biu_utest.cpp
    testcase/op_analyzer_pmu_utest.cpp
    testcase/job_wrapper_utest.cpp
)

set(src_file
    ../stub/drv_stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
    ../stub/profile_drv_user_stub.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_bin_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_command.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_pipe_transfer_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_api_plugin.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_runtime_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_compute_device_job_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_base_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_pmu_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_biu_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_pc_sampling_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_data_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_transport_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/app/application_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/app/env_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/argparse/argparser_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/config/config_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation/param_validation_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread_pool_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/socket/local_socket_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform/platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics/perf_count_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dsmi_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dev_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/channel/ai_drv_prof_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/src/dyn_prof_client_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/src/task_relationship_mgr_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/src/json_parser.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/platform_interface.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/cloud_v2_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_lite_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_v121_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/base_analyzer_tool.cpp
)

list(APPEND src_file
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/collection_job_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/collection_register_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_comm_job_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_channel_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_stars_job_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_biu_perf_job_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/prof_channel_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/uploader_mgr_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/uploader_tool.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
)

add_executable(acp_utest
    ${testSrc}
    ${src_file}
)

set(libmsprofHeaderDir
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${LLT_EXTEND_INCLUDE_DIR}
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/third_party/gtest_shared/include
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/include/driver
    ${TOP_DIR}/include/external
    ${TOP_DIR}/include/external/acl
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${TOP_DIR}/pkg_inc/dump
    ${TOP_DIR}/pkg_inc/aicpu
    ${TOP_DIR}/src/dfx/adump/inc/metadef/external
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/mstx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${TOP_DIR}/src/third_party/metadef
    ${TOP_DIR}/src/third_party/driver
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/slog/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/datagw/aicpu
)

target_include_directories(acp_utest PRIVATE
    ${libmsprofHeaderDir}
    stub
    ${MSPROF_SOURCE_DIR}/dvvp/acp/include
    ${MSPROF_SOURCE_DIR}/dvvp/
    ${MSPROF_SOURCE_DIR}/dvvp/app
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/argparse
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log
    ${MSPROF_SOURCE_DIR}/dvvp/common/errno
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/common/singleton
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/include
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/include/
    ${MSPROF_SOURCE_DIR}/dvvp/driver/inc
    ${MSPROF_SOURCE_DIR}/dvvp/transport
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/include
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/dvvp/message
    ${MSPROF_SOURCE_DIR}/dvvp/analyze/inc
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime/runtime
)

target_compile_options(acp_utest PRIVATE
    -g
    -Wall
)

target_compile_definitions(acp_utest PRIVATE
    __PROF_LLT
)

target_link_options(acp_utest PRIVATE
   -ldl
   -lpthread
)

target_link_libraries(acp_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:oam_intf_pub>
    GTestShared::gtest
    mockcpp
    alog
    c_sec
    dl
)

set_target_properties(acp_utest
    PROPERTIES
    OUTPUT_NAME acp_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
