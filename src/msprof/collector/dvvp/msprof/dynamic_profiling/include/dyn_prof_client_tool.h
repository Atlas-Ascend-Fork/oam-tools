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
#ifndef COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_CLIENT_H
#define COLLECTOR_DVVP_MSPROF_DYNAMIC_PROFILING_DYN_PROF_CLIENT_H

#include <atomic>
#include <cstdint>
#include <functional>
#include <map>
#include <set>
#include "dyn_prof_def_tool.h"
#include "thread/thread_tool.h"

namespace Collector {
namespace Dvvp {
namespace DynProf {
enum class DynProfCliCmd {
    DYN_PROF_CLI_CMD_START = 0,
    DYN_PROF_CLI_CMD_STOP,
    DYN_PROF_CLI_CMD_QUIT,
    DYN_PROF_CLI_CMD_HELP,
    DYN_PROF_CLI_CMD_UNKNOW
};

class DynProfClient : public analysis::dvvp::common::thread::Thread {
public:
    DynProfClient() = default;
    ~DynProfClient() override = default;

    void SetParams(const std::string& params);
    int32_t Start() override;
    int32_t Stop() override;
    bool IsCliStarted() const;

protected:
    void Run(const error_message::ErrorManagerContext& errorContext) override;

private:
    void DynProfCliInitProcFunc();
    int32_t DynProfCliCreate();
    int32_t DynProfCliSendParams();

    DynProfMsgRsqCode DynProfCliSendCmd(const int32_t cliSockFd, DynProfMsgType req) const;
    void DynProfCliProcStart(const int32_t cliSockFd);
    void DynProfCliProcStop(const int32_t cliSockFd);
    void DynProfCliProcQuit(const int32_t cliSockFd) const;
    void DynProfCliHelpInfo() const;
    int32_t DynProfCliConnectSocket(const int32_t cliSockFd, const std::string& srvSockDomain) const;
    void DynProfCliStopSocket(int32_t cliSockFd);
    void CheckServerPidsIfValid();
    int TryReadInputCmd(std::string& inputCmd) const;
    void SetSocketTimeout();

    std::set<int32_t> cliSockFds_;
    std::atomic<bool> cliStarted_{false};
    std::string dynProfParams_;
    std::map<DynProfCliCmd, ProcFunc> procFuncMap_;
    std::map<int32_t, int32_t> cliSockFdMap_;
};

class DynProfCliMgr : public analysis::dvvp::common::singleton::Singleton<DynProfCliMgr> {
    friend analysis::dvvp::common::singleton::Singleton<DynProfCliMgr>;

public:
    ~DynProfCliMgr() override;
    int32_t StartDynProfCli(const std::string& params);
    void StopDynProfCli();
    void SetKeyPid(const std::vector<int32_t> pids);
    std::set<int32_t> GetKeyPid() const;
    std::string GetKeyPidEnv() const;
    void EnableDynProfCli();
    bool IsDynProfCliEnable() const;
    std::string GetDynProfEnv() const;
    void SetAppMode();
    bool IsAppMode() const;
    bool IsCliStarted() const;
    void WaitQuit();

private:
    DynProfCliMgr() = default;
    bool enabled_{false};
    bool isAppMode_{false};     // --application
    std::set<int32_t> keyPids_; // --application: msprofbin pid; --pid: app pid
    SHARED_PTR_ALIA<Collector::Dvvp::DynProf::DynProfClient> dynProfCli_;
};
} // namespace DynProf
} // namespace Dvvp
} // namespace Collector

#endif
