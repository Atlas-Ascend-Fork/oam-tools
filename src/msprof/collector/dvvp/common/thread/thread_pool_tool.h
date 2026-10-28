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

#ifndef ANALYSIS_DVVP_COMMON_THREAD_THREAD_POOL_H
#define ANALYSIS_DVVP_COMMON_THREAD_THREAD_POOL_H

#include <atomic>
#include <condition_variable>
#include <memory>
#include <string>

#include "errno/error_code_tool.h"
#include "msprof_dlog_tool.h"
#include "queue/bound_queue_tool.h"
#include "thread_tool.h"
#include "utils/utils_tool.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace thread {
class Task {
public:
    virtual ~Task() {}

    virtual int32_t Execute() = 0;
    virtual size_t HashId() = 0;
};

using TaskQueue = analysis::dvvp::common::queue::BoundQueue<SHARED_PTR_ALIA<Task>>;

enum class LOAD_BALANCE_METHOD { ROUND_ROBIN = 0, ID_MOD = 1 };

const uint32_t THREAD_NUM_DEFAULT = 4;
class ThreadPool {
public:
    explicit ThreadPool(
        LOAD_BALANCE_METHOD method = LOAD_BALANCE_METHOD::ID_MOD, uint32_t threadNum = THREAD_NUM_DEFAULT);
    virtual ~ThreadPool();

    void SetThreadPoolNamePrefix(const std::string& name);
    void SetThreadPoolQueueSize(const size_t queueSize);
    int32_t Start();
    int32_t Stop();
    int32_t Dispatch(const SHARED_PTR_ALIA<Task> task);

private:
    class InnnerThread : public Thread {
        friend class ThreadPool;

    public:
        explicit InnnerThread(size_t queueSize) : started_(false), queue_(nullptr), queueSize_(queueSize) {}
        virtual ~InnnerThread() { (void)Stop(); }

        const SHARED_PTR_ALIA<TaskQueue> GetQueue() { return queue_; }

        int32_t Start() override
        {
            MSVP_MAKE_SHARED1(queue_, TaskQueue, queueSize_, return analysis::dvvp::common::error::PROFILING_FAILED);
            auto threadName = GetThreadName();
            queue_->SetQueueName(threadName);
            if (Thread::Start() != analysis::dvvp::common::error::PROFILING_SUCCESS) {
                return analysis::dvvp::common::error::PROFILING_FAILED;
            }

            started_ = true;

            return analysis::dvvp::common::error::PROFILING_SUCCESS;
        }

        int32_t Stop() override
        {
            if (started_) {
                started_ = false;
                queue_->Quit();
                return Thread::Stop();
            }

            return analysis::dvvp::common::error::PROFILING_SUCCESS;
        }

    protected:
        void Run(const error_message::ErrorManagerContext& errorContext) override
        {
            Analysis::Dvvp::MsprofErrMgr::MsprofErrorManager::instance()->SetErrorContext(errorContext);
            for (;;) {
                SHARED_PTR_ALIA<Task> task;
                if ((!queue_->TryPop(task)) && (Thread::IsQuit())) {
                    break;
                }

                if (!task) {
                    (void)queue_->Pop(task);
                }

                if (task) {
                    (void)task->Execute();
                }
            }
        }

    private:
        volatile bool started_;
        SHARED_PTR_ALIA<TaskQueue> queue_;
        size_t queueSize_;
    };

    uint32_t threadNum_;
    std::atomic_uint currIndex_;
    LOAD_BALANCE_METHOD balancerMethod_;
    volatile bool isStarted_;
    std::vector<SHARED_PTR_ALIA<ThreadPool::InnnerThread>> threads_;
    std::string threadPoolNamePrefix_;
    size_t threadPoolQueueSize_;
};
} // namespace thread
} // namespace common
} // namespace dvvp
} // namespace analysis

#endif
