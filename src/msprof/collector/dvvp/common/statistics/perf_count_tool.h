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
#ifndef ANALYSIS_DVVP_COMMON_PERF_STATISTICS_COUNT_H
#define ANALYSIS_DVVP_COMMON_PERF_STATISTICS_COUNT_H

#include <iostream>
#include <mutex>
#include "utils/utils_tool.h"

namespace Analysis {
namespace Dvvp {
namespace Common {
namespace Statistics {
class PerfCount {
public:
    explicit PerfCount(const std::string& moduleName);
    PerfCount(const std::string& moduleName, const uint64_t printFrequency);
    ~PerfCount();

    /**
     * @brief UpdatePerfInfo: update the perf data according the received data info
     * @param [in] startTime: data received time(ns)
     * @param [in] endTime: the time of data has been dealt
     * @param [in] dataLen: the length of the received data
     */
    void UpdatePerfInfo(uint64_t startTime, uint64_t endTime, size_t dataLen);

    /**
     * @brief OutPerfInfo: output the perf info with module name and device id
     * @param [in] tag: the module tag
     */
    void OutPerfInfo(const std::string& tag);

private:
    void PrintPerfInfo(const std::string& moduleName) const;
    void ResetPerfInfo();

    uint64_t overHeadMin_; // the Report data min overhead time(ns)
    uint64_t overHeadMax_; // the Report data max overhead time(ns)

    // the sum time of Report overhead(ns), UINT64_T can record 18446744073 seconds, it's means 584 years
    uint64_t overHeadSum_;
    uint64_t packetNums_; // Report data numbers, used to calculate overhead average
    size_t minDataLen_;   // the min data len when overHeadMin_
    size_t maxDataLen_;   // the max data len when overHeadMax_
    uint64_t throughPut_; // UINT64_T can record 17179869184 GB data package
    std::string moduleName_;
    uint64_t printFrequency_;
    std::mutex mtx_;
};
} // namespace Statistics
} // namespace Common
} // namespace Dvvp
} // namespace Analysis
#endif
