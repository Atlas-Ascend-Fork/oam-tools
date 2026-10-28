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

#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_BIU_PERF_JOB_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_BIU_PERF_JOB_H

#include "prof_comm_job_tool.h"
#include "platform_interface.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::config;

class ProfBiuPerfJob : public ProfDrvJob {
public:
    ProfBiuPerfJob();
    ~ProfBiuPerfJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;

private:
    int32_t CheckBiuPerfInitConfig(const SHARED_PTR_ALIA<CollectionJobCfg>& cfg) const;
    void SetBiuPerfMode(const SHARED_PTR_ALIA<CollectionJobCfg>& cfg);
    int32_t InitGroupConfig(int64_t aiCoreNum);
    uint32_t GenGroupVector(int64_t aiCoreNum);
    std::vector<::Dvvp::Collect::Platform::BiuPerfChannelInfo> GetBiuChannelInfos() const;

private:
    uint32_t groupNum_;
    uint32_t biuPcSamplingMode_;
    // Determined by the DRV and corresponding to the aicore quantity configuration
    std::vector<uint32_t> groupVector_;
    std::string profBiuPerfJobName_;
    AI_DRV_CHANNEL groupChannelIdMap_[BIU_PERF_HIGHER_GROUP_NUM][INSTR_PROFILING_GROUP_CHANNEL_NUM] = {
        {PROF_CHANNEL_BIU_GROUP0_AIC, PROF_CHANNEL_BIU_GROUP0_AIV0, PROF_CHANNEL_BIU_GROUP0_AIV1},
        {PROF_CHANNEL_BIU_GROUP1_AIC, PROF_CHANNEL_BIU_GROUP1_AIV0, PROF_CHANNEL_BIU_GROUP1_AIV1},
        {PROF_CHANNEL_BIU_GROUP2_AIC, PROF_CHANNEL_BIU_GROUP2_AIV0, PROF_CHANNEL_BIU_GROUP2_AIV1},
        {PROF_CHANNEL_BIU_GROUP3_AIC, PROF_CHANNEL_BIU_GROUP3_AIV0, PROF_CHANNEL_BIU_GROUP3_AIV1},
        {PROF_CHANNEL_BIU_GROUP4_AIC, PROF_CHANNEL_BIU_GROUP4_AIV0, PROF_CHANNEL_BIU_GROUP4_AIV1},
        {PROF_CHANNEL_BIU_GROUP5_AIC, PROF_CHANNEL_BIU_GROUP5_AIV0, PROF_CHANNEL_BIU_GROUP5_AIV1},
    };
};

} // namespace JobWrapper
} // namespace Dvvp
} // namespace Analysis
#endif
