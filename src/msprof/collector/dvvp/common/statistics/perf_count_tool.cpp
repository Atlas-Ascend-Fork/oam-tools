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

#include "perf_count_tool.h"
using namespace analysis::dvvp::common::error;

namespace Analysis {
namespace Dvvp {
namespace Common {
namespace Statistics {
PerfCount::PerfCount(const std::string& moduleName)
    : overHeadMin_(UINT64_MAX),
      overHeadMax_(0),
      overHeadSum_(0),
      packetNums_(0),
      minDataLen_(0),
      maxDataLen_(0),
      throughPut_(0),
      moduleName_(moduleName),
      printFrequency_(0)
{}

PerfCount::PerfCount(const std::string& moduleName, const uint64_t printFrequency)
    : overHeadMin_(UINT64_MAX),
      overHeadMax_(0),
      overHeadSum_(0),
      packetNums_(0),
      minDataLen_(0),
      maxDataLen_(0),
      throughPut_(0),
      moduleName_(moduleName),
      printFrequency_(printFrequency)
{}

PerfCount::~PerfCount() {}

/**
 * @brief UpdatePerfInfo: update the perf data according the received data info
 * @param [in] startTime: data received time(ns)
 * @param [in] endTime: the time of data has been dealt
 * @param [in] dataLen: the length of the received data
 */
void PerfCount::UpdatePerfInfo(uint64_t startTime, uint64_t endTime, size_t dataLen)
{
    if (startTime > endTime) {
        MSPROF_LOGE(
            "[UpdatePerfInfo] startTime:%" PRIu64 "ns is larger than endTime:%" PRIu64 "ns", startTime, endTime);
        return;
    }
    std::lock_guard<std::mutex> lk(mtx_);

    uint64_t timeInterval = endTime - startTime;
    if (timeInterval < overHeadMin_) {
        overHeadMin_ = timeInterval;
        minDataLen_ = dataLen;
    }

    if (timeInterval > overHeadMax_) {
        overHeadMax_ = timeInterval;
        maxDataLen_ = dataLen;
    }

    overHeadSum_ += timeInterval;
    packetNums_ += 1;
    throughPut_ += dataLen;
    if ((printFrequency_ != 0) && ((packetNums_ % printFrequency_) == 0)) {
        PrintPerfInfo(moduleName_);
        ResetPerfInfo();
    }
}

/*
 * @brief PrintPerfInfo: print the perf info with module name
 * @param [in] moduleName: the module name
 */
void PerfCount::PrintPerfInfo(const std::string& moduleName) const
{
    const uint64_t perfMsec = 1000000;
    uint64_t nsToMSec = overHeadSum_ / perfMsec;

    if ((packetNums_ > 0) && (nsToMSec > 0)) {
        MSPROF_EVENT(
            "moduleName: %s, overhead Min: %" PRIu64 " ns, data Min: %zu, overhead Max: %" PRIu64 " ns, "
            "data Max: %zu, overhead Avg: %" PRIu64 " ns, overhead Sum_: %" PRIu64 " ns, package nums: %" PRIu64 ", "
            "package size: %" PRIu64 " bytes, throughput: %" PRIu64 ".%" PRIu64 " B/ms",
            moduleName.c_str(), overHeadMin_, minDataLen_, overHeadMax_, maxDataLen_, overHeadSum_ / packetNums_,
            overHeadSum_, packetNums_, throughPut_, throughPut_ / nsToMSec, throughPut_ % nsToMSec);
    }
}

/*
 * @brief OutPerfInfo: output the perf info with module name and device id
 * @param [in] tag: the module tag
 */
void PerfCount::OutPerfInfo(const std::string& tag)
{
    std ::string moduleName = tag.empty() ? moduleName_ : tag;
    std::lock_guard<std::mutex> lk(mtx_);
    PrintPerfInfo(moduleName);
}

/**
 * @brief ResetPerfInfo: reset perf info
 */
void PerfCount::ResetPerfInfo()
{
    overHeadMin_ = UINT64_MAX;
    overHeadMax_ = 0;
    overHeadSum_ = 0;
    packetNums_ = 0;
    minDataLen_ = 0;
    maxDataLen_ = 0;
    throughPut_ = 0;
}
} // namespace Statistics
} // namespace Common
} // namespace Dvvp
} // namespace Analysis
