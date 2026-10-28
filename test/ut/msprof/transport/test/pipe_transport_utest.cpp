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
#include <memory>
#include <string>
#include "pipe_transport_tool.h"
#include "errno/error_code_tool.h"

using namespace analysis::dvvp::transport;
using namespace analysis::dvvp::common::error;

static int32_t g_callbackCalled = 0;
static int32_t StubRawDataCallback(MsprofRawData* rawData)
{
    g_callbackCalled++;
    EXPECT_NE(nullptr, rawData);
    return 0;
}

class PIPE_TRANSPORT_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        GlobalMockObject::verify();
        g_callbackCalled = 0;
    }
    virtual void TearDown() { GlobalMockObject::verify(); }
};

TEST_F(PIPE_TRANSPORT_TEST, Constructor)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    EXPECT_NE(nullptr, transport);
    EXPECT_FALSE(transport->IsRegisterRawDataCallback());
}

TEST_F(PIPE_TRANSPORT_TEST, SendBuffer_VoidPtr)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    uint8_t buf[] = {0x01, 0x02};
    EXPECT_EQ(0, transport->SendBuffer(buf, 2));
}

TEST_F(PIPE_TRANSPORT_TEST, SendBuffer_FileChunk_NoCallback)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    auto chunk = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    chunk->isLastChunk = true;
    chunk->chunkModule = 0;
    chunk->chunkSize = 5;
    chunk->offset = 0;
    chunk->chunk = "hello";
    EXPECT_EQ(PROFILING_FAILED, transport->SendBuffer(chunk));
}

TEST_F(PIPE_TRANSPORT_TEST, SendBuffer_FileChunk_WithCallback)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    transport->RegisterRawDataCallback(StubRawDataCallback);
    EXPECT_TRUE(transport->IsRegisterRawDataCallback());

    auto chunk = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    chunk->isLastChunk = true;
    chunk->chunkModule = 1;
    chunk->chunkSize = 5;
    chunk->offset = 10;
    chunk->chunk = "world";
    EXPECT_EQ(PROFILING_SUCCESS, transport->SendBuffer(chunk));
    EXPECT_EQ(1, g_callbackCalled);
}

TEST_F(PIPE_TRANSPORT_TEST, ConvertFileChunkToRawData)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    auto chunk = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    chunk->isLastChunk = true;
    chunk->chunkModule = 2;
    chunk->chunkSize = 3;
    chunk->offset = 7;
    chunk->chunk = "abc";
    MsprofRawData rawData;
    EXPECT_EQ(PROFILING_SUCCESS, transport->ConvertFileChunkToRawData(chunk, rawData));
    EXPECT_EQ(chunk->isLastChunk, rawData.isLastChunk);
    EXPECT_EQ(chunk->offset, rawData.offset);
    EXPECT_EQ(chunk->chunkModule, rawData.chunkModule);
    EXPECT_EQ(0, rawData.deviceId);
    EXPECT_EQ(RawDataType::DEFAULT_DATA_TYPE, rawData.type);
    EXPECT_EQ(chunk->chunkSize, rawData.chunkSize);
}

TEST_F(PIPE_TRANSPORT_TEST, ConvertFileChunkToRawData_ChunkTooLarge)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    auto chunk = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    chunk->isLastChunk = false;
    chunk->chunkModule = 0;
    chunk->chunkSize = 0;
    chunk->offset = 0;
    chunk->chunk = std::string(RAW_DATA_MAXSIZE + 1, 'x');
    MsprofRawData rawData;
    EXPECT_EQ(PROFILING_FAILED, transport->ConvertFileChunkToRawData(chunk, rawData));
}

TEST_F(PIPE_TRANSPORT_TEST, CloseSession)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    EXPECT_EQ(PROFILING_SUCCESS, transport->CloseSession());
}

TEST_F(PIPE_TRANSPORT_TEST, WriteDone)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    transport->WriteDone();
}

TEST_F(PIPE_TRANSPORT_TEST, RegisterAndUnregisterCallback)
{
    auto transport = std::make_shared<MsptiPipeTransport>();
    EXPECT_FALSE(transport->IsRegisterRawDataCallback());
    transport->RegisterRawDataCallback(StubRawDataCallback);
    EXPECT_TRUE(transport->IsRegisterRawDataCallback());
    transport->UnRegisterRawDataCallback();
    EXPECT_FALSE(transport->IsRegisterRawDataCallback());
}

TEST_F(PIPE_TRANSPORT_TEST, Factory_CreateMsptiPipeTransport)
{
    MsptiPipeTransportFactory factory;
    auto transport = factory.CreateMsptiPipeTransport();
    EXPECT_NE(nullptr, transport);
}
