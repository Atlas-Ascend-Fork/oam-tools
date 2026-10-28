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
#include <vector>
#include "config/config.h"
#include "david_platform.h"
#include "david_lite_platform.h"
#include "david_v121_platform.h"
#include "dc_platform.h"
#include "rc_lite_platform_stub.h"
#include "rc_lite_v2_platform_stub.h"
#include "rc_mini_v3_platform_stub.h"
#include "rc_platform_stub.h"
#include "rc_v2_platform_stub.h"
#include "mini_v3_platform.h"
#include "modena_platform.h"
#include "platform/platform_tool.h"

using namespace Dvvp::Collect::Platform;
using namespace analysis::dvvp::common::config;

namespace {
constexpr uint16_t MODENA_MAX_MONITOR_NUM = 8;
constexpr uint16_t RC_V2_QOS_MONITOR_NUM = 8;
constexpr uint32_t RC_V2_CHIP_ID = 17;
} // namespace

class PLATFORM_UTEST : public testing::Test {
protected:
    virtual void SetUp() { GlobalMockObject::verify(); }
    virtual void TearDown() { GlobalMockObject::verify(); }
};

TEST_F(PLATFORM_UTEST, DefaultPlatformInterfaceAccCoreMaskIsEmpty)
{
    PlatformInterface platformInterface;
    EXPECT_EQ(0U, platformInterface.GetAccProfileFixedCoreMask());
}

TEST_F(PLATFORM_UTEST, DavidLitePlatformKeepsDavidFeaturesAndLimitsDieChannels)
{
    DavidLitePlatform davidLitePlatform;
    EXPECT_TRUE(davidLitePlatform.FeatureIsSupport(PLATFORM_TASK_AIC_METRICS));
    EXPECT_TRUE(davidLitePlatform.FeatureIsSupport(PLATFORM_TASK_CCU_INSTRUTION));
    EXPECT_TRUE(davidLitePlatform.FeatureIsSupport(PLATFORM_TASK_PC_SAMPLING));
    EXPECT_EQ(BIU_PERF_LOWER_GROUP_NUM, davidLitePlatform.GetBiuPerfGroupNum());
    EXPECT_EQ(DAVID_LITE_CCU_DIE_NUM, davidLitePlatform.GetCcuDieNum());
}

TEST_F(PLATFORM_UTEST, DavidLitePlatformMatchesDavidFeatures)
{
    DavidPlatform davidPlatform;
    DavidLitePlatform davidLitePlatform;

    for (int feature = PLATFORM_FEATURE_INVALID; feature < PLATFORM_COLLECTOR_TYPES_MAX; ++feature) {
        const auto platformFeature = static_cast<PlatformFeature>(feature);
        EXPECT_EQ(davidPlatform.FeatureIsSupport(platformFeature), davidLitePlatform.FeatureIsSupport(platformFeature))
            << "feature: " << feature;
    }
    EXPECT_EQ(davidPlatform.GetMaxMonitorNumber(), davidLitePlatform.GetMaxMonitorNumber());
    EXPECT_EQ(davidPlatform.GetQosMonitorNumber(), davidLitePlatform.GetQosMonitorNumber());
    EXPECT_EQ(davidPlatform.GetSmmuDFXOffset(), davidLitePlatform.GetSmmuDFXOffset());
    EXPECT_EQ(davidPlatform.GetSmmuDFXRegMask(), davidLitePlatform.GetSmmuDFXRegMask());
    EXPECT_EQ(davidPlatform.GetL2CacheEvents(), davidLitePlatform.GetL2CacheEvents());
}

TEST_F(PLATFORM_UTEST, DavidLitePlatformUsesRequestedGroupRange)
{
    DavidLitePlatform davidLitePlatform;
    const std::vector<uint32_t> groupVector = {0, 1, 2};
    const auto channelInfos = davidLitePlatform.GetBiuPerfChannelInfos(groupVector, BIU_PERF_LOWER_GROUP_NUM);

    EXPECT_EQ(static_cast<size_t>(BIU_PERF_LOWER_GROUP_NUM * INSTR_PROFILING_GROUP_CHANNEL_NUM), channelInfos.size());
    for (const auto& channelInfo : channelInfos) {
        EXPECT_LT(channelInfo.groupId, static_cast<uint32_t>(BIU_PERF_LOWER_GROUP_NUM));
        EXPECT_LT(channelInfo.groupNo, static_cast<uint32_t>(BIU_PERF_LOWER_GROUP_NUM));
    }
}

TEST_F(PLATFORM_UTEST, DavidLitePlatformCanBeCreatedByReflection)
{
    auto platform = PlatformReflection::CreatePlatformClass(CHIP_CLOUD_V3_LITE);
    ASSERT_NE(nullptr, platform);
    EXPECT_EQ(BIU_PERF_LOWER_GROUP_NUM, platform->GetBiuPerfGroupNum());
    EXPECT_EQ(DAVID_LITE_CCU_DIE_NUM, platform->GetCcuDieNum());
}

// ================================ DavidV121Platform ================================

TEST_F(PLATFORM_UTEST, DavidV121_FeatureIsSupport)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AICPU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_PC_SAMPLING));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_MC2));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_STARS_QOS));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_FWK));
}

TEST_F(PLATFORM_UTEST, TaskPmuResourceNotResetOnlySupportedOnDavidV121)
{
    DavidPlatform davidPlatform;
    DavidLitePlatform davidLitePlatform;
    DavidV121Platform davidV121Platform;

    EXPECT_FALSE(davidPlatform.FeatureIsSupport(PLATFORM_TASK_PMU_RESOURCE_NOT_RESET));
    EXPECT_FALSE(davidLitePlatform.FeatureIsSupport(PLATFORM_TASK_PMU_RESOURCE_NOT_RESET));
    EXPECT_TRUE(davidV121Platform.FeatureIsSupport(PLATFORM_TASK_PMU_RESOURCE_NOT_RESET));
}

TEST_F(PLATFORM_UTEST, DavidV121_GetMaxMonitorNumber)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(MAX_DAVID_MONITOR_NUM, platform->GetMaxMonitorNumber());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetQosMonitorNumber)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(8, platform->GetQosMonitorNumber());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetPipeUtilizationMetrics)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x501,0x301,0x1,0x701,0x202,0x203,0x34,0x35,0x714"), platform->GetPipeUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetMemoryMetrics)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x422,0x423,0x56f,0x571,0x570,0x572,0x707,0x709"), platform->GetMemoryMetrics());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetMemoryL0Metrics)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x304,0x703,0x306,0x705,0x712,0x30a,0x308"), platform->GetMemoryL0Metrics());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetMemoryUBMetrics)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x3,0x5,0x70c,0x206,0x204,0x571,0x572"), platform->GetMemoryUBMetrics());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetArithmeticUtilizationMetrics)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x323,0x324"), platform->GetArithmeticUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetResourceConflictRatioMetrics)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x540,0x556,0x502,0x528"), platform->GetResourceConflictRatioMetrics());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetL2CacheMetrics)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x424,0x425,0x426,0x42a,0x42b,0x42c"), platform->GetL2CacheMetrics());
}

TEST_F(PLATFORM_UTEST, DavidV121_GetL2CacheEvents)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(std::string("0x00,0x81,0x82,0x83,0x74,0x75"), platform->GetL2CacheEvents());
}

TEST_F(PLATFORM_UTEST, DavidV121_InitOnlineAnalyzer)
{
    auto platform = std::make_shared<DavidV121Platform>();
    EXPECT_EQ(0, platform->InitOnlineAnalyzer());
}

// ================================ DcPlatform ================================

TEST_F(PLATFORM_UTEST, Dc_FeatureIsSupport)
{
    auto platform = std::make_shared<DcPlatform>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AICPU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_HBM));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_MC2));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_PC_SAMPLING));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_PUEXCT_PMU));
}

TEST_F(PLATFORM_UTEST, Dc_GetL2CacheEvents)
{
    auto platform = std::make_shared<DcPlatform>();
    EXPECT_EQ(std::string("0x78,0x79,0x77,0x71,0x6a,0x6c,0x74,0x62"), platform->GetL2CacheEvents());
}

// ================================ RcLitePlatformStub ================================

TEST_F(PLATFORM_UTEST, RcLite_FeatureIsSupport)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_HBM));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_AICPU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_PC_SAMPLING));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_MC2));
}

TEST_F(PLATFORM_UTEST, RcLite_GetPipeUtilizationMetrics)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x500,0x301,0x1,0x701,0x202,0x203,0x34,0x35"), platform->GetPipeUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, RcLite_GetPipelineExecuteUtilizationMetrics)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x500,0x301,0x1,0x701,0x202,0x203,0x714"), platform->GetPipelineExecuteUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, RcLite_GetMemoryMetrics)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x404,0x406,0x566,0x567,0x707,0x709"), platform->GetMemoryMetrics());
}

TEST_F(PLATFORM_UTEST, RcLite_GetMemoryL0Metrics)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x304,0x702,0x306,0x703,0x712,0x30a,0x308"), platform->GetMemoryL0Metrics());
}

TEST_F(PLATFORM_UTEST, RcLite_GetMemoryUBMetrics)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x3,0x5,0x70c,0x206,0x204,0x57b,0x57c"), platform->GetMemoryUBMetrics());
}

TEST_F(PLATFORM_UTEST, RcLite_GetArithmeticUtilizationMetrics)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x302,0x303"), platform->GetArithmeticUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, RcLite_GetResourceConflictRatioMetrics)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x54f,0x551,0x552,0x561,0x563,0x564,0x557"), platform->GetResourceConflictRatioMetrics());
}

TEST_F(PLATFORM_UTEST, RcLite_GetL2CacheEvents)
{
    auto platform = std::make_shared<RcLitePlatformStub>();
    EXPECT_EQ(std::string("0x78,0x79,0x77,0x71,0x6a,0x6c,0x74,0x62"), platform->GetL2CacheEvents());
}

// ================================ RcLiteV2PlatformStub ================================

TEST_F(PLATFORM_UTEST, RcLiteV2_FeatureIsSupport)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_MC2));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_STARS_QOS));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AICPU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_FWK));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_SIO_PA));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_INTERCONNECTION));
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetMaxMonitorNumber)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(MAX_DAVID_MONITOR_NUM, platform->GetMaxMonitorNumber());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetQosMonitorNumber)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(8, platform->GetQosMonitorNumber());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetPipeUtilizationMetrics)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x501,0x301,0x1,0x701,0x202,0x203,0x34,0x35,0x714"), platform->GetPipeUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetMemoryMetrics)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x400,0x401,0x56f,0x571,0x570,0x572,0x707,0x709"), platform->GetMemoryMetrics());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetMemoryL0Metrics)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x304,0x703,0x306,0x705,0x712,0x30a,0x308"), platform->GetMemoryL0Metrics());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetMemoryUBMetrics)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x3,0x5,0x70c,0x206,0x204,0x571,0x572"), platform->GetMemoryUBMetrics());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetArithmeticUtilizationMetrics)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x323,0x324"), platform->GetArithmeticUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetResourceConflictRatioMetrics)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x540,0x556,0x502,0x528"), platform->GetResourceConflictRatioMetrics());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetL2CacheMetrics)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x424,0x425,0x426,0x42a,0x42b,0x42c"), platform->GetL2CacheMetrics());
}

TEST_F(PLATFORM_UTEST, RcLiteV2_GetL2CacheEvents)
{
    auto platform = std::make_shared<RcLiteV2PlatformStub>();
    EXPECT_EQ(std::string("0x00,0x81,0x82,0x83,0x74,0x75"), platform->GetL2CacheEvents());
}

// ================================ RcV2PlatformStub ================================

TEST_F(PLATFORM_UTEST, RcV2_FeatureIsSupport)
{
    RcV2PlatformStub platform;
    const std::vector<PlatformFeature> rcV2Features = {
        PLATFORM_TASK_NTS,
        PLATFORM_TASK_AICPU,
        PLATFORM_TASK_L2_CACHE_REG,
        PLATFORM_TASK_L2_CACHE_PMU,
        PLATFORM_TASK_SOC_PMU,
        PLATFORM_TASK_BLOCK,
        PLATFORM_TASK_BLOCK_ON,
        PLATFORM_AICORE_EVENT_FROM_ZERO,
        PLATFORM_SYS_DEVICE_LLC_EXT,
        PLATFORM_SYS_DEVICE_SIO_PA,
        PLATFORM_SYS_DEVICE_INTERCONNECTION};
    for (const auto& feature : rcV2Features) {
        EXPECT_TRUE(platform.FeatureIsSupport(feature));
    }
    EXPECT_FALSE(platform.FeatureIsSupport(PLATFORM_TASK_FWK));
    EXPECT_FALSE(platform.FeatureIsSupport(PLATFORM_TASK_PC_SAMPLING));
}

TEST_F(PLATFORM_UTEST, RcV2_MonitorNumberAndDefaultFreq)
{
    RcV2PlatformStub platform;
    EXPECT_EQ(MAX_DAVID_MONITOR_NUM, platform.GetMaxMonitorNumber());
    EXPECT_EQ(RC_V2_QOS_MONITOR_NUM, platform.GetQosMonitorNumber());
    // 频率归一到平台层：与扩展仓rc_v2平台实现保持一致
    EXPECT_EQ(std::string("38.4"), platform.GetDeviceOscDefaultFreq());
    EXPECT_EQ(std::string("1400"), platform.GetAicDefaultFreq());
}

TEST_F(PLATFORM_UTEST, RcV2_AicoreMetricsTables)
{
    RcV2PlatformStub platform;
    EXPECT_EQ(std::string("0x501,0x301,0x1,0x701,0x202,0x203,0x34,0x35,0x714"), platform.GetPipeUtilizationMetrics());
    EXPECT_EQ(std::string("0x323,0x324"), platform.GetArithmeticUtilizationMetrics());
    EXPECT_EQ(std::string("0x540,0x556,0x502,0x528"), platform.GetResourceConflictRatioMetrics());
}

TEST_F(PLATFORM_UTEST, RcV2_MemoryMetricsTables)
{
    RcV2PlatformStub platform;
    EXPECT_EQ(std::string("0x400,0x401,0x56f,0x571,0x570,0x572,0x707,0x709"), platform.GetMemoryMetrics());
    EXPECT_EQ(std::string("0x304,0x703,0x306,0x705,0x712,0x30a,0x308"), platform.GetMemoryL0Metrics());
    EXPECT_EQ(std::string("0x3,0x5,0x70c,0x206,0x204,0x571,0x572"), platform.GetMemoryUBMetrics());
}

TEST_F(PLATFORM_UTEST, RcV2_L2CacheMetricsAndEvents)
{
    RcV2PlatformStub platform;
    EXPECT_EQ(std::string("0x424,0x425,0x426,0x42a,0x42b,0x42c"), platform.GetL2CacheMetrics());
    EXPECT_EQ(std::string("0x00,0x75,0x76,0x77,0x66,0x67,0x68,0x69"), platform.GetL2CacheEvents());
}

TEST_F(PLATFORM_UTEST, RcV2_NtsPipeUtilizationMetrics)
{
    RcV2PlatformStub platform;
    EXPECT_EQ(
        std::string("0x301,0x312,0x315,0x316,0x32e,0x701,0x202,0x203,0x1,0x35"),
        platform.GetNtsPipeUtilizationMetrics());
}

TEST_F(PLATFORM_UTEST, RcV2_CanBeCreatedByReflection)
{
    auto platform = PlatformReflection::CreatePlatformClass(static_cast<PlatformTypeEnum>(RC_V2_CHIP_ID));
    ASSERT_NE(nullptr, platform);
    EXPECT_EQ(MAX_DAVID_MONITOR_NUM, platform->GetMaxMonitorNumber());
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_NTS));
}

// ================================ ModenaPlatform ================================

TEST_F(PLATFORM_UTEST, Modena_GetMetrics)
{
    auto platform = std::make_shared<ModenaPlatform>();
    EXPECT_EQ(std::string("0x501,0x301,0x1,0x202,0x203,0x34,0x35"), platform->GetPipeUtilizationMetrics());
    EXPECT_EQ(std::string("0x400,0x401,0x56f,0x570"), platform->GetMemoryMetrics());
    EXPECT_EQ(std::string("0x3,0x5,0x204,0x206,0x571,0x572"), platform->GetMemoryUBMetrics());
    EXPECT_EQ(std::string("0x32c,0x32d"), platform->GetArithmeticUtilizationMetrics());
    EXPECT_EQ(std::string("0x540,0x556"), platform->GetResourceConflictRatioMetrics());
}

TEST_F(PLATFORM_UTEST, Modena_FeatureIsSupport)
{
    auto platform = std::make_shared<ModenaPlatform>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_PU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_MEMORY_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_MEMORYUB_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_RCR_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_TRACE));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AIC_METRICS));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_L2_CACHE_PMU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_MEMORYL0_PMU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_MEMORY_ACCESS_PMU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_PSC_PMU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_BLOCK));
    EXPECT_EQ(MODENA_MAX_MONITOR_NUM, platform->GetMaxMonitorNumber());
}

TEST_F(PLATFORM_UTEST, Modena_CreateByReflection)
{
    auto platform = PlatformReflection::CreatePlatformClass(CHIP_5162A);
    ASSERT_NE(nullptr, platform);
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AIC_METRICS));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_LLC));
}

// ================================ RcMiniV3PlatformStub ================================

TEST_F(PLATFORM_UTEST, RcMiniV3_FeatureIsSupport_ErasedFeatures)
{
    auto platform = std::make_shared<RcMiniV3PlatformStub>();
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_AICPU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_BLOCK));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_NIC));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_AICORE_LPM));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_DYNAMIC));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_DELAY_DURATION));
}

TEST_F(PLATFORM_UTEST, RcMiniV3_FeatureIsSupport_RetainedFeatures)
{
    auto platform = std::make_shared<RcMiniV3PlatformStub>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_HCCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_NPU_MODULE_MEM));
}

// ================================ RcPlatformStub ================================

TEST_F(PLATFORM_UTEST, Rc_FeatureIsSupport)
{
    auto platform = std::make_shared<RcPlatformStub>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AICPU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_HBM));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_PC_SAMPLING));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_MC2));
}

TEST_F(PLATFORM_UTEST, Rc_GetL2CacheEvents)
{
    auto platform = std::make_shared<RcPlatformStub>();
    EXPECT_EQ(std::string("0x78,0x79,0x77,0x71,0x6a,0x6c,0x74,0x62"), platform->GetL2CacheEvents());
}

// ================================ MiniV3Platform ================================

TEST_F(PLATFORM_UTEST, MiniV3_FeatureIsSupport)
{
    auto platform = std::make_shared<MiniV3Platform>();
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AICPU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_AU_PMU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_DEVICE_NIC));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_TASK_PUEXCT_PMU));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_MC2));
}

TEST_F(PLATFORM_UTEST, MiniV3_FeatureIsSupport_SocSide)
{
    auto platform = std::make_shared<MiniV3Platform>();
    auto sysPlatform = Analysis::Dvvp::Common::Platform::Platform::instance();
    sysPlatform->runSide_ = Analysis::Dvvp::Common::Platform::SysPlatformType::DEVICE;
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_ASCENDCL));
    EXPECT_FALSE(platform->FeatureIsSupport(PLATFORM_SYS_HOST_ONE_PID_CPU));
    sysPlatform->runSide_ = Analysis::Dvvp::Common::Platform::SysPlatformType::HOST;
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_SYS_HOST_ONE_PID_CPU));
    EXPECT_TRUE(platform->FeatureIsSupport(PLATFORM_TASK_FWK));
    sysPlatform->runSide_ = Analysis::Dvvp::Common::Platform::SysPlatformType::INVALID;
}

TEST_F(PLATFORM_UTEST, MiniV3_GetMemoryUBMetrics)
{
    auto platform = std::make_shared<MiniV3Platform>();
    EXPECT_EQ(std::string("0x37,0x38,0x1a5,0x1a6,0x17f,0x180,0x191"), platform->GetMemoryUBMetrics());
}
