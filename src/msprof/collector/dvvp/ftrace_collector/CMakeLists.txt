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

# device side guard, same as msprofbin: this directory may be built standalone
include(${CMAKE_CURRENT_LIST_DIR}/../msprof_intf_pub_cxx.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../msprof_find_target.cmake)

set(ftraceCollectorCpp
    src/main.cpp
    src/cpu_reader.cpp
    src/file_owner.cpp
    src/ftrace_log.cpp
    src/tracefs.cpp
)

add_executable(ftrace_collector
    ${ftraceCollectorCpp}
)

target_include_directories(ftrace_collector PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/../common/logger
)

target_compile_options(ftrace_collector PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wextra>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-unused-parameter>
)

target_compile_definitions(ftrace_collector PRIVATE
    _GNU_SOURCE
    SECUREC_USING_STD_SECURE_LIB=0  # same securec flavour as msprofbin
)

target_compile_options(ftrace_collector PRIVATE -fstack-protector-all)
target_link_options(ftrace_collector PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
)

target_link_libraries(ftrace_collector PRIVATE
    -lpthread
    $<BUILD_INTERFACE:oam_intf_pub>
    $<BUILD_INTERFACE:slog_headers>
    alog
    c_sec  # memcpy_s / snprintf_s
)

set_target_properties(ftrace_collector
    PROPERTIES
    OUTPUT_NAME ftrace_collector
)

# Same layout as msprof: the collector ships to <install>/tools/profiler/bin, next to the msprof
# CLI that spawns it, so the runtime only has to know that one path.
if (DEFINED PKG_NAME AND PKG_NAME STREQUAL "oam")
    install(TARGETS ftrace_collector ${INSTALL_OPTIONAL}
        RUNTIME DESTINATION ${INSTALL_TOOLS_DIR}/profiler/bin
        PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
        COMPONENT oam-tools
    )
else()
    install(TARGETS ftrace_collector ${INSTALL_OPTIONAL}
        RUNTIME DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/bin
        COMPONENT oam-tools
    )
endif()
