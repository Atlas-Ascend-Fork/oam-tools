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
#include <dlfcn.h>
#include <mutex>
#include <thread>
#include <unistd.h>
#include "acl/acl_prof.h"
#include "acl/acl_rt.h"
#include "runtime/dev.h"
#include "runtime/kernel.h"
#include "platform/platform_tool.h"
#include "errno/error_code_tool.h"
#include "error_codes/rt_error_codes.h"
#include "acp_aclrt_injection_tool.h"
#include "acp_api_plugin.h"
#include "acp_manager_tool.h"

using namespace Collector::Dvvp::Acp;
using namespace analysis::dvvp::common::error;

namespace Collector {
namespace Dvvp {
namespace Acp {

static std::mutex g_setDeviceMtx;
static std::mutex g_hookRegisterMtx;

constexpr uint32_t KERNEL_TASK_TIME = 5;
constexpr uint16_t ACP_APP_MODE_ID = 33U; // 与 runtime 仓 acl::APP_MODE_ID_U16（APP=33）一致
constexpr int32_t HOOK_TOTAL_COUNT = 13;
constexpr int32_t RETRY_MAX_TIMES = 74;
// 首轮退避 5ms：覆盖启动链场景下 libacl_rt 紧随 libruntime 构造的窗口（已 map 未 init），
// 避免对未注册查找表查询产生 runtime 侧错误日志
constexpr useconds_t RETRY_FIRST_INTERVAL_US = 5000;
constexpr useconds_t RETRY_MAX_INTERVAL_US = 1000000;
constexpr uint32_t RETRY_BACKOFF_FACTOR = 2U;
constexpr char ACLRT_LIB_NAME[] = "libacl_rt.so";
constexpr char PROBE_NAME[] = "aclrtSetDevice";

using AclrtSetDeviceFunc = aclError (*)(int32_t);
using AclrtMallocFunc = aclError (*)(void**, size_t, aclrtMemMallocPolicy);
using AclrtFreeFunc = aclError (*)(void*);
using AclrtBinaryLoadFunc = aclError (*)(aclrtBinary, aclrtBinHandle*);
using AclrtBinaryUnLoadFunc = aclError (*)(aclrtBinHandle);
using AclrtBinaryGetFunctionFunc = aclError (*)(aclrtBinHandle, const char*, aclrtFuncHandle*);
using AclrtLaunchKernelFunc = aclError (*)(aclrtFuncHandle, uint32_t, const void*, size_t, aclrtStream);
using AclrtLaunchKernelWithConfigFunc =
    aclError (*)(aclrtFuncHandle, uint32_t, aclrtStream, aclrtLaunchKernelCfg*, aclrtArgsHandle, void*);
using AclrtLaunchKernelV2Func =
    aclError (*)(aclrtFuncHandle, uint32_t, const void*, size_t, aclrtLaunchKernelCfg*, aclrtStream);
using AclrtLaunchKernelWithHostArgsFunc = aclError (*)(
    aclrtFuncHandle, uint32_t, aclrtStream, aclrtLaunchKernelCfg*, void*, size_t, aclrtPlaceHolderInfo*, size_t);
using AclrtLaunchKernelWithArgsArrayFunc = aclError (*)(void*, uint32_t, aclrtStream, aclrtLaunchKernelCfg*, void**);

static AclrtApiFuncT g_aclrtSetDeviceOrigin = nullptr;
static AclrtApiFuncT g_aclrtMallocOrigin = nullptr;
static AclrtApiFuncT g_aclrtMallocAlign32Origin = nullptr;
static AclrtApiFuncT g_aclrtMallocCachedOrigin = nullptr;
static AclrtApiFuncT g_aclrtFreeOrigin = nullptr;
static AclrtApiFuncT g_aclrtBinaryLoadOrigin = nullptr;
static AclrtApiFuncT g_aclrtBinaryUnLoadOrigin = nullptr;
static AclrtApiFuncT g_aclrtBinaryGetFunctionOrigin = nullptr;
static AclrtApiFuncT g_aclrtLaunchKernelOrigin = nullptr;
static AclrtApiFuncT g_aclrtLaunchKernelWithConfigOrigin = nullptr;
static AclrtApiFuncT g_aclrtLaunchKernelV2Origin = nullptr;
static AclrtApiFuncT g_aclrtLaunchKernelWithHostArgsOrigin = nullptr;
static AclrtApiFuncT g_aclrtLaunchKernelWithArgsArrayOrigin = nullptr;

static void SaveBinaryBaseAddr()
{
    if (!AcpManager::instance()->PcSamplingIsEnable()) {
        return;
    }
    void* baseAddress = nullptr;
    auto hdl = AcpManager::instance()->GetBinaryHandle();
    auto error = AcpApiPlugin::instance()->ApiRtGetBinaryDeviceBaseAddress(hdl, baseAddress);
    if (error == RT_ERROR_NONE) {
        AcpManager::instance()->AddBinaryBaseAddr(hdl, baseAddress);
    } else {
        MSPROF_LOGW("Unable to get base address, code info = %u", error);
    }
}

/**
 * @name  KernelWarmUp
 * @brief Template method. Start Warm up process in different KernelLaunch phases.
 * @param [in] stream: operator stream id
 * @param [in] func: original aclrt kernel launch implementation
 * @param [in] args: input params from different KernelLaunch
 * @return RT_ERROR_NONE:SUCCESS, !RT_ERROR_NONE:FAILED
 */
template <typename Func, typename... Args>
static rtError_t KernelWarmUp(rtStream_t& stream, Func&& func, Args&&... args)
{
    rtError_t ret = RT_ERROR_NONE;
    ret = std::forward<Func>(func)(std::forward<Args>(args)...);
    FUNRET_CHECK_EXPR_ACTION(ret != RT_ERROR_NONE, return ret, "Failed to warm up kernel, ret: %d.", ret);
    ret = AcpApiPlugin::instance()->ApiRtStreamSynchronize(stream);
    FUNRET_CHECK_EXPR_ACTION(ret != RT_ERROR_NONE, return ret, "Failed to execute rtStreamSynchronize, ret: %d.", ret);
    return ret;
}

/**
 * @name  KernelReplay
 * @brief Template method. Start profiling process in different KernelLaunch phases.
 * @param [in] stream: operator stream id
 * @param [in] func: original aclrt kernel launch implementation
 * @param [in] args: input params from different KernelLaunch
 * @return RT_ERROR_NONE:SUCCESS, !RT_ERROR_NONE:FAILED
 */
template <typename Func, typename... Args>
static rtError_t KernelReplay(rtStream_t& stream, Func&& func, Args&&... args)
{
    rtError_t ret = RT_ERROR_NONE;
    int32_t acpRet = PROFILING_SUCCESS;
    for (uint32_t time = 0; time < KERNEL_TASK_TIME; ++time) {
        AcpManager::instance()->ResetMallocMemory(stream);
        acpRet = AcpManager::instance()->TaskStart();
        FUNRET_CHECK_EXPR_PRINT(acpRet != PROFILING_SUCCESS, "Failed to start acp task.");
        ret = std::forward<Func>(func)(std::forward<Args>(args)...);
        FUNRET_CHECK_EXPR_PRINT(ret != RT_ERROR_NONE, "Failed to execute kernel, ret: %d.", ret);
        if (ret == RT_ERROR_NONE) {
            SaveBinaryBaseAddr();
            ret = AcpApiPlugin::instance()->ApiRtStreamSynchronize(stream);
            FUNRET_CHECK_EXPR_PRINT(ret != RT_ERROR_NONE, "Failed to execute rtStreamSynchronize, ret: %d.", ret);
        }
        acpRet = AcpManager::instance()->TaskStop();
        FUNRET_CHECK_EXPR_PRINT(acpRet != PROFILING_SUCCESS, "Failed to stop acp task.");
        FUNRET_CHECK_EXPR_ACTION(
            ret != RT_ERROR_NONE || acpRet != PROFILING_SUCCESS, break, "Failed to execute kernel task, time: %u.",
            time);
    }

    return ret;
}

/**
 * @name  KernelExec
 * @brief Template method. Start kernel execution in different KernelLaunch phases.
 * @param [in] stream: operator stream id
 * @param [in] func: original aclrt kernel launch implementation
 * @param [in] args: input params from different KernelLaunch
 * @return RT_ERROR_NONE:SUCCESS, !RT_ERROR_NONE:FAILED
 */
template <typename Func, typename... Args>
static rtError_t KernelExec(rtStream_t stream, Func&& func, Args&&... args)
{
    rtError_t ret = RT_ERROR_NONE;
    AcpManager::instance()->SaveMallocMemory(stream);
    ret = KernelWarmUp(stream, func, args...);
    FUNRET_CHECK_EXPR_ACTION(ret != RT_ERROR_NONE, return ret, "Failed to warm up kernel replay, ret: %d.", ret);
    AcpManager::instance()->ResetMallocMemory(stream);
    ret = KernelWarmUp(stream, func, args...);
    FUNRET_CHECK_EXPR_ACTION(ret != RT_ERROR_NONE, return ret, "Failed to warm up kernel replay, ret: %d.", ret);
    uint32_t replayTime = AcpManager::instance()->GetKernelReplayTime();
    for (uint32_t time = 0; time < replayTime; time++) {
        AcpManager::instance()->SetKernelReplayMetrics(time);
        ret = KernelReplay(stream, func, args...);
        FUNRET_CHECK_EXPR_ACTION(ret != RT_ERROR_NONE, break, "Failed to execute kernel replay, ret: %d.", ret);
    }
    AcpManager::instance()->ClearMallocMemory();
    return ret;
}

static void SaveFuncHandle(void* handle)
{
    if (handle == nullptr) {
        return;
    }
    AcpManager::instance()->SaveBinaryHandle(handle);
}

static void SaveFuncBinaryHandle(void* funcHandle)
{
    if (funcHandle == nullptr) {
        return;
    }
    // aclrtLaunch* 入参是函数句柄；PC 采样基址需要二进制句柄，不能直接覆盖 binaryHandle_。
    aclrtBinHandle binHandle = nullptr;
    auto func = AcpApiPlugin::instance()->GetPluginApiStubFunc("aclrtFunctionGetBinary");
    if ((func == nullptr) ||
        (reinterpret_cast<aclError (*)(const void*, aclrtBinHandle*)>(func)(funcHandle, &binHandle) != ACL_SUCCESS)) {
        MSPROF_LOGW("Unable to get binary handle from function handle.");
        return;
    }
    SaveFuncHandle(binHandle);
}

static void RegisterBackupFuncsOnce()
{
    static std::once_flag once;
    std::call_once(once, []() -> void {
        auto mallocFunc = AcpApiPlugin::instance()->GetPluginApiStubFunc("rtMalloc");
        auto freeFunc = AcpApiPlugin::instance()->GetPluginApiStubFunc("rtFree");
        auto memcpyFunc = AcpApiPlugin::instance()->GetPluginApiStubFunc("rtMemcpyAsync");
        if (mallocFunc == nullptr || freeFunc == nullptr || memcpyFunc == nullptr) {
            MSPROF_LOGW("Acp load rt memory apis failed, memory backup disabled.");
            return;
        }
        AcpManager::instance()->RegisterRtMallocFunc(
            reinterpret_cast<RtMallocFunc>(mallocFunc), reinterpret_cast<RtFreeFunc>(freeFunc));
        AcpManager::instance()->RegisterRtMemcpyFunc(reinterpret_cast<RtMemcpyAsyncFunc>(memcpyFunc));
    });
}

uint32_t PolicyToRtMemType(aclrtMemMallocPolicy policy, bool cached)
{
    switch (policy) {
        case ACL_MEM_MALLOC_HUGE_FIRST:
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_FIRST;
        case ACL_MEM_MALLOC_HUGE_ONLY:
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_ONLY;
        case ACL_MEM_MALLOC_NORMAL_ONLY:
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_DEFAULT_PAGE_ONLY;
        case ACL_MEM_MALLOC_HUGE_FIRST_P2P:
            if (cached) {
                return RT_MEMORY_DEFAULT;
            }
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_FIRST_P2P;
        case ACL_MEM_MALLOC_HUGE_ONLY_P2P:
            if (cached) {
                return RT_MEMORY_DEFAULT;
            }
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_ONLY_P2P;
        case ACL_MEM_MALLOC_NORMAL_ONLY_P2P:
            if (cached) {
                return RT_MEMORY_DEFAULT;
            }
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_DEFAULT_PAGE_ONLY_P2P;
        case ACL_MEM_MALLOC_HUGE1G_ONLY:
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE1G_PAGE_ONLY;
        case ACL_MEM_MALLOC_HUGE1G_ONLY_P2P:
            if (cached) {
                return RT_MEMORY_DEFAULT;
            }
            return RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE1G_PAGE_ONLY_P2P;
        default:
            return RT_MEMORY_DEFAULT;
    }
}

static void SaveMallocAttr(void* devPtr, uint64_t size, aclrtMemMallocPolicy policy, bool cached)
{
    if (devPtr == nullptr) {
        return;
    }
    AcpBackupAttr attr = {devPtr, size, PolicyToRtMemType(policy, cached), ACP_APP_MODE_ID};
    AcpManager::instance()->SaveRtMallocAttr(attr);
}

static aclError HookAclrtSetDevice(int32_t deviceId)
{
    MSPROF_LOGI("Acp aclrtSetDevice injection start.");
    const std::lock_guard<std::mutex> lock(g_setDeviceMtx);
    int32_t ret = Platform::instance()->Init();
    FUNRET_CHECK_EXPR_PRINT(ret != PROFILING_SUCCESS, "Failed to init platform.");

    ret = AcpManager::instance()->Init(deviceId);
    FUNRET_CHECK_EXPR_PRINT(ret != PROFILING_SUCCESS, "Failed to init manager.");

    MSPROF_LOGI("Acp aclrtSetDevice injection finished.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtSetDeviceOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtSetDevice origin func is nullptr.");
    return reinterpret_cast<AclrtSetDeviceFunc>(reinterpret_cast<void*>(g_aclrtSetDeviceOrigin))(deviceId);
}

static aclError HookAclrtMalloc(void** devPtr, size_t size, aclrtMemMallocPolicy policy)
{
    MSPROF_LOGI("Acp aclrtMalloc injection start.");
    RegisterBackupFuncsOnce();
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtMallocOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR, "Acp aclrtMalloc origin func is nullptr.");
    const aclError ret =
        reinterpret_cast<AclrtMallocFunc>(reinterpret_cast<void*>(g_aclrtMallocOrigin))(devPtr, size, policy);
    FUNRET_CHECK_EXPR_ACTION(ret != ACL_SUCCESS, return ret, "Acp aclrtMalloc origin failed, ret: %d.", ret);
    SaveMallocAttr((devPtr == nullptr) ? nullptr : *devPtr, static_cast<uint64_t>(size), policy, false);
    return ret;
}

static aclError HookAclrtMallocAlign32(void** devPtr, size_t size, aclrtMemMallocPolicy policy)
{
    MSPROF_LOGI("Acp aclrtMallocAlign32 injection start.");
    RegisterBackupFuncsOnce();
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtMallocAlign32Origin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtMallocAlign32 origin func is nullptr.");
    const aclError ret =
        reinterpret_cast<AclrtMallocFunc>(reinterpret_cast<void*>(g_aclrtMallocAlign32Origin))(devPtr, size, policy);
    FUNRET_CHECK_EXPR_ACTION(ret != ACL_SUCCESS, return ret, "Acp aclrtMallocAlign32 origin failed, ret: %d.", ret);
    SaveMallocAttr((devPtr == nullptr) ? nullptr : *devPtr, static_cast<uint64_t>(size), policy, false);
    return ret;
}

static aclError HookAclrtMallocCached(void** devPtr, size_t size, aclrtMemMallocPolicy policy)
{
    MSPROF_LOGI("Acp aclrtMallocCached injection start.");
    RegisterBackupFuncsOnce();
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtMallocCachedOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtMallocCached origin func is nullptr.");
    const aclError ret =
        reinterpret_cast<AclrtMallocFunc>(reinterpret_cast<void*>(g_aclrtMallocCachedOrigin))(devPtr, size, policy);
    FUNRET_CHECK_EXPR_ACTION(ret != ACL_SUCCESS, return ret, "Acp aclrtMallocCached origin failed, ret: %d.", ret);
    SaveMallocAttr((devPtr == nullptr) ? nullptr : *devPtr, static_cast<uint64_t>(size), policy, true);
    return ret;
}

static aclError HookAclrtFree(void* devPtr)
{
    MSPROF_LOGI("Acp aclrtFree injection start.");
    AcpManager::instance()->ReleaseRtMallocAddr(devPtr);
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtFreeOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR, "Acp aclrtFree origin func is nullptr.");
    return reinterpret_cast<AclrtFreeFunc>(reinterpret_cast<void*>(g_aclrtFreeOrigin))(devPtr);
}

static aclError HookAclrtBinaryLoad(const aclrtBinary binary, aclrtBinHandle* binHandle)
{
    MSPROF_LOGI("Acp aclrtBinaryLoad injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtBinaryLoadOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtBinaryLoad origin func is nullptr.");
    const aclError ret =
        reinterpret_cast<AclrtBinaryLoadFunc>(reinterpret_cast<void*>(g_aclrtBinaryLoadOrigin))(binary, binHandle);
    FUNRET_CHECK_EXPR_ACTION(ret != ACL_SUCCESS, return ret, "Acp aclrtBinaryLoad origin failed, ret: %d.", ret);
    if (binHandle != nullptr && *binHandle != nullptr) {
        SaveFuncHandle(*binHandle);
    }
    return ret;
}

static aclError HookAclrtBinaryUnLoad(aclrtBinHandle binHandle)
{
    MSPROF_LOGI("Acp aclrtBinaryUnLoad injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtBinaryUnLoadOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtBinaryUnLoad origin func is nullptr.");
    const aclError ret =
        reinterpret_cast<AclrtBinaryUnLoadFunc>(reinterpret_cast<void*>(g_aclrtBinaryUnLoadOrigin))(binHandle);
    FUNRET_CHECK_EXPR_ACTION(ret != ACL_SUCCESS, return ret, "Acp aclrtBinaryUnLoad origin failed, ret: %d.", ret);
    AcpManager::instance()->RemoveBinary(binHandle);
    return ret;
}

static aclError HookAclrtBinaryGetFunction(
    const aclrtBinHandle binHandle, const char* kernelName, aclrtFuncHandle* funcHandle)
{
    MSPROF_LOGI("Acp aclrtBinaryGetFunction injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtBinaryGetFunctionOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtBinaryGetFunction origin func is nullptr.");
    const aclError ret = reinterpret_cast<AclrtBinaryGetFunctionFunc>(
        reinterpret_cast<void*>(g_aclrtBinaryGetFunctionOrigin))(binHandle, kernelName, funcHandle);
    FUNRET_CHECK_EXPR_ACTION(ret != ACL_SUCCESS, return ret, "Acp aclrtBinaryGetFunction origin failed, ret: %d.", ret);
    SaveFuncHandle(reinterpret_cast<void*>(binHandle));
    return ret;
}

static aclError HookAclrtLaunchKernel(
    aclrtFuncHandle funcHandle, uint32_t numBlocks, const void* argsData, size_t argsSize, aclrtStream stream)
{
    MSPROF_LOGI("Acp aclrtLaunchKernel injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtLaunchKernelOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtLaunchKernel origin func is nullptr.");
    AcpManager::instance()->SetTaskBlockDim(numBlocks);
    SaveFuncBinaryHandle(reinterpret_cast<void*>(funcHandle));
    return KernelExec(
        reinterpret_cast<rtStream_t>(stream),
        reinterpret_cast<AclrtLaunchKernelFunc>(reinterpret_cast<void*>(g_aclrtLaunchKernelOrigin)), funcHandle,
        numBlocks, argsData, argsSize, stream);
}

static aclError HookAclrtLaunchKernelWithConfig(
    aclrtFuncHandle funcHandle, uint32_t numBlocks, aclrtStream stream, aclrtLaunchKernelCfg* cfg,
    aclrtArgsHandle argsHandle, void* reserve)
{
    MSPROF_LOGI("Acp aclrtLaunchKernelWithConfig injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtLaunchKernelWithConfigOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtLaunchKernelWithConfig origin func is nullptr.");
    AcpManager::instance()->SetTaskBlockDim(numBlocks);
    SaveFuncBinaryHandle(reinterpret_cast<void*>(funcHandle));
    return KernelExec(
        reinterpret_cast<rtStream_t>(stream),
        reinterpret_cast<AclrtLaunchKernelWithConfigFunc>(reinterpret_cast<void*>(g_aclrtLaunchKernelWithConfigOrigin)),
        funcHandle, numBlocks, stream, cfg, argsHandle, reserve);
}

static aclError HookAclrtLaunchKernelV2(
    aclrtFuncHandle funcHandle, uint32_t numBlocks, const void* argsData, size_t argsSize, aclrtLaunchKernelCfg* cfg,
    aclrtStream stream)
{
    MSPROF_LOGI("Acp aclrtLaunchKernelV2 injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtLaunchKernelV2Origin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtLaunchKernelV2 origin func is nullptr.");
    AcpManager::instance()->SetTaskBlockDim(numBlocks);
    SaveFuncBinaryHandle(reinterpret_cast<void*>(funcHandle));
    return KernelExec(
        reinterpret_cast<rtStream_t>(stream),
        reinterpret_cast<AclrtLaunchKernelV2Func>(reinterpret_cast<void*>(g_aclrtLaunchKernelV2Origin)), funcHandle,
        numBlocks, argsData, argsSize, cfg, stream);
}

static aclError HookAclrtLaunchKernelWithHostArgs(
    aclrtFuncHandle funcHandle, uint32_t numBlocks, aclrtStream stream, aclrtLaunchKernelCfg* cfg, void* hostArgs,
    size_t argsSize, aclrtPlaceHolderInfo* placeHolderArray, size_t placeHolderNum)
{
    MSPROF_LOGI("Acp aclrtLaunchKernelWithHostArgs injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtLaunchKernelWithHostArgsOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtLaunchKernelWithHostArgs origin func is nullptr.");
    AcpManager::instance()->SetTaskBlockDim(numBlocks);
    SaveFuncBinaryHandle(reinterpret_cast<void*>(funcHandle));
    return KernelExec(
        reinterpret_cast<rtStream_t>(stream),
        reinterpret_cast<AclrtLaunchKernelWithHostArgsFunc>(
            reinterpret_cast<void*>(g_aclrtLaunchKernelWithHostArgsOrigin)),
        funcHandle, numBlocks, stream, cfg, hostArgs, argsSize, placeHolderArray, placeHolderNum);
}

static aclError HookAclrtLaunchKernelWithArgsArray(
    void* func, uint32_t numBlocks, aclrtStream stream, aclrtLaunchKernelCfg* cfg, void** args)
{
    MSPROF_LOGI("Acp aclrtLaunchKernelWithArgsArray injection start.");
    FUNRET_CHECK_EXPR_ACTION(
        g_aclrtLaunchKernelWithArgsArrayOrigin == nullptr, return ACL_ERROR_RT_PROFILING_ERROR,
        "Acp aclrtLaunchKernelWithArgsArray origin func is nullptr.");
    AcpManager::instance()->SetTaskBlockDim(numBlocks);
    SaveFuncBinaryHandle(func);
    return KernelExec(
        reinterpret_cast<rtStream_t>(stream),
        reinterpret_cast<AclrtLaunchKernelWithArgsArrayFunc>(
            reinterpret_cast<void*>(g_aclrtLaunchKernelWithArgsArrayOrigin)),
        func, numBlocks, stream, cfg, args);
}

struct AclrtHookEntry {
    const char* name;
    AclrtApiFuncT hook;
    AclrtApiFuncT* originSlot;
    bool registered{false};
};

#if __GNUC__ >= 8
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wcast-function-type"
#endif
static AclrtHookEntry g_hookEntries[] = {
    {"aclrtSetDevice", reinterpret_cast<AclrtApiFuncT>(HookAclrtSetDevice), &g_aclrtSetDeviceOrigin},
    {"aclrtMalloc", reinterpret_cast<AclrtApiFuncT>(HookAclrtMalloc), &g_aclrtMallocOrigin},
    {"aclrtMallocAlign32", reinterpret_cast<AclrtApiFuncT>(HookAclrtMallocAlign32), &g_aclrtMallocAlign32Origin},
    {"aclrtMallocCached", reinterpret_cast<AclrtApiFuncT>(HookAclrtMallocCached), &g_aclrtMallocCachedOrigin},
    {"aclrtFree", reinterpret_cast<AclrtApiFuncT>(HookAclrtFree), &g_aclrtFreeOrigin},
    {"aclrtBinaryLoad", reinterpret_cast<AclrtApiFuncT>(HookAclrtBinaryLoad), &g_aclrtBinaryLoadOrigin},
    {"aclrtBinaryUnLoad", reinterpret_cast<AclrtApiFuncT>(HookAclrtBinaryUnLoad), &g_aclrtBinaryUnLoadOrigin},
    {"aclrtBinaryGetFunction", reinterpret_cast<AclrtApiFuncT>(HookAclrtBinaryGetFunction),
     &g_aclrtBinaryGetFunctionOrigin},
    {"aclrtLaunchKernel", reinterpret_cast<AclrtApiFuncT>(HookAclrtLaunchKernel), &g_aclrtLaunchKernelOrigin},
    {"aclrtLaunchKernelWithConfig", reinterpret_cast<AclrtApiFuncT>(HookAclrtLaunchKernelWithConfig),
     &g_aclrtLaunchKernelWithConfigOrigin},
    {"aclrtLaunchKernelV2", reinterpret_cast<AclrtApiFuncT>(HookAclrtLaunchKernelV2), &g_aclrtLaunchKernelV2Origin},
    {"aclrtLaunchKernelWithHostArgs", reinterpret_cast<AclrtApiFuncT>(HookAclrtLaunchKernelWithHostArgs),
     &g_aclrtLaunchKernelWithHostArgsOrigin},
    {"aclrtLaunchKernelWithArgsArray", reinterpret_cast<AclrtApiFuncT>(HookAclrtLaunchKernelWithArgsArray),
     &g_aclrtLaunchKernelWithArgsArrayOrigin},
};
#if __GNUC__ >= 8
#pragma GCC diagnostic pop
#endif

int32_t RegisterAclrtHooks(AclrtApiInjectionSetFuncT setFunc, AclrtApiInjectionGetFuncT getFunc)
{
    if (setFunc == nullptr || getFunc == nullptr) {
        return 0;
    }

    const std::lock_guard<std::mutex> lock(g_hookRegisterMtx);
    int32_t registered = 0;
    for (auto& entry : g_hookEntries) {
        if (entry.registered) {
            ++registered;
            continue;
        }
        AclrtApiFuncT origin = nullptr;
        if ((getFunc(entry.name, &origin, nullptr) != ACL_SUCCESS) || (origin == nullptr)) {
            MSPROF_LOGW("Acp get origin func[%s] failed, retry later.", entry.name);
            continue;
        }
        // Cache origin before publishing the hook so it is available as soon as setFunc succeeds.
        *entry.originSlot = origin;
        if (setFunc(entry.name, entry.hook) != ACL_SUCCESS) {
            *entry.originSlot = nullptr;
            MSPROF_LOGW("Acp inject hook[%s] failed, retry later.", entry.name);
            continue;
        }
        entry.registered = true;
        ++registered;
        MSPROF_LOGI("Acp inject hook[%s] success.", entry.name);
    }
    return registered;
}

bool IsAclRtReady()
{
    // 两级探测（全程最多产生 1 条/轮 runtime 侧日志，正常场景为 0 条）：
    // 1) RTLD_NOLOAD 仅探测 libacl_rt.so 是否已加载，不产生任何日志。
    //    晚加载场景（shim dlopen）下返回句柄时其构造已完成，查找表必已注册。
    // 2) 启动链场景下"已 map"可能早于构造完成，再用单名 getFunc 确认查找表
    //    已注册后才做全量注册，避免对未注册表逐 API 查询。
    void* hdl = dlopen(ACLRT_LIB_NAME, RTLD_LAZY | RTLD_NOLOAD);
    if (hdl == nullptr) {
        return false;
    }
    dlclose(hdl); // 配对释放探测引用；libacl_rt 由真实调用方持有，不受影响
    return true;
}

void RetryPendingHooks(
    AclrtApiInjectionSetFuncT setFunc, AclrtApiInjectionGetFuncT getFunc, AclrtRtReadyProbeT probeFunc)
{
    useconds_t interval = RETRY_FIRST_INTERVAL_US;
    for (int32_t time = 0; time < RETRY_MAX_TIMES; ++time) {
        usleep(interval);
        // 5ms 起步指数退避封顶 1s：快恢复场景亚秒级完成，
        // 晚加载场景（应用首次 aclrt 调用才 dlopen libacl_rt）最长等待约 60s。
        interval = (interval * RETRY_BACKOFF_FACTOR > RETRY_MAX_INTERVAL_US) ? RETRY_MAX_INTERVAL_US :
                                                                               interval * RETRY_BACKOFF_FACTOR;
        if (!probeFunc()) {
            continue; // libacl_rt 尚未加载，零日志
        }
        AclrtApiFuncT probeOrigin = nullptr;
        if ((getFunc(PROBE_NAME, &probeOrigin, nullptr) != ACL_SUCCESS) || (probeOrigin == nullptr)) {
            continue; // 已加载但查找表尚未注册（启动链构造窗口），下轮再试
        }
        const int32_t registered = RegisterAclrtHooks(setFunc, getFunc);
        if (registered >= HOOK_TOTAL_COUNT) {
            MSPROF_LOGI("Acp all aclrt hooks registered after retry %d.", time + 1);
            return;
        }
    }
    MSPROF_LOGW("Acp retry register aclrt hooks timeout, some hooks may be missing.");
}

void ResetAclrtHooksForTest()
{
    const std::lock_guard<std::mutex> lock(g_hookRegisterMtx);
    for (auto& entry : g_hookEntries) {
        entry.registered = false;
        *entry.originSlot = nullptr;
    }
}

static int32_t StartRetryThread(
    AclrtApiInjectionSetFuncT setFunc, AclrtApiInjectionGetFuncT getFunc, AclrtRtReadyProbeT probeFunc)
{
    try {
        std::thread(RetryPendingHooks, setFunc, getFunc, probeFunc).detach();
    } catch (const std::exception& e) {
        MSPROF_LOGE("Acp start retry thread failed: %s.", e.what());
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

int32_t AclToolInitializeCore(AclrtRtReadyProbeT probeFunc, AclrtRetryThreadStartT startRetryFunc)
{
    auto setFunc = reinterpret_cast<AclrtApiInjectionSetFuncT>(
        AcpApiPlugin::instance()->GetMsprofInjectionFunc(ACP_PROF_HOOK_SET));
    auto getFunc = reinterpret_cast<AclrtApiInjectionGetFuncT>(
        AcpApiPlugin::instance()->GetMsprofInjectionFunc(ACP_PROF_HOOK_GET));
    if (setFunc == nullptr || getFunc == nullptr) {
        MSPROF_LOGE("Acp get injection funcs failed.");
        return PROFILING_FAILED;
    }
    // hook 一经 setFunc 发布即可能被业务线程并发调用；备份 API 查找必须在发布前完成。
    RegisterBackupFuncsOnce();

    if (probeFunc()) {
        AclrtApiFuncT probeOrigin = nullptr;
        if ((getFunc(PROBE_NAME, &probeOrigin, nullptr) == ACL_SUCCESS) && (probeOrigin != nullptr)) {
            const int32_t registered = RegisterAclrtHooks(setFunc, getFunc);
            if (registered >= HOOK_TOTAL_COUNT) {
                MSPROF_LOGI("Acp all aclrt hooks registered at init.");
                return PROFILING_SUCCESS;
            }
            if (startRetryFunc != nullptr) {
                const int32_t retryResult = startRetryFunc(setFunc, getFunc, probeFunc);
                return ((retryResult == PROFILING_SUCCESS) || (registered > 0)) ? PROFILING_SUCCESS : PROFILING_FAILED;
            }
            return PROFILING_SUCCESS;
        }
    }
    if (startRetryFunc != nullptr) {
        return startRetryFunc(setFunc, getFunc, probeFunc);
    }
    return PROFILING_SUCCESS;
}

} // namespace Acp
} // namespace Dvvp
} // namespace Collector

/**
 * @ingroup libascend_profinj
 * @name  acltoolInitialize
 * @brief Injection entry called by libprofapi when ACL_API_INJECTION is set.
 * @return 0: at least one hook registered or retry thread started; !0: no hook and no thread.
 */
extern "C" MSVP_PROF_API int32_t acltoolInitialize(void)
{
    using namespace Collector::Dvvp::Acp;
    MSPROF_LOGI("Acp acltoolInitialize enter.");
    return AclToolInitializeCore(&IsAclRtReady, &StartRetryThread);
}
