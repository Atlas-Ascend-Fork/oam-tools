/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
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

#include "errno/error_code_tool.h"
#include "memory/chunk_pool_tool.h"

using namespace analysis::dvvp::common::memory;

class CHUNK_POOL_UTEST : public testing::Test {
protected:
    void TearDown() override
    {
        GlobalMockObject::verify();
        GlobalMockObject::reset();
    }
};

TEST_F(CHUNK_POOL_UTEST, ChunkInitZeroSize)
{
    // bufferSize_ == 0: Init 直接返回 true，buffer_ 保持空
    auto chunk = std::make_shared<Chunk>(0);
    EXPECT_EQ(true, chunk->Init());
    EXPECT_EQ(nullptr, chunk->GetBuffer());
    EXPECT_EQ(0U, chunk->GetBufferSize());
}

TEST_F(CHUNK_POOL_UTEST, ChunkInitAndAccessors)
{
    const size_t bufferSize = 16;
    auto chunk = std::make_shared<Chunk>(bufferSize);
    EXPECT_EQ(true, chunk->Init());
    EXPECT_NE(nullptr, chunk->GetBuffer());
    EXPECT_EQ(bufferSize, chunk->GetBufferSize());
    EXPECT_EQ(0U, chunk->GetUsedSize());
    EXPECT_EQ(bufferSize, chunk->GetFreeSize());

    chunk->SetUsedSize(4);
    EXPECT_EQ(4U, chunk->GetUsedSize());
    EXPECT_EQ(bufferSize - 4, chunk->GetFreeSize());

    chunk->Clear();
    EXPECT_EQ(0U, chunk->GetUsedSize());

    chunk->Uninit();
    EXPECT_EQ(0U, chunk->GetBufferSize());
}

TEST_F(CHUNK_POOL_UTEST, ChunkPoolInitFailedWhenPoolSizeZero)
{
    auto chunkPool = std::make_shared<ChunkPool>(0, 16);
    EXPECT_EQ(false, chunkPool->Init());
}

TEST_F(CHUNK_POOL_UTEST, ChunkPoolAllocReleaseTryAlloc)
{
    const size_t poolSize = 2;
    auto chunkPool = std::make_shared<ChunkPool>(poolSize, 16);
    EXPECT_EQ(true, chunkPool->Init());

    // Alloc 两个，池被取空
    auto chunk1 = chunkPool->Alloc();
    auto chunk2 = chunkPool->Alloc();
    EXPECT_NE(nullptr, chunk1);
    EXPECT_NE(nullptr, chunk2);

    // 池已空，TryAlloc 返回 nullptr
    EXPECT_EQ(nullptr, chunkPool->TryAlloc());

    // Release 后可再次取出
    chunkPool->Release(chunk1);
    auto chunk3 = chunkPool->TryAlloc();
    EXPECT_NE(nullptr, chunk3);

    // Release 一个未被 used_ 记录的资源，应安全无副作用
    chunkPool->Release(std::make_shared<Chunk>(0));
    // Release 空指针，命中保护分支
    chunkPool->Release(nullptr);

    chunkPool->Uninit();
}
