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
#ifndef DVVP_ACP_ANALYZE_TRANSPORT_H
#define DVVP_ACP_ANALYZE_TRANSPORT_H

#include "transport_tool.h"
#include "utils/utils_tool.h"
#include "op_analyzer_tool.h"

namespace analysis {
namespace dvvp {
namespace transport {
class OpTransport : public ITransport {
public:
    explicit OpTransport();
    ~OpTransport() override;

public:
    int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) override;
    int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) override;
    int32_t CloseSession() override;
    void WriteDone() override;
    void SetDevId(const std::string& deviceId) override;

private:
    SHARED_PTR_ALIA<Dvvp::Acp::Analyze::OpAnalyzer> analyzer_;
};

class OpTransportFactory {
public:
    OpTransportFactory() {}
    virtual ~OpTransportFactory() {}

public:
    SHARED_PTR_ALIA<ITransport> CreateOpTransport(const std::string& deviceId) const;
};
} // namespace transport
} // namespace dvvp
} // namespace analysis

#endif
