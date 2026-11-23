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
static const char ACL_API_LIB_PATH[] = "libacl_rt.so";
static const std::set<std::string> g_aclApiStubSet = {"aclrtBinaryGetDevAddress", "aclrtFunctionGetBinary"};

static std::set<std::string> g_pluginApiStubSet = {
    "rtSetDevice",
    "rtDevBinaryRegister",
    "rtDevBinaryUnRegister",
    "rtFunctionRegister",
    "rtRegisterAllKernel",
    "rtGetBinaryDeviceBaseAddr",
    "rtProfSetProSwitch",
    "aclrtBinaryGetDevAddress",
    "rtMemcpy",
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
    "aclrtFunctionGetBinary",
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

static VOID_PTR LoadAclApiStubAddr(const std::string& funcName)
{
    VOID_PTR aclApiLibHandle = dlopen(ACL_API_LIB_PATH, RTLD_LAZY | RTLD_NOLOAD);
    if (aclApiLibHandle == nullptr) {
        const char* dlError = dlerror();
        MSPROF_LOGW("Dlopen api from %s failed, dlopen error: %s", ACL_API_LIB_PATH, dlError == nullptr ? "" : dlError);
        return nullptr;
    }

    VOID_PTR addr = dlsym(aclApiLibHandle, funcName.c_str());
    (void)dlclose(aclApiLibHandle);
    return addr;
}

void AcpApiPlugin::LoadRuntimeApi()
{
    FUNRET_CHECK_EXPR_ACTION(acpRuntimeLibHandle_ == nullptr, return, "Runtime handle is nullptr, load api failed.");
    for (auto& it : g_pluginApiStubSet) {
        const bool isAclApi = g_aclApiStubSet.find(it) != g_aclApiStubSet.cend();
        VOID_PTR addr = isAclApi ? LoadAclApiStubAddr(it) : nullptr;
        const char* libName = isAclApi ? ACL_API_LIB_PATH : RUNTIME_LIB_PATH;
        if (addr == nullptr) {
            addr = dlsym(acpRuntimeLibHandle_, it.c_str());
            libName = RUNTIME_LIB_PATH;
        }
        FUNRET_CHECK_EXPR_ACTION_LOGW(addr == nullptr, continue, "Unable to load API %s from %s.", it.c_str(), libName);

        MSPROF_LOGI("Load api[%s] from %s success.", it.c_str(), libName);
        apiStubInfoMap_.insert({it, {it, addr}});
    }

    msprofGetInjectionFunc_ =
        reinterpret_cast<MsprofGetInjectionFuncT>(dlsym(acpRuntimeLibHandle_, "MsprofGetInjectionFunc"));
    if (msprofGetInjectionFunc_ == nullptr) {
        MSPROF_LOGW("Unable to load MsprofGetInjectionFunc from %s.", RUNTIME_LIB_PATH);
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

rtError_t AcpApiPlugin::ApiGetBinaryData(aclrtBinHandle handle, std::vector<uint8_t>& data)
{
    aclrtBinaryGetDevAddress_ =
        reinterpret_cast<AclrtBinaryGetDevAddressFunc>(GetPluginApiStubFunc("aclrtBinaryGetDevAddress"));
    rtMemcpy_ = reinterpret_cast<RtMemcpyFunc>(GetPluginApiStubFunc("rtMemcpy"));
    if ((aclrtBinaryGetDevAddress_ == nullptr) || (rtMemcpy_ == nullptr)) {
        return ACL_ERROR_RT_PROFILING_ERROR;
    }

    void* binaryAddr = nullptr;
    size_t binarySize = 0;
    if (aclrtBinaryGetDevAddress_(handle, &binaryAddr, &binarySize) != ACL_SUCCESS) {
        return ACL_ERROR_RT_PROFILING_ERROR;
    }
    if ((binaryAddr == nullptr) || (binarySize == 0)) {
        return ACL_ERROR_RT_PROFILING_ERROR;
    }

    data.resize(binarySize);
    if (rtMemcpy_(data.data(), data.size(), binaryAddr, binarySize, RT_MEMCPY_DEVICE_TO_HOST) != RT_ERROR_NONE) {
        data.clear();
        return ACL_ERROR_RT_PROFILING_ERROR;
    }
    return RT_ERROR_NONE;
}

VOID_PTR AcpApiPlugin::GetPluginApiStubFunc(const std::string funcName)
{
    ProfAPI::PthreadOnce(&apiLoadFlag_, []() -> void { AcpApiPlugin::instance()->LoadRuntimeApi(); });
    {
        const std::lock_guard<std::mutex> lock(apiStubMutex_);
        auto it = apiStubInfoMap_.find(funcName);
        if (it != apiStubInfoMap_.cend()) {
            return it->second.funcAddr;
        }

        // libacl_rt may be loaded after the one-time runtime API preload. Retry ACL wrappers
        // lazily so late loading can recover without resetting the process-wide once flag.
        if (g_aclApiStubSet.find(funcName) != g_aclApiStubSet.cend()) {
            VOID_PTR addr = LoadAclApiStubAddr(funcName);
            if (addr != nullptr) {
                MSPROF_LOGI("Load api[%s] from %s success after retry.", funcName.c_str(), ACL_API_LIB_PATH);
                apiStubInfoMap_.insert({funcName, {funcName, addr}});
                return addr;
            }
        }
    }

    MSPROF_LOGE("Can't find api %s", funcName.c_str());
    return nullptr;
}

void* AcpApiPlugin::GetMsprofInjectionFunc(uint32_t type)
{
    ProfAPI::PthreadOnce(&apiLoadFlag_, []() -> void { AcpApiPlugin::instance()->LoadRuntimeApi(); });
    if (msprofGetInjectionFunc_ == nullptr) {
        MSPROF_LOGE("MsprofGetInjectionFunc is not loaded.");
        return nullptr;
    }

    return msprofGetInjectionFunc_(type);
}

} // namespace Acp
} // namespace Dvvp
} // namespace Collector
