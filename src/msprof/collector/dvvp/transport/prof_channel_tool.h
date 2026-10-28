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
#ifndef ANALYSIS_DVVP_TRANSPORT_PROF_CHANNEL_H
#define ANALYSIS_DVVP_TRANSPORT_PROF_CHANNEL_H

#include <map>
#include <memory>
#include <mutex>
#include <atomic>
#include "ai_drv_dev_api.h"
#include "ai_drv_prof_api.h"
#include "message/prof_params.h"
#include "statistics/perf_count_tool.h"
#include "thread/thread_tool.h"
#include "thread/thread_pool_tool.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace Analysis::Dvvp::Common::Statistics;

class ChannelBuffer : public analysis::dvvp::common::thread::Thread {
public:
    ChannelBuffer();
    ~ChannelBuffer() override;
    int32_t Start() override;
    int32_t Stop() override;
    bool SwapChannelBuffer(std::string& buffer);

protected:
    void Run(const error_message::ErrorManagerContext& errorContext) override;

private:
    std::queue<std::string> preBufferQueue_;
    volatile bool isStart_;
    uint32_t bufferPrepareCount_;
    uint32_t bufferPopCount_;
    std::mutex preQueueMutex_;
};

class ChannelReader : public analysis::dvvp::common::thread::Task {
public:
    ChannelReader(
        int32_t deviceId, analysis::dvvp::driver::AI_DRV_CHANNEL channelId, const std::string& relativeFileName,
        SHARED_PTR_ALIA<analysis::dvvp::message::JobContext> jobCtx);
    virtual ~ChannelReader();

    int32_t Execute() final;
    size_t HashId() final;

    int32_t Init();
    int32_t Uinit();
    void UploadData();
    void FlushBuffToUpload();
    void SetChannelStopped();
    bool GetSchedulingStatus();
    void SetSchedulingStatus(bool isScheduling);
    void FlushDrvBuff();
    void CheckIfSendFlush(const size_t curLen);
    void SendFlushFinished();
    void RegisterBufferThread(SHARED_PTR_ALIA<ChannelBuffer> channelBuffer);

private:
    bool IsSupportFlushDrvBuff();

private:
    int32_t deviceId_;
    analysis::dvvp::driver::AI_DRV_CHANNEL channelId_;
    std::string relativeFileName_;
    uint32_t bufSize_;
    uint32_t dataSize_;
    uint32_t spaceSize_;
    std::string buffer_;
    size_t hashId_;
    SHARED_PTR_ALIA<analysis::dvvp::message::JobContext> jobCtx_;
    long long totalSize_;
    volatile bool isChannelStopped_;
    volatile bool isInited_;
    SHARED_PTR_ALIA<PerfCount> readSpeedPerfCount_;
    SHARED_PTR_ALIA<PerfCount> overallReadSpeedPerfCount_;
    uint64_t lastEndRawTime_;
    uint64_t drvChannelReadCont_;
    std::mutex mtx_;
    std::atomic<uint32_t> schedulingTime_;
    uint32_t totalSchedulingInCnt_;
    uint32_t totalSchedulingOutCnt_;
    // flush
    bool needWait_;
    uint32_t flushBufSize_;
    uint32_t flushCurSize_;
    uint32_t readExecCnt_;
    std::mutex flushMutex_;
    std::condition_variable flushFlag_;
    uint64_t uploadDataMaxDuration_;
    SHARED_PTR_ALIA<ChannelBuffer> readerBuffer_;
};

class ChannelPoll : public analysis::dvvp::common::thread::Thread {
public:
    ChannelPoll();
    virtual ~ChannelPoll();

    int32_t AddReader(uint32_t devId, uint32_t channelId, SHARED_PTR_ALIA<ChannelReader> reader);
    int32_t RemoveReader(uint32_t devId, uint32_t channelId);
    SHARED_PTR_ALIA<ChannelReader> GetReader(uint32_t devId, uint32_t channelId);
    int32_t DispatchChannel(uint32_t devId, uint32_t channelId);
    void FlushDrvBuff();

    int32_t Start() override;
    int32_t Stop() override;

protected:
    void Run(const error_message::ErrorManagerContext& errorContext) override;

private:
    std::vector<SHARED_PTR_ALIA<ChannelReader>> GetAllReaders();
    void DispatchReader(SHARED_PTR_ALIA<ChannelReader> reader);

    SHARED_PTR_ALIA<analysis::dvvp::common::thread::ThreadPool> threadPool_;
    SHARED_PTR_ALIA<ChannelBuffer> threadBuffer_;
    std::map<uint32_t, std::map<uint32_t, SHARED_PTR_ALIA<ChannelReader>>> readers_;
    std::mutex mtx_;
    volatile bool isStart_;
    uint32_t pollCount_;
    uint32_t pollSleepCount_;
    uint32_t dispatchCount_;
    uint32_t dispatchChannelCount_;
};
} // namespace transport
} // namespace dvvp
} // namespace analysis

#endif
