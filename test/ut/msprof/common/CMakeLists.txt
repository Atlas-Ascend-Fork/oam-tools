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

###################### osal_linux_utest ###########################
set(osalLinuxSrc
    test/main.cpp
    test/osal_linux_utest.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal_linux.c
    ${MSPROF_SOURCE_DIR}/basic/osal/osal_linux_mem.c
    ../stub/common-utils-stub.cpp
    ../stub/hdc-log-stub.cpp
)

add_executable(osal_linux_utest
    ${osalLinuxSrc}
)

set(libmsprofHeaderDir
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/output/third_party/gtest_shared/include
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/mstx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
)

target_include_directories(osal_linux_utest PRIVATE
    ${libmsprofHeaderDir}
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/basic/osal
    ../stub/
)

target_compile_options(osal_linux_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(osal_linux_utest PRIVATE
    OSAL
)

target_link_options(osal_linux_utest PRIVATE
   -ldl
   -lpthread
)

target_link_libraries(osal_linux_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    c_sec
)

set_target_properties(osal_linux_utest
    PROPERTIES
    OUTPUT_NAME osal_linux_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)

###################### osal_utest ###########################
# 覆盖 osal.c 的 OsalXxx 封装转发层（osal_linux_utest 只测 LinuxXxx 实现）
add_executable(osal_utest
    test/main.cpp
    test/osal_utest.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/basic/osal/osal_linux.c
    ${MSPROF_SOURCE_DIR}/basic/osal/osal_linux_mem.c
    ../stub/common-utils-stub.cpp
    ../stub/hdc-log-stub.cpp
)

target_include_directories(osal_utest PRIVATE
    ${libmsprofHeaderDir}
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/basic/osal
    ../stub/
)

target_compile_options(osal_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(osal_utest PRIVATE
    OSAL
)

target_link_options(osal_utest PRIVATE
   -ldl
   -lpthread
)

target_link_libraries(osal_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    c_sec
)

set_target_properties(osal_utest
    PROPERTIES
    OUTPUT_NAME osal_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)

###################### local_socket_utest ###########################
add_executable(local_socket_utest
    test/main.cpp
    test/local_socket_utest.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/socket/local_socket_tool.cpp
    ../stub/hdc-log-stub.cpp
)

target_include_directories(local_socket_utest PRIVATE
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/output/third_party/gtest_shared/include
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${TOP_DIR}/src/msprof/inc/external
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${MSPROF_SOURCE_DIR}/basic/osal
    ../stub/
)

target_compile_options(local_socket_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(local_socket_utest PRIVATE
    OSAL
)

target_link_libraries(local_socket_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    c_sec
)

set_target_properties(local_socket_utest
    PROPERTIES
    OUTPUT_NAME local_socket_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)

###################### chunk_pool_utest ###########################
add_executable(chunk_pool_utest
    test/main.cpp
    test/chunk_pool_utest.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/memory/chunk_pool_tool.cpp
    ../stub/hdc-log-stub.cpp
)

target_include_directories(chunk_pool_utest PRIVATE
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/output/third_party/gtest_shared/include
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${TOP_DIR}/src/msprof/inc/external
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${MSPROF_SOURCE_DIR}/basic/osal
    ../stub/
)

target_compile_options(chunk_pool_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(chunk_pool_utest PRIVATE
    OSAL
)

target_link_libraries(chunk_pool_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    c_sec
)

set_target_properties(chunk_pool_utest
    PROPERTIES
    OUTPUT_NAME chunk_pool_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)

###################### param_validation_utest ###########################

add_executable(param_validation_utest
    test/main.cpp
    test/param_validation_utest.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation/param_validation_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/config/config_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform/platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics/perf_count_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dev_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/channel/ai_drv_prof_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/src/json_parser.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/platform_interface.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/mini_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/cloud_v2_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_lite_platform.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../platform/stub/rc_v2_platform_stub.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/modena_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/base_analyzer_tool.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ../stub/drv_stub.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
    ../stub/profile_drv_user_stub.cpp
)

target_include_directories(param_validation_utest PRIVATE
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
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
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/json
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${MSPROF_SOURCE_DIR}/dvvp/message
    ${MSPROF_SOURCE_DIR}/dvvp/driver/inc
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/include
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ../stub/
    ${CMAKE_CURRENT_SOURCE_DIR}/../platform/stub
)

target_compile_options(param_validation_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(param_validation_utest PRIVATE
    MSPROF_DEBUG
)

target_link_libraries(param_validation_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    alog
    c_sec
)

set_target_properties(param_validation_utest
    PROPERTIES
    OUTPUT_NAME param_validation_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)

###################### utils_utest ###########################

add_executable(utils_utest
    test/main.cpp
    test/utils_utest.cpp
    test/json_utest.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation/param_validation_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/config/config_manager_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform/platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics/perf_count_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dev_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/channel/ai_drv_prof_api_tool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/src/json_parser.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/platform_interface.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/mini_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/cloud_v2_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_lite_platform.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../platform/stub/rc_v2_platform_stub.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/modena_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/base_analyzer_tool.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub_tool.cpp
    ../stub/drv_stub.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
    ../stub/profile_drv_user_stub.cpp
)

target_include_directories(utils_utest PRIVATE
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
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
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/json
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${MSPROF_SOURCE_DIR}/dvvp/message
    ${MSPROF_SOURCE_DIR}/dvvp/driver/inc
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/include
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ../stub/
)

target_compile_options(utils_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(utils_utest PRIVATE
    MSPROF_DEBUG
)

target_link_libraries(utils_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    alog
    c_sec
)

set_target_properties(utils_utest
    PROPERTIES
    OUTPUT_NAME utils_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
