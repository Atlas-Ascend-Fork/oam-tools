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

set(profilerSrcList
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation/param_validation_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/app/application_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/app/env_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/config/config_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/socket/local_socket_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform/platform.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dev_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/src/dyn_prof_client_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/platform_interface.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/base_analyzer_tool.cpp
)

set(profilerSrcFile
    test/main.cpp
    ../stub/hdc-api-stub.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/drv_stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
    ../stub/profile_drv_user_stub.cpp
    test/application_utest.cpp
    ${profilerSrcList}
)


add_executable(
    application_utest
    ${profilerSrcFile}
)

set(libmsprofHeaderDir
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/output/third_party/gtest_shared/include
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/include/driver
    ${TOP_DIR}/include/external
    ${TOP_DIR}/include/external/acl
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${TOP_DIR}/pkg_inc/dump
    ${TOP_DIR}/pkg_inc/aicpu_sched
    ${TOP_DIR}/src/dfx/adump/inc/metadef/external
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/mstx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
)

target_include_directories(application_utest PRIVATE
    ${libmsprofHeaderDir}
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${TOP_DIR}/src/msprof/inc/external
    ${TOP_DIR}/src/msprof/inc/external/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/slog/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/datagw/aicpu
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/aicpu
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/profiling
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
    ${TOP_DIR}/src/third_party/adcore
    ${TOP_DIR}/abl/libc_sec/include
    ${TOP_DIR}/inc/driver
    ${TOP_DIR}/inc/tsch
    ${TOP_DIR}/inc/external/acl
    ${TOP_DIR}/runtime/src/dfx/adump
    ${TOP_DIR}/runtime/src/dfx/adump/external
    ${TOP_DIR}/ace/npuruntime/inc
    ${TOP_DIR}/abl/msprof/inc
    ${TOP_DIR}/abl/msprof/inc/toolchain
    ../stub/
    ../stub/common
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/aging
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/app
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics
    ${MSPROF_SOURCE_DIR}/dvvp/common/json
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${MSPROF_SOURCE_DIR}/dvvp/host/include
    ${MSPROF_SOURCE_DIR}/dvvp/streamio/server/include
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/include
    ${MSPROF_SOURCE_DIR}/dvvp/driver/inc
    ${MSPROF_SOURCE_DIR}/dvvp/transport
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/include
    ${MSPROF_SOURCE_DIR}/dvvp/streamio/common/include
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/include
)


target_compile_options(application_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(application_utest PRIVATE
    MSPROF_DEBUG
)

target_link_libraries(application_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    alog
    c_sec
)

set_target_properties(application_utest
    PROPERTIES
    OUTPUT_NAME application_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
