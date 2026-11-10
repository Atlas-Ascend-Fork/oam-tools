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
#ifndef MSPROF_FTRACE_COLLECTOR_TRACEFS_H
#define MSPROF_FTRACE_COLLECTOR_TRACEFS_H

#include <cstdint>
#include <string>
#include <vector>

#include "ftrace_types.h"

namespace Ftrace {
// A tracepoint parsed from "--ftrace=sched/sched_switch,..."
struct EventSpec {
    std::string system;
    std::string event;
    std::string FullName() const { return system + "/" + event; }
};

class TraceFs {
public:
    static bool DetectRoot(std::string& root);
    static bool ReadText(const std::string& root, const std::string& relativePath, std::string& content);
    static bool WriteText(const std::string& root, const std::string& relativePath, const std::string& value);

    static bool CheckEvent(const std::string& root, const EventSpec& spec);
    static bool ParseFormat(const std::string& root, const EventSpec& spec, TraceEvent& event);
    static bool ReadCpuDrops(const std::string& root, int32_t cpu, uint64_t& drops);

    static bool Prepare(
        const std::string& root, const Options& options, const std::vector<EventSpec>& specs,
        const std::vector<int32_t>& cpus);
    static bool Start(const std::string& root);
    static bool Stop(const std::string& root);
    static bool Clear(const std::string& root);

    static bool WriteEventMetaJson(
        const std::string& root, const std::vector<EventSpec>& specs, size_t pageSize, size_t pageDataOffset,
        const std::string& path);
    static bool WriteThreadMapJson(const std::string& path, uint64_t snapshotStartNs, uint64_t snapshotEndNs);

    static std::string HashOf(const std::string& content);

private:
    static bool SetClock(const std::string& root, const std::string& clock);
    static bool SetBufferSizeKb(const std::string& root, int32_t sizeKb);
    static bool SetCpuMask(const std::string& root, const std::string& mask);
    static bool EnableEvents(const std::string& root, const std::vector<EventSpec>& specs);
};
} // namespace Ftrace

#endif // MSPROF_FTRACE_COLLECTOR_TRACEFS_H
