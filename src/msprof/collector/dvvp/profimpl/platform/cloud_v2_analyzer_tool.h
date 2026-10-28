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

#ifndef DVVP_COLLECT_PLATFORM_CLOUD_V2_ANALYZER_H
#define DVVP_COLLECT_PLATFORM_CLOUD_V2_ANALYZER_H
#include "base_analyzer_tool.h"

namespace Dvvp {
namespace Collect {
namespace Platform {

class CloudV2Analyzer : public BaseAnalyzer {
public:
    CloudV2Analyzer() { AdaptCloudV2PmuMap(); }
    ~CloudV2Analyzer() {}

private:
    void AdaptCloudV2PmuMap() const
    {
        BaseAnalyzer::aicPmuMap_["PipeUtilization"] = {"0x416", "0x417", "0x9",  "0x302",
                                                       "0xc",   "0x303", "0x54", "0x55"};
        BaseAnalyzer::aivPmuMap_["PipeUtilization"] = {"0x8", "0xa", "0x9", "0xb", "0xc", "0xd", "0x54", "0x55"};
    }
};
} // namespace Platform
} // namespace Collect
} // namespace Dvvp
#endif
