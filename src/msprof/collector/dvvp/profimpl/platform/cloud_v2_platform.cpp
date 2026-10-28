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
#include "cloud_v2_platform.h"
#include "cloud_v2_analyzer_tool.h"

namespace Dvvp {
namespace Collect {
namespace Platform {
// SOC PMU SMMU DFX config values for the milan platform (independent from other platforms).
constexpr uint32_t CLOUD_V2_SMMU_DFX_OFFSET = 0x0E78;
constexpr uint32_t CLOUD_V2_SMMU_DFX_REG_MASK = 0x3FFFFFFF; // bits 0-29 set, bits 30,31 clear

PLATFORM_REGISTER(CHIP_CLOUD_V2, CloudV2Platform);
CloudV2Platform::CloudV2Platform()
{
    supportedFeature_ = {
        // TASK
        PLATFORM_TASK_ASCENDCL, PLATFORM_TASK_RUNTIME_API, PLATFORM_TASK_METRICS, PLATFORM_TASK_AIC_METRICS,
        PLATFORM_TASK_AIV_METRICS, PLATFORM_TASK_AICORE_LPM, PLATFORM_TASK_AICORE_LPM_INFO, PLATFORM_TASK_GE_API,
        PLATFORM_TASK_HCCL, PLATFORM_TASK_TSFW, PLATFORM_TASK_L2_CACHE_REG, PLATFORM_TASK_MEMORY,
        PLATFORM_TASK_MSPROFTX, PLATFORM_TASK_SWITCH, PLATFORM_TASK_TRACE, PLATFORM_TASK_TRACE_L3,
        PLATFORM_TASK_STARS_ACSQ, PLATFORM_TASK_TS_KEYPOINT, PLATFORM_TASK_TS_MEMCPY, PLATFORM_TASK_BLOCK,
        PLATFORM_TASK_TRAINING_TRACE, PLATFORM_TASK_AICPU, PLATFORM_TASK_DYNAMIC, PLATFORM_TASK_DELAY_DURATION,
        // PMU
        PLATFORM_TASK_AU_PMU, PLATFORM_TASK_PU_PMU, PLATFORM_TASK_PUEXCT_PMU, PLATFORM_TASK_MEMORY_PMU,
        PLATFORM_TASK_MEMORYL0_PMU, PLATFORM_TASK_MEMORYUB_PMU, PLATFORM_TASK_L2_CACHE_PMU, PLATFORM_TASK_RCR_PMU,
        PLATFORM_TASK_SOC_PMU, PLATFORM_TASK_MEMORY_ACCESS_PMU,
        // System-device
        PLATFORM_SYS_DEVICE_SYS_CPU_MEM_USAGE, PLATFORM_SYS_DEVICE_ALL_PID_CPU_MEM_USAGE,
        PLATFORM_SYS_DEVICE_TS_CPU_HOT_FUNC_PMU, PLATFORM_SYS_DEVICE_AI_CTRL_CPU_HOT_FUNC_PMU,
        PLATFORM_SYS_DEVICE_NPU_MODULE_MEM, PLATFORM_SYS_DEVICE_LLC, PLATFORM_SYS_DEVICE_HBM, PLATFORM_SYS_DEVICE_NIC,
        PLATFORM_SYS_DEVICE_ROCE, PLATFORM_SYS_DEVICE_HCCS, PLATFORM_SYS_DEVICE_PCIE, PLATFORM_SYS_DEVICE_DVPP,
        PLATFORM_SYS_DEVICE_DVPP_EX, PLATFORM_SYS_DEVICE_INSTR_PROFILING, PLATFORM_SYS_DEVICE_QOS,
        PLATFORM_SYS_DEVICE_INTERCONNECTION,
        // System-host
        PLATFORM_SYS_HOST_ONE_PID_CPU, PLATFORM_SYS_HOST_ALL_PID_CPU, PLATFORM_SYS_HOST_ONE_PID_MEM,
        PLATFORM_SYS_HOST_ALL_PID_MEM, PLATFORM_SYS_HOST_ONE_PID_DISK, PLATFORM_SYS_HOST_ONE_PID_OSRT,
        PLATFORM_SYS_HOST_NETWORK, PLATFORM_SYS_HOST_SYS_CPU, PLATFORM_SYS_HOST_SYS_MEM,
        // Feature collection
        PLATFORM_COLLECTOR_ACP, PLATFORM_DIAGNOSTIC_COLLECTION, PLATFORM_MC2, PLATFORM_AICPU_HCCL,
        PLATFORM_SYS_MEM_SERVICEFLOW, PLATFORM_AICSCALE_ACP, PLATFORM_ACLAPI_SETDEVICE_ENABLE, PLATFORM_EXPORT_TYPE};
    supportedFeature_.insert(PLATFORM_ADPROF);
}

int32_t CloudV2Platform::InitOnlineAnalyzer()
{
    MSVP_MAKE_SHARED0(analyzer_, CloudV2Analyzer, return -1);
    return 0;
}

uint32_t CloudV2Platform::GetSmmuDFXOffset() const { return CLOUD_V2_SMMU_DFX_OFFSET; }

uint32_t CloudV2Platform::GetSmmuDFXRegMask() const { return CLOUD_V2_SMMU_DFX_REG_MASK; }
} // namespace Platform
} // namespace Collect
} // namespace Dvvp
