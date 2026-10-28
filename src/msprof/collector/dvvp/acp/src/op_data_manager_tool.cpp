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
#include "op_data_manager_tool.h"
#include "msprof_dlog_tool.h"
#include "utils/utils_tool.h"

namespace Dvvp {
namespace Acp {
namespace Analyze {
using namespace analysis::dvvp::common::utils;

constexpr uint32_t EVENT_RECORD_MASK = 0x8000;

OpDataManager::OpDataManager() : analyzeCount_(0), replayInfo_({}), summaryInfo_({}), metrics_({}) {}

OpDataManager::~OpDataManager() { UnInit(); }

void OpDataManager::UnInit()
{
    analyzeCount_ = 0;
    replayInfo_.clear();
    summaryInfo_.clear();
    metrics_.clear();
    MSPROF_LOGI("Success to uninit op data manager.");
}

/**
 * @brief Add total analayze count
 * @return
 */
void OpDataManager::AddAnalyzeCount() { analyzeCount_++; }

/**
 * @brief Add op metrics
 * @param [in] metrics: aic metrics
 * @return
 */
void OpDataManager::AddMetrics(std::string& metrics)
{
    if (analyzeCount_ % KERNEL_EXECUTE_TIME == 0) {
        MSPROF_LOGI("Op data manager add op metrics to manager: %s.", metrics.c_str());
        metrics_.emplace_back(metrics);
    }
}

/**
 * @brief Add op log info
 * @param [in] data: kernel detail
 * @return
 */
void OpDataManager::AddSummaryInfo(KernelDetail& data)
{
    // eliminating EVENT_RECORD
    if ((data.streamId & EVENT_RECORD_MASK) != 0) {
        MSPROF_LOGW(
            "Op data manager eliminate EVENT_RECORD task, task id: %u, stream id: %u.", data.taskId, data.streamId);
        return;
    }
    replayInfo_.emplace_back(data);
    if (static_cast<uint32_t>(replayInfo_.size()) == KERNEL_EXECUTE_TIME) {
        MSPROF_LOGI("Op data manager add op replay info to summary info.");
        summaryInfo_.emplace_back(replayInfo_);
        replayInfo_.clear();
    }
}

/**
 * @brief Check summary info data
 * @param [in] replayTime: replay time
 * @return
 */
bool OpDataManager::CheckSummaryInfoData(uint32_t replayTime) const
{
    size_t summarySize = summaryInfo_.size();
    FUNRET_CHECK_EXPR_ACTION(
        static_cast<uint32_t>(summarySize) > replayTime, return false,
        "Op data over flow, summary info collect data size: %zu, while acp replay time: %u. "
        "Please noted that acp tool applies only to single operator scene.",
        summarySize, replayTime);

    FUNRET_CHECK_EXPR_ACTION(
        static_cast<uint32_t>(summarySize) < replayTime, return false,
        "Op data not enough, summary info collect data size: %zu, while acp replay time: %u."
        "Please check if exist task execute failed.",
        summarySize, replayTime);

    for (auto& summaryIter : summaryInfo_) {
        for (auto& iter : summaryIter) {
            FUNRET_CHECK_EXPR_ACTION(
                iter.beginTime == 0 || iter.endTime == 0 || (iter.aicTotalCycle == 0 && iter.aivTotalCycle == 0),
                return false,
                "Op data not complete, task id: %u, stream id: %u, begin time: %llu, end time: %llu, "
                "aic total cycle: %llu, aiv total cycle: %llu.",
                iter.taskId, iter.streamId, iter.beginTime, iter.endTime, iter.aicTotalCycle, iter.aivTotalCycle);
        }
    }
    return true;
}

/**
 * @brief Get total analyze count
 * @return
 */
uint32_t OpDataManager::GetAnalyzeCount() const { return analyzeCount_; }

/**
 * @brief Get op metrics vector
 * @return
 */
std::vector<std::string> OpDataManager::GetMetricsInfo() const { return metrics_; }

/**
 * @brief Get summary info vector
 * @return
 */
std::vector<std::vector<KernelDetail>> OpDataManager::GetSummaryInfo() const { return summaryInfo_; }
} // namespace Analyze
} // namespace Acp
} // namespace Dvvp
