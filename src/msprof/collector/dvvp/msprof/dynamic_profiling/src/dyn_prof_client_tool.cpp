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
#include <poll.h>
#include <sys/socket.h>
#include <algorithm>
#include <cerrno>
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
constexpr long DYN_PROF_MS_PER_SEC = 1000;
constexpr int32_t DYN_PROF_NS_PER_MS = 1000000;
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

namespace {
// 单调时钟毫秒值，用于计算 poll 的剩余超时预算，避免受系统时间跳变影响。
int64_t GetMonotonicMs() { return static_cast<int64_t>(Utils::GetClockMonotonicRaw()) / DYN_PROF_NS_PER_MS; }
} // namespace

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
    // LocalSocket::Close 的入参是引用，会把 fd 改写成 -1；必须先按原 fd 摘除，否则 erase(-1) 是空操作，
    // 已关闭的 fd 会残留在两个容器里，后续命令反复在失效 fd 上失败。
    cliSockFds_.erase(cliSockFd);
    cliSockFdMap_.erase(cliSockFd);
    LocalSocket::Close(cliSockFd);
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
        // 先按原 fd 从两个容器摘除再关闭：LocalSocket::Close 的入参是引用，会把 fd 改写成 -1，
        // 先 Close 会让下面的 map erase 变成 erase(-1)，cliSockFdMap_ 里留下永不释放的条目。
        iter = cliSockFds_.erase(iter);
        cliSockFdMap_.erase(cliSockFd);
        LocalSocket::Close(cliSockFd);
    }
}

void DynProfClient::SetSocketTimeout()
{
    // 快照：下面失败时会关闭 socket 并修改 cliSockFds_，不能边遍历边删
    const std::vector<int32_t> fds(cliSockFds_.begin(), cliSockFds_.end());
    for (auto cliSockFd : fds) {
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
        // 提前返回也必须复位启动标志，否则 Stop() 会对已退出的线程再调一次 Thread::Stop，
        // IsCliStarted() 也会一直返回 true。
        cliStarted_ = false;
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
        DynProfCliDispatch(it->second);
        if (inputCmd == "quit" || inputCmd == "q") {
            MSPROF_LOGI("receive quit signal, stop dynamic profiler");
            break;
        }
        std::cout << "> " << std::flush;
    }
    // 快照：DynProfCliStopSocket 会修改 cliSockFds_
    const std::vector<int32_t> restFds(cliSockFds_.begin(), cliSockFds_.end());
    for (auto cliSockFd : restFds) {
        DynProfCliStopSocket(cliSockFd);
    }
    cliStarted_ = false;
    MSPROF_LOGI("dynamic profiler client thread exit");
}

void DynProfClient::DynProfCliInitProcFunc()
{
    procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_START] =
        std::bind(&DynProfClient::DynProfCliProcStart, this, std::placeholders::_1, std::placeholders::_2);
    procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_STOP] =
        std::bind(&DynProfClient::DynProfCliProcStop, this, std::placeholders::_1, std::placeholders::_2);
    procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_QUIT] =
        std::bind(&DynProfClient::DynProfCliProcQuit, this, std::placeholders::_1, std::placeholders::_2);

    cmdReqMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_START] = DynProfMsgType::DYN_PROF_START_REQ;
    cmdReqMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_STOP] = DynProfMsgType::DYN_PROF_STOP_REQ;
    cmdReqMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_QUIT] = DynProfMsgType::DYN_PROF_QUIT_REQ;
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

    // 快照：失败时会关闭 socket 并修改 cliSockFds_
    const std::vector<int32_t> fds(cliSockFds_.begin(), cliSockFds_.end());

    // 阶段一：先向所有已连接的目标进程连续下发参数，不等待回执
    std::vector<int32_t> waiting;
    waiting.reserve(fds.size());
    for (auto cliSockFd : fds) {
        // 同上：参数下发阶段目标进程也可能刚退出，避免 SIGPIPE
        if (LocalSocket::Send(cliSockFd, &params, sizeof(params), MSG_NOSIGNAL) == PROFILING_FAILED) {
            MSPROF_LOGE("send params failed for pid %d", cliSockFdMap_.at(cliSockFd));
            DynProfCliStopSocket(cliSockFd);
            continue;
        }
        waiting.push_back(cliSockFd);
    }

    // 阶段二：所有回执共用一个超时预算，而不是每个 pid 各等一次
    const std::set<int32_t> ready = DynProfCliWaitReadable(waiting);
    for (auto cliSockFd : waiting) {
        const int32_t pid = cliSockFdMap_.at(cliSockFd);
        if (ready.count(cliSockFd) == 0) {
            CmdLog::CmdErrorLog("recv params timeout, server for pid %d has been connected to another client.", pid);
            MSPROF_LOGE("recv params timeout, server for pid %d has been connected to another client.", pid);
            DynProfCliStopSocket(cliSockFd);
            continue;
        }
        // 接收回执
        DynProfMsg rsqMsg;
        const int32_t ret = RecvFull(cliSockFd, &rsqMsg, sizeof(rsqMsg));
        if (ret == SOCKET_ERR_EAGAIN) {
            CmdLog::CmdErrorLog("recv params timeout, server for pid %d has been connected to another client.", pid);
            MSPROF_LOGE("recv params timeout, server for pid %d has been connected to another client.", pid);
            DynProfCliStopSocket(cliSockFd);
            continue;
        }
        if (ret != static_cast<int32_t>(sizeof(rsqMsg))) {
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

int32_t DynProfClient::DynProfCliSendReq(const int32_t cliSockFd, DynProfMsgType req) const
{
    DynProfMsg reqMsg;
    reqMsg.msgType = req;
    reqMsg.statusCode = DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL; // 请求中该字段无意义，显式初始化避免发送未初始化数据
    // MSG_NOSIGNAL：目标进程可能在 CheckServerPidsIfValid 之后、本次发送之前退出，
    // 向已断开的连接写数据会触发 SIGPIPE 直接终止 msprofbin 进程（msprofbin 未忽略 SIGPIPE）。
    if (LocalSocket::Send(cliSockFd, &reqMsg, sizeof(reqMsg), MSG_NOSIGNAL) != PROFILING_SUCCESS) {
        MSPROF_LOGE("send req: %d failed", static_cast<int32_t>(req));
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("client send req: %d", static_cast<int32_t>(req));
    return PROFILING_SUCCESS;
}

int32_t DynProfClient::RecvFull(const int32_t cliSockFd, void* buff, int32_t len) const
{
    // 字节游标用 uint8_t 而不是 char：这里收发的是二进制消息缓冲区（DynProfMsg），不是字符串，
    // 用 char* 表示会被检视工具判定为“用 char* 表示字符串”。
    uint8_t* cursor = static_cast<uint8_t*>(buff);
    int32_t received = 0;
    while (received < len) {
        const int32_t ret = LocalSocket::Recv(cliSockFd, cursor + received, len - received, 0);
        if (ret <= 0) {
            // 保留 SOCKET_ERR_EAGAIN 与错误码语义，交给调用方区分超时和其他失败
            return ret;
        }
        received += ret;
    }
    return received;
}

DynProfMsgRsqCode DynProfClient::DynProfCliRecvRsq(const int32_t cliSockFd, DynProfMsgType req) const
{
    // 接收回执
    DynProfMsg rsqMsg;
    if (RecvFull(cliSockFd, &rsqMsg, sizeof(rsqMsg)) != static_cast<int32_t>(sizeof(rsqMsg))) {
        MSPROF_LOGE("recv server rsq failed");
        return DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL;
    }
    MSPROF_LOGI("client recv rsq: %d(%d)", rsqMsg.msgType, rsqMsg.statusCode);
    // rsq在req后
    if (static_cast<int32_t>(rsqMsg.msgType) != static_cast<int32_t>(req) + 1) {
        MSPROF_LOGE(
            "req type:%d and rsq type:%d is not matched", static_cast<int32_t>(req),
            static_cast<int32_t>(rsqMsg.msgType));
        return DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL;
    }
    return rsqMsg.statusCode;
}

std::set<int32_t> DynProfClient::DynProfCliWaitReadable(const std::vector<int32_t>& waiting) const
{
    std::set<int32_t> ready;
    if (waiting.empty()) {
        return ready;
    }

    // 所有 pid 共用一份超时预算：批量下发后总等待时间不再随 pid 数量线性增长
    const int64_t deadlineMs = GetMonotonicMs() + static_cast<int64_t>(DYN_PROF_PROC_TIME_OUT) * DYN_PROF_MS_PER_SEC;
    std::vector<int32_t> pending = waiting;
    while (!pending.empty()) {
        const int64_t leftMs = deadlineMs - GetMonotonicMs();
        if (leftMs <= 0) {
            break;
        }
        std::vector<struct pollfd> pfds;
        pfds.reserve(pending.size());
        for (auto cliSockFd : pending) {
            struct pollfd pfd {};
            pfd.fd = cliSockFd;
            pfd.events = POLLIN;
            pfds.push_back(pfd);
        }
        const int32_t ret = poll(pfds.data(), static_cast<nfds_t>(pfds.size()), static_cast<int32_t>(leftMs));
        if (ret < 0) {
            if (errno == EINTR) {
                // 被信号打断不是超时：剩余预算内继续等，否则一次 EINTR 会让所有 pid 都判失败
                continue;
            }
            break;
        }
        if (ret == 0) {
            // 预算耗尽
            break;
        }
        std::vector<int32_t> next;
        next.reserve(pending.size());
        for (size_t i = 0; i < pfds.size(); ++i) {
            // POLLERR/POLLHUP/POLLNVAL 也一并收掉，否则这些 fd 会让 poll 反复就绪导致空转
            if ((pfds[i].revents & (POLLIN | POLLHUP | POLLERR | POLLNVAL)) == 0) {
                next.push_back(pending[i]);
                continue;
            }
            ready.insert(pending[i]);
        }
        pending.swap(next);
    }
    return ready;
}

void DynProfClient::DynProfCliDispatch(DynProfCliCmd cmd)
{
    const auto funcIt = procFuncMap_.find(cmd);
    const auto reqIt = cmdReqMap_.find(cmd);
    if (funcIt == procFuncMap_.cend() || reqIt == cmdReqMap_.cend()) {
        return;
    }
    const DynProfMsgType req = reqIt->second;

    // 快照：收执与处理阶段可能关闭 socket 并修改 cliSockFds_ / cliSockFdMap_
    const std::vector<int32_t> fds(cliSockFds_.begin(), cliSockFds_.end());

    // 阶段一：先向所有 pid 连续下发请求，不等待任何回执，使各目标进程尽可能同时收到命令
    std::vector<int32_t> waiting;
    waiting.reserve(fds.size());
    for (auto cliSockFd : fds) {
        if (DynProfCliSendReq(cliSockFd, req) != PROFILING_SUCCESS) {
            MSPROF_LOGE("send req for pid %d failed", cliSockFdMap_.at(cliSockFd));
            DynProfCliStopSocket(cliSockFd);
            continue;
        }
        waiting.push_back(cliSockFd);
    }

    // 阶段二：所有回执共用一个超时预算
    const std::set<int32_t> ready = DynProfCliWaitReadable(waiting);

    // 阶段三：逐个解释回执；处理函数内部可能关闭 socket，此处遍历的是快照
    for (auto cliSockFd : waiting) {
        if (ready.count(cliSockFd) == 0) {
            MSPROF_LOGE("recv rsq for pid %d timeout", cliSockFdMap_.at(cliSockFd));
            funcIt->second(cliSockFd, DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL);
            continue;
        }
        funcIt->second(cliSockFd, DynProfCliRecvRsq(cliSockFd, req));
    }
}

void DynProfClient::DynProfCliProcStart(const int32_t cliSockFd, const DynProfMsgRsqCode rsq)
{
    MSPROF_LOGI("dynamic profiling start message proc.");
    const int32_t pid = cliSockFdMap_.at(cliSockFd);
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

void DynProfClient::DynProfCliProcStop(const int32_t cliSockFd, const DynProfMsgRsqCode rsq)
{
    MSPROF_LOGI("dynamic profiling stop message proc.");
    const int32_t pid = cliSockFdMap_.at(cliSockFd);
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

void DynProfClient::DynProfCliProcQuit(const int32_t cliSockFd, const DynProfMsgRsqCode rsq) const
{
    MSPROF_LOGI("dynamic profiling quit message proc.");
    const int32_t pid = cliSockFdMap_.at(cliSockFd);
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
