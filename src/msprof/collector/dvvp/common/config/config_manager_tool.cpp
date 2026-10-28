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
#include "config_manager_tool.h"
#include <string>
#include <algorithm>
#include "message/prof_params.h"
#include "singleton/singleton_tool.h"
#include "utils/utils_tool.h"
#include "errno/error_code_tool.h"
#include "config/config.h"
#include "config/config_manager_tool.h"
#include "validation/param_validation_tool.h"
#include "ascend_hal.h"
#include "ai_drv_dev_api.h"

namespace Analysis {
namespace Dvvp {
namespace Common {
namespace Config {
static const std::string TYPE_CONFIG = "type";
static const std::string FRQ_CONFIG = "frq";
static const std::string AIC_CONFIG = "aicFrq";
static const std::string INOTIFY_CFG_PATH_STR = "/var/log/npu/profiling/";

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::message;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::validation;
using namespace analysis::dvvp::driver;

ConfigManager::ConfigManager() : isInit_(false) { (void)Init(); }
ConfigManager::~ConfigManager() { Uninit(); }

int32_t ConfigManager::Init()
{
    if (isInit_) {
        MSPROF_LOGD("ConfigManager has been inited");
        return PROFILING_SUCCESS;
    }
    // get device num and id list
    int32_t devNum = DrvGetDevNum();
    if (devNum <= 0) {
        MSPROF_LOGW("Get device num %d.", devNum);
    }
    std::vector<int32_t> devList;
    if (devNum > 0 && DrvGetDevIds(devNum, devList) != PROFILING_SUCCESS) {
        MSPROF_LOGW("Get device id list, device num: %d.", devNum);
    }
    if (devList.empty()) {
        devList.push_back(0);
    }
    int64_t versionInfo = 0;
    uint32_t chipId = 0;
    drvError_t ret = DRV_ERROR_NO_DEVICE;
    for (auto& devId : devList) {
        if (!DrvGetDeviceStatus(devId)) {
            continue;
        }
        ret = halGetDeviceInfo(
            devId, static_cast<int32_t>(MODULE_TYPE_SYSTEM), static_cast<int32_t>(INFO_TYPE_VERSION), &versionInfo);
        if (ret == DRV_ERROR_NONE) {
            chipId = ((static_cast<uint64_t>(versionInfo) >> 8) & 0xff); // 8:shift 8 bits, get the low 8 bits(0xff)
            break;
        } else if (ret == DRV_ERROR_NOT_SUPPORT) {
            MSPROF_LOGW(
                "Driver doesn't support device type version by halGetDeviceInfo interface, ret=%d"
                ", set PlatformType::HELPER_DEVICE_TYPE",
                static_cast<int32_t>(ret));
#ifdef MSPROF_MODULE_EXT_DEFAULT_PLATFORM_TYPE
            chipId = static_cast<uint32_t>(MSPROF_MODULE_EXT_DEFAULT_PLATFORM_TYPE);
#else
            chipId = static_cast<uint32_t>(HELPER_DEVICE_TYPE);
#endif
            break;
        }
    }
    if (ret != DRV_ERROR_NONE && ret != DRV_ERROR_NOT_SUPPORT) {
        MSPROF_LOGE("Failed to get chip id.");
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("Success to get chip id: %u.", chipId);
    configMap_[TYPE_CONFIG] = std::to_string(chipId);
    InitFrequency();
    isInit_ = true;
    return PROFILING_SUCCESS;
}

void ConfigManager::Uninit()
{
    if (isInit_) {
        isInit_ = false;
    }
}

void ConfigManager::GetVersionSpecificMetrics(std::string& aicMetrics) const
{
    if (GetPlatformType() == PlatformType::CHIP_V4_1_0 && (aicMetrics.compare(PIPE_UTILIZATION) == 0)) {
        aicMetrics = PIPE_UTILIZATION_EXCT;
    }
}

std::string ConfigManager::GetFrequency() const
{
    std::string frequency;
    auto iter = configMap_.find(FRQ_CONFIG);
    if (iter != configMap_.end()) {
        frequency = iter->second;
    }
    return frequency;
}

std::string ConfigManager::GetAicDefFrequency() const
{
    std::string frequency;
    auto iter = configMap_.find(AIC_CONFIG);
    if (iter != configMap_.end()) {
        frequency = iter->second;
    }
    return frequency;
}

void ConfigManager::InitFrequency()
{
    std::string frequency;
    std::string aicFrq;
    std::string type = configMap_[TYPE_CONFIG];
    int32_t typeInt = 0;
    FUNRET_CHECK_EXPR_ACTION(!Utils::StrToInt32(typeInt, type), return, "type %s is invalid", type.c_str());
    auto platType = static_cast<PlatformType>(typeInt);
    auto iterator = FREQUENCY_TYPE.find(platType);
    if (iterator != FREQUENCY_TYPE.end()) {
        frequency = iterator->second;
    }
    auto iter = AIC_TYPE.find(platType);
    if (iter != AIC_TYPE.end()) {
        aicFrq = iter->second;
    }
    configMap_[AIC_CONFIG] = aicFrq;
    configMap_[FRQ_CONFIG] = frequency;
}

void ConfigManager::UpdateFrequency(const std::string& frequency, const std::string& aicFrequency)
{
    if (!frequency.empty()) {
        configMap_[FRQ_CONFIG] = frequency;
    }
    if (!aicFrequency.empty()) {
        configMap_[AIC_CONFIG] = aicFrequency;
    }
}

std::string ConfigManager::GetChipIdStr()
{
    const auto iter = configMap_.find(TYPE_CONFIG);
    if (iter != configMap_.end()) {
        return iter->second;
    }
    return std::to_string(static_cast<uint32_t>(PlatformType::MINI_TYPE));
}

PlatformType ConfigManager::GetPlatformType() const
{
    auto iter = configMap_.find(TYPE_CONFIG);
    if (iter != configMap_.end()) {
        int32_t typeInt = 0;
        FUNRET_CHECK_EXPR_ACTION(
            !Utils::StrToInt32(typeInt, iter->second), return PlatformType::MINI_TYPE, "iter->second %s is invalid",
            iter->second.c_str());
        auto type = static_cast<PlatformType>(typeInt);
        return type;
    }
    return PlatformType::MINI_TYPE;
}

bool ConfigManager::IsDriverSupportLlc() const
{
    PlatformType type = GetPlatformType();
    if (type == PlatformType::CLOUD_TYPE || type == PlatformType::DC_TYPE || type == PlatformType::CHIP_V4_1_0 ||
        type == PlatformType::MINI_V3_TYPE || type == PlatformType::CHIP_TINY_V1 ||
        type == PlatformType::CHIP_CLOUD_V3 || type == PlatformType::CHIP_CLOUD_V3_LITE ||
        type == PlatformType::CHIP_CLOUD_V4) {
        return true;
    }
    return false;
}

std::string ConfigManager::GetPerfDataDir(const int32_t devId) const
{
    std::string perfDataDir = INOTIFY_CFG_PATH_STR + std::to_string(devId);
    return perfDataDir;
}

std::string ConfigManager::GetDefaultWorkDir() const { return std::string(INOTIFY_CFG_PATH_STR); }
} // namespace Config
} // namespace Common
} // namespace Dvvp
} // namespace Analysis
