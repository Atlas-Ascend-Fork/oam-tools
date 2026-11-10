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
#ifndef MSPROF_FTRACE_COLLECTOR_TYPES_H
#define MSPROF_FTRACE_COLLECTOR_TYPES_H

#include <cstdint>
#include <string>
#include <vector>

namespace Ftrace {
// struct buffer_data_page is { u64 time_stamp; local_t commit; data[] }. Measured on
// aarch64 kernel 6.8: commit == page_size - 16, so the first event header sits at offset 16
// (the cacheline attribute affects the page alignment, not the data[] offset). The minimum is
// used to reject a corrupted value decoded from a meta file.
constexpr size_t PAGE_DATA_OFFSET_MIN = 16;
// Ring buffer pseudo event lengths (kernel dependent). They are written into
// trace_event_meta.json so the parser on another machine does not have to guess.
constexpr uint32_t kTimeExtendLen = 8;
constexpr uint32_t kTimeStampLen = 8;

constexpr size_t PAGE_DATA_OFFSET_DEFAULT = 16;
constexpr size_t FOOTER_SIZE = 64;
constexpr char FOOTER_MAGIC[] = "FTBC0001";
constexpr uint32_t FTRACE_FOOTER_VERSION = 1;
constexpr uint32_t FTRACE_DRAIN_TIMEOUT_MS = 5000;  // drain must finish before this, else _exit and drop the lock
constexpr uint32_t FTRACE_WATCHDOG_MARGIN_SEC = 20; // lifetime = period + this, covers drain and footer
constexpr uint32_t FTRACE_LEASE_STALE_SEC = 15;     // holder heartbeat older than this is considered stuck

// end reason written into footer / diag summary
enum class EndReason : uint32_t {
    NORMAL = 0, // parent asked to stop
    PERIOD = 1, // --period expired
    PARENT_GONE = 2,
    SIGNAL = 3,
    DISK_FULL = 4,
    ERROR = 5,
};

// exit codes, keep in sync with design doc 4.4.2
enum ExitCode : int32_t {
    EXIT_OK = 0,
    EXIT_BAD_ARGS = 2,
    EXIT_ENV_CHECK = 3,
    EXIT_DISK_FULL = 4,
    EXIT_TRACEFS = 5,
    EXIT_DRAIN_TIMEOUT = 6,
    EXIT_LOCK_BUSY = 7,      // another collector already owns the node lock
    EXIT_COLLECT_FAILED = 8, // a cpu file, its footer or the thread map could not be written
};

struct Options {
    std::string outputDir;
    std::string eventList; // "sched/sched_switch,irq/irq_handler_entry"
    std::string cpuMask;   // hex cpumask, empty means all online cpus
    std::vector<int32_t> cpus;
    int32_t bufferSizeKb = 4096;
    int32_t periodSec = 0;                            // seconds; 0 means follow the profiling lifetime
    uint64_t maxBytes = 0;                            // 0: unlimited
    std::string lockPath;                             // node lock; empty disables single-instance protection
    size_t pageSize = 4096;                           // one tracefs sub-buffer, from buffer_subbuf_size_kb
    size_t pageDataOffset = PAGE_DATA_OFFSET_DEFAULT; // data[] offset inside a page
};

struct CpuStats {
    int32_t cpu = -1;
    uint64_t bytes = 0;
    uint64_t events = 0;
    uint64_t drops = 0;
    bool ok = true;
    std::string error;
};

struct TraceEventField {
    std::string name;
    std::string cType; // "unsigned short", "char", "pid_t" ...
    int32_t offset = 0;
    int32_t size = 0;
    bool isSigned = true;
};

struct TraceEvent {
    std::string system;
    std::string name;
    int32_t kernelId = -1;
    std::string formatHash;
    std::vector<TraceEventField> fields;
};

struct Footer {
    char magic[8];
    uint32_t version;
    uint32_t cpu;
    uint64_t bytes;
    uint64_t events;
    uint64_t drop;
    uint32_t endReason;
    uint32_t crc;
    uint32_t reserved;
    uint8_t padding[12];
};
static_assert(sizeof(Footer) == FOOTER_SIZE, "Footer must stay 64 bytes");
} // namespace Ftrace

#endif // MSPROF_FTRACE_COLLECTOR_TYPES_H
