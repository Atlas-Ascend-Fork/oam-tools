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
#include "op_analyzer_base_tool.h"

namespace Dvvp {
namespace Acp {
namespace Analyze {
using namespace analysis::dvvp::common::error;
static const uint32_t MHZ_CONVERT_GHZ = 1000; // 1000: mhz to ghz, syscnt * (1 / ghz) = ns
static const std::string DEFAULT_FREQ = "50"; // default freq in chip v4, not using when api version >= 0x071905

int32_t OpAnalyzerBase::InitFrequency(uint32_t deviceId)
{
    std::string freq =
        Analysis::Dvvp::Common::Platform::Platform::instance()->PlatformGetDeviceOscFreq(deviceId, DEFAULT_FREQ);
    frequency_ = std::stod(freq) / MHZ_CONVERT_GHZ;
    if (frequency_ <= 0) {
        MSPROF_LOGE("Failed to init Op analyzer frequency: %f ghz, get freq %s mhz.", frequency_, freq.c_str());
        return PROFILING_FAILED;
    } else {
        MSPROF_EVENT("Success to init Op analyzer frequency: %f.", frequency_);
        return PROFILING_SUCCESS;
    }
}
} // namespace Analyze
} // namespace Acp
} // namespace Dvvp
