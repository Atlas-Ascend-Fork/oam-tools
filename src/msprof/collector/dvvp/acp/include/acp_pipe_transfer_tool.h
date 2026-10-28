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
#ifndef ACP_PIPE_TRANSFER_H
#define ACP_PIPE_TRANSFER_H

#include "message/prof_params.h"

namespace Collector {
namespace Dvvp {
namespace Acp {
const int32_t ON_OFF_MAX_LEN = 4;
const int32_t AIC_CORE_METRICS_MAX_LEN = 256;
const int32_t RESULT_DIR_MAX_LEN = 512;
const int32_t AIC_SCALE_MAX_LEN = 10;
struct AcpPipeParams {
    char aicCoreMetrics[AIC_CORE_METRICS_MAX_LEN];
    char resultDir[RESULT_DIR_MAX_LEN];
    char aicScale[AIC_SCALE_MAX_LEN];
    char instrProfiling[ON_OFF_MAX_LEN];
    char pcSampling[ON_OFF_MAX_LEN];
};
int32_t AcpPipeWrite(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, int32_t& fdPipe);
SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> AcpPipeRead();
} // namespace Acp
} // namespace Dvvp
} // namespace Collector
#endif
