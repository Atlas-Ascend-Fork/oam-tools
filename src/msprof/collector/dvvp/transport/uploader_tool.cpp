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

#include "uploader_tool.h"
#include "config/config.h"
#include "errno/error_code_tool.h"
#include "msprof_dlog_tool.h"
#include "utils/utils_tool.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;
using namespace Analysis::Dvvp::MsprofErrMgr;

Uploader::Uploader(SHARED_PTR_ALIA<analysis::dvvp::transport::ITransport> transport)
    : transport_(transport), queue_(nullptr), isInited_(false), forceQuit_(false), isStopped_(false)
{}

Uploader::~Uploader() { Uinit(); }

int32_t Uploader::Init(size_t size)
{
    int32_t ret = PROFILING_FAILED;

    do {
        MSVP_MAKE_SHARED1_NODO(queue_, UploaderQueue, size, break);
        queue_->SetQueueName(UPLOADER_QUEUE_NAME);
        isInited_ = true;

        ret = PROFILING_SUCCESS;
    } while (0);

    return ret;
}

int32_t Uploader::Uinit()
{
    MSPROF_LOGD("Uploader Uninit, isInited_:%d.", (isInited_ ? 1 : 0));
    if (isInited_) {
        (void)Stop(true);
        transport_.reset();
        if (pipeTransport_ != nullptr) {
            pipeTransport_->CloseSession();
            pipeTransport_->WriteDone();
        }
        isInited_ = false;
    }

    return PROFILING_SUCCESS;
}

int32_t Uploader::UploadData(CONST_VOID_PTR data, int32_t len)
{
    if (!isInited_) {
        MSPROF_LOGE("Uploader was not inited.");
        MSPROF_INNER_ERROR("EK9999", "Uploader was not inited.");
        return PROFILING_FAILED;
    }

    if (data == nullptr) {
        MSPROF_LOGE("[Uploader::UploadData]data is nullptr.");
        MSPROF_INNER_ERROR("EK9999", "data is nullptr.");
        return PROFILING_FAILED;
    }

    SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq;
    MSVP_MAKE_SHARED0(fileChunkReq, analysis::dvvp::ProfileFileChunk, return PROFILING_FAILED);
    fileChunkReq->chunk = std::string(reinterpret_cast<CHAR_PTR>(const_cast<VOID_PTR>(data)), len);
    fileChunkReq->chunkSize = len;
    fileChunkReq->chunkModule = FileChunkDataModule::PROFILING_IS_FROM_INNER;
    return UploadData(fileChunkReq);
}

int32_t Uploader::UploadData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq)
{
    if (!isInited_) {
        MSPROF_LOGE("Uploader was not inited.");
        MSPROF_INNER_ERROR("EK9999", "Uploader was not inited.");
        return PROFILING_FAILED;
    }

    if (fileChunkReq == nullptr) {
        MSPROF_LOGE("[Uploader::UploadData]data is nullptr.");
        MSPROF_INNER_ERROR("EK9999", "data is nullptr.");
        return PROFILING_FAILED;
    }
    if (!queue_->Push(fileChunkReq)) {
        MSPROF_LOGE("[Uploader::UploadData]Push data failed.");
        MSPROF_INNER_ERROR("EK9999", "Push data failed.");
        return PROFILING_FAILED;
    }

    return PROFILING_SUCCESS;
}

void Uploader::Run(const error_message::ErrorManagerContext& errorContext)
{
    MsprofErrorManager::instance()->SetErrorContext(errorContext);
    if (!isInited_) {
        MSPROF_LOGE("Uploader was not inited.");
        MSPROF_INNER_ERROR("EK9999", "Uploader was not inited.");
        return;
    }

    do {
        SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq = nullptr;
        if (!queue_->TryPop(fileChunkReq) && Thread::IsQuit()) {
            break;
        }
        if (fileChunkReq == nullptr) {
            (void)queue_->Pop(fileChunkReq);
        }
        if (fileChunkReq == nullptr) {
            continue;
        }
        // send the data
        if (fileChunkReq->chunkModule == FileChunkDataModule::PROFILING_IS_FROM_INNER) {
            const int32_t sentLen = transport_->SendBuffer(fileChunkReq->chunk.c_str(), fileChunkReq->chunkSize);
            if (pipeTransport_ != nullptr && pipeTransport_->IsRegisterRawDataCallback()) {
                pipeTransport_->SendBuffer(fileChunkReq->chunk.c_str(), fileChunkReq->chunkSize);
            }
            if (sentLen != static_cast<int32_t>(fileChunkReq->chunkSize)) {
                MSPROF_LOGE(
                    "Failed to upload data, data_len=%zu bytes, sent len=%d bytes", fileChunkReq->chunkSize, sentLen);
                MSPROF_INNER_ERROR(
                    "EK9999", "Failed to upload data, data_len=%zu bytes, sent len=%d bytes", fileChunkReq->chunkSize,
                    sentLen);
            }
        } else {
            if (transport_->SendBuffer(fileChunkReq) != PROFILING_SUCCESS) {
                MSPROF_LOGE("Failed to upload data");
                MSPROF_INNER_ERROR("EK9999", "Failed to upload data");
            }
            if (pipeTransport_ != nullptr && pipeTransport_->IsRegisterRawDataCallback()) {
                int32_t ret = pipeTransport_->SendBuffer(fileChunkReq);
                if (ret != PROFILING_SUCCESS) {
                    MSPROF_LOGE("PipeTransport failed to upload raw data");
                }
            }
        }
    } while (!forceQuit_);

    MSPROF_LOGI("queue size remaining: %zu, force_quit:%d", queue_->Size(), (forceQuit_ ? 1 : 0));
}

// Before you invoke stop, all data should already been enqueued
int32_t Uploader::Stop(bool force)
{
    if (!isStopped_ && isInited_) {
        isStopped_ = true;
        forceQuit_ = force;

        MSPROF_LOGI("Stopping uploader, force_quit:%d.", (forceQuit_ ? 1 : 0));

        queue_->Quit();
        int32_t ret = Thread::Stop();
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("Failed to stop uploader");
            MSPROF_INNER_ERROR("EK9999", "Failed to stop uploader");
        }
    }

    return PROFILING_SUCCESS;
}

void Uploader::SetTransportStopped() { transport_->SetStopped(); }

void Uploader::SetPipeTransport(SHARED_PTR_ALIA<ITransport> trans) { pipeTransport_ = trans; }

int32_t Uploader::RegisterPipeTransportCallback(MsprofRawDataCallback callback)
{
    if (pipeTransport_ == nullptr) {
        MSPROF_LOGD("pipeTransport_ is null");
        return PROFILING_FAILED;
    }
    pipeTransport_->RegisterRawDataCallback(callback);
    MSPROF_LOGD("PipeTransport register raw data callback done");
    return PROFILING_SUCCESS;
}

int32_t Uploader::UnRegisterPipeTransportCallback()
{
    if (pipeTransport_ == nullptr) {
        MSPROF_LOGD("pipeTransport_ is null");
        return PROFILING_FAILED;
    }
    pipeTransport_->UnRegisterRawDataCallback();
    MSPROF_LOGD("UnRegisterPipeTransportCallback done");
    return PROFILING_SUCCESS;
}

void Uploader::RegisterTransportGenHashIdFuncPtr(HashDataGenIdFuncPtr* ptr)
{
    transport_->RegisterHashDataGenIdFuncPtr(ptr);
}

// wait all data to send
void Uploader::Flush() const
{
    while (queue_->Size() != 0) {
        const unsigned long UPLOADER_SLEEP_TIME_IN_US = 100000;
        analysis::dvvp::common::utils::Utils::UsleepInterupt(UPLOADER_SLEEP_TIME_IN_US);
    }
}

SHARED_PTR_ALIA<analysis::dvvp::transport::ITransport> Uploader::GetTransport() { return transport_; }
} // namespace transport
} // namespace dvvp
} // namespace analysis
