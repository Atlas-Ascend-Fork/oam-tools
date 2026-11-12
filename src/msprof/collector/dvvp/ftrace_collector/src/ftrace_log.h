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
#ifndef MSPROF_FTRACE_COLLECTOR_FTRACE_LOG_H
#define MSPROF_FTRACE_COLLECTOR_FTRACE_LOG_H

#include <cstdint>
#include <string>

namespace Ftrace {
// Thin facade over MSPROF_LOG: the collector runs as a child of the profiling process, so its
// diagnostics belong in the same plog as the parent instead of a private file or the console.
class FtraceLog {
public:
    static FtraceLog& Instance();

    // level is "info" / "warn" / "error"; the message keeps the key=value shape used in the logs
    void Write(const std::string& level, const std::string& message) const;
    // Runs through MSPROF_EVENT, the plog "event" channel used for one-shot lifecycle records
    // (the collector's version banner is the only user for now).
    void Event(const std::string& event, const std::string& detail) const;
    void KeyValues(const std::string& event, const std::string& kvs) const;
    void Heartbeat(
        uint64_t bytes, uint64_t events, uint64_t drops, uint64_t diskFreeMb, int64_t writeLatencyP99Ms,
        double cpuBusy) const;

private:
    FtraceLog() = default;
    ~FtraceLog() = default;
    FtraceLog(const FtraceLog&) = delete;
    FtraceLog& operator=(const FtraceLog&) = delete;
};
} // namespace Ftrace

#endif // MSPROF_FTRACE_COLLECTOR_FTRACE_LOG_H
