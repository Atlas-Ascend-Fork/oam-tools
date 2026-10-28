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
#include <string>
#include "task_relationship_mgr_tool.h"
#include "msprof_dlog_tool.h"

namespace Analysis {
namespace Dvvp {
namespace TaskHandle {
void TaskRelationshipMgr::AddHostIdDevIdRelationship(int32_t hostId, int32_t devId)
{
    MSPROF_LOGI("hostId: %d, devId: %d Entering HostId DeviceId Map...", hostId, devId);
    std::lock_guard<std::mutex> lock(hostIdMapMutex_);
    hostIdToDevId_[hostId] = devId;
}

int32_t TaskRelationshipMgr::GetDevIdByHostId(int32_t hostId)
{
    std::lock_guard<std::mutex> lock(hostIdMapMutex_);
    const auto iter = hostIdToDevId_.find(hostId);
    if (iter != hostIdToDevId_.end()) {
        return iter->second;
    }
    return hostId;
}

int32_t TaskRelationshipMgr::GetHostIdByDevId(int32_t devId)
{
    std::lock_guard<std::mutex> lock(hostIdMapMutex_);
    for (auto iter = hostIdToDevId_.begin(); iter != hostIdToDevId_.end(); iter++) {
        if (iter->second == devId) {
            return iter->first;
        }
    }
    return devId;
}

void TaskRelationshipMgr::AddLocalFlushJobId(const std::string& jobId)
{
    MSPROF_LOGI("Job %s should flush locally", jobId.c_str());
    (void)localFlushJobIds_.insert(jobId);
}

int32_t TaskRelationshipMgr::GetFlushSuffixDevId(const std::string& jobId, int32_t indexId)
{
    if (localFlushJobIds_.find(jobId) != localFlushJobIds_.end()) {
        return indexId;
    } else {
        return GetHostIdByDevId(indexId);
    }
}
} // namespace TaskHandle
} // namespace Dvvp
} // namespace Analysis
