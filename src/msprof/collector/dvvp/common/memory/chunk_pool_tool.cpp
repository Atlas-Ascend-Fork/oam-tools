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

#include "chunk_pool_tool.h"
#include "securec.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace memory {
using namespace analysis::dvvp::common::utils;
Chunk::Chunk(size_t bufferSize) : buffer_(nullptr), bufferSize_(bufferSize), usedSize_(0) {}

Chunk::~Chunk() { Uninit(); }

bool Chunk::Init()
{
    if (bufferSize_ == 0) {
        return true;
    }

    buffer_ = static_cast<UNSIGNED_CHAR_PTR>(malloc(bufferSize_));
    if (buffer_ == nullptr) {
        return false;
    }

    Clear();

    return true;
}

void Chunk::Uninit()
{
    if (buffer_ != nullptr) {
        free(buffer_);
        buffer_ = nullptr;
    }
    bufferSize_ = 0;
}

void Chunk::Clear()
{
    if (buffer_ != nullptr) {
        (void)memset_s(buffer_, bufferSize_ * sizeof(unsigned char), 0, bufferSize_ * sizeof(unsigned char));
    }
    usedSize_ = 0;
}

uint8_t* Chunk::GetBuffer() const { return buffer_; }

size_t Chunk::GetUsedSize() const { return usedSize_; }

void Chunk::SetUsedSize(size_t size) { usedSize_ = size; }

size_t Chunk::GetFreeSize() const { return bufferSize_ - usedSize_; }

size_t Chunk::GetBufferSize() const { return bufferSize_; }

ChunkPool::ChunkPool(size_t poolSize, size_t chunkSize) : ResourcePool<Chunk, size_t>(poolSize, chunkSize) {}

ChunkPool::~ChunkPool() {}
} // namespace memory
} // namespace common
} // namespace dvvp
} // namespace analysis
