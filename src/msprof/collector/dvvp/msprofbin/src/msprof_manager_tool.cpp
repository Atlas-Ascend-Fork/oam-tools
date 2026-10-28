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

#include "msprof_manager_tool.h"
#include "errno/error_code_tool.h"
#include "cmd_log/cmd_log_tool.h"
#include "message/prof_params.h"
#include "platform/platform_tool.h"
#include "dyn_prof_client_tool.h"
#include "input_parser_tool.h"

namespace Analysis {
namespace Dvvp {
namespace Msprof {
using namespace analysis::dvvp::common::cmdlog;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::message;
using namespace Collector::Dvvp::Msprofbin;
using namespace Collector::Dvvp::DynProf;
using namespace Analysis::Dvvp::Common::Platform;

MsprofManager::MsprofManager() {}

MsprofManager::~MsprofManager() {}

int32_t MsprofManager::Init(SHARED_PTR_ALIA<ProfileParams> params)
{
    MSPROF_LOGI("init MsprofManager begin.");
    if (params == nullptr) {
        MSPROF_LOGE("MsprofManager init failed because of params is null.");
        return PROFILING_FAILED;
    }
    params_ = params;
    if (GenerateRunningMode() != PROFILING_SUCCESS) {
        MSPROF_LOGE("MsprofManager init failed because of generating running mode error.");
        return PROFILING_FAILED;
    }
    if (ParamsCheck() != PROFILING_SUCCESS) {
        MSPROF_LOGE("MsprofManager init failed because of checking params failed.");
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("init MsprofManager end.");
    return PROFILING_SUCCESS;
}

int32_t MsprofManager::UnInit()
{
    params_.reset();
    rMode_.reset();
    return PROFILING_SUCCESS;
}

void MsprofManager::NotifyStop()
{
    if (rMode_ == nullptr) {
        return;
    }
    rMode_->isQuit_ = true;
}

int32_t MsprofManager::MsProcessCmd() const
{
    if (rMode_ == nullptr) {
        MSPROF_LOGE("[MsprocessCmd] No running mode found!");
        return PROFILING_FAILED;
    }
    return rMode_->RunModeTasks();
}

int32_t MsprofManager::GenerateRunningMode()
{
    MSPROF_LOGI("[MsprofManager] GenerateRunningMode");
    if (params_ == nullptr) {
        MSPROF_LOGE("[MsprocessCmd] Invalid params!");
        return PROFILING_FAILED;
    }

    if (GenerateCollectRunningMode() == PROFILING_SUCCESS || GenerateAnalyzeRunningMode() == PROFILING_SUCCESS) {
        return PROFILING_SUCCESS;
    }

    if (Platform::instance()->RunSocSide()) {
        CmdLog::CmdErrorLog("No valid argument found in --application --sys-devices");
    } else {
        CmdLog::CmdErrorLog("No valid argument found in --application "
                            "--sys-devices --host-sys --host-sys-usage --parse --query --export --analyze");
    }

    ArgsManager::instance()->PrintHelp();
    return PROFILING_FAILED;
}

int32_t MsprofManager::GenerateCollectRunningMode()
{
    if (!params_->app.empty() || DynProfCliMgr::instance()->IsDynProfCliEnable()) {
        MSVP_MAKE_SHARED2(rMode_, AppMode, "application", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    if (!params_->devices.empty()) {
        if (Platform::instance()->PlatformIsHelperHostSide()) {
            CmdLog::CmdErrorLog("sys-device mode not support in helper");
            return PROFILING_FAILED;
        }
        MSVP_MAKE_SHARED2(rMode_, SystemMode, "sys-devices", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    if (!params_->host_sys.empty()) {
        if (Platform::instance()->PlatformIsHelperHostSide()) {
            CmdLog::CmdErrorLog("sys-host_sys mode not support in helper");
            return PROFILING_FAILED;
        }
        MSVP_MAKE_SHARED2(rMode_, SystemMode, "host-sys", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    if (!params_->hostSysUsage.empty()) {
        if (Platform::instance()->PlatformIsHelperHostSide()) {
            CmdLog::CmdErrorLog("sys-host_sys_usage mode not support in helper");
            return PROFILING_FAILED;
        }
        MSVP_MAKE_SHARED2(rMode_, SystemMode, "host-sys-usage", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    return PROFILING_FAILED;
}

int32_t MsprofManager::GenerateAnalyzeRunningMode()
{
    if (params_->parseSwitch == MSVP_PROF_ON) {
        MSVP_MAKE_SHARED2(rMode_, ParseMode, "parse", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    if (params_->querySwitch == MSVP_PROF_ON) {
        MSVP_MAKE_SHARED2(rMode_, QueryMode, "query", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    if (params_->exportSwitch == MSVP_PROF_ON) {
        MSVP_MAKE_SHARED2(rMode_, ExportMode, "export", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    if (params_->analyzeSwitch == MSVP_PROF_ON) {
        MSVP_MAKE_SHARED2(rMode_, AnalyzeMode, "analyze", params_, return PROFILING_FAILED);
        return PROFILING_SUCCESS;
    }

    return PROFILING_FAILED;
}

int32_t MsprofManager::ParamsCheck() const
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[MsprocessCmd] Invalid params!");
        return PROFILING_FAILED;
    }
    if (rMode_ == nullptr) {
        MSPROF_LOGE("[MsprocessCmd] Invalid running mode!");
        return PROFILING_FAILED;
    }
    if (rMode_->ModeParamsCheck() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[MsprocessCmd] Invalid input arguments!");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}
} // namespace Msprof
} // namespace Dvvp
} // namespace Analysis
