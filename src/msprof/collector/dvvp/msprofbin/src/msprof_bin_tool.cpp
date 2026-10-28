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

#include <iostream>
#include <fstream>
#include <string>
#include <thread>
#include <condition_variable>
#include <mutex>
#include "message/prof_params.h"
#include "errno/error_code_tool.h"
#include "msprof_manager_tool.h"
#include "input_parser_tool.h"
#include "env_manager_tool.h"
#include "platform/platform_tool.h"
#include "config/config.h"
#include "cmd_log/cmd_log_tool.h"
#include "dyn_prof_client_tool.h"
#include "msopprof_manager_tool.h"

using namespace Analysis::Dvvp::App;
using namespace Analysis::Dvvp::Msprof;
using namespace Analysis::Dvvp::Msopprof;
using namespace analysis::dvvp::common::cmdlog;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Collector::Dvvp::Msprofbin;
using namespace Collector::Dvvp::DynProf;

#if defined(__PROF_LLT)
#define STATIC
#else
#define STATIC static
#endif

STATIC void PrintOutPutDir()
{
    if (MsprofManager::instance()->rMode_ == nullptr || MsprofManager::instance()->rMode_->jobResultDir_.empty()) {
        return;
    }
    auto& outputDirInfo = MsprofManager::instance()->rMode_->jobResultDir_;
    CmdLog::CmdInfoLog("Process profiling data complete. Data is saved in %s", outputDirInfo.c_str());
}

STATIC void SetEnvList(CONST_CHAR_PTR& envp, std::vector<std::string>& envpList)
{
    uint32_t envpLen = 0;
    constexpr uint32_t maxEnvpLen = 4096;
    CONST_CHAR_PTR_PTR env = &envp;
    while (*env) {
        envpList.push_back(*env++);
        envpLen++;
        if (envpLen >= maxEnvpLen) {
            CmdLog::CmdErrorLog("Truncate env params due to exceeding limit!");
            break;
        }
    }
}

STATIC void StopProfiling(int signum)
{
    UNUSED(signum);
    usleep(OSAL_TIMES_MILLIONS);
    if (DynProfCliMgr::instance()->IsCliStarted()) {
        CmdLog::CmdLogNoLevel("Use 'quit' or 'q' to exit dynamic profiling.");
    }
    MsprofManager::instance()->NotifyStop();
}

#ifdef __PROF_LLT
int LltMain(int argc, const char** argv, const char** envp)
#else
int main(int argc, const char** argv, const char** envp)
#endif
{
    std::vector<std::string> envpList;
    SetEnvList(*envp, envpList);
    EnvManager::instance()->SetGlobalEnv(envpList);
    if (Platform::instance()->PlatformInitByDriver() != PROFILING_SUCCESS) {
        CmdLog::CmdErrorLog("Init platform by driver failed!");
        return PROFILING_FAILED;
    }
    if (Platform::instance()->Init() != PROFILING_SUCCESS) {
        CmdLog::CmdErrorLog("MsprofManager init failed because of init platform mode error.");
        return PROFILING_FAILED;
    }
    InputParser parser = InputParser();
    if (argc <= 1) {
        parser.MsprofCmdUsage("");
        return PROFILING_FAILED;
    }
    if (MsopprofManager::instance()->MsopprofProcess(argc, argv) == PROFILING_SUCCESS) {
        return PROFILING_SUCCESS;
    }
    auto params = parser.MsprofGetOpts(argc, argv);
    if (params == nullptr) {
        return PROFILING_FAILED;
    }
    if (parser.HasHelpParamOnly()) {
        return PROFILING_SUCCESS;
    }
    if (MsprofManager::instance()->Init(params) != PROFILING_SUCCESS) {
        CmdLog::CmdErrorLog("Start profiling failed");
        return PROFILING_FAILED;
    }
    signal(SIGINT, [](int signum) { StopProfiling(signum); });
    CmdLog::CmdInfoLog("Start profiling....");
    auto ret = MsprofManager::instance()->MsProcessCmd();
    if (ret != PROFILING_SUCCESS) {
        if (ret == PROFILING_NOTSUPPORT) {
            CmdLog::CmdWarningLog("System profiling isn't supported in container of ascend virtual instance.");
        } else {
            CmdLog::CmdErrorLog("Running profiling failed. Please check log for more info.");
        }
        DlogFlush();
        return ret;
    }
    if (!DynProfCliMgr::instance()->IsDynProfCliEnable()) {
        CmdLog::CmdInfoLog("Profiling finished.");
        PrintOutPutDir();
    }
    return PROFILING_SUCCESS;
}
