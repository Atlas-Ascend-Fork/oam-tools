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

#ifndef ANALYSIS_DVVP_COMMON_PIPE_TRANSPORT_H
#define ANALYSIS_DVVP_COMMON_PIPE_TRANSPORT_H

#include "utils/utils_tool.h"
#include "transport_tool.h"

namespace analysis {
namespace dvvp {
namespace transport {
class MsptiPipeTransport : public ITransport {
public:
    // using the existing session
    explicit MsptiPipeTransport();
    ~MsptiPipeTransport() override;

public:
    int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) override;
    int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) override;
    int32_t CloseSession() override;
    void WriteDone() override;
    void RegisterRawDataCallback(MsprofRawDataCallback callback) override;
    void UnRegisterRawDataCallback() override;
    bool IsRegisterRawDataCallback() override;
    int32_t ConvertFileChunkToRawData(
        SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq, MsprofRawData& rawData) const;

private:
    MsprofRawDataCallback profRawDataCallback_;
};

class MsptiPipeTransportFactory {
public:
    explicit MsptiPipeTransportFactory();
    ~MsptiPipeTransportFactory();

public:
    SHARED_PTR_ALIA<ITransport> CreateMsptiPipeTransport() const;
};

} // namespace transport
} // namespace dvvp
} // namespace analysis

#endif
