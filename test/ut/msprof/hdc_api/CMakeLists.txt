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

add_executable(hdc_api_utest
    test/main.cpp
    test/hdc_api_utest.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/wrapper/hdc_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/wrapper/memory_utils.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ../stub/ide_hdc_stub.cc
    ../stub/hdc-log-stub.cpp
    ../stub/drv_stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
)

set(libmsprofHeaderDir
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/output/third_party/gtest_shared/include
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${TOP_DIR}/src/msprof/inc/external
    ${TOP_DIR}/src/msprof/inc/external/acl
    ${LLT_EXTEND_INCLUDE_DIR}
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc
)

target_include_directories(hdc_api_utest PRIVATE
    ${libmsprofHeaderDir}
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/halinc
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${TOP_DIR}/src/third_party/adcore
    ../stub/
)

target_compile_options(hdc_api_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(hdc_api_utest PRIVATE
    MSPROF_DEBUG
)

target_link_libraries(hdc_api_utest PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    c_sec
    rt
    dl
    pthread
)

set_target_properties(hdc_api_utest
    PROPERTIES
    OUTPUT_NAME hdc_api_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
