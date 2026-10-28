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
#include "msprof_manager_tool.h"
#include "config/config.h"
#include "config_manager_tool.h"
#include "param_validation_tool.h"
#include "running_mode_tool.h"
#include "input_parser_tool.h"
#include "platform/platform_tool.h"
#include "msprofbin_test_helper.h"
#include "securec.h"
#include "utils/utils_tool.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;
using namespace Analysis::Dvvp::Msprof;
using namespace Analysis::Dvvp::Common::Platform;
using namespace analysis::dvvp::common::utils;

namespace {
constexpr uint16_t QOS_MODE_MPAM_LIST = 0;
constexpr uint16_t QOS_MODE_STREAM_NAME = 1;
constexpr uint16_t QOS_MODE_STREAM_MPAM = 2;
constexpr uint16_t DAVID_STREAM_NUM = 10;
constexpr uint16_t MILAN_STREAM_NUM = 2;
constexpr uint16_t MPAM_ID_BASE = 12;
constexpr size_t MILAN_QOS_EVENT_SIZE = 8;
constexpr char QOS_STREAM_NAME[] = "st_mpamid_i";

class FakeRunningMode : public Collector::Dvvp::Msprofbin::RunningMode {
public:
    explicit FakeRunningMode(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params)
        : RunningMode("app", "app", params)
    {}
    ~FakeRunningMode() override = default;

    int32_t ModeParamsCheck() override { return PopModeResult(); }

    int32_t RunModeTasks() override { return PopRunResult(); }

    std::vector<int32_t> modeResults_;
    std::vector<int32_t> runResults_;
    int32_t lastModeResult_{PROFILING_FAILED};
    int32_t lastRunResult_{PROFILING_FAILED};

private:
    int32_t PopModeResult()
    {
        this->lastModeResult_ = Analysis::Dvvp::MsprofbinTest::PopResult(this->modeResults_);
        return this->lastModeResult_;
    }

    int32_t PopRunResult()
    {
        this->lastRunResult_ = Analysis::Dvvp::MsprofbinTest::PopResult(this->runResults_);
        return this->lastRunResult_;
    }
};

class MSPROF_MANAGER_UTEST : public testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override { GlobalMockObject::verify(); }
};

TEST_F(MSPROF_MANAGER_UTEST, Init)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);

    auto msprofManager = MsprofManager::instance();
    msprofManager->UnInit();
    EXPECT_EQ(PROFILING_FAILED, MsprofManager::instance()->Init(nullptr));
    EXPECT_EQ(PROFILING_FAILED, MsprofManager::instance()->Init(params));

    auto rMode = std::make_shared<FakeRunningMode>(params);
    msprofManager->params_ = params;
    msprofManager->rMode_ = nullptr;
    EXPECT_EQ(PROFILING_FAILED, msprofManager->ParamsCheck());
    msprofManager->rMode_ = rMode;
    rMode->modeResults_ = {PROFILING_FAILED};
    EXPECT_EQ(PROFILING_FAILED, msprofManager->ParamsCheck());
    rMode->modeResults_ = {PROFILING_SUCCESS};
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->ParamsCheck());
    msprofManager->UnInit();
}

TEST_F(MSPROF_MANAGER_UTEST, NotifyStop)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    std::shared_ptr<Collector::Dvvp::Msprofbin::AppMode> rMode(new Collector::Dvvp::Msprofbin::AppMode("app", params));
    auto msprofManager = MsprofManager::instance();

    msprofManager->rMode_ = nullptr;
    msprofManager->NotifyStop();
    EXPECT_TRUE(msprofManager->rMode_ == nullptr);
    msprofManager->rMode_ = rMode;
    msprofManager->NotifyStop();
    EXPECT_TRUE(msprofManager->rMode_->isQuit_);
}

TEST_F(MSPROF_MANAGER_UTEST, AppOnlyOptionsAreInAppModeWhitelist)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode appMode("app", params);
    Collector::Dvvp::Msprofbin::SystemMode systemMode("system", params);

    EXPECT_TRUE(appMode.whiteSet_.find(ARGS_NTS_METRICS) != appMode.whiteSet_.end());
    EXPECT_TRUE(systemMode.whiteSet_.find(ARGS_NTS_METRICS) == systemMode.whiteSet_.end());
    EXPECT_TRUE(appMode.whiteSet_.find(ARGS_AICORE_SHAPE) != appMode.whiteSet_.end());
    EXPECT_TRUE(systemMode.whiteSet_.find(ARGS_AICORE_SHAPE) == systemMode.whiteSet_.end());
}

TEST_F(MSPROF_MANAGER_UTEST, MsProcessCmd)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    auto rMode = std::make_shared<FakeRunningMode>(params);
    auto msprofManager = MsprofManager::instance();
    msprofManager->UnInit();
    EXPECT_EQ(PROFILING_FAILED, msprofManager->MsProcessCmd());
    msprofManager->params_ = params;
    msprofManager->rMode_ = rMode;
    rMode->runResults_ = {PROFILING_SUCCESS};

    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->MsProcessCmd());
}

TEST_F(MSPROF_MANAGER_UTEST, GenerateRunningMode)
{
    auto msprofManager = MsprofManager::instance();
    msprofManager->UnInit();
    EXPECT_EQ(PROFILING_FAILED, msprofManager->GenerateRunningMode());
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Platform::instance()->runSide_ = SysPlatformType::HOST;
    params->app = "main";
    msprofManager->params_ = params;
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->GenerateRunningMode());
    params->app = "";
    params->devices = "0";
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->GenerateRunningMode());
    params->devices = "";
    params->host_sys = "on";
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->GenerateRunningMode());
    params->host_sys = "";
    params->parseSwitch = "on";
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->GenerateRunningMode());
    params->parseSwitch = "";
    params->querySwitch = "on";
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->GenerateRunningMode());
    params->querySwitch = "";
    params->exportSwitch = "on";
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->GenerateRunningMode());
    params->exportSwitch = "";
    params->analyzeSwitch = "on";
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->GenerateRunningMode());
    params->analyzeSwitch = "";
    EXPECT_EQ(PROFILING_FAILED, msprofManager->GenerateRunningMode());
    Platform::instance()->runSide_ = SysPlatformType::INVALID;
}

TEST_F(MSPROF_MANAGER_UTEST, GenerateRunningMod_helper)
{
    auto msprofManager = MsprofManager::instance();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);

    msprofManager->UnInit();
    params->devices = "0";
    EXPECT_EQ(PROFILING_FAILED, msprofManager->GenerateRunningMode());
    params->host_sys = "on";
    EXPECT_EQ(PROFILING_FAILED, msprofManager->GenerateRunningMode());
}

TEST_F(MSPROF_MANAGER_UTEST, SystemModeDataWillBeCollected)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);

    EXPECT_EQ(false, rMode.DataWillBeCollected());

    params->usedParams = {ARGS_OUTPUT, ARGS_SYS_PERIOD, ARGS_SYS_DEVICES};
    EXPECT_EQ(false, rMode.DataWillBeCollected());

    params->usedParams = {ARGS_SYS_PERIOD, ARGS_SYS_DEVICES};
    EXPECT_EQ(false, rMode.DataWillBeCollected());

    params->usedParams = {ARGS_SYS_PERIOD, ARGS_SYS_DEVICES, ARGS_SYS_PROFILING};
    EXPECT_EQ(true, rMode.DataWillBeCollected());

    params->usedParams = {ARGS_OUTPUT, ARGS_SYS_PERIOD, ARGS_SYS_DEVICES, ARGS_SYS_PROFILING};
    EXPECT_EQ(true, rMode.DataWillBeCollected());

    params->usedParams = {ARGS_OUTPUT, ARGS_SYS_PERIOD, ARGS_SYS_DEVICES, ARGS_HOST_SYS_USAGE};
    EXPECT_EQ(true, rMode.DataWillBeCollected());
}

TEST_F(MSPROF_MANAGER_UTEST, ParamsCheck)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    auto rMode = std::make_shared<FakeRunningMode>(params);
    auto msprofManager = MsprofManager::instance();
    msprofManager->UnInit();
    EXPECT_EQ(PROFILING_FAILED, msprofManager->ParamsCheck());
    msprofManager->params_ = params;
    EXPECT_EQ(PROFILING_FAILED, msprofManager->ParamsCheck());
    msprofManager->rMode_ = rMode;
    rMode->modeResults_ = {PROFILING_FAILED, PROFILING_SUCCESS};
    EXPECT_EQ(PROFILING_FAILED, msprofManager->ParamsCheck());
    EXPECT_EQ(PROFILING_SUCCESS, msprofManager->ParamsCheck());
}

drvError_t g_error = static_cast<drvError_t>(0);

drvError_t HalGetDeviceInfoByBuffStub(uint32_t devId, int32_t moduleType, int32_t infoType, void* value, int32_t* len)
{
    (void)devId;
    (void)infoType;
    (void)len;
    if (moduleType == MODULE_TYPE_QOS) {
        auto* info = static_cast<QosProfileInfo*>(value);
        if (info->mode == QOS_MODE_MPAM_LIST) {
            info->streamNum = DAVID_STREAM_NUM;
            for (uint16_t index = 0; index < DAVID_STREAM_NUM; ++index) {
                info->mpamId[index] = MPAM_ID_BASE + index;
            }
        } else if (info->mode == QOS_MODE_STREAM_NAME) {
            (void)strcpy_s(info->streamName, sizeof(info->streamName), QOS_STREAM_NAME);
        } else if (info->mode == QOS_MODE_STREAM_MPAM) {
            info->streamNum = MILAN_STREAM_NUM;
            for (uint16_t index = 0; index < MILAN_STREAM_NUM; ++index) {
                info->mpamId[index] = MPAM_ID_BASE + index;
            }
        }
    }
    return g_error;
}

TEST_F(MSPROF_MANAGER_UTEST, PlatformDavidGetQosProfileInfo)
{
    GlobalMockObject::verify();
    // david
    Analysis::Dvvp::Common::Config::ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::CLOUD_TYPE));
    Platform::instance()->Uninit();
    Platform::instance()->Init();
    Platform::instance()->ascendHalAdaptor_.halGetDeviceInfoByBuff_ =
        reinterpret_cast<HalGetDeviceInfoByBuffFunc>(HalGetDeviceInfoByBuffStub);
    std::string info;
    std::vector<uint8_t> events;
    Platform::instance()->GetQosProfileInfo(0, info, events);
    std::string info2 = "aaa,bbb";
    Platform::instance()->GetQosProfileInfo(0, info2, events);
    Platform::instance()->ascendHalAdaptor_.halGetDeviceInfoByBuff_ = nullptr;
    Platform::instance()->Uninit();
}

TEST_F(MSPROF_MANAGER_UTEST, PlatformMilanGetQosProfileInfo)
{
    GlobalMockObject::verify();
    // milan
    Analysis::Dvvp::Common::Config::ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::CHIP_V4_1_0));
    Platform::instance()->Uninit();
    Platform::instance()->Init();
    Platform::instance()->ascendHalAdaptor_.halGetDeviceInfoByBuff_ =
        reinterpret_cast<HalGetDeviceInfoByBuffFunc>(HalGetDeviceInfoByBuffStub);
    std::string info;
    std::vector<uint8_t> events;
    Platform::instance()->GetQosProfileInfo(0, info, events);
    EXPECT_EQ(MILAN_QOS_EVENT_SIZE, events.size());
    Platform::instance()->ascendHalAdaptor_.halGetDeviceInfoByBuff_ = nullptr;
    Platform::instance()->Uninit();
}
} // namespace
