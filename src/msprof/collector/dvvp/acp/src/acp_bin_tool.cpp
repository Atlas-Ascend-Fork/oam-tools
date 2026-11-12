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
#include "cmd_log/cmd_log_tool.h"
#include "argparser_tool.h"
#include "acp_command.h"
#include "env_manager_tool.h"

using namespace analysis::dvvp::common::cmdlog;
using namespace Analysis::Dvvp::App;
using namespace analysis::dvvp::common::utils;
using namespace Collector::Dvvp::Acp;

static bool IsEnvNeedFilter(const std::string& envItem)
{
    // ASCEND_WORK_PATH/ASCEND_DUMP_PATH 会激活应用内 IDEDD（kernel dfx dump），其初始化
    // 将提前触发 runtime Boot，此时芯片属性尚未注册导致 Boot 失败报错（首次必败、二次成功）。
    // 单算子采集场景不依赖 dump 能力，过滤以消除该初始化竞态噪音。
    constexpr char ASCEND_WORK_PATH_PREFIX[] = "ASCEND_WORK_PATH=";
    constexpr char ASCEND_DUMP_PATH_PREFIX[] = "ASCEND_DUMP_PATH=";
    return (envItem.compare(0, sizeof(ASCEND_WORK_PATH_PREFIX) - 1, ASCEND_WORK_PATH_PREFIX) == 0) ||
           (envItem.compare(0, sizeof(ASCEND_DUMP_PATH_PREFIX) - 1, ASCEND_DUMP_PATH_PREFIX) == 0);
}

static void SetEnvList(CONST_CHAR_PTR& envp, std::vector<std::string>& envpList)
{
    uint32_t envpLen = 0;
    constexpr uint32_t maxEnvpLen = 4096;
    const char** env = &envp;
    while (*env) {
        const std::string envItem = *env++;
        if (IsEnvNeedFilter(envItem)) {
            continue;
        }
        envpList.push_back(envItem);
        envpLen++;
        if (envpLen >= maxEnvpLen) {
            CmdLog::CmdErrorLog("Truncate env params due to exceeding limit!");
            break;
        }
    }
}

#ifdef __PROF_LLT
int32_t LltAcpMain(int32_t argc, const char* argv[], const char** envp)
#else
int32_t main(int32_t argc, const char* argv[], const char** envp)
#endif
{
    std::vector<std::string> envpList;
    SetEnvList(*envp, envpList);
    EnvManager::instance()->SetGlobalEnv(envpList);
    EnvManager::instance()->SetParamEnv("acp");
    auto acpCommand = AcpCommandBuild("acp");
    acpCommand.Parse(argc, argv);
    return acpCommand.Execute();
}
