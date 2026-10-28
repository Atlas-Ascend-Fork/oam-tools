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

#ifndef ANALYSIS_DVVP_MSPROFBIN_MSPROF_MANAGER_H
#define ANALYSIS_DVVP_MSPROFBIN_MSPROF_MANAGER_H
#include "singleton/singleton_tool.h"
#include "message/prof_params.h"
#include "running_mode_tool.h"

namespace Analysis {
namespace Dvvp {
namespace Msprof {

class MsprofManager : public analysis::dvvp::common::singleton::Singleton<MsprofManager> {
public:
    MsprofManager();
    ~MsprofManager() override;
    int32_t Init(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    int32_t UnInit();
    void NotifyStop();
    int32_t MsProcessCmd() const;

    SHARED_PTR_ALIA<Collector::Dvvp::Msprofbin::RunningMode> rMode_;

private:
    int32_t GenerateRunningMode();
    int32_t GenerateCollectRunningMode();
    int32_t GenerateAnalyzeRunningMode();
    // check params dependence and update metrics and events
    int32_t ParamsCheck() const;

    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params_;
};
} // namespace Msprof
} // namespace Dvvp
} // namespace Analysis
#endif
