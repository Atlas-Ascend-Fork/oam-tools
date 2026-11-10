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
#include "ftrace_log.h"

#include <cstdio>

#include "securec.h"

#include "msprof_dlog_tool.h"

namespace Ftrace {
namespace {
constexpr char LOG_TAG[] = "[ftrace_collector] ";
constexpr size_t MAX_LINE_LEN = 1024;
} // namespace

FtraceLog& FtraceLog::Instance()
{
    static FtraceLog instance;
    return instance;
}

void FtraceLog::Write(const std::string& level, const std::string& message)
{
    const std::string line = std::string(LOG_TAG) + level + ": " + message;
    if (level == "error") {
        MSPROF_LOGE("%s", line.c_str());
    } else if (level == "warn") {
        MSPROF_LOGW("%s", line.c_str());
    } else {
        MSPROF_LOGI("%s", line.c_str());
    }
}

void FtraceLog::Event(const std::string& event, const std::string& detail)
{
    MSPROF_EVENT("%s%s %s", LOG_TAG, event.c_str(), detail.c_str());
}

void FtraceLog::KeyValues(const std::string& event, const std::string& kvs)
{
    MSPROF_LOGI("%s%s %s", LOG_TAG, event.c_str(), kvs.c_str());
}

void FtraceLog::Heartbeat(
    uint64_t bytes, uint64_t events, uint64_t drops, uint64_t diskFreeMb, int64_t writeLatencyP99Ms, double cpuBusy)
{
    char line[MAX_LINE_LEN] = {0};
    const int32_t written = snprintf_s(
        line, sizeof(line), sizeof(line) - 1,
        "%sheartbeat bytes_written=%llu events_est=%llu drop_total=%llu disk_free_mb=%llu "
        "write_lat_ms_p99=%lld cpu_busy=%.2f",
        LOG_TAG, static_cast<unsigned long long>(bytes), static_cast<unsigned long long>(events),
        static_cast<unsigned long long>(drops), static_cast<unsigned long long>(diskFreeMb),
        static_cast<long long>(writeLatencyP99Ms), cpuBusy);
    if (written <= 0) {
        return;
    }
    MSPROF_LOGI("%s", line);
}
} // namespace Ftrace
