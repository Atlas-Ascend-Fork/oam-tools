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
#ifndef ANALYSIS_DVVP_PROF_CHANNEL_MANAGER_H
#define ANALYSIS_DVVP_PROF_CHANNEL_MANAGER_H

#include <mutex>
#include "singleton/singleton_tool.h"
#include "transport/prof_channel_tool.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
class ProfChannelManager : public analysis::dvvp::common::singleton::Singleton<ProfChannelManager> {
    friend analysis::dvvp::common::singleton::Singleton<ProfChannelManager>;

public:
    ProfChannelManager();
    ~ProfChannelManager() override;
    int32_t Init();
    void UnInit(bool isReset = false);
    SHARED_PTR_ALIA<analysis::dvvp::transport::ChannelPoll> GetChannelPoller();
    void FlushChannel();

private:
    SHARED_PTR_ALIA<analysis::dvvp::transport::ChannelPoll> drvChannelPoll_;
    std::mutex channelPollMutex_;
    uint64_t index_;
};
} // namespace JobWrapper
} // namespace Dvvp
} // namespace Analysis

#endif
