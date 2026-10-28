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
#ifndef ANALYSIS_DVVP_COMMON_MEMORY_CHUNK_POOL_H
#define ANALYSIS_DVVP_COMMON_MEMORY_CHUNK_POOL_H
#include <condition_variable>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include "utils/utils_tool.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace memory {
class Chunk {
public:
    explicit Chunk(size_t bufferSize);
    virtual ~Chunk();

    bool Init();
    void Uninit();

    void Clear();
    uint8_t* GetBuffer() const;

    size_t GetUsedSize() const;
    void SetUsedSize(size_t size);

    size_t GetFreeSize() const;
    size_t GetBufferSize() const;

private:
    Chunk& operator=(const Chunk& chunk);
    Chunk(const Chunk& chunk);

    unsigned char* buffer_;
    size_t bufferSize_;
    size_t usedSize_;
};

template <class T, class ArgT>
class PoolBase {
public:
    explicit PoolBase(size_t poolSize, ArgT resArg) : poolSize_(poolSize), resArg_(resArg) {}
    virtual ~PoolBase() {}

    bool Init()
    {
        if (poolSize_ == 0) {
            return false;
        }

        for (size_t ii = 0; ii < poolSize_; ++ii) {
            auto res = AllocResource(resArg_);
            if (!res) {
                break;
            }

            freed_.push_back(res);
        }

        return (poolSize_ == freed_.size()) ? true : false;
    }

protected:
    size_t poolSize_;
    ArgT resArg_;
    std::list<SHARED_PTR_ALIA<T>> freed_;

private:
    SHARED_PTR_ALIA<T> AllocResource(ArgT arg) const
    {
        SHARED_PTR_ALIA<T> res;

        do {
            MSVP_MAKE_SHARED1_NODO(res, T, arg, break);
            if (!(res->Init())) {
                res.reset();
            }
        } while (0);

        return res;
    }
};

template <class T, class ArgT>
class ResourcePool : public PoolBase<T, ArgT> {
public:
    explicit ResourcePool(size_t poolSize, ArgT resArg) : PoolBase<T, ArgT>(poolSize, resArg) {}

    ~ResourcePool() override { Uninit(); }

    void Uninit()
    {
        std::unique_lock<std::mutex> lk(mtx_);
        this->freed_.clear();
        used_.clear();
    }

    SHARED_PTR_ALIA<T> Alloc()
    {
        std::unique_lock<std::mutex> lk(mtx_);

        cvFree_.wait(lk, [this] { return !this->freed_.empty(); });

        auto res = this->freed_.front();
        this->freed_.pop_front();
        used_[reinterpret_cast<uintptr_t>(res.get())] = res;

        return res;
    }

    SHARED_PTR_ALIA<T> TryAlloc()
    {
        std::lock_guard<std::mutex> lk(mtx_);

        if (this->freed_.empty()) {
            return nullptr;
        }

        auto res = this->freed_.front();
        this->freed_.pop_front();
        used_[reinterpret_cast<uintptr_t>(res.get())] = res;

        return res;
    }

    void Release(SHARED_PTR_ALIA<T> res)
    {
        std::lock_guard<std::mutex> lk(mtx_);

        if (res) {
            auto iter = used_.find(reinterpret_cast<uintptr_t>(res.get()));
            if (iter != used_.end()) {
                used_.erase(iter);
                this->freed_.push_back(res);

                cvFree_.notify_all();
            }
        }
    }

private:
    std::map<uintptr_t, SHARED_PTR_ALIA<T>> used_;
    std::condition_variable cvFree_;
    std::mutex mtx_;
};

class ChunkPool : public ResourcePool<Chunk, size_t> {
public:
    ChunkPool(size_t poolSize, size_t chunkSize);
    ~ChunkPool() override;
};
} // namespace memory
} // namespace common
} // namespace dvvp
} // namespace analysis

#endif
