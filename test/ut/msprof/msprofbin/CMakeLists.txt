# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------
set(MSPROF_SOURCE_DIR ${TOP_DIR}/src/msprof/collector)

set(common_file
    ${MSPROF_SOURCE_DIR}/dvvp/app/application_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/app/env_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/config/config_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/memory/chunk_pool_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread_pool_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics/perf_count_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation/param_validation_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform/platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/socket/local_socket_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json_tool.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dev_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dsmi_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/channel/ai_drv_prof_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/src/dyn_prof_client_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/pipe_transport_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/src/task_relationship_mgr_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/stub/adx_prof_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/wrapper/memory_utils.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/platform_interface.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/cloud_v2_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_lite_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/cloud_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/modena_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/base_analyzer_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/src/json_parser.cpp
    #${MSPROF_SOURCE_DIR}/dvvp/proto/profiler.pb.cc
)


set(src_file
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/src/msprof_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/src/msprof_params_adapter_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/src/input_parser_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/src/running_mode_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/src/prof_api_loader.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/src/msopprof_manager_tool.cpp
)

add_executable(msprof_bin_utest
    ${common_file}
    ${src_file}
    test/main.cpp
    test/msprof_bin_utest.cpp
    test/input_parser_utest.cpp
    test/msprof_manager_utest.cpp
    test/prof_param_adapter_utest.cpp
    test/dyn_prof_client_utest.cpp
    test/json_parser_utest.cpp
    test/msopprof_manager_utest.cpp
    test/running_mode_utest.cpp
    test/task_relationship_mgr_utest.cpp
    test/adx_prof_api_utest.cpp
    ../stub/drv_stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/profile_drv_user_stub.cpp
    ../stub/hdc-api-stub.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
)

message(STATUS "#####################ASCEND_CANN_PACKAGE_PATH:"${ASCEND_CANN_PACKAGE_PATH})

set(libmsprofHeaderDir
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${LLT_EXTEND_INCLUDE_DIR}
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/third_party/gtest_shared/include
    ${TOP_DIR}/src/dfx/msprof/collector/basic/osal
    ${TOP_DIR}/src/dfx/msprof/collector/dvvp/proto
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/include/driver
    ${TOP_DIR}/include/external
    ${TOP_DIR}/include/external/acl
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${TOP_DIR}/pkg_inc/dump
    ${TOP_DIR}/pkg_inc/aicpu
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/mstx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/devprof/include
    ${TOP_DIR}/src/third_party/metadef
    ${TOP_DIR}/src/third_party/driver
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/slog/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/datagw/aicpu
)

target_include_directories(msprof_bin_utest PRIVATE
    ${libmsprofHeaderDir}
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin
    ${MSPROF_SOURCE_DIR}/dvvp/app
    ${MSPROF_SOURCE_DIR}/dvvp/
    ${TOP_DIR}/abl/libc_sec/include
    ${TOP_DIR}/inc/driver
    ${TOP_DIR}/inc/external/acl
    ${TOP_DIR}/inc/aicpu
    ${TOP_DIR}/ace/npuruntime/inc
    ${TOP_DIR}/abl/msprof/inc
    ${TOP_DIR}/metadef/inc
    ${TOP_DIR}/metadef/inc/external
    ${TOP_DIR}/abl/msprof/inc/toolchain
    ${MSPROF_SOURCE_DIR}/dvvp/host/include/
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/json
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${MSPROF_SOURCE_DIR}/dvvp/common/errno
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/inc
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/include
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/halinc
    ${MSPROF_SOURCE_DIR}/dvvp/driver/inc
    ${MSPROF_SOURCE_DIR}/dvvp/transport
    ${MSPROF_SOURCE_DIR}/dvvp/stub/
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/common/include
)


target_compile_options(msprof_bin_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    # Keep mockcpp interception effective for Release unit tests.
    -fno-inline
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(msprof_bin_utest PRIVATE
    C_SEC
    __PROF_LLT
)

target_link_libraries(msprof_bin_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    alog
    ${CMAKE_DL_LIBS}
)

set_target_properties(msprof_bin_utest
    PROPERTIES
    OUTPUT_NAME msprof_bin_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)
