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

#ifndef DVVP_COLLECT_PLATFORM_BASE_ANALYZER_H
#define DVVP_COLLECT_PLATFORM_BASE_ANALYZER_H
#include <vector>
#include <unordered_map>
#include "pmu_calculator_tool.h"

namespace Dvvp {
namespace Collect {
namespace Platform {

enum class PmuCalculationType { WITH_FREQ, WITHOUT_FREQ, WITH_ITSELF };

struct PmuCalculationAttr {
    std::string pmuName;
    CalculatePmuFunc formula;
    PmuCalculationType type;
    CalculateAttr attr;
};

class BaseAnalyzer {
public:
    BaseAnalyzer()
    {
        UnInit();
        Init();
    }
    ~BaseAnalyzer() {}
    uint32_t GetMetricsPmuNum(const std::string& name) const;
    std::string GetMetricsTopName(const std::string& name) const;
    PmuCalculationAttr* GetMetricsFunc(const std::string& name, uint32_t index) const;
    float GetTotalTime(uint64_t cycle, double freq, uint16_t blockDim, int64_t coreNum);

protected:
    static uint32_t maxPmuNum_;
    static std::unordered_map<std::string, PmuCalculationAttr> pmuFuncMap_;
    static std::unordered_map<std::string, std::vector<std::string>> aicPmuMap_;
    static std::unordered_map<std::string, std::vector<std::string>> aivPmuMap_;
    SHARED_PTR_ALIA<PmuCalculator> pmuCalculator_;
    PmuCalculationAttr customAttr_;

private:
    void Init();
    void UnInit() const;
    void InitFuncMapWithoutFreqOne();
    void InitFuncMapWithoutFreqTwo();
    void InitFuncMapWithFreqOne();
    void InitFuncMapWithFreqTwo();
    void InitFuncMapWithItself();
    std::string GetMetricsPmuName(const std::string& name) const;
    PmuCalculationAttr* GetAicMetricsFunc(const std::string& name, uint32_t index) const;
    PmuCalculationAttr* GetAivMetricsFunc(const std::string& name, uint32_t index) const;
};
} // namespace Platform
} // namespace Collect
} // namespace Dvvp
#endif
