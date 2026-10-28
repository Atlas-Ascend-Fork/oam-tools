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

#ifndef ANALYSIS_DVVP_TRANSPORT_UPLOADER_H
#define ANALYSIS_DVVP_TRANSPORT_UPLOADER_H

#include <cstddef>
#include "config/config.h"
#include "queue/bound_queue_tool.h"
#include "thread/thread_tool.h"
#include "transport/transport_tool.h"
#include "prof_common.h"

namespace analysis {
namespace dvvp {
namespace transport {
using UploaderQueue = analysis::dvvp::common::queue::BoundQueue<SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> >;
class Uploader : public analysis::dvvp::common::thread::Thread {
    using analysis::dvvp::common::thread::Thread::Stop;

public:
    explicit Uploader(SHARED_PTR_ALIA<ITransport> transport);

    virtual ~Uploader();

public:
    int32_t Init(size_t size = analysis::dvvp::common::config::UPLOADER_QUEUE_CAPACITY);
    int32_t Uinit();
    int32_t UploadData(CONST_VOID_PTR data, int32_t len);
    int32_t UploadData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    int32_t Stop(bool force);
    void SetTransportStopped();
    void SetPipeTransport(SHARED_PTR_ALIA<ITransport> trans);
    int32_t RegisterPipeTransportCallback(MsprofRawDataCallback callback);
    int32_t UnRegisterPipeTransportCallback();
    void RegisterTransportGenHashIdFuncPtr(HashDataGenIdFuncPtr* ptr);
    void Flush() const;
    void CloseTransport();
    SHARED_PTR_ALIA<ITransport> GetTransport();

protected:
    void Run(const error_message::ErrorManagerContext& errorContext) override;

private:
    SHARED_PTR_ALIA<ITransport> transport_;
    SHARED_PTR_ALIA<ITransport> pipeTransport_;
    SHARED_PTR_ALIA<UploaderQueue> queue_;
    bool isInited_;
    volatile bool forceQuit_;
    volatile bool isStopped_;
};
} // namespace transport
} // namespace dvvp
} // namespace analysis

#endif
