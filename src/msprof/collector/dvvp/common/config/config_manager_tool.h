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
#ifndef ANALYSIS_DVVP_COMMON_CONFIG_MANAGER_H
#define ANALYSIS_DVVP_COMMON_CONFIG_MANAGER_H

#include <string>
#include <map>
#include "singleton/singleton_tool.h"
#include "errno/error_code_tool.h"
#include "utils/utils_tool.h"
#include "message/prof_params.h"

namespace Analysis {
namespace Dvvp {
namespace Common {
namespace Config {

// helper形态设备类型：由扩展平台注入的chip id（数值与扩展仓注入实现一致），未注入时为2
constexpr int32_t HELPER_DEVICE_TYPE = 2;
constexpr uint32_t VER_310M = 5;
enum class PlatformType {
    MINI_TYPE = 0,
    CLOUD_TYPE,
    DC_TYPE = 4,
    CHIP_V4_1_0,
    MINI_V3_TYPE = 7,
    CHIP_TINY_V1 = 8,
    CHIP_NANO_V1 = 9,
    CHIP_CLOUD_V3 = 15,
    CHIP_CLOUD_V3_LITE = 19,
    CHIP_CLOUD_V4 = 16,
    CHIP_5162A = 21,
    END_TYPE
};

const std::map<PlatformType, std::string> FREQUENCY_TYPE = {
    {PlatformType::MINI_TYPE, "19.2"},     {PlatformType::CLOUD_TYPE, "100"},
    {PlatformType::DC_TYPE, "38.4"},       {PlatformType::CHIP_V4_1_0, "50"},
    {PlatformType::MINI_V3_TYPE, "48"},    {PlatformType::CHIP_TINY_V1, "48"},
    {PlatformType::CHIP_CLOUD_V3, "1000"}, {PlatformType::CHIP_CLOUD_V3_LITE, "1000"},
    {PlatformType::CHIP_CLOUD_V4, "1000"}, {PlatformType::CHIP_5162A, "20"}};

// clang-format off
const std::map<PlatformType, std::string> AIC_TYPE = {
    {PlatformType::MINI_TYPE, "680"},
    {PlatformType::CLOUD_TYPE, "800"},
    {PlatformType::DC_TYPE, "1150"},
    {PlatformType::CHIP_V4_1_0, "800"},
    {PlatformType::MINI_V3_TYPE, "1250"},
    {PlatformType::CHIP_TINY_V1, "1250"},
    {PlatformType::CHIP_CLOUD_V3, "800"},
    {PlatformType::CHIP_CLOUD_V3_LITE, "800"},
    {PlatformType::CHIP_CLOUD_V4, "1650"},
    {PlatformType::CHIP_5162A, "20"}};
// clang-format on

class ConfigManager : public analysis::dvvp::common::singleton::Singleton<ConfigManager> {
public:
    ConfigManager();
    ~ConfigManager() override;
    int32_t Init();
    void Uninit();
    std::string GetFrequency() const;
    std::string GetChipIdStr();
    PlatformType GetPlatformType() const;
    std::string GetAicDefFrequency() const;
    bool IsDriverSupportLlc() const;
    std::string GetPerfDataDir(const int32_t devId = 0) const;
    std::string GetDefaultWorkDir() const;
    void GetVersionSpecificMetrics(std::string& aicMetrics) const;
    void UpdateFrequency(const std::string& frequency, const std::string& aicFrequency);

private:
    void InitFrequency();

    bool isInit_;
    std::map<std::string, std::string> configMap_;
};
} // namespace Config
} // namespace Common
} // namespace Dvvp
} // namespace Analysis
#endif
