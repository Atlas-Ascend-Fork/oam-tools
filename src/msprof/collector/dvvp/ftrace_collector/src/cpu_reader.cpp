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
#include "cpu_reader.h"

#include "ftrace_path.h"

#include <fcntl.h>
#include <poll.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <mutex>
#include <vector>

#include "securec.h"

#include "file_owner.h"
#include "ftrace_constants.h"
#include "ftrace_log.h"

namespace Ftrace {
namespace {
constexpr int32_t POLL_TIMEOUT_MS = 50;
constexpr int32_t MAX_EMPTY_READS_ON_DRAIN = 2;

// ring_buffer_event header: u32 type_len:5, time_delta:27
constexpr uint32_t RB_TYPE_MASK = 0x1f;
constexpr size_t RB_EVENT_HDR_SIZE = 4; // sizeof(u32) event header, excluded from type_len
constexpr uint32_t RB_TYPE_PADDING = 29;
constexpr uint32_t RB_TYPE_TIME_EXTEND = 30;
constexpr uint32_t RB_TYPE_TIME_STAMP = 31;
// Kernel dependent lengths live in ftrace_types.h and are recorded in the meta json;
// the collector counts events with the same values it reports.
constexpr uint32_t RB_LEN_TIME_EXTEND = kTimeExtendLen;
constexpr uint32_t RB_LEN_TIME_STAMP = kTimeStampLen;
} // namespace

CpuReader::CpuReader(int32_t cpu, std::string traceRoot, std::string outputPath, size_t pageSize, size_t pageDataOffset)
    : cpu_(cpu),
      traceRoot_(std::move(traceRoot)),
      outputPath_(std::move(outputPath)),
      pageSize_(pageSize),
      pageDataOffset_(pageDataOffset)
{}

CpuReader::~CpuReader()
{
    RequestStop();
    if (thread_.joinable()) {
        thread_.join();
    }
    CloseFiles();
}

void CpuReader::Start()
{
    thread_ = std::thread([this]() { Run(); });
}

void CpuReader::RequestStop() { stopRequested_.store(true); }

void CpuReader::Join()
{
    if (thread_.joinable()) {
        thread_.join();
    }
}

CpuStats CpuReader::Snapshot() const
{
    CpuStats stats;
    stats.cpu = cpu_;
    stats.bytes = bytes_.load();
    stats.events = events_.load();
    {
        std::lock_guard<std::mutex> lock(errorMutex_);
        stats.error = error_;
        stats.ok = error_.empty();
    }
    return stats;
}

std::string CpuReader::Error() const
{
    std::lock_guard<std::mutex> lock(errorMutex_);
    return error_;
}

bool CpuReader::OpenFiles()
{
    const std::string rawPath =
        CanonicalizeFilePath(traceRoot_ + "/per_cpu/cpu" + std::to_string(cpu_) + "/trace_pipe_raw");
    rawFd_ = open(rawPath.c_str(), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (rawFd_ < 0) {
        std::lock_guard<std::mutex> lock(errorMutex_);
        error_ = "open " + rawPath + " failed: " + strerror(errno);
        return false;
    }
    const std::string outputPath = CanonicalizeFilePath(outputPath_);
    outFd_ = open(outputPath.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, kWriterFileMode);
    if (outFd_ < 0) {
        std::lock_guard<std::mutex> lock(errorMutex_);
        error_ = "open " + outputPath_ + " failed: " + strerror(errno);
        return false;
    }
    // Running under sudo makes this file root owned; the parser that reads it later runs as the
    // profiling user and would report "footer missing or invalid" for every cpu.
    GiveBackOwnership(outputPath_);
    return true;
}

void CpuReader::CloseFiles()
{
    if (rawFd_ >= 0) {
        close(rawFd_);
        rawFd_ = -1;
    }
    if (outFd_ >= 0) {
        close(outFd_);
        outFd_ = -1;
    }
}

namespace {
// Length of one ring_buffer_event on the page, and whether it carries a trace event.
// type_len*4 + header for data events; padding / type 0 store the payload length separately.
bool ClassifyEventLen(const uint8_t* page, size_t offset, size_t end, size_t& eventLen, bool& isEvent)
{
    eventLen = 0;
    isEvent = false;
    uint32_t header = 0;
    if (memcpy_s(&header, sizeof(header), page + offset, sizeof(header)) != EOK) {
        return false;
    }
    const uint32_t type = header & RB_TYPE_MASK;
    if (type == RB_TYPE_PADDING) {
        if (offset + kEventHdrWithLen > end) {
            return false;
        }
        uint32_t paddingLen = 0;
        if (memcpy_s(&paddingLen, sizeof(paddingLen), page + offset + sizeof(uint32_t), sizeof(paddingLen)) != EOK) {
            return false;
        }
        // Measured on kernel 6.8: array[0] holds the payload length, the 4 byte header is extra
        // (padding fills the page exactly: header + array[0] == commit - offset).
        eventLen = static_cast<size_t>(paddingLen) + RB_EVENT_HDR_SIZE;
        return true;
    }
    if (type == RB_TYPE_TIME_EXTEND) {
        eventLen = RB_LEN_TIME_EXTEND;
        return true;
    }
    if (type == RB_TYPE_TIME_STAMP) {
        eventLen = RB_LEN_TIME_STAMP;
        return true;
    }
    if (type == 0) {
        if (offset + kEventHdrWithLen > end) {
            return false;
        }
        uint32_t payloadLen = 0;
        if (memcpy_s(&payloadLen, sizeof(payloadLen), page + offset + sizeof(uint32_t), sizeof(payloadLen)) != EOK) {
            return false;
        }
        // rb_event_data_length(): for type_len == 0 the stored value is the payload only,
        // so the 4 byte header must be added.
        eventLen = static_cast<size_t>(payloadLen) + RB_EVENT_HDR_SIZE;
        isEvent = true;
        return true;
    }
    // rb_event_data_length() returns type_len*4 + RB_EVENT_HDR_SIZE for data events,
    // the header itself is not part of type_len.
    eventLen = static_cast<size_t>(type) * kRbTypeLenUnit + RB_EVENT_HDR_SIZE;
    isEvent = true;
    return true;
}
} // namespace

uint64_t CpuReader::CountPageEvents(const uint8_t* page, size_t length) const
{
    if (length < pageDataOffset_) {
        return 0;
    }
    uint64_t committed = 0;
    // local_t commit, right after time_stamp
    if (memcpy_s(&committed, sizeof(committed), page + sizeof(uint64_t), sizeof(committed)) != EOK) {
        return 0;
    }
    size_t end = pageDataOffset_ + static_cast<size_t>(committed);
    if (end > length) {
        end = length;
    }
    size_t offset = pageDataOffset_;
    uint64_t count = 0;
    while (offset + sizeof(uint32_t) <= end) {
        size_t eventLen = 0;
        bool isEvent = false;
        if (!ClassifyEventLen(page, offset, end, eventLen, isEvent)) {
            break;
        }
        if (eventLen == 0 || offset + eventLen > end) {
            break;
        }
        // Count only after the bounds check: a corrupted tail must not inflate the statistic.
        if (isEvent) {
            count++;
        }
        offset += eventLen;
    }
    return count;
}

bool CpuReader::ReadOnce(bool drainMode)
{
    std::vector<uint8_t> buffer(pageSize_);
    const ssize_t readLen = read(rawFd_, buffer.data(), buffer.size());
    if (readLen < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return false;
        }
        if (errno == EINTR) {
            return true;
        }
        std::lock_guard<std::mutex> lock(errorMutex_);
        error_ = "read cpu" + std::to_string(cpu_) + " failed: " + strerror(errno);
        return false;
    }
    if (readLen == 0) {
        return false; // no more data in this sub-buffer
    }
    const size_t writeLen = static_cast<size_t>(readLen);
    size_t written = 0;
    while (written < writeLen) {
        const ssize_t ret = write(outFd_, buffer.data() + written, writeLen - written);
        if (ret < 0) {
            if (errno == EINTR) {
                continue;
            }
            std::lock_guard<std::mutex> lock(errorMutex_);
            error_ = "write cpu" + std::to_string(cpu_) + " failed: " + strerror(errno);
            return false;
        }
        written += static_cast<size_t>(ret);
    }
    bytes_.fetch_add(writeLen);
    events_.fetch_add(CountPageEvents(buffer.data(), writeLen));
    (void)drainMode;
    return true;
}

void CpuReader::Run()
{
    if (!OpenFiles()) {
        finished_.store(true);
        return;
    }
    // trace_pipe_raw does not reliably report POLLIN, so read() is always attempted first:
    // the fd is O_NONBLOCK and a bare EAGAIN simply means "nothing committed yet". poll() is
    // only used as a short sleep to avoid a busy loop.
    int32_t emptyReads = 0;
    while (true) {
        const bool stopping = stopRequested_.load();
        if (ReadOnce(stopping)) {
            emptyReads = 0;
            continue;
        }
        {
            std::lock_guard<std::mutex> lock(errorMutex_);
            if (!error_.empty()) {
                break;
            }
        }
        if (stopping) {
            if (++emptyReads >= MAX_EMPTY_READS_ON_DRAIN) {
                break;
            }
        }
        struct pollfd pfd {};
        pfd.fd = rawFd_;
        pfd.events = POLLIN;
        (void)poll(&pfd, 1, POLL_TIMEOUT_MS);
    }
    CloseFiles();
    finished_.store(true);
}
} // namespace Ftrace
