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

#include "prof_channel_manager_tool.h"
#include "errno/error_code_tool.h"
#include "transport/prof_channel_tool.h"
#include "utils/utils_tool.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::transport;

ProfChannelManager::ProfChannelManager() : index_(0) {}

ProfChannelManager::~ProfChannelManager() {}

int32_t ProfChannelManager::Init()
{
    std::lock_guard<std::mutex> lock(channelPollMutex_);
    index_++;
    MSPROF_LOGI("ProfChannelManager Init index:%" PRIu64, index_);
    if (drvChannelPoll_ != nullptr) {
        MSPROF_LOGI("ProfChannelManager already inited");
        return PROFILING_SUCCESS;
    }
    MSVP_MAKE_SHARED0(drvChannelPoll_, ChannelPoll, return PROFILING_FAILED);
    int32_t ret = drvChannelPoll_->Start();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGW("drvChannelPoll start thread pool result, ret=%d", ret);
        return ret;
    }
    MSPROF_LOGI("Init Poll Succ");
    return PROFILING_SUCCESS;
}

SHARED_PTR_ALIA<ChannelPoll> ProfChannelManager::GetChannelPoller()
{
    std::lock_guard<std::mutex> lock(channelPollMutex_);
    return drvChannelPoll_;
}

void ProfChannelManager::UnInit(bool isReset)
{
    std::lock_guard<std::mutex> lock(channelPollMutex_);
    MSPROF_LOGI("ProfChannelManager UnInit index:%" PRIu64, index_);
    if (!isReset) {
        if (index_ == 0) {
            return;
        }
        index_--;
        if (index_ != 0) {
            return;
        }
    } else {
        index_ = 0;
    }
    if (drvChannelPoll_ != nullptr) {
        int32_t ret = drvChannelPoll_->Stop();
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("drvChannelPoll_ stop failed");
        }
        drvChannelPoll_.reset();
        drvChannelPoll_ = nullptr;
    }

    MSPROF_LOGI("UnInit Poll Succ");
}

void ProfChannelManager::FlushChannel()
{
    if (drvChannelPoll_ != nullptr) {
        drvChannelPoll_->FlushDrvBuff();
    }
}
} // namespace JobWrapper
} // namespace Dvvp
} // namespace Analysis
