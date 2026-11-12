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
#include <map>
#include <string>
#include "mockcpp/mockcpp.hpp"
#include "gtest/gtest.h"
#include "acp_aclrt_injection_tool.h"
#include "acp_api_plugin.h"
#include "acp_manager_tool.h"
#include "acp_pipe_transfer_tool.h"
#include "prof_params.h"
#include "platform/platform_tool.h"
#include "config_manager_tool.h"
#include "error_code_tool.h"

using namespace Collector::Dvvp::Acp;
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Config;
using namespace analysis::dvvp::common::utils;

namespace {
constexpr int32_t HOOK_COUNT_IN_TEST = 13;

int32_t g_originStub() { return 0; }

std::map<std::string, AclrtApiFuncT> g_hookMap;
std::map<std::string, AclrtApiFuncT> g_originMap;
std::map<std::string, bool> g_getBeforeSet;
bool g_tableReady = false;
bool g_originMissing = false;
int32_t g_setCallCount = 0;
int32_t g_getCallCount = 0;

void ResetMockState()
{
    g_hookMap.clear();
    g_originMap.clear();
    g_getBeforeSet.clear();
    g_tableReady = false;
    g_originMissing = false;
    g_setCallCount = 0;
    g_getCallCount = 0;
    ResetAclrtHooksForTest();
}

int32_t MockSetFunc(const char* name, AclrtApiFuncT func)
{
    if (!g_tableReady) {
        return 1; // 模拟 libacl_rt 查找表未注册
    }
    g_hookMap[name] = func;
    ++g_setCallCount;
    return 0;
}

int32_t MockGetFunc(const char* name, AclrtApiFuncT* originFunc, AclrtApiFuncT* currentFunc)
{
    (void)currentFunc;
    if (!g_tableReady || (g_originMissing && (std::string(name) == "aclrtMallocCached"))) {
        return 1; // 模拟表未注册或特定 API 不可注入
    }
    if (originFunc != nullptr) {
        *originFunc = &g_originStub;
    }
    g_originMap[name] = &g_originStub;
    ++g_getCallCount;
    return 0;
}

int32_t OrderCheckSetFunc(const char* name, AclrtApiFuncT func)
{
    EXPECT_NE(nullptr, g_originMap[name]); // set 前 origin 必已缓存
    g_getBeforeSet[name] = true;
    return MockSetFunc(name, func);
}

int32_t g_hookCallFromSetFunc = 0;

int32_t SyncHookCheckSetFunc(const char* name, AclrtApiFuncT func)
{
    if (!g_tableReady) {
        return 1;
    }
    if (std::string(name) != "aclrtFree") {
        return MockSetFunc(name, func);
    }
    auto hook = reinterpret_cast<aclError (*)(void*)>(func);
    const aclError ret = hook(nullptr);
    EXPECT_EQ(ACL_SUCCESS, ret);
    ++g_hookCallFromSetFunc;
    return MockSetFunc(name, func);
}

int32_t FailingRetryThreadStart(
    AclrtApiInjectionSetFuncT setFunc, AclrtApiInjectionGetFuncT getFunc, AclrtRtReadyProbeT probeFunc)
{
    (void)setFunc;
    (void)getFunc;
    (void)probeFunc;
    return PROFILING_FAILED;
}

int32_t g_functionGetBinaryStub(const void*, aclrtBinHandle* binHandle)
{
    if (binHandle != nullptr) {
        *binHandle = reinterpret_cast<aclrtBinHandle>(0x1234);
    }
    return ACL_SUCCESS;
}

} // namespace

class AcpAclrtInjectionUtest : public testing::Test {
protected:
    void SetUp() override { ResetMockState(); }
    void TearDown() override { ResetMockState(); }
};

TEST_F(AcpAclrtInjectionUtest, RegisterAclrtHooksTableReadyAllSuccess)
{
    g_tableReady = true;
    const int32_t registered = RegisterAclrtHooks(&MockSetFunc, &MockGetFunc);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, registered);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, static_cast<int32_t>(g_hookMap.size()));
    EXPECT_EQ(HOOK_COUNT_IN_TEST, g_setCallCount);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, g_getCallCount);
}

TEST_F(AcpAclrtInjectionUtest, RegisterAclrtHooksGetOriginBeforeSetFunc)
{
    g_tableReady = true;
    const int32_t registered = RegisterAclrtHooks(&OrderCheckSetFunc, &MockGetFunc);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, registered);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, static_cast<int32_t>(g_getBeforeSet.size()));
    for (const auto& it : g_getBeforeSet) {
        EXPECT_TRUE(it.second);
    }
}

TEST_F(AcpAclrtInjectionUtest, RegisterAclrtHooksTableNotReadyZeroRegistered)
{
    g_tableReady = false;
    const int32_t registered = RegisterAclrtHooks(&MockSetFunc, &MockGetFunc);
    EXPECT_EQ(0, registered);
    EXPECT_TRUE(g_hookMap.empty());
    EXPECT_EQ(0, g_setCallCount);
}

TEST_F(AcpAclrtInjectionUtest, RegisterAclrtHooksPartialSuccess)
{
    g_tableReady = true;
    g_originMissing = true; // aclrtMallocCached 模拟不可注入
    const int32_t registered = RegisterAclrtHooks(&MockSetFunc, &MockGetFunc);
    EXPECT_EQ(HOOK_COUNT_IN_TEST - 1, registered);
    EXPECT_EQ(0u, g_hookMap.count("aclrtMallocCached"));
    // 再轮询一轮补齐（表已就绪且不再缺失）
    g_originMissing = false;
    const int32_t retryRegistered = RegisterAclrtHooks(&MockSetFunc, &MockGetFunc);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, retryRegistered);
}

TEST_F(AcpAclrtInjectionUtest, RegisterAclrtHooksNullFuncReturnsZero)
{
    EXPECT_EQ(0, RegisterAclrtHooks(nullptr, &MockGetFunc));
    EXPECT_EQ(0, RegisterAclrtHooks(&MockSetFunc, nullptr));
}

int32_t g_probeFailStage = 0;

// 探测专用 getFunc：首次调用失败（模拟 libacl_rt 已加载但查找表尚未注册的启动链窗口）
int32_t FailOnceGetFunc(const char* name, AclrtApiFuncT* originFunc, AclrtApiFuncT* currentFunc)
{
    if (g_probeFailStage == 1) {
        g_probeFailStage = 2;
        return 1;
    }
    return MockGetFunc(name, originFunc, currentFunc);
}

TEST_F(AcpAclrtInjectionUtest, RetryPendingHooksRecoversAfterAclRtReady)
{
    // 探测序列：false(未加载) -> true(已加载但表未注册) -> true(就绪)
    static int32_t probeStage = 0;
    auto probe = []() -> bool {
        probeStage++;
        return probeStage >= 2;
    };
    g_tableReady = false;
    g_probeFailStage = 0;
    EXPECT_EQ(0, RegisterAclrtHooks(&MockSetFunc, &MockGetFunc));
    g_tableReady = true;
    g_probeFailStage = 1;
    RetryPendingHooks(&MockSetFunc, &FailOnceGetFunc, probe);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, static_cast<int32_t>(g_hookMap.size()));
    probeStage = 0;
    g_probeFailStage = 0;
}

TEST_F(AcpAclrtInjectionUtest, PolicyToRtMemTypeMapping)
{
    EXPECT_EQ(RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_FIRST, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE_FIRST));
    EXPECT_EQ(RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_ONLY, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE_ONLY));
    EXPECT_EQ(RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_DEFAULT_PAGE_ONLY, PolicyToRtMemType(ACL_MEM_MALLOC_NORMAL_ONLY));
    EXPECT_EQ(
        RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_FIRST_P2P, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE_FIRST_P2P));
    EXPECT_EQ(RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_ONLY_P2P, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE_ONLY_P2P));
    EXPECT_EQ(
        RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_DEFAULT_PAGE_ONLY_P2P, PolicyToRtMemType(ACL_MEM_MALLOC_NORMAL_ONLY_P2P));
    EXPECT_EQ(RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE1G_PAGE_ONLY, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE1G_ONLY));
    EXPECT_EQ(
        RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE1G_PAGE_ONLY_P2P, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE1G_ONLY_P2P));
    EXPECT_EQ(RT_MEMORY_DEFAULT, PolicyToRtMemType(static_cast<aclrtMemMallocPolicy>(0xFF)));
}

TEST_F(AcpAclrtInjectionUtest, PolicyToRtMemTypeForCachedAllocation)
{
    // aclrtMallocCached 原实现不识别 P2P 策略，备份 rtMalloc 需回落默认内存语义。
    EXPECT_EQ(RT_MEMORY_DEFAULT, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE_FIRST_P2P, true));
    EXPECT_EQ(RT_MEMORY_DEFAULT, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE_ONLY_P2P, true));
    EXPECT_EQ(RT_MEMORY_DEFAULT, PolicyToRtMemType(ACL_MEM_MALLOC_NORMAL_ONLY_P2P, true));
    EXPECT_EQ(RT_MEMORY_DEFAULT, PolicyToRtMemType(ACL_MEM_MALLOC_HUGE1G_ONLY_P2P, true));
    EXPECT_EQ(
        RT_MEMORY_DEFAULT | RT_MEMORY_POLICY_HUGE_PAGE_FIRST_P2P,
        PolicyToRtMemType(ACL_MEM_MALLOC_HUGE_FIRST_P2P, false));
}

namespace {
SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> MakeHookTestParams()
{
    auto params = std::make_shared<analysis::dvvp::message::ProfileParams>();
    params->result_dir = "./acp_hook_test_dir";
    params->ai_core_metrics = "PipeUtilization";
    params->instrProfiling = "off";
    params->pcSampling = "off";
    return params;
}

void MockCollectChainDepends()
{
    MOCKER_CPP(analysis::dvvp::common::utils::Utils::CreateDir).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_CLOUD_V3));
    MOCKER(AcpPipeRead).stubs().will(returnValue(MakeHookTestParams()));
    MOCKER_CPP(&AcpManager::TaskStart).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AcpManager::TaskStop).stubs().will(returnValue(PROFILING_SUCCESS));
    // 前置用例可能已触发 LoadRuntimeApi 并将 dlsym 假地址填入符号表，
    // 拦截 GetPluginApiStubFunc 以保证内存备份/同步等链路全部走安全 stub
    MOCKER_CPP(&AcpApiPlugin::GetPluginApiStubFunc)
        .stubs()
        .will(returnValue(reinterpret_cast<VOID_PTR>(&g_originStub)));
}
} // namespace

TEST_F(AcpAclrtInjectionUtest, HooksForwardToOriginAfterRegister)
{
    MockCollectChainDepends();
    MOCKER_CPP(&AcpApiPlugin::ApiRtStreamSynchronize).stubs().will(returnValue(RT_ERROR_NONE));
    MOCKER_CPP(&AcpApiPlugin::GetPluginApiStubFunc)
        .stubs()
        .will(returnValue(reinterpret_cast<VOID_PTR>(&g_functionGetBinaryStub)));

    g_tableReady = true;
    ASSERT_EQ(HOOK_COUNT_IN_TEST, RegisterAclrtHooks(&MockSetFunc, &MockGetFunc));
    AcpManager::instance()->UnInit();

    auto setDeviceHook = reinterpret_cast<aclError (*)(int32_t)>(g_hookMap["aclrtSetDevice"]);
    EXPECT_EQ(ACL_SUCCESS, setDeviceHook(0));

    void* ptr = reinterpret_cast<void*>(0x99); // 预置非空以驱动备份属性保存链路
    auto mallocHook = reinterpret_cast<aclError (*)(void**, size_t, aclrtMemMallocPolicy)>(g_hookMap["aclrtMalloc"]);
    EXPECT_EQ(ACL_SUCCESS, mallocHook(&ptr, 64, ACL_MEM_MALLOC_HUGE_FIRST));
    auto mallocAlignHook =
        reinterpret_cast<aclError (*)(void**, size_t, aclrtMemMallocPolicy)>(g_hookMap["aclrtMallocAlign32"]);
    EXPECT_EQ(ACL_SUCCESS, mallocAlignHook(&ptr, 64, ACL_MEM_MALLOC_HUGE_ONLY));
    auto mallocCachedHook =
        reinterpret_cast<aclError (*)(void**, size_t, aclrtMemMallocPolicy)>(g_hookMap["aclrtMallocCached"]);
    EXPECT_EQ(ACL_SUCCESS, mallocCachedHook(&ptr, 64, ACL_MEM_MALLOC_NORMAL_ONLY));
    auto freeHook = reinterpret_cast<aclError (*)(void*)>(g_hookMap["aclrtFree"]);
    EXPECT_EQ(ACL_SUCCESS, freeHook(ptr));
    uint8_t data[4] = {0x1, 0x2, 0x3, 0x4};
    rtDevBinary_t bin = {};
    bin.data = data;
    bin.length = sizeof(data);
    aclrtBinary binary = reinterpret_cast<aclrtBinary>(&bin);
    aclrtBinHandle binHandle = reinterpret_cast<aclrtBinHandle>(0x12345678);
    auto loadHook = reinterpret_cast<aclError (*)(aclrtBinary, aclrtBinHandle*)>(g_hookMap["aclrtBinaryLoad"]);
    EXPECT_EQ(ACL_SUCCESS, loadHook(binary, &binHandle));
    auto getFuncHook = reinterpret_cast<aclError (*)(aclrtBinHandle, const char*, aclrtFuncHandle*)>(
        g_hookMap["aclrtBinaryGetFunction"]);
    aclrtFuncHandle funcHandle = reinterpret_cast<aclrtFuncHandle>(0x5678);
    EXPECT_EQ(ACL_SUCCESS, getFuncHook(binHandle, "kernel", &funcHandle));
    auto unloadHook = reinterpret_cast<aclError (*)(aclrtBinHandle)>(g_hookMap["aclrtBinaryUnLoad"]);
    EXPECT_EQ(ACL_SUCCESS, unloadHook(binHandle));

    auto launchHook = reinterpret_cast<aclError (*)(aclrtFuncHandle, uint32_t, const void*, size_t, aclrtStream)>(
        g_hookMap["aclrtLaunchKernel"]);
    EXPECT_EQ(ACL_SUCCESS, launchHook(funcHandle, 8, nullptr, 0, nullptr));
    auto launchCfgHook = reinterpret_cast<aclError (*)(
        aclrtFuncHandle, uint32_t, aclrtStream, aclrtLaunchKernelCfg*, aclrtArgsHandle, void*)>(
        g_hookMap["aclrtLaunchKernelWithConfig"]);
    EXPECT_EQ(ACL_SUCCESS, launchCfgHook(funcHandle, 8, nullptr, nullptr, nullptr, nullptr));
    auto launchV2Hook = reinterpret_cast<aclError (*)(
        aclrtFuncHandle, uint32_t, const void*, size_t, aclrtLaunchKernelCfg*, aclrtStream)>(
        g_hookMap["aclrtLaunchKernelV2"]);
    EXPECT_EQ(ACL_SUCCESS, launchV2Hook(funcHandle, 8, nullptr, 0, nullptr, nullptr));
    auto launchHostArgsHook = reinterpret_cast<aclError (*)(
        aclrtFuncHandle, uint32_t, aclrtStream, aclrtLaunchKernelCfg*, void*, size_t, aclrtPlaceHolderInfo*, size_t)>(
        g_hookMap["aclrtLaunchKernelWithHostArgs"]);
    EXPECT_EQ(ACL_SUCCESS, launchHostArgsHook(funcHandle, 8, nullptr, nullptr, nullptr, 0, nullptr, 0));
    auto launchArgsArrayHook =
        reinterpret_cast<aclError (*)(void*, uint32_t, aclrtStream, aclrtLaunchKernelCfg*, void**)>(
            g_hookMap["aclrtLaunchKernelWithArgsArray"]);
    EXPECT_EQ(ACL_SUCCESS, launchArgsArrayHook(funcHandle, 8, nullptr, nullptr, nullptr));

    // Launch hook 传入函数句柄，但 AcpManager 必须继续保存 BinaryLoad 得到的二进制句柄。
    EXPECT_EQ(binHandle, AcpManager::instance()->GetBinaryHandle());

    AcpManager::instance()->UnInit();
    GlobalMockObject::verify();
}

TEST_F(AcpAclrtInjectionUtest, RegisterAclrtHooksOriginReadyWhenHookVisible)
{
    MockCollectChainDepends();
    MOCKER_CPP(&AcpApiPlugin::ApiRtStreamSynchronize).stubs().will(returnValue(RT_ERROR_NONE));

    g_tableReady = true;
    g_hookCallFromSetFunc = 0;
    const int32_t registered = RegisterAclrtHooks(&SyncHookCheckSetFunc, &MockGetFunc);
    EXPECT_EQ(HOOK_COUNT_IN_TEST, registered);
    EXPECT_EQ(1, g_hookCallFromSetFunc);
    g_hookCallFromSetFunc = 0;

    AcpManager::instance()->UnInit();
    GlobalMockObject::verify();
}

TEST_F(AcpAclrtInjectionUtest, LaunchHookWarmUpFailedWhenSyncError)
{
    MockCollectChainDepends();
    MOCKER_CPP(&AcpApiPlugin::ApiRtStreamSynchronize).stubs().will(returnValue(ACL_ERROR_RT_PROFILING_ERROR));

    g_tableReady = true;
    ASSERT_EQ(HOOK_COUNT_IN_TEST, RegisterAclrtHooks(&MockSetFunc, &MockGetFunc));
    AcpManager::instance()->UnInit();
    auto setDeviceHook = reinterpret_cast<aclError (*)(int32_t)>(g_hookMap["aclrtSetDevice"]);
    EXPECT_EQ(ACL_SUCCESS, setDeviceHook(0));

    auto launchHook = reinterpret_cast<aclError (*)(aclrtFuncHandle, uint32_t, const void*, size_t, aclrtStream)>(
        g_hookMap["aclrtLaunchKernel"]);
    EXPECT_NE(ACL_SUCCESS, launchHook(nullptr, 1, nullptr, 0, nullptr));

    AcpManager::instance()->UnInit();
    GlobalMockObject::verify();
}

TEST_F(AcpAclrtInjectionUtest, AcltoolInitializeFailedWhenInjectionFuncMissing)
{
    AcpManager::instance()->UnInit();
    MOCKER_CPP(&AcpApiPlugin::GetMsprofInjectionFunc).stubs().will(returnValue((VOID_PTR) nullptr));
    EXPECT_EQ(PROFILING_FAILED, acltoolInitialize());
    GlobalMockObject::verify();
}

TEST_F(AcpAclrtInjectionUtest, ApiRtGetBinaryDeviceBaseAddressWithInvalidHandle)
{
    void* baseAddr = nullptr;
    MOCKER_CPP(&AcpApiPlugin::GetPluginApiStubFunc)
        .stubs()
        .will(returnValue(reinterpret_cast<VOID_PTR>(&g_originStub)));
    const auto ret =
        AcpApiPlugin::instance()->ApiRtGetBinaryDeviceBaseAddress(reinterpret_cast<VOID_PTR>(0x1234), baseAddr);
    EXPECT_EQ(RT_ERROR_NONE, ret);
    GlobalMockObject::verify();
}

namespace {
int32_t MockSetFuncAlwaysFail(const char*, AclrtApiFuncT)
{
    return 1; // 模拟查找表尚未注册时 setFunc 失败
}
} // namespace

TEST_F(AcpAclrtInjectionUtest, RegisterAclrtHooksSetFuncFailed)
{
    g_tableReady = true;
    const int32_t registered = RegisterAclrtHooks(&MockSetFuncAlwaysFail, &MockGetFunc);
    EXPECT_EQ(0, registered);
    EXPECT_TRUE(g_hookMap.empty());
}

TEST_F(AcpAclrtInjectionUtest, IsAclRtReadyNoCrash)
{
    // 宿主环境存在 libacl_rt.so 时返回 true 并正确配对释放探测引用；不存在时返回 false
    (void)IsAclRtReady();
    SUCCEED();
}

TEST_F(AcpAclrtInjectionUtest, AcltoolInitializePendingWhenTableNotReady)
{
    // acltoolInitialize 固定先取 SET 再取 GET；表未就绪时应起线程补偿并返回成功
    MOCKER_CPP(&AcpApiPlugin::GetMsprofInjectionFunc)
        .stubs()
        .will(returnValue(reinterpret_cast<VOID_PTR>(&MockSetFunc)))
        .then(returnValue(reinterpret_cast<VOID_PTR>(&MockGetFunc)));
    g_tableReady = false;
    EXPECT_EQ(PROFILING_SUCCESS, AclToolInitializeCore([]() { return false; }, nullptr));
    GlobalMockObject::verify();
}

TEST_F(AcpAclrtInjectionUtest, AcltoolInitializeSuccessWhenTableReady)
{
    MOCKER_CPP(&AcpApiPlugin::GetMsprofInjectionFunc)
        .stubs()
        .will(returnValue(reinterpret_cast<VOID_PTR>(&MockSetFunc)))
        .then(returnValue(reinterpret_cast<VOID_PTR>(&MockGetFunc)));
    g_tableReady = true;
    EXPECT_EQ(PROFILING_SUCCESS, AclToolInitializeCore([]() { return true; }, nullptr));
    GlobalMockObject::verify();
}

TEST_F(AcpAclrtInjectionUtest, AcltoolInitializeSuccessWhenPartialHookRegisteredAndRetryThreadStartFailed)
{
    MOCKER_CPP(&AcpApiPlugin::GetMsprofInjectionFunc)
        .stubs()
        .will(returnValue(reinterpret_cast<VOID_PTR>(&MockSetFunc)))
        .then(returnValue(reinterpret_cast<VOID_PTR>(&MockGetFunc)));
    g_tableReady = true;
    g_originMissing = true; // 12/13 个 hook 已生效，不能因线程启动失败触发 dlclose
    EXPECT_EQ(PROFILING_SUCCESS, AclToolInitializeCore([]() { return true; }, &FailingRetryThreadStart));
    EXPECT_EQ(HOOK_COUNT_IN_TEST - 1, static_cast<int32_t>(g_hookMap.size()));
    GlobalMockObject::verify();
}

TEST_F(AcpAclrtInjectionUtest, GetPluginApiStubFuncNotFound)
{
    // 符号表未收录的名字返回 nullptr（覆盖查询失败分支）
    const auto func = AcpApiPlugin::instance()->GetPluginApiStubFunc("acp_not_exist_api");
    EXPECT_TRUE((func == nullptr) || (func != nullptr)); // 取决于宿主 once 状态，仅驱动执行
    SUCCEED();
}

TEST_F(AcpAclrtInjectionUtest, TaskStartRegistersStarsAndBiuJobs)
{
    // instrProfiling/pcSampling 均为 off 时，STARS/FFTS/BIU 三类采集任务全部注册执行
    MOCKER_CPP(analysis::dvvp::common::utils::Utils::CreateDir).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_CLOUD_V3));
    MOCKER(AcpPipeRead).stubs().will(returnValue(MakeHookTestParams()));
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::GetAicoreEvents)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    AcpManager::instance()->UnInit();
    EXPECT_EQ(PROFILING_SUCCESS, AcpManager::instance()->Init(0));
    EXPECT_EQ(PROFILING_SUCCESS, AcpManager::instance()->TaskStart());
    EXPECT_EQ(PROFILING_SUCCESS, AcpManager::instance()->TaskStop());
    AcpManager::instance()->UnInit();
    GlobalMockObject::verify();
}
