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
#ifndef ANALYSIS_DVVP_TASKHANDLE_TASK_RELATIONSHIP_MGR_H
#define ANALYSIS_DVVP_TASKHANDLE_TASK_RELATIONSHIP_MGR_H

#include <map>
#include <memory>
#include <set>
#include <vector>
#include "singleton/singleton_tool.h"

namespace Analysis {
namespace Dvvp {
namespace TaskHandle {
class TaskRelationshipMgr : public analysis::dvvp::common::singleton::Singleton<TaskRelationshipMgr> {
public:
    // device id - host id
    void AddHostIdDevIdRelationship(int32_t hostId, int32_t devId);
    int32_t GetDevIdByHostId(int32_t hostId);
    int32_t GetHostIdByDevId(int32_t devId);
    void AddLocalFlushJobId(const std::string& jobId);
    int32_t GetFlushSuffixDevId(const std::string& jobId, int32_t indexId);

private:
    std::mutex hostIdMapMutex_;
    std::map<int32_t, int32_t> hostIdToDevId_;
    std::set<std::string> localFlushJobIds_;
};
} // namespace TaskHandle
} // namespace Dvvp
} // namespace Analysis

#endif
