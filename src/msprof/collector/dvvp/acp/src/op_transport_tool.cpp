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
#include "op_transport_tool.h"
#include "errno/error_code_tool.h"
#include "msprof_dlog_tool.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;

OpTransport::OpTransport()
{
    MSVP_MAKE_SHARED0(analyzer_, Dvvp::Acp::Analyze::OpAnalyzer, return);
    MSPROF_LOGI("OpTransport create successfully.");
}

OpTransport::~OpTransport() {}

int32_t OpTransport::SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq)
{
    if (analyzer_ == nullptr) {
        MSPROF_LOGW("Analyzer is not init.");
        return PROFILING_FAILED;
    }

    analyzer_->OnOpData(fileChunkReq);
    return PROFILING_SUCCESS;
}

int32_t OpTransport::SendBuffer(CONST_VOID_PTR buffer, int32_t length)
{
    UNUSED(buffer);
    UNUSED(length);
    return PROFILING_SUCCESS;
}

int32_t OpTransport::CloseSession() { return PROFILING_SUCCESS; }

void OpTransport::WriteDone()
{
    if (analyzer_ == nullptr) {
        MSPROF_LOGW("Analyzer is not init.");
        return;
    }

    analyzer_->WaitOpDone();
}

void OpTransport::SetDevId(const std::string& deviceId)
{
    if (analyzer_ == nullptr) {
        MSPROF_LOGW("Analyzer is not init.");
        return;
    }

    analyzer_->InitAnalyzerByDeviceId(deviceId);
}

SHARED_PTR_ALIA<ITransport> OpTransportFactory::CreateOpTransport(const std::string& deviceId) const
{
    SHARED_PTR_ALIA<OpTransport> transport = nullptr;
    MSVP_MAKE_SHARED0(transport, OpTransport, return transport);
    transport->SetDevId(deviceId);
    return transport;
}
} // namespace transport
} // namespace dvvp
} // namespace analysis
