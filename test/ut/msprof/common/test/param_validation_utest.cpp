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
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include <string>
#include <memory>
#include "message/prof_params.h"
#include "param_validation_tool.h"
#include "platform/platform_tool.h"
#include "devdrv_runtime_api_stub.h"
#include "errno/error_code_tool.h"
#include "ai_drv_dev_api.h"
#include "config_manager_tool.h"
#include "platform_interface.h"
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Analysis::Dvvp::Common::Config;
using namespace analysis::dvvp::common::validation;
using namespace Dvvp::Collect::Platform;

namespace {
constexpr uint16_t MODENA_MAX_MONITOR_NUM = 8;
}

class COMMON_VALIDATION_PARAM_VALIDATION_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() { GlobalMockObject::verify(); }
};

static int _drv_get_dev_ids(int num_devices, std::vector<int>& dev_ids)
{
    static int phase = 0;
    if (phase == 0) {
        phase++;
        return -1;
    }

    if (phase >= 1) {
        dev_ids.push_back(0);
        return 0;
    }
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckProfilingParams)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    params->devices = "all";
    // jobStartReq == nullptr
    EXPECT_EQ(false, entry->CheckProfilingParams(nullptr));
    // job_id is empty
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
    params->host_sys = "cpu";
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
    // job_id is illegal
    params->job_id = "0aA-$";
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
    params->job_id = "0aA-";
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
    // profiling_mode is empty
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
    params->profiling_mode = "def_mode";
    params->devices = "0,1";
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
    params->devices = "0,1,a";
    EXPECT_EQ(false, entry->CheckProfilingParams(params));
    params->devices = "0,88";
    EXPECT_EQ(false, entry->CheckProfilingParams(params));
    params->devices = "7";
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
    params->devices = "0,1";
    params->l2CacheTaskProfilingEvents = "0x5b,0x5b,0x5b,0x5b";
    params->llc_profiling_events = "asdff_$";
    EXPECT_EQ(false, entry->CheckProfilingParams(params));
    params->llc_profiling_events = "asdff_01";
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckProfilingIntervalIsValid)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(nullptr));
    params->cpu_sampling_interval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->cpu_sampling_interval = 10;
    params->sys_sampling_interval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->sys_sampling_interval = 10;
    params->aicore_sampling_interval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->aiv_sampling_interval = 0;
    params->aicore_sampling_interval = 10;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->aiv_sampling_interval = 10;
    params->hccsInterval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->hccsInterval = 10;
    params->pcieInterval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->pcieInterval = 10;
    params->roceInterval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->roceInterval = 10;
    params->llc_interval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->llc_interval = 10;
    params->ddr_interval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->ddr_interval = 10;
    params->hbmInterval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->hbmInterval = 10;
    params->hardware_mem_sampling_interval = 0;
    EXPECT_EQ(false, entry->CheckProfilingIntervalIsValid(params));
    params->hardware_mem_sampling_interval = 10;
    params->profiling_period = 0;
    EXPECT_EQ(true, entry->CheckProfilingIntervalIsValid(params));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckSystemTraceSwitchProfiling)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(nullptr));
    params->cpu_profiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->cpu_profiling = "on";
    params->tsCpuProfiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->tsCpuProfiling = "on";
    params->aiCtrlCpuProfiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->aiCtrlCpuProfiling = "on";
    params->sys_profiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->sys_profiling = "on";
    params->pid_profiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->pid_profiling = "on";
    params->hardware_mem = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->hardware_mem = "on";
    params->io_profiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->io_profiling = "on";
    params->interconnection_profiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->interconnection_profiling = "on";
    params->dvpp_profiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->dvpp_profiling = "on";
    params->nicProfiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->nicProfiling = "on";
    params->roceProfiling = "asd";
    EXPECT_EQ(false, entry->CheckSystemTraceSwitchProfiling(params));
    params->roceProfiling = "on";
    EXPECT_EQ(true, entry->CheckSystemTraceSwitchProfiling(params));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckControlSwitchProfiling)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    params->taskTsfw = "asd";
    EXPECT_EQ(true, entry->CheckControlSwitchProfiling(params));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckTsSwitchProfiling)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    params->ts_task_track = "asd";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->ts_cpu_usage = "asd";
    params->ts_task_track = "on";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->ai_core_status = "asd";
    params->ts_cpu_usage = "on";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->ai_core_status = "on";
    params->ts_timeline = "asd";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->ts_timeline = "on";
    params->ts_fw_training = "asd";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->ts_fw_training = "on";
    params->hwts_log = "asd";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->hwts_log = "on";
    params->hwts_log1 = "asd";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->hwts_log1 = "on";
    params->ai_vector_status = "ada";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->ai_vector_status = "on";
    params->ts_memcpy = "asd";
    EXPECT_EQ(false, entry->CheckTsSwitchProfiling(params));
    params->ts_memcpy = "on";
    EXPECT_EQ(true, entry->CheckTsSwitchProfiling(params));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckPmuSwitchProfiling)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    params->ai_core_profiling = "asd";
    EXPECT_EQ(false, entry->CheckPmuSwitchProfiling(params));
    params->ai_core_profiling = "on";
    params->aiv_profiling = "asd";
    EXPECT_EQ(false, entry->CheckPmuSwitchProfiling(params));
    params->aiv_profiling = "on";
    params->llc_profiling = "on";
    params->ddr_profiling = "asd";
    EXPECT_EQ(false, entry->CheckPmuSwitchProfiling(params));
    params->ddr_profiling = "on";
    params->hccsProfiling = "asd";
    EXPECT_EQ(false, entry->CheckPmuSwitchProfiling(params));
    params->pcieProfiling = "asd";
    params->hccsProfiling = "on";
    EXPECT_EQ(false, entry->CheckPmuSwitchProfiling(params));
    params->hbmProfiling = "asd";
    params->pcieProfiling = "on";
    EXPECT_EQ(false, entry->CheckPmuSwitchProfiling(params));
    params->hbmProfiling = "on";
    EXPECT_EQ(true, entry->CheckPmuSwitchProfiling(params));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckAivEventCoresIsValid)
{
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    const std::vector<int> coreId = {0, 1, 2, 3, 4, 5, 6, 7, 8};
    EXPECT_EQ(true, entry->CheckAivEventCoresIsValid(coreId));
    const std::vector<int> coreId1 = {0, 1, 2, 3, -4};
    EXPECT_EQ(false, entry->CheckAivEventCoresIsValid(coreId1));
    const std::vector<int> coreId2 = {0, 1, 2, 3, 4};
    EXPECT_EQ(true, entry->CheckAivEventCoresIsValid(coreId2));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckTsCpuEventIsValid)
{
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    std::vector<std::string> events = {"read", "write", "read", "write", "read", "asd", "write", "read", "write"};
    EXPECT_EQ(false, entry->CheckTsCpuEventIsValid(events));
    std::vector<std::string> events1 = {"read", "write", "read", "write"};
    EXPECT_EQ(false, entry->CheckTsCpuEventIsValid(events1));
    std::vector<std::string> events2 = {"0xa"};
    EXPECT_EQ(true, entry->CheckTsCpuEventIsValid(events2));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckDdrEventsIsValid)
{
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    std::vector<std::string> events = {"read",  "write", "read",  "write", "read",
                                       "write", "read",  "write", "read",  "write"};
    EXPECT_EQ(false, entry->CheckDdrEventsIsValid(events));
    events = {"read", "write1"};
    EXPECT_EQ(false, entry->CheckDdrEventsIsValid(events));
    events = {"read", "write"};
    EXPECT_EQ(true, entry->CheckDdrEventsIsValid(events));
    events = {"master_id"};
    EXPECT_EQ(true, entry->CheckDdrEventsIsValid(events));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckHbmEventsIsValid)
{
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    std::vector<std::string> events = {"read",  "write", "read",  "write", "read",
                                       "write", "read",  "write", "read",  "write"};
    EXPECT_EQ(false, entry->CheckHbmEventsIsValid(events));
    events = {"read", "write1"};
    EXPECT_EQ(false, entry->CheckHbmEventsIsValid(events));
    events = {"read", "write"};
    EXPECT_EQ(true, entry->CheckHbmEventsIsValid(events));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, InvalidDdrEventCountLogIncludesCurrentValueAndRange)
{
    MOCKER_CPP(&Platform::GetMaxMonitorNumber).stubs().will(returnValue(MODENA_MAX_MONITOR_NUM));
    const std::vector<std::string> events(MODENA_MAX_MONITOR_NUM + 1, "read");

    testing::internal::CaptureStdout();
    EXPECT_FALSE(ParamValidation::instance()->CheckDdrEventsIsValid(events));
    const std::string log = testing::internal::GetCapturedStdout();

    EXPECT_NE(
        std::string::npos,
        log.find("Invalid DDR event count: 9, valid range: [0, " + std::to_string(MODENA_MAX_MONITOR_NUM) + "]."));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, InvalidHbmEventCountLogIncludesCurrentValueAndRange)
{
    MOCKER_CPP(&Platform::GetMaxMonitorNumber).stubs().will(returnValue(MODENA_MAX_MONITOR_NUM));
    const std::vector<std::string> events(MODENA_MAX_MONITOR_NUM + 1, "read");

    testing::internal::CaptureStdout();
    EXPECT_FALSE(ParamValidation::instance()->CheckHbmEventsIsValid(events));
    const std::string log = testing::internal::GetCapturedStdout();

    EXPECT_NE(
        std::string::npos,
        log.find("Invalid HBM event count: 9, valid range: [0, " + std::to_string(MODENA_MAX_MONITOR_NUM) + "]."));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, InvalidIntervalLogIncludesCurrentValueRangeAndUnit)
{
    testing::internal::CaptureStdout();
    EXPECT_FALSE(ParamValidation::instance()->IsValidInterval(0, "ddr"));
    EXPECT_TRUE(ParamValidation::instance()->IsValidInterval(1, "ddr"));
    EXPECT_TRUE(ParamValidation::instance()->IsValidInterval(1296000000, "ddr"));
    EXPECT_FALSE(ParamValidation::instance()->IsValidInterval(1296000001, "ddr"));
    const std::string log = testing::internal::GetCapturedStdout();

    EXPECT_NE(
        std::string::npos, log.find(
                               "Invalid ddr interval: 0 milliseconds, valid range: [1, " +
                               std::to_string(15 * 24 * 3600 * 1000) + "] milliseconds."));
    EXPECT_NE(
        std::string::npos, log.find(
                               "Invalid ddr interval: 1296000001 milliseconds, valid range: [1, " +
                               std::to_string(15 * 24 * 3600 * 1000) + "] milliseconds."));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, InvalidProfilingParamsIntervalLogIncludesConfigValueAndRange)
{
    auto params = std::make_shared<analysis::dvvp::message::ProfileParams>();
    params->devices = "all";
    params->aiv_sampling_interval = 10;
    params->hccsInterval = 10;
    params->pcieInterval = 10;
    params->roceInterval = 10;
    params->llc_interval = 10;
    params->hbmInterval = 10;
    params->cpu_sampling_interval = 10;
    params->sys_sampling_interval = 10;
    params->pid_sampling_interval = 10;
    params->hardware_mem_sampling_interval = 10;
    params->io_sampling_interval = 10;
    params->interconnection_sampling_interval = 10;
    params->dvpp_sampling_interval = 10;
    params->nicInterval = 10;
    params->aicore_sampling_interval = 10;
    params->ddr_interval = 0;

    testing::internal::CaptureStdout();
    EXPECT_FALSE(ParamValidation::instance()->CheckProfilingParams(params));
    const std::string log = testing::internal::GetCapturedStdout();

    EXPECT_NE(
        std::string::npos, log.find(
                               "[CheckProfilingParams] Invalid ddr interval: 0 milliseconds, valid range: [1, " +
                               std::to_string(15 * 24 * 3600 * 1000) + "] milliseconds."));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, InvalidProfilingParamsTwoIntervalLog)
{
    auto params = std::make_shared<analysis::dvvp::message::ProfileParams>();
    params->devices = "all";
    params->sys_sampling_interval = 0;
    testing::internal::CaptureStdout();
    EXPECT_FALSE(ParamValidation::instance()->CheckProfilingParams(params));
    const std::string log = testing::internal::GetCapturedStdout();
    EXPECT_NE(std::string::npos, log.find("Invalid sys_profiling interval: 0 milliseconds"));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckAivEventsIsValid)
{
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    const std::vector<std::string> aiv;
    EXPECT_EQ(true, entry->CheckAivEventsIsValid(aiv));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckAppNameIsValid)
{
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(false, entry->CheckAppNameIsValid(""));

    const std::string appName = "asd0";
    EXPECT_EQ(true, entry->CheckAppNameIsValid(appName));

    const std::string invalidAppName = "$SD";
    EXPECT_EQ(false, entry->CheckAppNameIsValid(invalidAppName));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckProfilingParams1)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams());
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    // profiling_mode is illegal
    std::string sampleConfig =
        "{\"result_dir\":\"/tmp/\", \"job_id\":\"aaaZZZZ000-\", \"profiling_mode\":\"system-wide\", \"devices\":\"1\"}";
    params->FromString(sampleConfig);
    EXPECT_EQ(true, entry->CheckProfilingParams(params));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, Init)
{
    GlobalMockObject::verify();
    EXPECT_EQ(0, analysis::dvvp::common::validation::ParamValidation::instance()->Init());
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, UnInit)
{
    GlobalMockObject::verify();
    EXPECT_EQ(0, analysis::dvvp::common::validation::ParamValidation::instance()->Uninit());
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckLlcEventsIsValid)
{
    GlobalMockObject::verify();

    std::string llcEvents;
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(true, entry->CheckLlcEventsIsValid(llcEvents));
    llcEvents = "/$$}";
    EXPECT_EQ(false, entry->CheckLlcEventsIsValid(llcEvents));
    llcEvents = "read";
    EXPECT_EQ(true, entry->CheckLlcEventsIsValid(llcEvents));
    llcEvents = "/llc/0/abc";
    EXPECT_EQ(true, entry->CheckLlcEventsIsValid(llcEvents));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckEventsSize)
{
    GlobalMockObject::verify();
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(PROFILING_SUCCESS, entry->CheckEventsSize(""));
    EXPECT_EQ(PROFILING_FAILED, entry->CheckEventsSize("0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9"));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckAicoreMetricsIsValid)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::MINI_TYPE));
    Platform::instance()->Init();
    MOCKER_CPP(&Platform::PmuToFeature)
        .stubs()
        .with(eq(std::string("PipeUtilization")))
        .will(returnValue(PLATFORM_TASK_PU_PMU));
    MOCKER_CPP(&Platform::PmuToFeature).stubs().with(any()).will(returnValue(PLATFORM_FEATURE_INVALID));
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .with(eq(static_cast<PlatformFeature>(PLATFORM_FEATURE_INVALID)))
        .will(returnValue(false));
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .with(any())
        .will(returnValue(true));
    std::string aicoreMetrics;
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(true, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "/$$}";
    EXPECT_EQ(false, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "PipeUtilization";
    EXPECT_EQ(true, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "aicoreMetricsAll";
    EXPECT_EQ(false, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "trace";
    EXPECT_EQ(false, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "Custom:0x0x0x0x00x0x0x0x00x0x0x0x00x0x0x0x00x0x0x0x00x0x0x0x00x0x0x0x0";
    EXPECT_EQ(false, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "Custom:0x500,0x502,0x504,0x506,0x508,0x50a,0xc,0xd";
    EXPECT_EQ(true, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "Custom:0x500,,0x504,0x506,0x508,0x50a,0xc,0xd";
    EXPECT_EQ(false, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
    aicoreMetrics = "PipelineExecuteUtilization";
    EXPECT_EQ(false, entry->CheckAicoreMetricsIsValid(aicoreMetrics));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckL2CacheEventsValid)
{
    using namespace analysis::dvvp::common::validation;
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_CLOUD_V3));
    Platform::instance()->Uninit();
    Platform::instance()->Init();
    std::vector<std::string> events = {"0x00", "0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07", "0x08"};
    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(false, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    events = {"0x90", "0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07"};
    EXPECT_EQ(true, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    events = {" 0x00", "0x01 ", " 0x02 ", "  0x03 ", " 0x04   ", "0x05    ", "     0x06"};
    EXPECT_EQ(true, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    events = {"0x 00", "0x01", "0x02", "0x03", "0x04", "0x05", "0x06"};
    EXPECT_EQ(false, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    events = {"0x78", "0x79", "0x77", "0x71", "0x6a", "0x6c", "0x74", "0x62"};
    EXPECT_EQ(true, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    events = {"0x78", "0x79", "0x77", "0x71", "0x6a", "0x6c", "0x74", "0x100"};
    EXPECT_EQ(false, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    events = {"0x78", "0x79", "0x77", "0x71", "0x6a", "0x6c", "0x74", "0xFF"};
    EXPECT_EQ(true, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    events = {"0x78", "0x79", "0x77", "0x71", "0x6a", "0x6c", "0x74", "0x809"};
    EXPECT_EQ(false, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_SMMU, events));
    events = {"0x78", "0x79", "0x77", "0x71", "0x6a", "0x6c", "0x74", "0x808"};
    EXPECT_EQ(true, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_SMMU, events));
    events = {"0x01", "0x02", "0x03", "0x3f"};
    EXPECT_EQ(true, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_NOC, events));
    events = {"0x01", "0x02", "0x03", "0x40"};
    EXPECT_EQ(false, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_NOC, events));
    Platform::instance()->Uninit();
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    Platform::instance()->Init();
    // noc not support on CHIP_V4_1_0
    events = {"0x01", "0x02", "0x03", "0x3f"};
    EXPECT_EQ(false, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_NOC, events));
    Platform::instance()->Uninit();
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::MINI_TYPE));
    Platform::instance()->Init();
    events = {"0x78", "0x79", "0x77", "0x71", "0x6a", "0x6c", "0x74", "0x255"};
    EXPECT_EQ(false, entry->CheckSocPmuEventsValid(ProfSocPmuType::PMU_TYPE_HA, events));
    Platform::instance()->Uninit();
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, L2CacheAdaptorSmmuDfx)
{
    GlobalMockObject::verify();
    // David (CHIP_CLOUD_V3) supports SMMU DFX: npuEvents gets the ";SMMU_DFX:" segment appended.
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_CLOUD_V3));
    Platform::instance()->Uninit();
    Platform::instance()->Init();
    EXPECT_EQ(0x0E78u, Platform::instance()->GetSmmuDFXOffset());
    EXPECT_EQ(0x3FFFFFFFu, Platform::instance()->GetSmmuDFXRegMask());
    std::string l2Switch = "on";
    std::string l2Events;
    std::string npuEvents;
    Platform::instance()->L2CacheAdaptor(npuEvents, l2Switch, l2Events);
    EXPECT_NE(std::string::npos, npuEvents.find(";SMMU_DFX:"));
    Platform::instance()->Uninit();

    // RC v2 platform does not override SMMU DFX: offset/mask are 0, no ";SMMU_DFX:" appended.
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(static_cast<PlatformType>(17)));
    Platform::instance()->Init();
    EXPECT_EQ(0u, Platform::instance()->GetSmmuDFXOffset());
    EXPECT_EQ(0u, Platform::instance()->GetSmmuDFXRegMask());
    l2Switch = "on";
    l2Events.clear();
    npuEvents.clear();
    Platform::instance()->L2CacheAdaptor(npuEvents, l2Switch, l2Events);
    EXPECT_EQ(std::string::npos, npuEvents.find(";SMMU_DFX:"));
    Platform::instance()->Uninit();
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, SmmuDFXOffsetAndRegMask)
{
    GlobalMockObject::verify();
    // CloudV2 (CHIP_V4_1_0 maps to PlatformTypeEnum::CHIP_CLOUD_V2)
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    Platform::instance()->Uninit();
    Platform::instance()->Init();
    EXPECT_EQ(0x0E78u, Platform::instance()->GetSmmuDFXOffset());
    EXPECT_EQ(0x3FFFFFFFu, Platform::instance()->GetSmmuDFXRegMask());
    // After Uninit, platform_ is nullptr — getters return 0.
    Platform::instance()->Uninit();
    EXPECT_EQ(0u, Platform::instance()->GetSmmuDFXOffset());
    EXPECT_EQ(0u, Platform::instance()->GetSmmuDFXRegMask());
    GlobalMockObject::verify();

    // Mini platform does not override SMMU DFX — PlatformInterface default returns 0.
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::MINI_TYPE));
    Platform::instance()->Init();
    EXPECT_EQ(0u, Platform::instance()->GetSmmuDFXOffset());
    EXPECT_EQ(0u, Platform::instance()->GetSmmuDFXRegMask());
    Platform::instance()->Uninit();
    GlobalMockObject::verify();
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, IsValidSleepPeriod)
{
    GlobalMockObject::verify();

    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(0, entry->IsValidSleepPeriod(-1));
    EXPECT_EQ(1, entry->IsValidSleepPeriod(1));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckHostSysOptionsIsValid)
{
    GlobalMockObject::verify();

    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    std::string hostSysOptions;
    EXPECT_EQ(false, entry->CheckHostSysOptionsIsValid(hostSysOptions));
    hostSysOptions = "COMMON_VALIDATION_PARAM_VALIDATION_TEST/CheckHostSysOptionsIsValid";
    EXPECT_EQ(false, entry->CheckHostSysOptionsIsValid(hostSysOptions));
    hostSysOptions = "cpu";
    EXPECT_EQ(true, entry->CheckHostSysOptionsIsValid(hostSysOptions));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckHostSysPidIsValid)
{
    GlobalMockObject::verify();

    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    int hostSysPid = -1;
    EXPECT_EQ(0, entry->CheckHostSysPidIsValid(hostSysPid));
    hostSysPid = 100000000;
    EXPECT_EQ(0, entry->CheckHostSysPidIsValid(hostSysPid));
    hostSysPid = 1;
    EXPECT_EQ(1, entry->CheckHostSysPidIsValid(hostSysPid));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckHostSysUsageOptionsIsValid)
{
    GlobalMockObject::verify();

    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(0, entry->CheckHostSysUsageOptionsIsValid(""));
    EXPECT_EQ(0, entry->CheckHostSysUsageOptionsIsValid("xxx"));
    EXPECT_EQ(1, entry->CheckHostSysUsageOptionsIsValid("cpu"));
    EXPECT_EQ(1, entry->CheckHostSysUsageOptionsIsValid("mem"));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, ProfStarsAcsqParamIsValid)
{
    GlobalMockObject::verify();

    auto entry = analysis::dvvp::common::validation::ParamValidation::instance();
    EXPECT_EQ(0, entry->ProfStarsAcsqParamIsValid("ddd"));
    EXPECT_EQ(1, entry->ProfStarsAcsqParamIsValid("dsa,vdec"));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckStorageLimit)
{
    using namespace analysis::dvvp::common::validation;
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);

    params->storageLimit = "MB";
    bool ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(false, ret);

    params->storageLimit = "10MB0";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(false, ret);

    params->storageLimit = "A12345MB";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(false, ret);

    params->storageLimit = "123456789100MB";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(false, ret);

    params->storageLimit = "100MB";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(false, ret);

    params->storageLimit = "8294967296MB";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(false, ret);

    params->storageLimit = "4294967295MB";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(true, ret);

    params->storageLimit = "1000MB";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(true, ret);

    params->storageLimit = "";
    ret = ParamValidation::instance()->CheckStorageLimit(params);
    EXPECT_EQ(true, ret);
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckInstrProfilingFreqValid)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    Platform::instance()->Init();
    using namespace analysis::dvvp::common::validation;
    // 平台不支持 INSTR_PROFILING 特性时，走频率范围校验
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(false));
    bool ret = ParamValidation::instance()->CheckInstrProfilingFreqValid(0);
    EXPECT_EQ(false, ret);
    ret = ParamValidation::instance()->CheckInstrProfilingFreqValid(1000);
    EXPECT_EQ(true, ret);
    ret = ParamValidation::instance()->CheckInstrProfilingFreqValid(1000000);
    EXPECT_EQ(false, ret);
    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    EXPECT_EQ(true, ParamValidation::instance()->CheckInstrProfilingFreqValid(1000));
    Platform::instance()->Uninit();
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckAiCoreEventCoresIsValid)
{
    using namespace analysis::dvvp::common::validation;
    std::vector<int> coreId(81);
    bool ret = ParamValidation::instance()->CheckAiCoreEventCoresIsValid(coreId);
    EXPECT_EQ(false, ret);
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckAiCoreEventsIsValidRcLiteV2)
{
    using namespace analysis::dvvp::common::validation;
    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::GetMaxMonitorNumber).stubs().will(returnValue(MAX_DAVID_MONITOR_NUM));
    MOCKER_CPP(&Platform::GetPlatformType).stubs().will(returnValue(static_cast<PlatformTypeEnum>(18)));
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));

    std::vector<std::string> events = {"0x0", "0x714", "0x715"};
    EXPECT_EQ(true, ParamValidation::instance()->CheckAiCoreEventsIsValid(events));

    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::GetMaxMonitorNumber).stubs().will(returnValue(MAX_COLLECT_MONITOR_NUM));
    MOCKER_CPP(&Platform::GetPlatformType).stubs().will(returnValue(static_cast<PlatformTypeEnum>(12)));
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(false));

    events = {"0x0"};
    EXPECT_EQ(false, ParamValidation::instance()->CheckAiCoreEventsIsValid(events));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckAiCoreEventsIsValidModena)
{
    using namespace analysis::dvvp::common::validation;
    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::GetMaxMonitorNumber).stubs().will(returnValue(MODENA_MAX_MONITOR_NUM));
    MOCKER_CPP(&Platform::GetPlatformType).stubs().will(returnValue(PlatformTypeEnum::CHIP_5162A));

    std::vector<std::string> events = {"0x0"};
    EXPECT_EQ(true, ParamValidation::instance()->CheckAiCoreEventsIsValid(events));

    events = {"0x1", "0x2", "0x3", "0x4", "0x5", "0x6", "0x7", "0x8"};
    EXPECT_EQ(true, ParamValidation::instance()->CheckAiCoreEventsIsValid(events));

    events = {"0x1", "0x2", "0x3", "0x4", "0x5", "0x6", "0x7", "0x8", "0x9"};
    EXPECT_EQ(false, ParamValidation::instance()->CheckAiCoreEventsIsValid(events));

    events = {"0x7fffffff"};
    EXPECT_EQ(true, ParamValidation::instance()->CheckAiCoreEventsIsValid(events));

    events = {"0x80000000"};
    EXPECT_EQ(false, ParamValidation::instance()->CheckAiCoreEventsIsValid(events));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckParamL0L1InvalidBasicResult)
{
    using namespace analysis::dvvp::common::validation;
    GlobalMockObject::verify();
    EXPECT_EQ(true, ParamValidation::instance()->CheckParamL0L1Invalid("ge_api", ""));

    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const std::string) const).stubs().will(returnValue(false));
    EXPECT_EQ(false, ParamValidation::instance()->CheckParamL0L1Invalid("ge_api", "l0"));

    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const std::string) const).stubs().will(returnValue(true));
    EXPECT_EQ(true, ParamValidation::instance()->CheckParamL0L1Invalid("ge_api", "l0"));
    EXPECT_EQ(false, ParamValidation::instance()->CheckParamL0L1Invalid("ge_api", "invalid"));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckParamEmptyInvalidBasicResult)
{
    using namespace analysis::dvvp::common::validation;
    GlobalMockObject::verify();
    EXPECT_EQ(true, ParamValidation::instance()->CheckParamEmptyInvalid("task_trace", ""));

    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const std::string) const).stubs().will(returnValue(false));
    EXPECT_EQ(false, ParamValidation::instance()->CheckParamEmptyInvalid("task_trace", "on"));

    GlobalMockObject::verify();
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const std::string) const).stubs().will(returnValue(true));
    EXPECT_EQ(true, ParamValidation::instance()->CheckParamEmptyInvalid("task_trace", "on"));
    EXPECT_EQ(true, ParamValidation::instance()->CheckParamEmptyInvalid("task_trace", "off"));
    EXPECT_EQ(false, ParamValidation::instance()->CheckParamEmptyInvalid("task_trace", "invalid"));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, GetPlatformTypeModena)
{
    auto configManager = ConfigManager::instance();
    configManager->configMap_["type"] = "21";
    EXPECT_EQ(PlatformType::CHIP_5162A, configManager->GetPlatformType());
    configManager->InitFrequency();
    EXPECT_EQ("20", configManager->GetFrequency());
    EXPECT_EQ("20", configManager->GetAicDefFrequency());
    EXPECT_EQ(false, configManager->IsDriverSupportLlc());
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, GetPlatformTypeDavidLite)
{
    auto configManager = ConfigManager::instance();
    configManager->configMap_["type"] = "19";
    EXPECT_EQ(PlatformType::CHIP_CLOUD_V3_LITE, configManager->GetPlatformType());
    configManager->InitFrequency();
    EXPECT_EQ("1000", configManager->GetFrequency());
    EXPECT_EQ("800", configManager->GetAicDefFrequency());
    EXPECT_EQ(true, configManager->IsDriverSupportLlc());
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckFreqIsValid)
{
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const std::string) const)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));
    std::string switchName("host_sys_usage_freq");
    uint32_t freq = 50;

    EXPECT_EQ(false, ParamValidation::instance()->CheckFreqIsValid(switchName, freq));
    EXPECT_EQ(true, ParamValidation::instance()->CheckFreqIsValid(switchName, freq));

    switchName = "sys_io_sampling_freq";
    EXPECT_EQ(true, ParamValidation::instance()->CheckFreqIsValid(switchName, freq));
    switchName = "dvpp_freq";
    EXPECT_EQ(true, ParamValidation::instance()->CheckFreqIsValid(switchName, freq));
    switchName = "host_sys_usage_freq";
    EXPECT_EQ(true, ParamValidation::instance()->CheckFreqIsValid(switchName, freq));
    freq = 120;
    EXPECT_EQ(false, ParamValidation::instance()->CheckFreqIsValid(switchName, freq));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckLlcConfigValid)
{
    MOCKER_CPP(&Platform::GetPlatformType)
        .stubs()
        .will(repeat(PlatformTypeEnum::CHIP_MINI, 3))
        .then(returnValue(PlatformTypeEnum::CHIP_CLOUD));
    std::string llc("xxx");
    EXPECT_EQ(false, ParamValidation::instance()->CheckLlcConfigValid(llc));
    llc = "capacity";
    EXPECT_EQ(false, ParamValidation::instance()->CheckLlcConfigValid(llc));
    llc = "bandwidth";
    EXPECT_EQ(false, ParamValidation::instance()->CheckLlcConfigValid(llc));
    llc = "read";
    EXPECT_EQ(true, ParamValidation::instance()->CheckLlcConfigValid(llc));
    llc = "write";
    EXPECT_EQ(true, ParamValidation::instance()->CheckLlcConfigValid(llc));
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, CheckOpTypeIsValid)
{
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));
    std::string opType;
    std::string errInfo;

    std::string opTypeInput = "MatMul,Index";
    EXPECT_EQ(false, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));

    opType.clear();
    EXPECT_EQ(true, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("Index,MatMul", opType);

    opType.clear();
    opTypeInput = "";
    EXPECT_EQ(false, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("Failed to check empty opType.", errInfo);

    opType.clear();
    opTypeInput = "MatMul,,Index";
    EXPECT_EQ(false, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("Failed to check empty opType item in input.", errInfo);

    opType.clear();
    std::string longOpType(257, 't');
    EXPECT_EQ(false, ParamValidation::instance()->CheckOpTypeIsValid(longOpType, opType, errInfo));
    EXPECT_EQ(
        "Failed to check overflow opType: " + longOpType.substr(0, 128) + "..., the max input size is 256.", errInfo);

    opType.clear();
    std::string criticalOpType(256, 't');
    EXPECT_EQ(true, ParamValidation::instance()->CheckOpTypeIsValid(criticalOpType, opType, errInfo));
    EXPECT_EQ(criticalOpType, opType);

    opType.clear();
    opTypeInput = "MatMul,Index,MatMul";
    EXPECT_EQ(true, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("Index,MatMul", opType);

    opType.clear();
    opTypeInput = "MatMul";
    EXPECT_EQ(true, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("MatMul", opType);

    opType.clear();
    opTypeInput = ",MatMul";
    EXPECT_EQ(false, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("Failed to check empty opType item in input.", errInfo);

    opType.clear();
    opTypeInput = "MatMul,";
    EXPECT_EQ(false, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("Failed to check empty opType item in input.", errInfo);

    opType.clear();
    opTypeInput = "MatMul,MatMul,MatMul";
    EXPECT_EQ(true, ParamValidation::instance()->CheckOpTypeIsValid(opTypeInput, opType, errInfo));
    EXPECT_EQ("MatMul", opType);

    GlobalMockObject::verify();
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, GetBiuPerfChannelInfos)
{
    GlobalMockObject::verify();
    std::vector<uint32_t> groupVector = {0, 4};

    // PlatformInterface default — covers platform_interface.cpp.
    PlatformInterface platformInterface;
    auto infos = platformInterface.GetBiuPerfChannelInfos(groupVector, 2);
    EXPECT_EQ(6u, infos.size()); // 2 groups * 3 channel types

    // platform_ is nullptr without Init — covers platform.cpp nullptr early return.
    Platform::instance()->Uninit();
    EXPECT_TRUE(Platform::instance()->GetBiuPerfChannelInfos(groupVector, 2).empty());
    GlobalMockObject::verify();
}

TEST_F(COMMON_VALIDATION_PARAM_VALIDATION_TEST, RcV2PlatformL2CacheEvents)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(static_cast<PlatformType>(17)));
    Platform::instance()->Uninit();
    Platform::instance()->Init();

    // 与扩展仓rc_v2平台实现的L2事件表保持一致
    EXPECT_EQ("0x00,0x75,0x76,0x77,0x66,0x67,0x68,0x69", Platform::instance()->GetL2CacheEvents());
    EXPECT_EQ(MAX_DAVID_MONITOR_NUM, Platform::instance()->GetMaxMonitorNumber());
    EXPECT_TRUE(Platform::instance()->CheckIfSupport(PLATFORM_TASK_L2_CACHE_REG));
    EXPECT_TRUE(Platform::instance()->CheckIfSupport(PLATFORM_TASK_L2_CACHE_PMU));

    Platform::instance()->Uninit();
}
