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

# device 侧联编场景守卫：本目录及各子目录均可能被 device 侧单独作为入口联编，统一 include
include(${CMAKE_CURRENT_LIST_DIR}/msprof_intf_pub_cxx.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/msprof_find_target.cmake)

add_subdirectory(acp)
add_subdirectory(msprofbin)
