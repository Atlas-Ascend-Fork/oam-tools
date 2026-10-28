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

#ifndef ANALYSIS_DVVP_COMMON_TRANSPORT_H
#define ANALYSIS_DVVP_COMMON_TRANSPORT_H

#include <condition_variable>
#include <memory>
#include "statistics/perf_count_tool.h"
#include "utils/utils_tool.h"
#include "prof_common.h"

using HashDataGenIdFuncPtr = uint64_t(const std::string& hashInfo);

namespace analysis {
namespace dvvp {
namespace transport {
using namespace Analysis::Dvvp::Common::Statistics;
using namespace analysis::dvvp::common::utils;
class ITransport {
public:
    explicit ITransport() : perfCount_(nullptr) {}
    virtual ~ITransport() {}

public:
    virtual int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) = 0;
    virtual int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) = 0;
    virtual int32_t CloseSession() = 0;
    virtual void WriteDone() = 0;
    virtual void SetDevId(const std::string& /* devIdStr */) {};
    virtual void SetType(const uint32_t /* type */) {};
    virtual void SetHelperDir(const std::string& /* id */, const std::string& /* helperPath */) {};
    virtual void SetStopped() {};
    virtual void RegisterHashDataGenIdFuncPtr(HashDataGenIdFuncPtr*) {};
    virtual void RegisterRawDataCallback(MsprofRawDataCallback){};
    virtual bool IsRegisterRawDataCallback() { return false; };
    virtual void UnRegisterRawDataCallback() {};

public:
    SHARED_PTR_ALIA<PerfCount> perfCount_; // calculate statistics
};

class TransportFactory {
public:
    TransportFactory() {}
    virtual ~TransportFactory() {}

public:
    SHARED_PTR_ALIA<ITransport> CreateIdeTransport(IDE_SESSION session);
};
} // namespace transport
} // namespace dvvp
} // namespace analysis

#endif
