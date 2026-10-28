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
#include "acp_api_plugin.h"
#include <set>
#include <dlfcn.h>
#include "msprof_dlog_tool.h"
#include "error_codes/rt_error_codes.h"
#include "utils/utils_tool.h"

namespace Collector {
namespace Dvvp {
namespace Acp {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;

static const char RUNTIME_LIB_PATH[] = "libruntime.so";

static std::set<std::string> g_pluginApiStubSet = {
    "rtSetDevice",
    "rtDevBinaryRegister",
    "rtDevBinaryUnRegister",
    "rtFunctionRegister",
    "rtRegisterAllKernel",
    "rtGetBinaryDeviceBaseAddr",
    "rtProfSetProSwitch",
    "rtKernelLaunch",
    "rtKernelLaunchWithHandle",
    "rtKernelLaunchWithHandleV2",
    "rtKernelLaunchWithFlag",
    "rtKernelLaunchWithFlagV2",
    "rtsLaunchKernelWithConfig",
    "rtsLaunchKernelWithDevArgs",
    "rtsLaunchKernelWithHostArgs",
    "rtLaunchKernelByFuncHandleV3",
    "rtLaunchKernelWithArgsArray",
    "rtStreamSynchronize",
    "rtMalloc",
    "rtFree",
    "rtMemcpyAsync"};

AcpApiPlugin::~AcpApiPlugin()
{
    if (acpRuntimeLibHandle_ != nullptr) {
        dlclose(acpRuntimeLibHandle_);
    }
}

void AcpApiPlugin::LoadRuntimeApi()
{
    FUNRET_CHECK_EXPR_ACTION(acpRuntimeLibHandle_ == nullptr, return, "Runtime handle is nullptr, load api failed.");
    for (auto& it : g_pluginApiStubSet) {
        auto addr = dlsym(acpRuntimeLibHandle_, it.c_str());
        FUNRET_CHECK_EXPR_ACTION_LOGW(
            addr == nullptr, continue, "Unable to load API %s from %s.", it.c_str(), RUNTIME_LIB_PATH);

        MSPROF_LOGI("Load api[%s] from %s success.", it.c_str(), RUNTIME_LIB_PATH);
        apiStubInfoMap_.insert({it, {it, addr}});
    }
}

AcpApiPlugin::AcpApiPlugin() : apiLoadFlag_(false)
{
    if (acpRuntimeLibHandle_ == nullptr) {
        MSPROF_LOGD("Init api handle from %s", RUNTIME_LIB_PATH);
        acpRuntimeLibHandle_ = dlopen(RUNTIME_LIB_PATH, RTLD_NOW | RTLD_GLOBAL | RTLD_NODELETE);
    }
    if (acpRuntimeLibHandle_ == nullptr) {
        MSPROF_LOGE("Dlopen api from %s failed, dlopen error: %s\n", RUNTIME_LIB_PATH, dlerror());
    }
    MSPROF_LOGD("%s has loaded runtime handle.", __FUNCTION__);
}

rtError_t AcpApiPlugin::ApiRtStreamSynchronize(rtStream_t stream)
{
    if (rtStreamSynchronize_ == nullptr) {
        rtStreamSynchronize_ = reinterpret_cast<RtStreamSynchronizeFunc>(GetPluginApiStubFunc("rtStreamSynchronize"));
        FUNRET_CHECK_EXPR_ACTION(
            rtStreamSynchronize_ == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
            "Failed to load api rtStreamSynchronize");
    }

    return rtStreamSynchronize_(stream);
}

rtError_t AcpApiPlugin::ApiRtGetBinaryDeviceBaseAddress(CONST_VOID_PTR handle, VOID_PTR& launchBase)
{
    if (rtGetBinaryDeviceBaseAddress_ == nullptr) {
        rtGetBinaryDeviceBaseAddress_ =
            reinterpret_cast<RtGetBinaryDeviceBaseAddressFunc>(GetPluginApiStubFunc("rtGetBinaryDeviceBaseAddr"));
        FUNRET_CHECK_EXPR_ACTION(
            rtGetBinaryDeviceBaseAddress_ == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
            "Failed to load api rtGetBinaryDeviceBaseAddr");
    }

    return rtGetBinaryDeviceBaseAddress_(handle, &launchBase);
}

VOID_PTR AcpApiPlugin::GetPluginApiStubFunc(const std::string funcName)
{
    ProfAPI::PthreadOnce(&apiLoadFlag_, []() -> void { AcpApiPlugin::instance()->LoadRuntimeApi(); });
    auto it = apiStubInfoMap_.find(funcName);
    if (it == apiStubInfoMap_.cend()) {
        MSPROF_LOGE("Can't find api %s", funcName.c_str());
        return nullptr;
    }

    return it->second.funcAddr;
}

} // namespace Acp
} // namespace Dvvp
} // namespace Collector
