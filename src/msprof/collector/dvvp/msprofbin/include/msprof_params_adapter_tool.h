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

#ifndef ANALYSIS_DVVP_MSPROFBIN_PARAMS_ADAPTER_H
#define ANALYSIS_DVVP_MSPROFBIN_PARAMS_ADAPTER_H
#include "singleton/singleton_tool.h"
#include "message/prof_params.h"
#include "utils/utils_tool.h"
namespace Analysis {
namespace Dvvp {
namespace Msprof {
class MsprofParamsAdapter : public analysis::dvvp::common::singleton::Singleton<MsprofParamsAdapter> {
public:
    MsprofParamsAdapter();
    ~MsprofParamsAdapter() override;
    int32_t Init() const;
    void GenerateLlcEvents(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
    int32_t UpdateParams(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;

private:
    std::string GenerateCapacityEvents() const;
    std::string GenerateBandwidthEvents() const;
    void GenerateLlcDefEvents(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;

private:
    std::map<std::string, std::string> aicoreEvents_;
};
} // namespace Msprof
} // namespace Dvvp
} // namespace Analysis

#endif
