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
#ifndef COLLECTOR_DVVP_ACP_ACLRT_INJECTION_TOOL_H
#define COLLECTOR_DVVP_ACP_ACLRT_INJECTION_TOOL_H

#include <cstdint>
#include "acl/acl_prof.h"
#include "acl/acl_rt.h"
#include "runtime/mem.h"

namespace Collector {
namespace Dvvp {
namespace Acp {

// 本地最小 ABI 声明，取值与 runtime 仓 pkg_inc/profiling/aprof_pub.h 保持一致
constexpr uint32_t ACP_PROF_HOOK_SET = 0U;
constexpr uint32_t ACP_PROF_HOOK_GET = 1U;

// 取值与 runtime 仓 include/external/acl/acl_rt.h 的 aclrtApiFunc 保持一致
using AclrtApiFuncT = int32_t (*)(void);
using AclrtApiInjectionSetFuncT = int32_t (*)(const char* name, AclrtApiFuncT func);
using AclrtApiInjectionGetFuncT = int32_t (*)(const char* name, AclrtApiFuncT* originFunc, AclrtApiFuncT* currentFunc);
using MsprofGetInjectionFuncT = void* (*)(uint32_t type);

// 单轮注册所有 hook；返回成功注册数
int32_t RegisterAclrtHooks(AclrtApiInjectionSetFuncT setFunc, AclrtApiInjectionGetFuncT getFunc);

// libacl_rt 就绪探测：已加载（其构造已注册 hook 查找表）返回 true，全程不产生 runtime 侧日志
bool IsAclRtReady();

// libacl_rt 就绪探测函数类型，可注入以便 UT 模拟
using AclrtRtReadyProbeT = bool (*)();

// 重试线程启动函数类型，可注入以便 UT 模拟线程创建失败
using AclrtRetryThreadStartT =
    int32_t (*)(AclrtApiInjectionSetFuncT setFunc, AclrtApiInjectionGetFuncT getFunc, AclrtRtReadyProbeT probeFunc);

// 轮询补偿注册（libacl_rt 延迟加载场景，探测确认就绪后才全量注册）
void RetryPendingHooks(
    AclrtApiInjectionSetFuncT setFunc, AclrtApiInjectionGetFuncT getFunc, AclrtRtReadyProbeT probeFunc);

// 初始化核心逻辑；UT 传入 nullptr 或失败启动函数，避免泄漏后台线程并覆盖返回语义
int32_t AclToolInitializeCore(AclrtRtReadyProbeT probeFunc, AclrtRetryThreadStartT startRetryFunc);

// aclrtMemMallocPolicy -> rtMemType_t 位标志映射；cached=true 时与 aclrtMallocCached 实现一致，
// P2P 策略在该实现中回落 RT_MEMORY_DEFAULT。
uint32_t PolicyToRtMemType(aclrtMemMallocPolicy policy, bool cached = false);

// 仅 UT 使用：重置注册状态
void ResetAclrtHooksForTest();

} // namespace Acp
} // namespace Dvvp
} // namespace Collector

extern "C" MSVP_PROF_API int32_t acltoolInitialize(void);

#endif // COLLECTOR_DVVP_ACP_ACLRT_INJECTION_TOOL_H
