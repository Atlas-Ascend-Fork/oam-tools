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
#ifndef ANALYSIS_DVVP_TRANSPORT_UPLOADER_MGR_H
#define ANALYSIS_DVVP_TRANSPORT_UPLOADER_MGR_H

#include <atomic>
#include "config/config.h"
#include "message/prof_params.h"
#include "singleton/singleton_tool.h"
#include "uploader_tool.h"
#include "prof_common.h"

namespace analysis {
namespace dvvp {
namespace transport {
constexpr uint32_t WAIT_CLEAR_UPLOADER_TIME = 20000; // 20ms
struct FileDataParams {
    std::string fileName;
    bool isLastChunk;
    analysis::dvvp::common::config::FileChunkDataModule mode;
    FileDataParams(
        const std::string& fileNameStr, bool isLastChunkB, analysis::dvvp::common::config::FileChunkDataModule modeE)
        : fileName(fileNameStr), isLastChunk(isLastChunkB), mode(modeE)
    {}
};
class UploaderMgr : public analysis::dvvp::common::singleton::Singleton<UploaderMgr> {
public:
    UploaderMgr();
    ~UploaderMgr() override;

    int32_t Init() const;
    int32_t Uninit();

    int32_t CreateUploader(
        const std::string& id, SHARED_PTR_ALIA<ITransport> transport,
        size_t queueSize = analysis::dvvp::common::config::UPLOADER_QUEUE_CAPACITY);
    void AddUploader(const std::string& id, SHARED_PTR_ALIA<Uploader> uploader);
    void GetUploader(const std::string& id, SHARED_PTR_ALIA<Uploader>& uploader);
    void DelUploader(const std::string& id);
    void DelAllUploader();
    void SetAllUploaderTransportStopped();
    int32_t SetAllUploaderRegisterPipeTransportCallback(MsprofRawDataCallback callback);
    int32_t SetAllUploaderUnRegisterPipeTransportCallback();
    void RegisterAllUploaderTransportGenHashIdFuncPtr(HashDataGenIdFuncPtr* ptr);

    int32_t UploadData(const std::string& id, CONST_VOID_PTR data, uint32_t dataLen);
    int32_t UploadData(const std::string& id, SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    int32_t UploadCtrlFileData(
        const std::string& id, const std::string& data, const struct FileDataParams& fileDataParams,
        SHARED_PTR_ALIA<analysis::dvvp::message::JobContext> jobCtx) const;
    void AddMapByDevIdMode(int32_t devId, const std::string& mode, const std::string& jobId);
    std::string GetJobId(int32_t devId, const std::string& mode);
    void SetUploadDataIfStart(bool ifStart);

private:
    bool IsUploadDataStart(const std::string& dataDeviceId, const std::string& dataFileName);

private:
    std::map<std::string, SHARED_PTR_ALIA<Uploader>> uploaderMap_;
    std::mutex uploaderMutex_;
    std::map<std::string, std::string> devModeJobMap_;
    std::atomic<bool> isUploadStart_{true};
};
} // namespace transport
} // namespace dvvp
} // namespace analysis
#endif
