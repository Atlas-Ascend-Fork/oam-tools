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
#include <iostream>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "errno/error_code_tool.h"
#include "msprof_params_adapter_tool.h"
#include "config/config.h"
#include "config_manager_tool.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;
using namespace Analysis::Dvvp::Msprof;

namespace {
class PROF_PARAM_ADAPTER_UTEST : public testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override {}
};

TEST_F(PROF_PARAM_ADAPTER_UTEST, GenerateLlcEvents)
{
    GlobalMockObject::verify();
    std::shared_ptr<Analysis::Dvvp::Msprof::MsprofParamsAdapter> paramsAdapter(
        new Analysis::Dvvp::Msprof::MsprofParamsAdapter);
    std::shared_ptr<analysis::dvvp::message::ProfileParams> srcParams(new analysis::dvvp::message::ProfileParams);

    Analysis::Dvvp::Common::Config::ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::MINI_TYPE));
    srcParams->llc_profiling = "";
    srcParams->hardware_mem = "on";
    paramsAdapter->GenerateLlcEvents(nullptr);
    // empty events
    paramsAdapter->GenerateLlcEvents(srcParams);
    srcParams->llc_profiling = "capacity";
    paramsAdapter->GenerateLlcEvents(srcParams);
    srcParams->llc_profiling = "bandwidth";
    paramsAdapter->GenerateLlcEvents(srcParams);
    srcParams->llc_profiling = "read";
    paramsAdapter->GenerateLlcEvents(srcParams);
    srcParams->llc_profiling = "write";
    paramsAdapter->GenerateLlcEvents(srcParams);
    GlobalMockObject::verify();
    Analysis::Dvvp::Common::Config::ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::CLOUD_TYPE));
    paramsAdapter->GenerateLlcEvents(srcParams);
    EXPECT_EQ(srcParams->llc_profiling_events, "write");
}

TEST_F(PROF_PARAM_ADAPTER_UTEST, UpdateParams)
{
    GlobalMockObject::verify();
    std::shared_ptr<Analysis::Dvvp::Msprof::MsprofParamsAdapter> paramsAdapter(
        new Analysis::Dvvp::Msprof::MsprofParamsAdapter);
    std::shared_ptr<analysis::dvvp::message::ProfileParams> srcParams(new analysis::dvvp::message::ProfileParams);

    srcParams->io_profiling = "on";
    srcParams->interconnection_profiling = "on";
    srcParams->hardware_mem = "on";
    srcParams->cpu_profiling = "on";
    EXPECT_EQ(PROFILING_FAILED, paramsAdapter->UpdateParams(nullptr));
    EXPECT_EQ(PROFILING_SUCCESS, paramsAdapter->UpdateParams(srcParams));
}

TEST_F(PROF_PARAM_ADAPTER_UTEST, UpdateParamsKeepsAiCoreEventsWhenNtsPmuEventsExist)
{
    std::shared_ptr<Analysis::Dvvp::Msprof::MsprofParamsAdapter> paramsAdapter(
        new Analysis::Dvvp::Msprof::MsprofParamsAdapter);
    std::shared_ptr<analysis::dvvp::message::ProfileParams> srcParams(new analysis::dvvp::message::ProfileParams);

    srcParams->ai_core_profiling_events = "0x1,0x2";
    srcParams->ntsMetrics = "Custom:0x301,0x312";
    srcParams->ntsPmuEvents = "0x301,0x312";

    EXPECT_EQ(PROFILING_SUCCESS, paramsAdapter->UpdateParams(srcParams));
    EXPECT_EQ("0x1,0x2", srcParams->ai_core_profiling_events);
    EXPECT_EQ("0x301,0x312", srcParams->ntsPmuEvents);
}
} // namespace
