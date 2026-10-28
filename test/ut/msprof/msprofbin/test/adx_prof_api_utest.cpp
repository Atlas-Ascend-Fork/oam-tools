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
#include "mockcpp/mockcpp.hpp"
#include "gtest/gtest.h"
#include "adx_prof_api_tool.h"
#include "errno/error_code_tool.h"
#include "securec.h"

using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Adx;

class ADX_PROF_API_STEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() { GlobalMockObject::verify(); }
};

TEST_F(ADX_PROF_API_STEST, AdxIdeGetVfIdBySession)
{
    GlobalMockObject::verify();
    HDC_SESSION session = (HDC_SESSION)0x12345678;
    int32_t vfId = 0;
    EXPECT_EQ(IDE_DAEMON_OK, AdxIdeGetVfIdBySession(session, vfId));
    EXPECT_EQ(0, vfId);
}

TEST_F(ADX_PROF_API_STEST, AdxIdeCreatePacketChecksInputs)
{
    IdeBuffT buffer = nullptr;
    int32_t length = 0;
    IdeBuffT output = nullptr;
    int32_t outputLength = 0;

    EXPECT_EQ(IDE_DAEMON_ERROR, AdxIdeCreatePacket(nullptr, length, output, outputLength));
    EXPECT_EQ(nullptr, output);
    EXPECT_EQ(0, outputLength);

    output = reinterpret_cast<IdeBuffT>(1);
    EXPECT_EQ(
        IDE_DAEMON_OK, AdxIdeCreatePacket(reinterpret_cast<CONST_VOID_PTR>(&buffer), length, output, outputLength));
    AdxIdeFreePacket(output);
}

TEST_F(ADX_PROF_API_STEST, AdxIdeCreatePacketRejectsOversizedLength)
{
    IdeBuffT input = nullptr;
    IdeBuffT output = nullptr;
    int32_t outputLength = 0;
    const uint32_t oversizedLength = UINT32_MAX;

    EXPECT_EQ(
        IDE_DAEMON_ERROR,
        AdxIdeCreatePacket(
            reinterpret_cast<CONST_VOID_PTR>(&input), static_cast<int32_t>(oversizedLength), output, outputLength));
    EXPECT_EQ(nullptr, output);
    EXPECT_EQ(0, outputLength);
}

TEST_F(ADX_PROF_API_STEST, AdxIdeCreateAndFreePacket)
{
    const char input[] = "adx";
    IdeBuffT output = nullptr;
    int32_t outputLength = 0;

    EXPECT_EQ(IDE_DAEMON_OK, AdxIdeCreatePacket(input, sizeof(input) - 1, output, outputLength));
    EXPECT_NE(nullptr, output);
    EXPECT_EQ(static_cast<int32_t>(sizeof(struct tlv_req) + sizeof(input) - 1), outputLength);
    AdxIdeFreePacket(output);
    EXPECT_EQ(nullptr, output);
}
