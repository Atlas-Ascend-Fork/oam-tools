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
#include <dlfcn.h>
#include <map>
#include <errno.h>
#include <iostream>
#include <stdexcept>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "errno/error_code_tool.h"
#include "ai_drv_dev_api.h"
#include "ai_drv_prof_api.h"
#include "config_manager_tool.h"
#include "validation/param_validation_tool.h"
#include "utils_tool.h"
#include "platform/platform_tool.h"
#include "../../stub/hdc-log-stub.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::driver;
using namespace Analysis::Dvvp::Common::Config;
using namespace analysis::dvvp::common::validation;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::Common::Platform;
#define CHANNEL_STR(s) #s

///////////////////////////////////////////////////////////////////
class DRIVER_AI_DRV_API_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() {}
};

namespace {
constexpr uint32_t ACC_PROFILE_DEFAULT_CORE_MASK = 0xFFFFU;
constexpr uint32_t ACC_PROFILE_FIXED_CORE_MASK = 0xFFFFFU;

void CheckAccProfileCoreMask(struct prof_start_para* startPara, uint32_t expectedCoreMask)
{
    EXPECT_NE(nullptr, startPara);
    EXPECT_NE(nullptr, startPara->user_data);
    const auto* config = static_cast<const StarsAccProfileConfigT*>(startPara->user_data);
    EXPECT_EQ(expectedCoreMask, config->aiEventCfg[FFTS_PROF_MODE_AIC].coreMask);
    EXPECT_EQ(expectedCoreMask, config->aiEventCfg[FFTS_PROF_MODE_AIV].coreMask);
}

int ProfDrvStartAccProfileCoreMaskStub(unsigned int deviceId, unsigned int channelId, struct prof_start_para* startPara)
{
    EXPECT_EQ(0U, deviceId);
    EXPECT_EQ(static_cast<unsigned int>(PROF_CHANNEL_FFTS_PROFILE_TASK), channelId);
    static uint32_t callCount = 0;
    const uint32_t expectedCoreMask = (callCount++ == 0) ? ACC_PROFILE_DEFAULT_CORE_MASK : ACC_PROFILE_FIXED_CORE_MASK;
    CheckAccProfileCoreMask(startPara, expectedCoreMask);
    return PROF_OK;
}

} // namespace

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetDeviceStatusTest)
{
    GlobalMockObject::verify();

    drvStatus_t deviceStatus = DRV_STATUS_COMMUNICATION_LOST;

    MOCKER(drvDeviceStatus)
        .stubs()
        .with(any(), outBoundP(&deviceStatus))
        .will(returnValue(DRV_ERROR_NOT_SUPPORT))
        .then(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE));

    EXPECT_EQ(true, analysis::dvvp::driver::DrvGetDeviceStatus(0));
    EXPECT_EQ(false, analysis::dvvp::driver::DrvGetDeviceStatus(0));
    EXPECT_EQ(false, analysis::dvvp::driver::DrvGetDeviceStatus(0));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetDevNum)
{
    GlobalMockObject::verify();

    uint32_t num_dev = 0;

    MOCKER(drvGetDevNum)
        .stubs()
        .with(outBoundP(&num_dev))
        .will(returnValue(DRV_ERROR_NOT_SUPPORT))
        .then(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetDevNum());
    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetDevNum());
    EXPECT_EQ((int)num_dev, analysis::dvvp::driver::DrvGetDevNum());
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetDevIds)
{
    GlobalMockObject::verify();

    std::vector<int> dev_ids;

    uint32_t num_dev = 0;

    MOCKER(drvGetDevIDs)
        .stubs()
        .with(outBoundP(&num_dev))
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetDevIds(0, dev_ids));
    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetDevIds(1, dev_ids));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetDevIds(1, dev_ids));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvPeripheralStart)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_NIC;
    int prof_sample_period = 10;
    std::string prof_data_file_path = "/path/to/data";

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));
    analysis::dvvp::driver::DrvPeripheralProfileCfg peripheralCfg;
    peripheralCfg.configP = nullptr;
    peripheralCfg.configSize = 0;
    peripheralCfg.profChannel = prof_channel;
    peripheralCfg.profDeviceId = prof_device_id;
    peripheralCfg.profSamplePeriod = prof_sample_period;
    peripheralCfg.profDataFilePath = prof_data_file_path;

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvPeripheralStart(peripheralCfg));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvPeripheralStart(peripheralCfg));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvTscpuStart)
{
    GlobalMockObject::verify();

    analysis::dvvp::driver::DrvPeripheralProfileCfg peripheralCfg;
    peripheralCfg.profDeviceId = 0;
    peripheralCfg.profChannel = analysis::dvvp::driver::PROF_CHANNEL_TS_CPU;
    peripheralCfg.profSamplePeriod = 10;
    peripheralCfg.profDataFilePath = "/path/to/data";

    std::vector<std::string> prof_events;
    prof_events.push_back("0x11");

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvTscpuStart(peripheralCfg, prof_events));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvTscpuStart(peripheralCfg, prof_events));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvAicoreStart)
{
    GlobalMockObject::verify();

    analysis::dvvp::driver::DrvPeripheralProfileCfg peripheralCfg;
    peripheralCfg.profDeviceId = 0;
    peripheralCfg.profChannel = analysis::dvvp::driver::PROF_CHANNEL_AI_CORE;
    peripheralCfg.profSamplePeriod = 10;
    peripheralCfg.profDataFilePath = "/path/to/data";

    std::vector<std::string> prof_events;
    std::vector<int> prof_cores;
    prof_events.resize(PMU_EVENT_MAX_NUM + 1);
    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvAicoreStart(peripheralCfg, prof_cores, prof_events));
    prof_events.clear();

    prof_events.push_back("0x11");
    prof_cores.push_back(0);

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvAicoreStart(peripheralCfg, prof_cores, prof_events));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvAicoreStart(peripheralCfg, prof_cores, prof_events));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvAicoreTaskBasedStart)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_AI_CORE;
    std::vector<std::string> prof_events;
    std::vector<int> prof_cores;
    std::string prof_data_file_path = "/path/to/data";
    prof_events.resize(PMU_EVENT_MAX_NUM + 1);
    EXPECT_EQ(
        PROFILING_FAILED, analysis::dvvp::driver::DrvAicoreTaskBasedStart(prof_device_id, prof_channel, prof_events));
    prof_events.clear();

    prof_events.push_back("0x11");

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(
        PROFILING_FAILED, analysis::dvvp::driver::DrvAicoreTaskBasedStart(prof_device_id, prof_channel, prof_events));

    EXPECT_EQ(
        PROFILING_SUCCESS, analysis::dvvp::driver::DrvAicoreTaskBasedStart(prof_device_id, prof_channel, prof_events));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvAicpuStart)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_AICPU;
    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));
    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvAicpuStart(prof_device_id, prof_channel));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvAicpuStart(prof_device_id, prof_channel));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvFftsProfileStart)
{
    GlobalMockObject::verify();

    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_FFTS_PROFILE_TASK;
    std::vector<int> prof_cores;
    std::vector<std::string> prof_events;
    std::vector<int> prof_aivCores;
    std::vector<std::string> prof_aivEvents;
    std::string prof_data_file_path = "/path/to/data";

    prof_cores.push_back(0);
    prof_events.push_back("0x8");
    prof_events.push_back("0xa");
    prof_events.push_back("0x9");
    prof_events.push_back("0xb");
    prof_events.push_back("0xc");
    prof_events.push_back("0xd");
    prof_events.push_back("0x54");
    prof_events.push_back("0x55");
    prof_aivCores.push_back(0);
    prof_aivEvents.push_back("0x8");
    prof_aivEvents.push_back("0xa");
    prof_aivEvents.push_back("0x9");
    prof_aivEvents.push_back("0xb");
    prof_aivEvents.push_back("0xc");
    prof_aivEvents.push_back("0xd");
    prof_aivEvents.push_back("0x54");
    prof_aivEvents.push_back("0x55");
    analysis::dvvp::driver::DrvPeripheralProfileCfg drvPeripheralProfileCfg;
    drvPeripheralProfileCfg.profDeviceId = 0;
    drvPeripheralProfileCfg.profChannel = prof_channel;
    drvPeripheralProfileCfg.profSamplePeriod = 10;
    drvPeripheralProfileCfg.profSamplePeriodHi = 10;
    drvPeripheralProfileCfg.cfgMode = 1;
    drvPeripheralProfileCfg.aicMode = 1;
    drvPeripheralProfileCfg.aivMode = 1;

    StarsAccProfileConfigT* configP =
        static_cast<StarsAccProfileConfigT*>(Utils::ProfMalloc(sizeof(StarsAccProfileConfigT)));
    EXPECT_NE(configP, nullptr);
    if (configP == nullptr) {
        return;
    }
    configP->aicScale = 1;
    drvPeripheralProfileCfg.configP = configP;

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(
        PROFILING_FAILED, analysis::dvvp::driver::DrvFftsProfileStart(
                              drvPeripheralProfileCfg, prof_cores, prof_events, prof_aivCores, prof_aivEvents));

    EXPECT_EQ(
        PROFILING_SUCCESS, analysis::dvvp::driver::DrvFftsProfileStart(
                               drvPeripheralProfileCfg, prof_cores, prof_events, prof_aivCores, prof_aivEvents));
    void* configVoid = static_cast<void*>(configP);
    Utils::ProfFree(configVoid);
    EXPECT_EQ(configVoid, nullptr);
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvAccProfileStart)
{
    GlobalMockObject::verify();

    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_FFTS_PROFILE_TASK;
    std::vector<int> prof_cores;
    std::vector<std::string> prof_events;
    std::vector<int> prof_aivCores;
    std::vector<std::string> prof_aivEvents;
    std::string prof_data_file_path = "/path/to/data";

    prof_cores.push_back(0);
    prof_events.push_back("0x8,0xa,0x9,0xb,0xc,0xd,0x54,0x55,0x06,0x07");
    prof_aivCores.push_back(0);
    prof_aivEvents.push_back("0x8,0xa,0x9,0xb,0xc,0xd,0x54,0x55,0x06,0x07");
    analysis::dvvp::driver::DrvPeripheralProfileCfg drvPeripheralProfileCfg;
    drvPeripheralProfileCfg.profDeviceId = 0;
    drvPeripheralProfileCfg.profChannel = prof_channel;
    drvPeripheralProfileCfg.profSamplePeriod = 10;
    drvPeripheralProfileCfg.profSamplePeriodHi = 10;
    drvPeripheralProfileCfg.cfgMode = 1;
    drvPeripheralProfileCfg.aicMode = 1;
    drvPeripheralProfileCfg.aivMode = 1;
    StarsAccProfileConfigT* configP =
        static_cast<StarsAccProfileConfigT*>(Utils::ProfMalloc(sizeof(StarsAccProfileConfigT)));
    configP->aicScale = 1;
    drvPeripheralProfileCfg.configP = configP;
    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(
        PROFILING_FAILED, analysis::dvvp::driver::DrvAccProfileStart(
                              drvPeripheralProfileCfg, prof_cores, prof_events, prof_aivCores, prof_aivEvents));

    StarsAccProfileConfigT* configP2 =
        static_cast<StarsAccProfileConfigT*>(Utils::ProfMalloc(sizeof(StarsAccProfileConfigT)));
    configP2->aicScale = 1;
    drvPeripheralProfileCfg.configP = configP2;
    EXPECT_EQ(
        PROFILING_SUCCESS, analysis::dvvp::driver::DrvAccProfileStart(
                               drvPeripheralProfileCfg, prof_cores, prof_events, prof_aivCores, prof_aivEvents));
    void* configVoid = static_cast<void*>(configP);
    Utils::ProfFree(configVoid);
    EXPECT_EQ(configVoid, nullptr);
    void* configVoid2 = static_cast<void*>(configP2);
    Utils::ProfFree(configVoid2);
    EXPECT_EQ(configVoid2, nullptr);
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvAccProfileStartCoreMask)
{
    GlobalMockObject::verify();

    constexpr int32_t accProfileCoreNum = 16;
    std::vector<int32_t> profCores;
    std::vector<std::string> profEvents = {"0x8"};
    for (int32_t coreId = 0; coreId < accProfileCoreNum; coreId++) {
        profCores.push_back(coreId);
    }

    StarsAccProfileConfigT configP;
    configP.aicScale = 1;
    analysis::dvvp::driver::DrvPeripheralProfileCfg peripheralCfg;
    peripheralCfg.profDeviceId = 0;
    peripheralCfg.profChannel = analysis::dvvp::driver::PROF_CHANNEL_FFTS_PROFILE_TASK;
    peripheralCfg.profSamplePeriod = 10;
    peripheralCfg.profSamplePeriodHi = 10;
    peripheralCfg.cfgMode = 1;
    peripheralCfg.aicMode = 1;
    peripheralCfg.aivMode = 1;
    peripheralCfg.configP = &configP;

    MOCKER(prof_drv_start).stubs().will(invoke(ProfDrvStartAccProfileCoreMaskStub));
    EXPECT_EQ(
        PROFILING_SUCCESS,
        analysis::dvvp::driver::DrvAccProfileStart(peripheralCfg, profCores, profEvents, profCores, profEvents));

    peripheralCfg.fixedCoreMask = ACC_PROFILE_FIXED_CORE_MASK;
    EXPECT_EQ(
        PROFILING_SUCCESS,
        analysis::dvvp::driver::DrvAccProfileStart(peripheralCfg, profCores, profEvents, profCores, profEvents));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvTsFwStart)
{
    GlobalMockObject::verify();

    analysis::dvvp::driver::DrvPeripheralProfileCfg peripheralCfg;
    peripheralCfg.profDeviceId = 0;
    peripheralCfg.profChannel = analysis::dvvp::driver::PROF_CHANNEL_TS_FW;
    peripheralCfg.profSamplePeriod = 10;
    peripheralCfg.profDataFilePath = "/path/to/data";

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvTsFwStart(peripheralCfg, nullptr));

    auto profileParams = std::make_shared<analysis::dvvp::message::ProfileParams>();

    profileParams->ts_timeline = "on";
    profileParams->ts_task_track = "on";
    profileParams->ts_cpu_usage = "on";
    profileParams->ai_core_status = "on";
    profileParams->ai_vector_status = "on";
    profileParams->taskTsfw = "on";
    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvTsFwStart(peripheralCfg, profileParams));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvTsFwStart(peripheralCfg, profileParams));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStarsSocLogStart)
{
    GlobalMockObject::verify();

    analysis::dvvp::driver::DrvPeripheralProfileCfg peripheralCfg;
    peripheralCfg.profDeviceId = 0;
    peripheralCfg.profChannel = analysis::dvvp::driver::PROF_CHANNEL_STARS_SOC_LOG;
    peripheralCfg.profSamplePeriod = 10;
    peripheralCfg.profDataFilePath = "/path/to/data";

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvStarsSocLogStart(peripheralCfg, nullptr));

    auto profileParams = std::make_shared<analysis::dvvp::message::ProfileParams>();

    profileParams->stars_acsq_task = "on";
    profileParams->taskBlock = "on";
    profileParams->sysLp = "on";
    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvStarsSocLogStart(peripheralCfg, profileParams));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvStarsSocLogStart(peripheralCfg, profileParams));
}

int ProfDrvStartStarsSocLogDieStub(unsigned int deviceId, unsigned int channelId, struct prof_start_para* startPara)
{
    EXPECT_NE(nullptr, startPara);
    EXPECT_NE(nullptr, startPara->user_data);
    const auto* config = static_cast<const analysis::dvvp::driver::StarsSocLogConfigT*>(startPara->user_data);
    EXPECT_EQ(static_cast<unsigned int>(TS_PROFILE_COMMAND_TYPE_PROFILING_ENABLE), config->acsq_task);
    EXPECT_EQ(static_cast<unsigned int>(TS_PROFILE_COMMAND_TYPE_PROFILING_ENABLE), config->ffts_context_task);
    EXPECT_EQ(static_cast<unsigned int>(TS_PROFILE_COMMAND_TYPE_PROFILING_ENABLE), config->blockShinkFlag);
    if (channelId == static_cast<unsigned int>(analysis::dvvp::driver::PROF_CHANNEL_STARS_SOC_LOG)) {
        // P die: task-block maps to ffts_block.
        EXPECT_EQ(static_cast<unsigned int>(TS_PROFILE_COMMAND_TYPE_PROFILING_ENABLE), config->ffts_block);
        EXPECT_EQ(0U, config->dvpp_vpc_block);
    } else if (channelId == static_cast<unsigned int>(analysis::dvvp::driver::PROF_CHANNEL_HWTS_LOG)) {
        // F die: task-block maps to dvpp_vpc_block.
        EXPECT_EQ(static_cast<unsigned int>(TS_PROFILE_COMMAND_TYPE_PROFILING_ENABLE), config->dvpp_vpc_block);
        EXPECT_EQ(0U, config->ffts_block);
    } else {
        ADD_FAILURE() << "unexpected channel: " << channelId;
    }
    return PROF_OK;
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStarsSocLogStartTaskBlockMapsByDie)
{
    GlobalMockObject::verify();

    auto profileParams = std::make_shared<analysis::dvvp::message::ProfileParams>();
    profileParams->stars_acsq_task = "on";
    profileParams->taskBlock = "on";
    profileParams->taskBlockShink = "on";

    analysis::dvvp::driver::DrvPeripheralProfileCfg peripheralCfg;
    peripheralCfg.profDeviceId = 0;
    peripheralCfg.profChannel = analysis::dvvp::driver::PROF_CHANNEL_STARS_SOC_LOG;
    peripheralCfg.profSamplePeriod = 10;
    MOCKER(prof_drv_start).stubs().will(invoke(ProfDrvStartStarsSocLogDieStub));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvStarsSocLogStart(peripheralCfg, profileParams));

    peripheralCfg.profChannel = analysis::dvvp::driver::PROF_CHANNEL_HWTS_LOG;
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvStarsSocLogStart(peripheralCfg, profileParams));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStart)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_HBM;
    struct prof_start_para data;
    MOCKER(prof_drv_start).stubs().will(returnValue(-10)).then(returnValue(-11)).then(returnValue(PROF_OK));

    EXPECT_EQ(-10, analysis::dvvp::driver::DrvStart(prof_device_id, prof_channel, &data));
    EXPECT_EQ(-11, analysis::dvvp::driver::DrvStart(prof_device_id, prof_channel, &data));
    EXPECT_EQ(PROF_OK, analysis::dvvp::driver::DrvStart(prof_device_id, prof_channel, &data));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartTaskPmuReturns918LogsDedicatedError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    MOCKER(prof_drv_start).stubs().will(returnValue(0x918));
    EXPECT_EQ(0x918, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_TASK, &data));
    const std::string logMsg = GetLastDlogRecordMsg();
    EXPECT_NE(std::string::npos, logMsg.find("device[0]"));
    EXPECT_NE(std::string::npos, logMsg.find("channel[53]"));
    EXPECT_NE(std::string::npos, logMsg.find("ret=0x918"));
    EXPECT_NE(std::string::npos, logMsg.find("Exit all processes before starting task-based PMU collection"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartTaskPmuReturns917LogsMutuallyExclusiveError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    MOCKER(prof_drv_start).stubs().will(returnValue(0x917));
    EXPECT_EQ(0x917, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_TASK, &data));
    const std::string logMsg = GetLastDlogRecordMsg();
    EXPECT_NE(std::string::npos, logMsg.find("device[0]"));
    EXPECT_NE(std::string::npos, logMsg.find("channel[53]"));
    EXPECT_NE(std::string::npos, logMsg.find("ret=0x917"));
    EXPECT_NE(std::string::npos, logMsg.find("sample-based and task-based profiling are mutually exclusive"));
    EXPECT_NE(std::string::npos, logMsg.find("Exit all processes before restarting profiling"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartSamplePmuReturns917LogsMutuallyExclusiveError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    MOCKER(prof_drv_start).stubs().will(returnValue(0x917));
    EXPECT_EQ(0x917, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_SAMPLE, &data));
    const std::string logMsg = GetLastDlogRecordMsg();
    EXPECT_NE(std::string::npos, logMsg.find("device[0]"));
    EXPECT_NE(std::string::npos, logMsg.find("channel[54]"));
    EXPECT_NE(std::string::npos, logMsg.find("ret=0x917"));
    EXPECT_NE(std::string::npos, logMsg.find("sample-based and task-based profiling are mutually exclusive"));
    EXPECT_NE(std::string::npos, logMsg.find("Exit all processes before restarting profiling"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartOtherPlatform917DoesNotLogMutuallyExclusiveError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(false));
    MOCKER(prof_drv_start).stubs().will(returnValue(0x917));
    EXPECT_EQ(0x917, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_TASK, &data));
    EXPECT_EQ(std::string::npos, std::string(GetLastDlogRecordMsg()).find("mutually exclusive"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartOtherChannel917DoesNotLogMutuallyExclusiveError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER(prof_drv_start).stubs().will(returnValue(0x917));
    EXPECT_EQ(0x917, DrvStart(0U, PROF_CHANNEL_HBM, &data));
    EXPECT_EQ(std::string::npos, std::string(GetLastDlogRecordMsg()).find("mutually exclusive"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartTaskPmuSuccessDoesNotLogDedicatedError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_OK));
    EXPECT_EQ(PROF_OK, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_TASK, &data));
    EXPECT_EQ(std::string::npos, std::string(GetLastDlogRecordMsg()).find("task-based PMU collection"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartTaskPmuOtherErrorCodeOnlyKeepsExistingBehavior)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    const int32_t existingCodes[] = {-10, -11, 115};

    for (const int32_t code : existingCodes) {
        ResetLastDlogRecordMsg();
        GlobalMockObject::reset();
        MOCKER(prof_drv_start).stubs().will(returnValue(code));
        EXPECT_EQ(code, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_TASK, &data));
        EXPECT_EQ(std::string::npos, std::string(GetLastDlogRecordMsg()).find("task-based PMU collection"));
    }
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartOtherPlatform918DoesNotLogDedicatedError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(false));
    MOCKER(prof_drv_start).stubs().will(returnValue(0x918));
    EXPECT_EQ(0x918, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_TASK, &data));
    EXPECT_EQ(std::string::npos, std::string(GetLastDlogRecordMsg()).find("task-based PMU collection"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStartOtherChannel918DoesNotLogDedicatedError)
{
    GlobalMockObject::verify();
    struct prof_start_para data = {};
    ResetLastDlogRecordMsg();

    MOCKER(prof_drv_start).stubs().will(returnValue(0x918));
    EXPECT_EQ(0x918, DrvStart(0U, PROF_CHANNEL_FFTS_PROFILE_SAMPLE, &data));
    EXPECT_EQ(std::string::npos, std::string(GetLastDlogRecordMsg()).find("task-based PMU collection"));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvStop)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_HBM;

    MOCKER(prof_stop).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvStop(prof_device_id, prof_channel));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvStop(prof_device_id, prof_channel));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvChannelRead)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_HBM;
    unsigned char out_buf[4096];
    uint32_t buf_size = 4096;

    MOCKER(prof_channel_read)
        .stubs()
        .will(returnValue(PROF_ERROR))
        .then(returnValue(64))
        .then(returnValue(PROF_STOPPED_ALREADY));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvChannelRead(prof_device_id, prof_channel, nullptr, 0));

    EXPECT_EQ(
        PROFILING_FAILED, analysis::dvvp::driver::DrvChannelRead(prof_device_id, prof_channel, out_buf, buf_size));

    EXPECT_EQ(64, analysis::dvvp::driver::DrvChannelRead(prof_device_id, prof_channel, out_buf, buf_size));
    EXPECT_EQ(
        PROFILING_SUCCESS, analysis::dvvp::driver::DrvChannelRead(prof_device_id, prof_channel, out_buf, buf_size));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvChannelPoll)
{
    GlobalMockObject::verify();

    struct prof_poll_info out_buf[2];

    MOCKER(prof_channel_poll).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvChannelPoll(nullptr, 0, 1));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvChannelPoll(out_buf, 2, 1));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvChannelPoll(out_buf, 2, 1));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvProfFlush)
{
    GlobalMockObject::verify();

    uint32_t bufSize = 0;
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvProfFlush(0U, 0U, bufSize));
}
//////////////////////////////////////////////////////////////////////////

TEST_F(DRIVER_AI_DRV_API_TEST, DrvHwtsLogStart)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_HWTS_LOG;
    int prof_sample_period = 10;
    std::string prof_data_file_path = "/path/to/data";

    GlobalMockObject::verify();

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvHwtsLogStart(prof_device_id, prof_channel));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvHwtsLogStart(prof_device_id, prof_channel));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvFmkDataStart)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_FMK;
    int prof_sample_period = 10;
    int real_time = 0;
    std::string prof_data_file_path = "/path/to/data";
    std::vector<std::string> prof_events;

    prof_events.push_back("0x5b");

    GlobalMockObject::verify();

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvFmkDataStart(prof_device_id, prof_channel));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvFmkDataStart(prof_device_id, prof_channel));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvL2CacheTaskStart)
{
    GlobalMockObject::verify();

    int prof_device_id = 0;
    analysis::dvvp::driver::AI_DRV_CHANNEL prof_channel = analysis::dvvp::driver::PROF_CHANNEL_L2_CACHE;

    std::string prof_data_file_path = "/path/to/data";
    std::vector<std::string> prof_events;

    prof_events.push_back("0x5b");

    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvL2CacheTaskStart(prof_device_id, prof_channel, prof_events));

    EXPECT_EQ(
        PROFILING_SUCCESS, analysis::dvvp::driver::DrvL2CacheTaskStart(prof_device_id, prof_channel, prof_events));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetDevIdsStr)
{
    GlobalMockObject::verify();

    uint32_t num_dev = 0;
    MOCKER(drvGetDevNum).stubs().will(returnValue(DRV_ERROR_NO_DEVICE)).then(returnValue(DRV_ERROR_NONE));

    MOCKER(drvGetDevIDs).stubs().will(returnValue(DRV_ERROR_NO_DEVICE)).then(returnValue(DRV_ERROR_NONE));

    EXPECT_EQ("", analysis::dvvp::driver::DrvGetDevIdsStr());

    EXPECT_EQ("", analysis::dvvp::driver::DrvGetDevIdsStr());
    EXPECT_EQ("", analysis::dvvp::driver::DrvGetDevIdsStr());
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetPlatformInfo)
{
    GlobalMockObject::verify();
    uint32_t platformInfo = 0;
    MOCKER(drvGetPlatformInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NONE))
        .then(returnValue(MSPROF_HELPER_HOST))
        .then(returnValue(DRV_ERROR_INNER_ERR));

    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetPlatformInfo(platformInfo));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetPlatformInfo(platformInfo));
    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetPlatformInfo(platformInfo));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvCheckIfHelperHost)
{
    GlobalMockObject::verify();
    MOCKER(drvGetDevNum).stubs().will(returnValue(DRV_ERROR_NONE)).then(returnValue(MSPROF_HELPER_HOST));

    EXPECT_EQ(false, analysis::dvvp::driver::DrvCheckIfHelperHost());
    EXPECT_EQ(true, analysis::dvvp::driver::DrvCheckIfHelperHost());
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetAivNum)
{
    GlobalMockObject::verify();
    uint32_t deviceId = 0;
    int64_t aivNum = 0;
    ConfigManager::instance()->configMap_["type"] = std::to_string(static_cast<uint64_t>(PlatformType::CHIP_V4_1_0));
    MOCKER(halGetDeviceInfo).stubs().will(returnValue(DRV_ERROR_NONE)).then(returnValue(DRV_ERROR_NO_DEVICE));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAivNum(deviceId, aivNum));
    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetAivNum(deviceId, aivNum));
    ConfigManager::instance()->configMap_["type"] = std::to_string(static_cast<uint64_t>(PlatformType::DC_TYPE));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAivNum(deviceId, aivNum));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetEnvType)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t envType = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetEnvType(deviceId, envType));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetEnvType(deviceId, envType));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetEnvType(deviceId, envType));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetCtrlCpuId)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t ctrlCpuId = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetCtrlCpuId(deviceId, ctrlCpuId));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetCtrlCpuId(deviceId, ctrlCpuId));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetCtrlCpuId(deviceId, ctrlCpuId));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetCtrlCpuCoreNum)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t ctrlCpuCoreNum = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetCtrlCpuCoreNum(deviceId, ctrlCpuCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetCtrlCpuCoreNum(deviceId, ctrlCpuCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetCtrlCpuCoreNum(deviceId, ctrlCpuCoreNum));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetCtrlCpuEndianLittle)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t ctrlCpuEndianLittle = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle(deviceId, ctrlCpuEndianLittle));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle(deviceId, ctrlCpuEndianLittle));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle(deviceId, ctrlCpuEndianLittle));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetAiCpuCoreNum)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t aiCpuCoreNum = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetAiCpuCoreNum(deviceId, aiCpuCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCpuCoreNum(deviceId, aiCpuCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCpuCoreNum(deviceId, aiCpuCoreNum));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetAiCpuCoreId)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t aiCpuCoreId = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetAiCpuCoreId(deviceId, aiCpuCoreId));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCpuCoreId(deviceId, aiCpuCoreId));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCpuCoreId(deviceId, aiCpuCoreId));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetAiCpuOccupyBitmap)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t aiCpuOccupyBitmap = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap(deviceId, aiCpuOccupyBitmap));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap(deviceId, aiCpuOccupyBitmap));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap(deviceId, aiCpuOccupyBitmap));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetTsCpuCoreNum)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t tsCpuCoreNum = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetTsCpuCoreNum(deviceId, tsCpuCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetTsCpuCoreNum(deviceId, tsCpuCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetTsCpuCoreNum(deviceId, tsCpuCoreNum));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetAiCoreId)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t aiCoreId = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetAiCoreId(deviceId, aiCoreId));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCoreId(deviceId, aiCoreId));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCoreId(deviceId, aiCoreId));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetAiCoreNum)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    int64_t aiCoreNum = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetAiCoreNum(deviceId, aiCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCoreNum(deviceId, aiCoreNum));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetAiCoreNum(deviceId, aiCoreNum));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetDeviceTime)
{
    GlobalMockObject::verify();

    uint32_t deviceId = 0;
    uint64_t startMono = 0;
    uint64_t cntvct = 0;

    MOCKER(halGetDeviceInfo)
        .stubs()
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NONE))
        .then(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT));

    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetDeviceTime(deviceId, startMono, cntvct));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetDeviceTime(deviceId, startMono, cntvct));
    EXPECT_EQ(PROFILING_FAILED, analysis::dvvp::driver::DrvGetDeviceTime(deviceId, startMono, cntvct));
    EXPECT_EQ(PROFILING_SUCCESS, analysis::dvvp::driver::DrvGetDeviceTime(deviceId, startMono, cntvct));
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetHostFreq)
{
    GlobalMockObject::verify();
    int64_t outFreq = 1000;
    std::string freq;
    MOCKER(halGetDeviceInfo)
        .stubs()
        .with(any(), any(), any(), outBoundP(&outFreq))
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT))
        .then(returnValue(DRV_ERROR_NONE));

    EXPECT_EQ(false, analysis::dvvp::driver::DrvGetHostFreq(freq));
    EXPECT_EQ(false, analysis::dvvp::driver::DrvGetHostFreq(freq));
    EXPECT_EQ(true, analysis::dvvp::driver::DrvGetHostFreq(freq));
    EXPECT_FLOAT_EQ(1.0, std::stof(freq)); // 返回1000Khz在处理完成之后返回1Mhz
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvGetDeviceFreq)
{
    GlobalMockObject::verify();
    int64_t outFreq = 1000;
    std::string freq;
    MOCKER(halGetDeviceInfo)
        .stubs()
        .with(any(), any(), any(), outBoundP(&outFreq, sizeof(int64_t)))
        .will(returnValue(DRV_ERROR_NO_DEVICE))
        .then(returnValue(DRV_ERROR_NOT_SUPPORT))
        .then(returnValue(DRV_ERROR_NONE));

    EXPECT_EQ(false, analysis::dvvp::driver::DrvGetDeviceFreq(0, freq));
    EXPECT_EQ(false, analysis::dvvp::driver::DrvGetDeviceFreq(0, freq));
    EXPECT_EQ(true, analysis::dvvp::driver::DrvGetDeviceFreq(0, freq));
    EXPECT_FLOAT_EQ(1.0, std::stof(freq)); // 返回1000Khz在处理完成之后返回1Mhz
}

TEST_F(DRIVER_AI_DRV_API_TEST, DrvSocPmuTaskStartWithSmmuDFX)
{
    GlobalMockObject::verify();
    constexpr uint32_t SUPPORT_SMMU_DFX_API_VERSION =
        static_cast<uint32_t>(Analysis::Dvvp::Common::Platform::SMMU_DFX_API_VERSION);

    // Part A: driver supports SMMU DFX — exercises the full pack/copy path.
    MOCKER_CPP(&Platform::DrvGetApiVersion).stubs().will(returnValue(SUPPORT_SMMU_DFX_API_VERSION));
    MOCKER_CPP(&Platform::GetSmmuDFXOffset).stubs().will(returnValue(0x0E78U));
    MOCKER_CPP(&Platform::GetSmmuDFXRegMask).stubs().will(returnValue(0x3FFFFFFFU));
    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_ERROR)).then(returnValue(PROF_OK));

    std::string events = "SMMU_DFX:";
    EXPECT_EQ(PROFILING_FAILED, DrvSocPmuTaskStart(0, PROF_CHANNEL_SOC_PMU, events));
    EXPECT_EQ(PROFILING_SUCCESS, DrvSocPmuTaskStart(0, PROF_CHANNEL_SOC_PMU, events));

    // Mixed events: HA + SMMU_DFX + SMMU — all three TLV segments packed.
    events = "HA:0x00,0x81;SMMU_DFX:;SMMU:0x2,0x8a";
    EXPECT_EQ(PROFILING_SUCCESS, DrvSocPmuTaskStart(0, PROF_CHANNEL_SOC_PMU, events));
    GlobalMockObject::verify();

    // Part B: old driver does not support SMMU DFX — segment silently dropped.
    MOCKER_CPP(&Platform::DrvGetApiVersion).stubs().will(returnValue(SUPPORT_SMMU_DFX_API_VERSION - 1));
    MOCKER(prof_drv_start).stubs().will(returnValue(PROF_OK));

    events = "SMMU_DFX:;HA:0x00";
    EXPECT_EQ(PROFILING_SUCCESS, DrvSocPmuTaskStart(0, PROF_CHANNEL_SOC_PMU, events));
    GlobalMockObject::verify();
}
