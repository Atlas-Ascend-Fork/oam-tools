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

#include "application_tool.h"
#include <fstream>
#include <algorithm>
#include "config/config.h"
#include "errno/error_code_tool.h"
#include "osal.h"
#include "msprof_dlog_tool.h"
#include "utils/utils_tool.h"
#include "validation/param_validation_tool.h"
#include "env_manager_tool.h"
#include "dyn_prof_client_tool.h"
namespace analysis {
namespace dvvp {
namespace app {
using namespace Analysis::Dvvp::App;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::message;
using namespace analysis::dvvp::common::validation;
using namespace Collector::Dvvp::DynProf;

int32_t Application::PrepareLaunchAppCmd(
    std::stringstream& ssCmdApp, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params)
{
    if (params->app_dir.empty()) {
        MSPROF_LOGE("app_dir is empty");
        return PROFILING_FAILED;
    }
    if (!ParamValidation::instance()->CheckAppNameIsValid(params->app)) {
        MSPROF_LOGE("app name(%s) is not valid.", params->app.c_str());
        return PROFILING_FAILED;
    }
    ssCmdApp << params->cmdPath;

    if (!params->app_parameters.empty()) {
        ssCmdApp << " ";
        ssCmdApp << params->app_parameters;
    }

    return PROFILING_SUCCESS;
}

std::string Application::GetCmdString(const std::string paramsName)
{
    if (paramsName.empty()) {
        return "";
    }
    if (analysis::dvvp::common::utils::Utils::IsAppName(paramsName)) {
        return analysis::dvvp::common::utils::Utils::CanonicalizePath(paramsName);
    } else {
        return paramsName;
    }
}

void Application::PrepareAppArgs(const std::vector<std::string>& params, std::vector<std::string>& argsV)
{
    for (uint32_t i = 1; i < params.size(); ++i) {
        if (!params[i].empty()) {
            argsV.push_back(params[i]);
        }
    }
}

int32_t Application::PrepareAppEnvs(
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::vector<std::string>& envsV)
{
    if (params == nullptr) {
        MSPROF_LOGE("params is nullptr");
        return PROFILING_FAILED;
    }

    // acl app
    SetAppEnv(params, envsV);

    return PROFILING_SUCCESS;
}

int32_t Application::ResolveAppCmd(
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::vector<std::string>& paramsCmd,
    std::string& cmd)
{
    if (!params->application.empty()) {
        paramsCmd = params->application;
        cmd = paramsCmd[0];
        return PROFILING_SUCCESS;
    }

    std::stringstream ssCmdApp; // cmd
    if (PrepareLaunchAppCmd(ssCmdApp, params) != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("Launch application %s", Utils::BaseName(params->cmdPath).c_str());
    paramsCmd = analysis::dvvp::common::utils::Utils::Split(ssCmdApp.str());
    if (paramsCmd.empty()) {
        MSPROF_LOGE("[LaunchApp]paramsCmd is empty.");
        return PROFILING_FAILED;
    }
    cmd = GetCmdString(paramsCmd[0]);
    if (cmd.empty()) {
        MSPROF_LOGE("app_dir(%s) is not valid.", Utils::BaseName(paramsCmd[0]).c_str());
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

int32_t Application::LaunchApp(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, OsalProcess& appProcess)
{
    if (params == nullptr) {
        MSPROF_LOGE("[LaunchApp]params is empty.");
        return PROFILING_FAILED;
    }
    std::vector<std::string> paramsCmd;
    std::string cmd;
    if (ResolveAppCmd(params, paramsCmd, cmd) != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }

    std::vector<std::string> argsVec;
    std::vector<std::string> envsVec;
    PrepareAppArgs(paramsCmd, argsVec);            // args
    int32_t ret = PrepareAppEnvs(params, envsVec); // envs
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to PrepareAppEnvs, cmd:%s", cmd.c_str());
        return PROFILING_FAILED;
    }
    appProcess = MSVP_PROCESS; // run

    int32_t exitCode = analysis::dvvp::common::utils::INVALID_EXIT_CODE;
    ExecCmdParams execCmdParams(cmd, true, "");
    ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsVec, envsVec, exitCode, appProcess);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to launch app: %s", cmd.c_str());
        return PROFILING_FAILED;
    }
    return ret;
}

void Application::SetAppEnv(
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::vector<std::string>& envsV)
{
    std::vector<std::string> appEnvs = analysis::dvvp::common::utils::Utils::Split(params->app_env, false, "", ";");
    MSPROF_LOGI("Handle app_env parameter with %zu entries", appEnvs.size());
    for (auto appEnv : appEnvs) {
        if (!appEnv.empty()) {
            if (appEnv.find("=") == std::string::npos) {
                MSPROF_LOGW("Invalid app_env parameter; expected KEY=VALUE");
                continue;
            }
            envsV.push_back(appEnv);
        }
    }
    auto envList = EnvManager::instance()->GetGlobalEnv();
    for (auto env : envList) {
        envsV.push_back(env);
    }
    std::string paramEnv = EnvManager::instance()->GetParamEnv();
    paramEnv = paramEnv.empty() ? PROFILER_SAMPLE_CONFIG_ENV : paramEnv;
    paramEnv.append("=");
    paramEnv.append(params->ToString());
    envsV.push_back(paramEnv);
    if (DynProfCliMgr::instance()->IsDynProfCliEnable()) {
        auto itr = std::find_if(
            envsV.begin(), envsV.end(), [](const std::string& value) { return value.find(PROFILING_MODE_ENV) == 0; });
        auto&& dynProfEnv = DynProfCliMgr::instance()->GetDynProfEnv();
        if (itr != envsV.end()) {
            *itr = dynProfEnv;
        } else {
            envsV.push_back(dynProfEnv);
        }
    }
    if (DynProfCliMgr::instance()->IsAppMode()) {
        envsV.push_back(DynProfCliMgr::instance()->GetKeyPidEnv());
    }
    if (!params->delayTime.empty() || !params->durationTime.empty()) {
        envsV.push_back(PROFILING_MODE_ENV + "=" + DELAY_DURARION_PROFILING_VALUE);
    }
}
} // namespace app
} // namespace dvvp
} // namespace analysis
