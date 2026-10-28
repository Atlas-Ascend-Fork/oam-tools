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
#include "mini_v3_platform.h"
#include "platform/platform_tool.h"

namespace Dvvp {
namespace Collect {
namespace Platform {
constexpr char MINI_V3_MEMORYUB[] = "0x37,0x38,0x1a5,0x1a6,0x17f,0x180,0x191";

PLATFORM_REGISTER(CHIP_MINI_V3, MiniV3Platform);
MiniV3Platform::MiniV3Platform()
{
    supportedFeature_ = {
        // Task
        PLATFORM_TASK_SWITCH,
        PLATFORM_TASK_ASCENDCL,
        PLATFORM_TASK_FWK,
        PLATFORM_TASK_RUNTIME,
        PLATFORM_TASK_AICPU,
        PLATFORM_TASK_HCCL,
        PLATFORM_TASK_L2_CACHE_REG,
        PLATFORM_TASK_L2_CACHE_PMU,
        PLATFORM_TASK_AU_PMU,
        PLATFORM_TASK_PU_PMU,
        PLATFORM_TASK_PEU_PMU,
        PLATFORM_TASK_RCR_PMU,
        PLATFORM_TASK_MEMORY_PMU,
        PLATFORM_TASK_MEMORYL0_PMU,
        PLATFORM_TASK_MEMORYUB_PMU,
        PLATFORM_TASK_TS_KEYPOINT,
        PLATFORM_TASK_TS_MEMCPY,
        PLATFORM_TASK_AIC_METRICS,
        PLATFORM_TASK_AIV_METRICS,
        PLATFORM_TASK_AICORE_LPM,
        PLATFORM_TASK_STARS_ACSQ,
        PLATFORM_TASK_GE_API,
        PLATFORM_TASK_TRACE,
        PLATFORM_TASK_MSPROFTX,
        PLATFORM_TASK_TSFW,
        PLATFORM_TASK_RUNTIME_API,
        PLATFORM_TASK_BLOCK,
        PLATFORM_TASK_METRICS,
        PLATFORM_TASK_TRAINING_TRACE,
        PLATFORM_TASK_MEMORY,
        PLATFORM_TASK_DYNAMIC,
        PLATFORM_TASK_DELAY_DURATION,
        // System-device
        PLATFORM_SYS_DEVICE_SYS_CPU_MEM_USAGE,
        PLATFORM_SYS_DEVICE_ALL_PID_CPU_MEM_USAGE,
        PLATFORM_SYS_DEVICE_AI_CTRL_CPU_HOT_FUNC_PMU,
        PLATFORM_SYS_DEVICE_NPU_MODULE_MEM,
        PLATFORM_SYS_DEVICE_LLC,
        PLATFORM_SYS_DEVICE_DDR,
        PLATFORM_SYS_DEVICE_NIC,
        PLATFORM_SYS_DEVICE_DVPP,
        PLATFORM_SYS_DEVICE_DVPP_EX,
    };

    epSupportFeature_ = {// System-host
                         PLATFORM_SYS_HOST_ONE_PID_CPU, PLATFORM_SYS_HOST_ALL_PID_CPU,  PLATFORM_SYS_HOST_ONE_PID_MEM,
                         PLATFORM_SYS_HOST_ALL_PID_MEM, PLATFORM_SYS_HOST_ONE_PID_DISK, PLATFORM_SYS_HOST_ONE_PID_OSRT,
                         PLATFORM_SYS_HOST_NETWORK,     PLATFORM_SYS_HOST_SYS_CPU,      PLATFORM_SYS_HOST_SYS_MEM};
}

bool MiniV3Platform::FeatureIsSupport(const PlatformFeature feature) const
{
    if (!Analysis::Dvvp::Common::Platform::Platform::instance()->RunSocSide()) {
        return (supportedFeature_.count(feature) > 0) || (epSupportFeature_.count(feature) > 0);
    }
    return (supportedFeature_.count(feature) > 0);
}

std::string MiniV3Platform::GetMemoryUBMetrics() { return MINI_V3_MEMORYUB; }
} // namespace Platform
} // namespace Collect
} // namespace Dvvp
