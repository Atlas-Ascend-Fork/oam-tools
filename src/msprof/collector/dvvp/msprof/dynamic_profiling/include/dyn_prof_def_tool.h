/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#ifndef COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_DEF_H
#define COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_DEF_H

#include <functional>
#include <string>

namespace Collector {
namespace Dvvp {
namespace DynProf {
static const std::string DYN_PROF_SOCK_UNIX_DOMAIN = "/dynamic_profiling_socket_";
constexpr uint32_t DYN_PROF_PARAMS_MAX_LEN = 4096;
constexpr uint32_t DYN_PROF_MAX_ACCEPT_TIMES = 128;
constexpr uint32_t DYN_PROF_IDLE_LINK_HOLD_TIME = 1800; // 30 mins
constexpr uint32_t DYN_PROF_SERVER_PROC_MSG_MAX_NUM = 100;
const uint32_t DYN_PROF_READ_INPUT_CMD_WAIT_TIME = 1;
constexpr long DYN_PROF_PROC_TIME_OUT = 60;

using ProcFunc = std::function<void(int)>;

enum class DynProfMsgType {
    DYN_PROF_PARAMS_RSQ = 0,
    DYN_PROF_START_REQ,
    DYN_PROF_START_RSQ,
    DYN_PROF_STOP_REQ,
    DYN_PROF_STOP_RSQ,
    DYN_PROF_QUIT_REQ,
    DYN_PROF_QUIT_RSQ,
    DYN_PROF_DISCONNECT_RSQ,
};

enum class DynProfMsgRsqCode {
    DYN_PROF_RSQ_SUCCESS = 0,
    DYN_PROF_RSQ_FAIL,
    // start
    DYN_PROF_RSQ_ALREADY_START,
    DYN_PROF_RSQ_NOT_SET_DEVICE,
    // stop
    DYN_PROF_RSQ_NOT_START,
};

struct DynProfMsg {
    DynProfMsgType msgType;
    DynProfMsgRsqCode statusCode;
};

struct DynProfParams {
    uint32_t dataLen = 0;
    char data[DYN_PROF_PARAMS_MAX_LEN] = {0};
};

struct DynProfDeviceInfo {
    uint32_t chipId = 0;
    uint32_t devId = 0;
    bool isOpenDevice = false;
};
} // namespace DynProf
} // namespace Dvvp
} // namespace Collector

#endif
