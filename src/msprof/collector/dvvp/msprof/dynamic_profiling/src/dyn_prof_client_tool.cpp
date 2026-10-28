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
#include "dyn_prof_client_tool.h"
#include <algorithm>
#include "cmd_log/cmd_log_tool.h"
#include "config/config.h"
#include "errno/error_code_tool.h"
#include "socket/local_socket_tool.h"
#include "msprof_dlog_tool.h"
#include "utils/utils_tool.h"
#include "param_validation_tool.h"

namespace Collector {
namespace Dvvp {
namespace DynProf {
const std::map<std::string, DynProfCliCmd> DYN_PROF_CLI_CMD_MAP = {
    {"start", DynProfCliCmd::DYN_PROF_CLI_CMD_START},
    {"stop", DynProfCliCmd::DYN_PROF_CLI_CMD_STOP},
    {"quit", DynProfCliCmd::DYN_PROF_CLI_CMD_QUIT},
    {"q", DynProfCliCmd::DYN_PROF_CLI_CMD_QUIT}};

using namespace analysis::dvvp::common::cmdlog;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::socket;
using namespace analysis::dvvp::common::thread;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::MsprofErrMgr;

void DynProfClient::SetParams(const std::string& params)
{
    if (params.size() >= DYN_PROF_PARAMS_MAX_LEN || params.empty()) {
        MSPROF_LOGE("dynamic profiling param length error, len=%zu bytes.", params.size());
        return;
    }
    MSPROF_LOGD("set params, size:%zu", params.size());
    dynProfParams_ = params;
}

int32_t DynProfClient::Start()
{
    MSPROF_LOGI("dynamic profiling begin to init client.");
    if (cliStarted_) {
        MSPROF_LOGW("dynamic profiling client thread has been started.");
        return PROFILING_SUCCESS;
    }
    if (dynProfParams_.empty()) {
        MSPROF_LOGE("must set params first");
        return PROFILING_FAILED;
    }
    DynProfCliInitProcFunc();
    if (DynProfCliCreate() != PROFILING_SUCCESS) {
        MSPROF_LOGE("dynamic profiling create client socket failed.");
        return PROFILING_FAILED;
    }
    if (DynProfCliSendParams() != PROFILING_SUCCESS) {
        MSPROF_LOGE("dynamic profiling create client socket failed.");
        return PROFILING_FAILED;
    }
    cliStarted_ = true;
    Thread::SetThreadName(MSVP_DYN_PROF_CLIENT_THREAD_NAME);
    if (Thread::Start() != PROFILING_SUCCESS) {
        (void)Stop();
        MSPROF_LOGE("dynamic profiling start thread failed.");
        return PROFILING_FAILED;
    }

    MSPROF_LOGI("dynamic profiling init client success.");
    return PROFILING_SUCCESS;
}

int32_t DynProfClient::Stop()
{
    MSPROF_LOGI("dynamic profiling stop client.");
    if (cliStarted_) {
        cliStarted_ = false;
        return Thread::Stop();
    }
    return PROFILING_SUCCESS;
}

void DynProfClient::DynProfCliStopSocket(int32_t cliSockFd)
{
    MSPROF_LOGI("dynamic profiling close client socket: %d", cliSockFd);
    LocalSocket::Close(cliSockFd);
    cliSockFds_.erase(cliSockFd);
    cliSockFdMap_.erase(cliSockFd);
}

bool DynProfClient::IsCliStarted() const { return cliStarted_; }

int DynProfClient::TryReadInputCmd(std::string& inputCmd) const
{
    timeval timeout = {DYN_PROF_READ_INPUT_CMD_WAIT_TIME, 0};
    fd_set fdSet;
    FD_ZERO(&fdSet);
    FD_SET(0, &fdSet);
    if (select(1, &fdSet, nullptr, nullptr, &timeout) == 0) {
        return -1;
    }
    (void)getline(std::cin, inputCmd);
    inputCmd = Utils::Trim(inputCmd);
    return inputCmd.size();
}

void DynProfClient::CheckServerPidsIfValid()
{
    for (auto iter = cliSockFds_.begin(); iter != cliSockFds_.end();) {
        auto cliSockFd = *iter;
        auto pid = cliSockFdMap_.at(cliSockFd);
        if (analysis::dvvp::common::validation::ParamValidation::instance()->CheckDynaPidIsValid(pid)) {
            ++iter;
            continue;
        }
        CmdLog::CmdLogNoLevel("server process %d did not create socket, or process has already exited", pid);
        LocalSocket::Close(cliSockFd);
        iter = cliSockFds_.erase(iter);
        cliSockFdMap_.erase(cliSockFd);
    }
}

void DynProfClient::SetSocketTimeout()
{
    for (auto cliSockFd : cliSockFds_) {
        if (LocalSocket::SetRecvTimeOut(cliSockFd, DYN_PROF_PROC_TIME_OUT, 0) == PROFILING_FAILED ||
            LocalSocket::SetSendTimeOut(cliSockFd, DYN_PROF_PROC_TIME_OUT, 0) == PROFILING_FAILED) {
            MSPROF_LOGE("set client recv time out for pid %d failed.", cliSockFdMap_.at(cliSockFd));
            DynProfCliStopSocket(cliSockFd);
        }
    }
}

void DynProfClient::Run(const error_message::ErrorManagerContext& errorContext)
{
    MsprofErrorManager::instance()->SetErrorContext(errorContext);

    SetSocketTimeout();
    if (cliSockFds_.empty()) {
        MSPROF_LOGE("set client recv time out for all pids failed.");
        return;
    }

    std::string inputCmd;
    std::cout << "> " << std::flush;
    while (cliStarted_) {
        CheckServerPidsIfValid();
        if (cliSockFds_.empty()) {
            break;
        }
        if (TryReadInputCmd(inputCmd) < 0) {
            continue;
        }
        if (inputCmd.empty()) {
            std::cout << "> " << std::flush;
            continue;
        }
        auto it = DYN_PROF_CLI_CMD_MAP.find(inputCmd);
        if (it == DYN_PROF_CLI_CMD_MAP.cend()) {
            CmdLog::CmdLogNoLevel("invalid option -- '%s'\n", inputCmd.c_str());
            DynProfCliHelpInfo();
            std::cout << "> " << std::flush;
            continue;
        }
        if (inputCmd == "help" || inputCmd == "h") {
            DynProfCliHelpInfo();
            std::cout << "> " << std::flush;
            continue;
        }
        for (auto cliSockFd : cliSockFds_) {
            procFuncMap_[it->second](cliSockFd);
        }
        if (inputCmd == "quit" || inputCmd == "q") {
            MSPROF_LOGI("receive quit signal, stop dynamic profiler");
            break;
        }
        std::cout << "> " << std::flush;
    }
    for (auto cliSockFd : cliSockFds_) {
        DynProfCliStopSocket(cliSockFd);
    }
    cliStarted_ = false;
    MSPROF_LOGI("dynamic profiler client thread exit");
}

void DynProfClient::DynProfCliInitProcFunc()
{
    procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_START] =
        std::bind(&DynProfClient::DynProfCliProcStart, this, std::placeholders::_1);
    procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_STOP] =
        std::bind(&DynProfClient::DynProfCliProcStop, this, std::placeholders::_1);
    procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_QUIT] =
        std::bind(&DynProfClient::DynProfCliProcQuit, this, std::placeholders::_1);
}

int32_t DynProfClient::DynProfCliConnectSocket(const int32_t cliSockFd, const std::string& srvSockDomain) const
{
    // app 场景下, 每秒重试一次直到超时或者连接上
    const int32_t sleepIntervalUs = 1000000;
    const uint32_t timeout = 60;
    int32_t result = PROFILING_SUCCESS;
    std::string pidStr = Utils::BaseName(srvSockDomain);
    if (DynProfCliMgr::instance()->IsAppMode()) {
        uint32_t tryTimes = 0;
        while (true) {
            result = LocalSocket::Connect(cliSockFd, srvSockDomain);
            if (result == PROFILING_SUCCESS) {
                break;
            }
            if (tryTimes >= timeout) {
                CmdLog::CmdErrorLog("cannot connect to server for pid %s, timeout", pidStr.c_str());
                MSPROF_LOGE("cannot connect to server for pid %s, timeout", pidStr.c_str());
                result = PROFILING_FAILED;
                break;
            }
            (void)Utils::UsleepInterupt(sleepIntervalUs);
            tryTimes++;
        }
    } else {
        if (LocalSocket::Connect(cliSockFd, srvSockDomain) == PROFILING_FAILED) {
            CmdLog::CmdErrorLog("cannot connect to server for pid %s, maybe server is closed", pidStr.c_str());
            MSPROF_LOGE("cannot connect to server for pid %s, maybe server is closed", pidStr.c_str());
            result = PROFILING_FAILED;
        }
    }
    return result;
}

int32_t DynProfClient::DynProfCliCreate()
{
    auto pids = DynProfCliMgr::instance()->GetKeyPid();
    if (pids.empty()) {
        MSPROF_LOGE("there is no valid pid to connect.");
        return PROFILING_FAILED;
    }
    for (auto& pid : pids) {
        int32_t cliSockFd = LocalSocket::Open();
        if (cliSockFd == PROFILING_FAILED) {
            MSPROF_LOGE("open client socket for pid %d failed", pid);
            continue;
        }
        MSPROF_LOGI("open client socket: %d for pid %d", cliSockFd, pid);
        auto srvSockDomain = Utils::IdeGetHomedir() + DYN_PROF_SOCK_UNIX_DOMAIN + std::to_string(pid);
        if (DynProfCliConnectSocket(cliSockFd, srvSockDomain) != PROFILING_SUCCESS) {
            LocalSocket::Close(cliSockFd);
            MSPROF_LOGE("connect to server socket for pid %d failed", pid);
            continue;
        }
        if (LocalSocket::SetRecvTimeOut(cliSockFd, 1, 0) == PROFILING_FAILED) {
            LocalSocket::Close(cliSockFd);
            MSPROF_LOGE("set client recv time out for pid %d failed.", pid);
            continue;
        }
        if (LocalSocket::SetSendTimeOut(cliSockFd, 1, 0) == PROFILING_FAILED) {
            LocalSocket::Close(cliSockFd);
            MSPROF_LOGE("set client send time out for pid %d failed.", pid);
            continue;
        }
        MSPROF_LOGI("connect to server, key:%s", srvSockDomain.c_str());
        cliSockFds_.insert(cliSockFd);
        cliSockFdMap_[cliSockFd] = pid;
    }
    return cliSockFds_.empty() ? PROFILING_FAILED : PROFILING_SUCCESS;
}

int32_t DynProfClient::DynProfCliSendParams()
{
    DynProfParams params;
    params.dataLen = dynProfParams_.size();
    (void)memcpy_s(params.data, sizeof(params.data), dynProfParams_.c_str(), dynProfParams_.size());

    for (auto cliSockFd : cliSockFds_) {
        int32_t pid = cliSockFdMap_.at(cliSockFd);
        if (LocalSocket::Send(cliSockFd, &params, sizeof(params), 0) == PROFILING_FAILED) {
            MSPROF_LOGE("send params failed for pid %d", pid);
            DynProfCliStopSocket(cliSockFd);
            continue;
        }
        // 接收回执
        DynProfMsg rsqMsg;
        auto ret = LocalSocket::Recv(cliSockFd, &rsqMsg, sizeof(rsqMsg), 0);
        if (ret == SOCKET_ERR_EAGAIN) {
            CmdLog::CmdErrorLog("recv params timeout, server for pid %d has been connected to another client.", pid);
            MSPROF_LOGE("recv params timeout, server for pid %d has been connected to another client.", pid);
            DynProfCliStopSocket(cliSockFd);
            continue;
        } else if (ret != sizeof(rsqMsg)) {
            MSPROF_LOGE("recv params rsq failed for pid %d", pid);
            DynProfCliStopSocket(cliSockFd);
            continue;
        }
        MSPROF_LOGI("recv params rsq: %d,%d for pid %d", rsqMsg.msgType, rsqMsg.statusCode, pid);
        if (rsqMsg.msgType != DynProfMsgType::DYN_PROF_PARAMS_RSQ ||
            rsqMsg.statusCode != DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS) {
            MSPROF_LOGE("server recv params rsq error for pid %d", pid);
            DynProfCliStopSocket(cliSockFd);
            continue;
        }
    }
    return PROFILING_SUCCESS;
}

DynProfMsgRsqCode DynProfClient::DynProfCliSendCmd(const int32_t cliSockFd, DynProfMsgType req) const
{
    DynProfMsg reqMsg;
    reqMsg.msgType = req;
    if (LocalSocket::Send(cliSockFd, &reqMsg, sizeof(reqMsg), 0) == PROFILING_FAILED) {
        MSPROF_LOGE("send req: %d failed", req);
        return DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL;
    }
    MSPROF_LOGI("client send req: %d", req);
    // 接收回执
    DynProfMsg rsqMsg;
    if (LocalSocket::Recv(cliSockFd, &(rsqMsg), sizeof(rsqMsg), 0) != sizeof(rsqMsg)) {
        MSPROF_LOGE("recv server rsq failed");
        return DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL;
    }
    MSPROF_LOGI("client recv rsq: %d(%d)", rsqMsg.msgType, rsqMsg.statusCode);
    // rsq在req后
    if (static_cast<int32_t>(rsqMsg.msgType) != static_cast<int32_t>(req) + 1) {
        MSPROF_LOGE("req type:%d and rsq type:%d is not matched", req, rsqMsg.msgType);
        return DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL;
    }
    return rsqMsg.statusCode;
}

void DynProfClient::DynProfCliProcStart(const int32_t cliSockFd)
{
    MSPROF_LOGI("dynamic profiling start message proc.");
    auto rsq = DynProfCliSendCmd(cliSockFd, DynProfMsgType::DYN_PROF_START_REQ);
    int32_t pid = cliSockFdMap_.at(cliSockFd);
    switch (rsq) {
        case DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS:
            CmdLog::CmdLogNoLevel("dynamic profiling for pid %d start success", pid);
            MSPROF_LOGI("dynamic profiling for pid %d start success", pid);
            break;
        case DynProfMsgRsqCode::DYN_PROF_RSQ_ALREADY_START:
            CmdLog::CmdWarningLog("dynamic profiling for pid %d already started", pid);
            MSPROF_LOGW("dynamic profiling for pid %d already started", pid);
            break;
        case DynProfMsgRsqCode::DYN_PROF_RSQ_NOT_SET_DEVICE:
            CmdLog::CmdWarningLog("dynamic profiling device for pid %d has not been set up", pid);
            MSPROF_LOGW("dynamic profiling device for pid %d has not been set up", pid);
            break;
        case DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL:
        default:
            CmdLog::CmdErrorLog("dynamic profiling for pid %d start failed", pid);
            MSPROF_LOGE("dynamic profiling for pid %d start failed", pid);
            DynProfCliStopSocket(cliSockFd);
            break;
    }
}

void DynProfClient::DynProfCliProcStop(const int32_t cliSockFd)
{
    MSPROF_LOGI("dynamic profiling stop message proc.");
    auto rsq = DynProfCliSendCmd(cliSockFd, DynProfMsgType::DYN_PROF_STOP_REQ);
    int32_t pid = cliSockFdMap_.at(cliSockFd);
    switch (rsq) {
        case DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS:
            CmdLog::CmdLogNoLevel("dynamic profiling for pid %d stop success", pid);
            MSPROF_LOGI("dynamic profiling for pid %d stop success", pid);
            break;
        case DynProfMsgRsqCode::DYN_PROF_RSQ_NOT_START:
            CmdLog::CmdWarningLog("dynamic profiling for pid %d has not started", pid);
            MSPROF_LOGW("dynamic profiling for pid %d has not started", pid);
            break;
        case DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL:
        default:
            CmdLog::CmdErrorLog("dynamic profiling for pid %d stop failed", pid);
            MSPROF_LOGE("dynamic profiling for pid %d stop failed", pid);
            DynProfCliStopSocket(cliSockFd);
            break;
    }
}

void DynProfClient::DynProfCliProcQuit(const int32_t cliSockFd) const
{
    MSPROF_LOGI("dynamic profiling quit message proc.");
    auto rsq = DynProfCliSendCmd(cliSockFd, DynProfMsgType::DYN_PROF_QUIT_REQ);
    int32_t pid = cliSockFdMap_.at(cliSockFd);
    switch (rsq) {
        case DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS:
            CmdLog::CmdLogNoLevel("dynamic profiling for pid %d quit success", pid);
            MSPROF_LOGI("dynamic profiling for pid %d quit success", pid);
            break;
        case DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL:
        default:
            CmdLog::CmdErrorLog("dynamic profiling for pid %d quit failed", pid);
            MSPROF_LOGE("dynamic profiling for pid %d quit failed", pid);
            break;
    }
}

void DynProfClient::DynProfCliHelpInfo() const
{
    CmdLog::CmdLogNoLevel("Usage:\n"
                          "\t start:                 Start a collection in interactive mode.\n"
                          "\t stop:                  Stop a collection that was started in interactive mode.\n"
                          "\t quit:                  Stop collection and quit interactive mode.");
}

DynProfCliMgr::~DynProfCliMgr() {}

int32_t DynProfCliMgr::StartDynProfCli(const std::string& params)
{
    MSVP_MAKE_SHARED0(dynProfCli_, DynProfClient, return PROFILING_FAILED);
    dynProfCli_->SetParams(params);
    if (dynProfCli_->Start() != PROFILING_SUCCESS) {
        MSPROF_LOGE("Dynamic profiling start client thread fail.");
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("Dynamic profiling start client.");
    return PROFILING_SUCCESS;
}

void DynProfCliMgr::StopDynProfCli()
{
    if (dynProfCli_ != nullptr) {
        (void)dynProfCli_->Stop();
    }
    MSPROF_LOGI("Dynamic profiling stop client.");
}

void DynProfCliMgr::SetKeyPid(const std::vector<int32_t> pids)
{
    for (auto pid : pids) {
        keyPids_.insert(pid);
    }
}

std::set<int32_t> DynProfCliMgr::GetKeyPid() const { return keyPids_; }

std::string DynProfCliMgr::GetKeyPidEnv() const
{
    std::vector<std::string> pidStrs(keyPids_.size());
    std::transform(keyPids_.begin(), keyPids_.end(), pidStrs.begin(), [](int32_t n) { return std::to_string(n); });

    UtilsStringBuilder<std::string> builder;
    std::string keyPids = builder.Join(pidStrs, ",");
    return isAppMode_ ? DYNAMIC_PROFILING_KEY_PID_ENV + "=" + keyPids : "";
}

void DynProfCliMgr::EnableDynProfCli() { enabled_ = true; }

bool DynProfCliMgr::IsDynProfCliEnable() const { return enabled_; }

std::string DynProfCliMgr::GetDynProfEnv() const
{
    return enabled_ ? PROFILING_MODE_ENV + "=" + DYNAMIC_PROFILING_VALUE : "";
}

void DynProfCliMgr::SetAppMode() { isAppMode_ = true; }

bool DynProfCliMgr::IsAppMode() const { return isAppMode_; }

bool DynProfCliMgr::IsCliStarted() const
{
    if (dynProfCli_ != nullptr) {
        return dynProfCli_->IsCliStarted();
    }
    return false;
}

void DynProfCliMgr::WaitQuit()
{
    if (dynProfCli_ != nullptr) {
        dynProfCli_->Join();
    }
}
} // namespace DynProf
} // namespace Dvvp
} // namespace Collector
