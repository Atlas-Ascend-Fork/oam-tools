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

#include <string>
#include <vector>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "error_code_tool.h"
#include "platform/platform_tool.h"
#include "collection_register_tool.h"
#include "prof_biu_perf_job_tool.h"
#include "prof_channel_manager_tool.h"
#include "prof_stars_job_tool.h"

using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Analysis::Dvvp::JobWrapper;

namespace {
class UtestCollectionJob : public ICollectionJob {
public:
    int Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override
    {
        (void)cfg;
        return PROFILING_SUCCESS;
    }

    int Process() override { return PROFILING_SUCCESS; }

    int Uninit() override { return PROFILING_SUCCESS; }
};

SHARED_PTR_ALIA<CollectionJobCfg> MakeJobCfg()
{
    auto cfg = std::make_shared<CollectionJobCfg>();
    auto comParams = std::make_shared<CollectionJobCommonParams>();
    comParams->params = std::make_shared<analysis::dvvp::message::ProfileParams>();
    comParams->jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();
    cfg->comParams = comParams;
    cfg->jobParams.events = std::make_shared<std::vector<std::string>>();
    cfg->jobParams.cores = std::make_shared<std::vector<int32_t>>();
    cfg->jobParams.aivEvents = std::make_shared<std::vector<std::string>>();
    cfg->jobParams.aivCores = std::make_shared<std::vector<int32_t>>();
    return cfg;
}
} // namespace

class JOB_WRAPPER_TOOL_UTEST : public testing::Test {
protected:
    void SetUp() override { jobCfg_ = MakeJobCfg(); }
    void TearDown() override { GlobalMockObject::verify(); }

    SHARED_PTR_ALIA<CollectionJobCfg> jobCfg_;
};

TEST_F(JOB_WRAPPER_TOOL_UTEST, CollectionRegisterLifecycle)
{
    CollectionRegisterMgr mgr;
    auto job = std::make_shared<UtestCollectionJob>();
    EXPECT_EQ(PROFILING_FAILED, mgr.CollectionJobRegisterAndRun(0, NR_MAX_COLLECTION_JOB, job));
    EXPECT_EQ(PROFILING_FAILED, mgr.CollectionJobRegisterAndRun(-1, DDR_DRV_COLLECTION_JOB, job));
    EXPECT_EQ(PROFILING_SUCCESS, mgr.CollectionJobRegisterAndRun(0, DDR_DRV_COLLECTION_JOB, job));
    EXPECT_EQ(PROFILING_FAILED, mgr.CollectionJobRegisterAndRun(0, DDR_DRV_COLLECTION_JOB, job));
    EXPECT_EQ(PROFILING_SUCCESS, mgr.CollectionJobUnregisterAndStop(0, DDR_DRV_COLLECTION_JOB));
    EXPECT_EQ(PROFILING_FAILED, mgr.CollectionJobUnregisterAndStop(0, DDR_DRV_COLLECTION_JOB));
    EXPECT_EQ(PROFILING_FAILED, mgr.CollectionJobRun(0, AICPU_COLLECTION_JOB));
}

TEST_F(JOB_WRAPPER_TOOL_UTEST, ProfChannelManagerLifecycle)
{
    auto manager = ProfChannelManager::instance();
    MOCKER(mmCreateTaskWithThreadAttr).stubs().will(returnValue(EN_OK));
    MOCKER(mmJoinTask).stubs().will(returnValue(EN_OK));
    ASSERT_EQ(PROFILING_SUCCESS, manager->Init());
    EXPECT_NE(nullptr, manager->GetChannelPoller());
    manager->FlushChannel();
    manager->UnInit();
}

TEST_F(JOB_WRAPPER_TOOL_UTEST, ProfBiuPerfJobInitBranches)
{
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));

    auto job = std::make_shared<ProfBiuPerfJob>();
    EXPECT_EQ(PROFILING_FAILED, job->Init(nullptr));
    jobCfg_->comParams->params->hostProfiling = true;
    jobCfg_->comParams->params->instrProfiling = "on";
    EXPECT_EQ(PROFILING_FAILED, job->Init(jobCfg_));
    jobCfg_->comParams->params->hostProfiling = false;
    jobCfg_->comParams->params->instrProfiling = "off";
    jobCfg_->comParams->params->pcSampling = "off";
    EXPECT_EQ(PROFILING_FAILED, job->Init(jobCfg_));
}

TEST_F(JOB_WRAPPER_TOOL_UTEST, ProfStarsJobInitBranches)
{
    auto starsLogJob = std::make_shared<ProfStarsSocLogJob>();
    EXPECT_EQ(PROFILING_FAILED, starsLogJob->Init(nullptr));
    jobCfg_->comParams->params->hostProfiling = true;
    EXPECT_EQ(PROFILING_FAILED, starsLogJob->Init(jobCfg_));
    jobCfg_->comParams->params->hostProfiling = false;
    EXPECT_EQ(PROFILING_SUCCESS, starsLogJob->Init(jobCfg_));
    jobCfg_->comParams->params->profMode = "system";
    EXPECT_EQ(PROFILING_FAILED, starsLogJob->Init(jobCfg_));

    auto blockLogJob = std::make_shared<ProfStarsBlockLogJob>();
    jobCfg_->comParams->params->profMode.clear();
    EXPECT_EQ(PROFILING_SUCCESS, blockLogJob->Init(jobCfg_));
    EXPECT_EQ(PROFILING_SUCCESS, blockLogJob->Process());
    EXPECT_EQ(PROFILING_SUCCESS, blockLogJob->Uninit());
}
