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

#ifndef ANALYSIS_DVVP_COMMON_THREAD_THREAD_H
#define ANALYSIS_DVVP_COMMON_THREAD_THREAD_H

#include <thread>
#include "osal.h"
#include "utils/utils_tool.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace thread {
using namespace analysis::dvvp::common::utils;
class Thread {
public:
    Thread();
    virtual ~Thread();

    virtual int32_t Start();
    virtual int32_t Stop();
    virtual void StopNoWait() { quit_ = true; };
    int32_t Join();
    bool IsQuit() const;
    void SetThreadName(const std::string& threadName);
    const std::string& GetThreadName() const;

protected:
    virtual void Run(const error_message::ErrorManagerContext& errorContext) = 0;

private:
    static void* ThrProcess(VOID_PTR arg);

    OsalThread tid_;
    volatile bool quit_;
    volatile bool isStarted_;
    std::string threadName_;
    error_message::ErrorManagerContext errorContext_;
};
} // namespace thread
} // namespace common
} // namespace dvvp
} // namespace analysis

#endif
