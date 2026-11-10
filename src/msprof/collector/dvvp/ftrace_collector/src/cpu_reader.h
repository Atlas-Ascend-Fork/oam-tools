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
#ifndef MSPROF_FTRACE_COLLECTOR_CPU_READER_H
#define MSPROF_FTRACE_COLLECTOR_CPU_READER_H

#include <atomic>
#include <mutex>
#include <cstdint>
#include <string>
#include <thread>

#include "ftrace_types.h"

namespace Ftrace {
// One reader thread per CPU: drains per_cpu/cpuN/trace_pipe_raw into trace.cpuN.bin.
// The CPU id is a property of the thread, never derived from the event payload
// (struct trace_entry carries no cpu field).
class CpuReader {
public:
    CpuReader(int32_t cpu, std::string traceRoot, std::string outputPath, size_t pageSize, size_t pageDataOffset);
    ~CpuReader();

    void Start();
    void RequestStop();
    void Join();

    CpuStats Snapshot() const;
    uint64_t Bytes() const { return bytes_.load(); }
    uint64_t Events() const { return events_.load(); }
    bool Finished() const { return finished_.load(); }
    std::string Error() const;

private:
    void Run();
    bool OpenFiles();
    bool ReadOnce(bool drainMode);
    uint64_t CountPageEvents(const uint8_t* page, size_t length) const;
    void CloseFiles();

    int32_t cpu_;
    std::string traceRoot_;
    std::string outputPath_;
    size_t pageSize_;
    size_t pageDataOffset_; // data[] offset inside one page, cacheline aligned in the kernel
    int32_t rawFd_ = -1;
    int32_t outFd_ = -1;
    std::thread thread_;
    std::atomic<bool> stopRequested_{false};
    std::atomic<bool> finished_{false};
    std::atomic<uint64_t> bytes_{0};
    std::atomic<uint64_t> events_{0};
    std::string error_;
    mutable std::mutex errorMutex_;
};
} // namespace Ftrace

#endif // MSPROF_FTRACE_COLLECTOR_CPU_READER_H
