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

#include "prof_biu_perf_job_tool.h"
#include "errno/error_code_tool.h"
#include "ai_drv_dev_api.h"
#include "platform/platform_tool.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Platform;
using BiuPerfChannelInfo = ::Dvvp::Collect::Platform::BiuPerfChannelInfo;

ProfBiuPerfJob::ProfBiuPerfJob() : groupNum_(BIU_PERF_LOWER_GROUP_NUM), biuPcSamplingMode_(0) {}

ProfBiuPerfJob::~ProfBiuPerfJob() {}

int32_t ProfBiuPerfJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_CONTEXT_PARAM_RET(cfg, return PROFILING_FAILED);
    collectionJobCfg_ = cfg;
    if (CheckBiuPerfInitConfig(cfg) != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }
    SetBiuPerfMode(cfg);
    int64_t aiCoreNum = 0;
    int32_t ret = DrvGetAiCoreNum(collectionJobCfg_->comParams->devId, aiCoreNum);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("[ProfBiuPerfJob]Failed to DrvGetAiCoreNum, deviceId=%d", collectionJobCfg_->comParams->devId);
        return PROFILING_FAILED;
    }
    if (InitGroupConfig(aiCoreNum) != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("Biu perf init success with aicore num %" PRId64 " and %u groups.", aiCoreNum, groupNum_);
    return PROFILING_SUCCESS;
}

int32_t ProfBiuPerfJob::CheckBiuPerfInitConfig(const SHARED_PTR_ALIA<CollectionJobCfg>& cfg) const
{
    if (cfg->comParams->params->hostProfiling ||
        (!Platform::instance()->CheckIfSupport(PLATFORM_TASK_INSTR_PROFILING) &&
         !Platform::instance()->CheckIfSupport(PLATFORM_TASK_PC_SAMPLING))) {
        MSPROF_LOGI("Biu perf job is not supported.");
        return PROFILING_FAILED;
    }

    if ((cfg->comParams->params->instrProfiling.compare(MSVP_PROF_ON) != 0) &&
        (cfg->comParams->params->pcSampling.compare(MSVP_PROF_ON) != 0)) {
        MSPROF_LOGI("Biu perf job is not enabled.");
        return PROFILING_FAILED;
    }

    return PROFILING_SUCCESS;
}

void ProfBiuPerfJob::SetBiuPerfMode(const SHARED_PTR_ALIA<CollectionJobCfg>& cfg)
{
    if (cfg->comParams->params->pcSampling.compare(MSVP_PROF_ON) == 0) {
        biuPcSamplingMode_ = 1;
        profBiuPerfJobName_ = "pc_sampling_";
        MSPROF_LOGI("Biu perf job is pc sampling.");
        return;
    }
    biuPcSamplingMode_ = 0;
    profBiuPerfJobName_ = "biu_perf_";
    MSPROF_LOGI("Biu perf job is perf monitor.");
}

int32_t ProfBiuPerfJob::InitGroupConfig(int64_t aiCoreNum)
{
    groupNum_ = BIU_PERF_LOWER_GROUP_NUM;
    if (aiCoreNum > DAVID_DIE0_AICORE_NUM) {
        groupNum_ = BIU_PERF_HIGHER_GROUP_NUM;
    }
    uint32_t platformGroupNum = Platform::instance()->GetBiuPerfGroupNum();
    if (platformGroupNum == BIU_PERF_GROUP_NUM_INVALID) {
        MSPROF_LOGE("[ProfBiuPerfJob]Platform does not support BIU perf profiling.");
        return PROFILING_FAILED;
    }
    if (groupNum_ > platformGroupNum) {
        groupNum_ = platformGroupNum;
    }
    uint32_t groupVectorNum = GenGroupVector(aiCoreNum);
    if (groupVectorNum != groupNum_) {
        MSPROF_LOGE("[ProfBiuPerfJob]Create group vector number %u is different from %u.", groupVectorNum, groupNum_);
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

uint32_t ProfBiuPerfJob::GenGroupVector(int64_t aiCoreNum)
{
    FUNRET_CHECK_EXPR_ACTION(
        aiCoreNum < 0 || aiCoreNum > std::numeric_limits<uint32_t>::max(), return 0,
        "Aicore number %" PRId64 " is abnormal.", aiCoreNum);
    uint32_t lowerCore = aiCoreNum;
    if (groupNum_ > BIU_PERF_LOWER_GROUP_NUM && aiCoreNum > DAVID_DIE0_AICORE_NUM) {
        lowerCore = static_cast<uint32_t>(aiCoreNum) >> 1;
    }
    // die 0
    groupVector_.push_back(0);
    groupVector_.push_back(lowerCore >> 1);
    groupVector_.push_back(lowerCore - 1);
    if (groupNum_ > BIU_PERF_LOWER_GROUP_NUM && aiCoreNum > DAVID_DIE0_AICORE_NUM) {
        // die 1
        groupVector_.push_back(lowerCore);
        groupVector_.push_back(aiCoreNum - (lowerCore >> 1));
        groupVector_.push_back(aiCoreNum - 1);
    }
    return groupVector_.size();
}

std::vector<BiuPerfChannelInfo> ProfBiuPerfJob::GetBiuChannelInfos() const
{
    if (biuPcSamplingMode_ == 0) {
        auto platformChannelInfos = Platform::instance()->GetBiuPerfChannelInfos(groupVector_, groupNum_);
        if (!platformChannelInfos.empty()) {
            return platformChannelInfos;
        }
    }

    std::vector<BiuPerfChannelInfo> channelInfos;
    for (uint32_t groupId = 0; groupId < groupNum_; groupId++) {
        for (uint32_t groupType = 0; groupType < INSTR_PROFILING_GROUP_CHANNEL_NUM; groupType++) {
            if (biuPcSamplingMode_ == 1 && groupType == 0) {
                continue;
            }
            channelInfos.push_back(
                {groupId, groupType, groupVector_[groupId],
                 static_cast<uint32_t>(groupChannelIdMap_[groupId][groupType])});
        }
    }
    return channelInfos;
}

int32_t ProfBiuPerfJob::Process()
{
    CHECK_JOB_CONTEXT_PARAM_RET(collectionJobCfg_, return PROFILING_FAILED);
    int32_t ret = PROFILING_SUCCESS;
    int32_t devId = collectionJobCfg_->comParams->devId;
    std::vector<std::string> coreName = {"aic", "aiv0", "aiv1"};

    for (const auto& channelInfo : GetBiuChannelInfos()) {
        auto channelId = static_cast<AI_DRV_CHANNEL>(channelInfo.channelId);
        if (!DrvChannelsMgr::instance()->ChannelIsValid(devId, channelId)) {
            MSPROF_LOGW("Channel is invalid, devId:%d, channelId:%d", devId, channelId);
            continue;
        }
        MSPROF_LOGI(
            "Begin to start biu perf job, devId:%d, channelId:%d, biu mode: %u", devId, channelId, biuPcSamplingMode_);
        std::string filePath = collectionJobCfg_->jobParams.dataPath + "." + profBiuPerfJobName_ + "group" +
                               std::to_string(channelInfo.groupId) + "_" + coreName[channelInfo.groupType];
        AddReader(std::to_string(collectionJobCfg_->comParams->devId), devId, channelId, filePath);
        if (IsDrvApiVersionSupport(BIU_REPORT_DATA_LOSS_API_VERSION)) {
            BiuProfileConfigTV2 config;
            config.period = DEFAULT_BIU_PERF_CYCLE;
            config.biuPcSamplingMode = biuPcSamplingMode_;
            config.groupType = channelInfo.groupType;
            config.groupNo = channelInfo.groupNo;
            config.reportDataLoss = true;
            ret = DrvInstrProfileStart(devId, channelId, static_cast<void*>(&config), sizeof(config));
        } else {
            BiuProfileConfigT config;
            config.period = DEFAULT_BIU_PERF_CYCLE;
            config.biuPcSamplingMode = biuPcSamplingMode_;
            config.groupType = channelInfo.groupType;
            config.groupNo = channelInfo.groupNo;
            ret = DrvInstrProfileStart(devId, channelId, static_cast<void*>(&config), sizeof(config));
        }
        if (ret != PROFILING_SUCCESS) {
            RemoveReader(std::to_string(collectionJobCfg_->comParams->devId), devId, channelId);
            MSPROF_LOGE("[ProfBiuPerfJob]DrvInstrProfileStart failed. devId:%d, channelId:%d", devId, channelId);
            continue;
        }
        MSPROF_LOGI("Start biu perf job end, devId:%d, channelId:%d", devId, channelId);
    }
    return ret;
}

int32_t ProfBiuPerfJob::Uninit()
{
    CHECK_JOB_CONTEXT_PARAM_RET(collectionJobCfg_, return PROFILING_FAILED);
    int32_t ret = PROFILING_SUCCESS;
    int32_t devId = collectionJobCfg_->comParams->devId;

    for (const auto& channelInfo : GetBiuChannelInfos()) {
        auto channelId = static_cast<AI_DRV_CHANNEL>(channelInfo.channelId);
        if (!DrvChannelsMgr::instance()->ChannelIsValid(devId, channelId)) {
            MSPROF_LOGW("Channel is invalid, devId:%d, channelId:%d", devId, channelId);
            continue;
        }
        ret = DrvBiuPerfStop(devId, channelId);
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("[ProfBiuPerfJob]DrvBiuPerfStop failed, ret:%d, devId:%d, channelId:%d", ret, devId, channelId);
        }
        RemoveReader(std::to_string(collectionJobCfg_->comParams->devId), devId, channelId);
        MSPROF_LOGI("Stop biu perf job end, devId:%d, channelId:%d", devId, channelId);
    }
    return ret;
}

} // namespace JobWrapper
} // namespace Dvvp
} // namespace Analysis
