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
#ifndef COLLECTOR_DVVP_ACP_COMPUTE_DEVICE_JOB_H
#define COLLECTOR_DVVP_ACP_COMPUTE_DEVICE_JOB_H

#include <array>
#include "collection_register_tool.h"
#include "job_adapter_tool.h"
#include "uploader_mgr_tool.h"

namespace Collector {
namespace Dvvp {
namespace Acp {
using namespace Analysis::Dvvp::JobWrapper;
class AcpComputeDeviceJob : public JobAdapter {
public:
    explicit AcpComputeDeviceJob(int32_t devIndexId);
    ~AcpComputeDeviceJob() override;

public:
    int32_t StartProf(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) override;
    int32_t StopProf(void) override;

private:
    int32_t CreateCollectionJobArray();
    int32_t CreateAcpCollectionJobArray();
    int32_t DoCreateCollectionJobArray();
    int32_t RegisterCollectionJobs();
    void UnRegisterCollectionJobs();
    int32_t ParseAiCoreConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParseAivConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParsePmuConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    std::string GenerateFileName(const std::string& fileName);
    int32_t StartProfHandle(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);

private:
    int32_t devIndexId_;
    bool isStarted_;
    std::string tmpResultDir_;
    std::string jobId_;
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params_;
    SHARED_PTR_ALIA<CollectionJobCommonParams> collectionJobCommCfg_;
    std::array<CollectionJobT, NR_MAX_COLLECTION_JOB> collectionJobV_;
    std::set<int32_t> jobUsed_;
};
} // namespace Acp
} // namespace Dvvp
} // namespace Collector
#endif
