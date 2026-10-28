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
#include "ai_drv_dsmi_api.h"
#include "errno/error_code_tool.h"
#include "msprof_dlog_tool.h"
#include "config_manager_tool.h"
namespace Analysis {
namespace Dvvp {
namespace Driver {
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Config;

int32_t DrvGetAicoreInfo(int32_t deviceId, int64_t& freq)
{
    if (deviceId < 0) {
        return PROFILING_FAILED;
    }
    return static_cast<int32_t>(halGetDeviceInfo(
        static_cast<uint32_t>(deviceId), static_cast<int32_t>(MODULE_TYPE_AICORE),
        static_cast<int32_t>(INFO_TYPE_FREQUE), &freq));
}

std::string DrvGeAicFrq(int32_t deviceId)
{
    const std::string defAicFrq = ConfigManager::instance()->GetAicDefFrequency();
    if (deviceId < 0) {
        return defAicFrq;
    }

    if (ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_TYPE) {
        return defAicFrq;
    }
    int64_t freq = 0;
    int32_t ret = DrvGetAicoreInfo(deviceId, freq);
    if (ret != PROFILING_SUCCESS || freq == 0) {
        MSPROF_LOGW("An anomaly was detected during DrvGetAicoreInfo, ret:%d", ret);
        return defAicFrq;
    }

    MSPROF_LOGI("DrvGetAicoreInfo curFreq %u", freq);
    return std::to_string(freq);
}

std::string DrvGeAivFrq(int32_t deviceId)
{
    const std::string defAivFrq = ConfigManager::instance()->GetAicDefFrequency();
    if (deviceId < 0 || ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_TYPE) {
        return defAivFrq;
    }
    int64_t freq = 0;
    const int32_t ret = static_cast<int32_t>(halGetDeviceInfo(
        static_cast<uint32_t>(deviceId), static_cast<int32_t>(MODULE_TYPE_VECTOR_CORE),
        static_cast<int32_t>(INFO_TYPE_FREQUE), &freq));
    if (ret != DRV_ERROR_NONE || freq == 0) {
        MSPROF_LOGW("An anomaly was detected during DrvGetAiVectorCoreInfo, ret:%d", ret);
        return defAivFrq;
    }

    MSPROF_LOGI("DrvGetAiVectorCoreInfo curFreq %" PRId64 ".", freq);
    return std::to_string(freq);
}
} // namespace Driver
} // namespace Dvvp
} // namespace Analysis
