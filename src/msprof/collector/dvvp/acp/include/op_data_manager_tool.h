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

#ifndef COLLECTOR_DVVP_ACP_OP_DATA_MANAGER_H
#define COLLECTOR_DVVP_ACP_OP_DATA_MANAGER_H

#include <vector>
#include "singleton/singleton_tool.h"
#include "data_struct_tool.h"

namespace Dvvp {
namespace Acp {
namespace Analyze {
using namespace Analysis::Dvvp::Analyze;

constexpr uint32_t KERNEL_EXECUTE_TIME = 5;

class OpDataManager : public analysis::dvvp::common::singleton::Singleton<OpDataManager> {
public:
    OpDataManager();
    ~OpDataManager() override;
    void UnInit();
    void AddAnalyzeCount();
    void AddMetrics(std::string& metrics);
    void AddSummaryInfo(KernelDetail& data);
    bool CheckSummaryInfoData(uint32_t replayTime) const;
    uint32_t GetAnalyzeCount() const;
    std::vector<std::string> GetMetricsInfo() const;
    std::vector<std::vector<KernelDetail>> GetSummaryInfo() const;

private:
    uint32_t analyzeCount_;
    std::vector<KernelDetail> replayInfo_;
    std::vector<std::vector<KernelDetail>> summaryInfo_;
    std::vector<std::string> metrics_;
};
} // namespace Analyze
} // namespace Acp
} // namespace Dvvp
#endif
