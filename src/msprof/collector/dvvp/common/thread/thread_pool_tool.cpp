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

#include "thread_pool_tool.h"
#include "errno/error_code_tool.h"
#include "config/config.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace thread {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;

ThreadPool::ThreadPool(LOAD_BALANCE_METHOD method /* = ID_MOD */, uint32_t threadNum /* = 4 */)
    : threadNum_(threadNum),
      currIndex_(0),
      balancerMethod_(method),
      isStarted_(false),
      threadPoolNamePrefix_(""),
      threadPoolQueueSize_(THREAD_QUEUE_SIZE_DEFAULT)
{}

ThreadPool::~ThreadPool() { (void)Stop(); }

void ThreadPool::SetThreadPoolNamePrefix(const std::string& name) { threadPoolNamePrefix_ = name; }

void ThreadPool::SetThreadPoolQueueSize(const size_t queueSize) { threadPoolQueueSize_ = queueSize; }

int32_t ThreadPool::Start()
{
    if (threadNum_ == 0) {
        return PROFILING_FAILED;
    }

    for (uint32_t ii = 0; ii < threadNum_; ++ii) {
        SHARED_PTR_ALIA<ThreadPool::InnnerThread> thread;
        MSVP_MAKE_SHARED1(thread, ThreadPool::InnnerThread, threadPoolQueueSize_, return PROFILING_FAILED);

        std::string threadName = threadPoolNamePrefix_ + std::to_string(ii);
        thread->SetThreadName(threadName);
        int32_t ret = thread->Start();
        if (ret != PROFILING_SUCCESS) {
            continue;
        }
        threads_.push_back(thread);
    }

    isStarted_ = true;

    return PROFILING_SUCCESS;
}

int32_t ThreadPool::Stop()
{
    isStarted_ = false;
    for (auto iter = threads_.begin(); iter != threads_.end(); ++iter) {
        if ((*iter)->Stop() != PROFILING_SUCCESS) {
            MSPROF_LOGE("Failed to stop thread: %s", (*iter)->GetThreadName().c_str());
        }
    }
    threads_.clear();

    return PROFILING_SUCCESS;
}

int32_t ThreadPool::Dispatch(const SHARED_PTR_ALIA<Task> task)
{
    if (task == nullptr) {
        return PROFILING_FAILED;
    }
    if (!isStarted_) {
        return PROFILING_FAILED;
    }

    uint32_t threadIndex = 0;

    switch (balancerMethod_) {
        case LOAD_BALANCE_METHOD::ID_MOD:
            threadIndex = static_cast<uint32_t>(task->HashId()) % threadNum_;
            break;
        case LOAD_BALANCE_METHOD::ROUND_ROBIN:
        default:
            threadIndex = currIndex_++ % threadNum_;
            break;
    }

    (void)threads_[threadIndex]->GetQueue()->Push(task);

    return PROFILING_SUCCESS;
}
} // namespace thread
} // namespace common
} // namespace dvvp
} // namespace analysis
