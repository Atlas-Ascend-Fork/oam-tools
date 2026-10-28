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

#include "msopprof_manager_tool.h"
#include <string>
#include <csignal>
#include "cmd_log/cmd_log_tool.h"
#include "env_manager_tool.h"
#include "config_manager_tool.h"
#include "param_validation_tool.h"
#include "errno/error_code_tool.h"

namespace Analysis {
namespace Dvvp {
namespace Msopprof {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::validation;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::cmdlog;
using namespace Analysis::Dvvp::App;

MsopprofManager::MsopprofManager() : msopprofPid_(MSVP_PROCESS)
{
    std::string ascendToolkitHome;
    MSPROF_GET_ENV(MM_ENV_ASCEND_TOOLKIT_HOME, ascendToolkitHome);
    if (!ascendToolkitHome.empty()) {
        msopprofPath_ = ascendToolkitHome + "/tools/msopprof/bin/msopprof";
    }
}

int MsopprofManager::MsopprofProcess(int argc, CONST_CHAR_PTR argv[])
{
    if (!Utils::CheckInputArgsLength(argc, argv)) {
        return PROFILING_FAILED;
    }

    std::vector<std::string> opArgv;
    if (!CheckMsopprofIfExist(argc, argv, opArgv)) {
        return PROFILING_FAILED;
    }

    if (!msopprofPath_.empty() && Utils::CheckBinValid(msopprofPath_)) {
        ExecuteMsopprof(opArgv);
    }

    return PROFILING_SUCCESS;
}

bool MsopprofManager::CheckMsopprofIfExist(int argc, CONST_CHAR_PTR argv[], std::vector<std::string>& opArgv) const
{
    bool ret = false;
    static std::string msopprofCmd = "op";
    if (argc > 1 && strncmp(argv[1], msopprofCmd.c_str(), msopprofCmd.size()) == 0) {
        ret = true;
    }
    if (ret) {
        if (msopprofPath_.empty()) {
            CmdLog::CmdErrorLog("Cannot find msopprof, "
                                "Maybe you should source set_env.sh in advance.");
        } else {
            for (int i = 2; i < argc; i++) {
                opArgv.emplace_back(argv[i]);
            }
        }
    }
    return ret;
}

void MsopprofManager::ExecuteMsopprof(const std::vector<std::string>& opArgv)
{
    (void)signal(SIGINT, [](int signum) {
        (void)Utils::UsleepInterupt(OSAL_TIMES_MILLIONS);
        CmdLog::CmdInfoLog("Msopprof received signal %d, exiting now.", signum);
    });
    auto envV = EnvManager::instance()->GetGlobalEnv();

    int32_t exitCode = INVALID_EXIT_CODE;
    ExecCmdParams execCmdParams(msopprofPath_, true, "");
    int32_t ret = Utils::ExecCmd(execCmdParams, opArgv, envV, exitCode, msopprofPid_);
    if (ret != PROFILING_SUCCESS) {
        CmdLog::CmdErrorLog("Execute msopprof failed.");
        return;
    }
    bool isExited = false;
    ret = Utils::WaitProcess(msopprofPid_, isExited, exitCode, true);
    if (ret != PROFILING_SUCCESS) {
        CmdLog::CmdErrorLog("Wait msopprof process failed.");
    }
}

bool MsopprofManager::IsMsopprofExist() const { return !msopprofPath_.empty() && Utils::IsFileExist(msopprofPath_); }
} // namespace Msopprof
} // namespace Dvvp
} // namespace Analysis
