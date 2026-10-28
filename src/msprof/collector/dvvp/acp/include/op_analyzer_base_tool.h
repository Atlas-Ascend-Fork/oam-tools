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
#ifndef DVVP_ACP_ANALYZE_OP_ANALYZER_BASE_H
#define DVVP_ACP_ANALYZE_OP_ANALYZER_BASE_H

#include <map>
#include "utils/utils_tool.h"
#include "data_struct_tool.h"
#include "platform/platform_tool.h"
namespace Dvvp {
namespace Acp {
namespace Analyze {
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::Analyze;
class OpAnalyzerBase {
public:
    OpAnalyzerBase() : dataPtr_(nullptr), dataLen_(0), pmuNum_(0), frequency_(0)
    {
        pmuNum_ = Analysis::Dvvp::Common::Platform::Platform::instance()->GetMaxMonitorNumber();
    }
    ~OpAnalyzerBase() {}
    int32_t InitFrequency(uint32_t deviceId);

public:
    CONST_CHAR_PTR dataPtr_;
    uint32_t dataLen_;
    uint32_t pmuNum_;
    double frequency_;
    std::multimap<std::string, KernelDetail> logInfo_;
    std::multimap<std::string, KernelDetail> subTaskInfo_;
    std::multimap<std::string, KernelDetail> blockInfo_;
};
} // namespace Analyze
} // namespace Acp
} // namespace Dvvp

#endif
