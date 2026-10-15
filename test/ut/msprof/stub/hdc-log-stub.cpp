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
#include "dlog_pub.h"
#include <unistd.h>
#include <stdio.h>
#include <stdarg.h>
#include <syslog.h>
#include <map>
#include <string>
#include <atomic>
#include "securec.h"

#ifndef DLOG_EVENT
#define DLOG_EVENT 4
#endif

const std::map<int, std::string> LOG_LEVEL_INFO = {
    {DLOG_DEBUG, "DEBUG"}, {DLOG_INFO, "INFO"}, {DLOG_WARN, "WARNING"}, {DLOG_ERROR, "ERROR"}, {DLOG_EVENT, "EVENT"}};

static std::atomic<int32_t> g_dlogRecordCount{0};

constexpr size_t LOG_BUFFER_SIZE = 4096;
char g_lastDlogRecordMsg[LOG_BUFFER_SIZE] = {0};

bool FormatLog(char* buffer, size_t bufferSize, const char* format, va_list args)
{
    if (buffer == nullptr || bufferSize == 0 || format == nullptr) {
        return false;
    }
    return vsnprintf_s(buffer, bufferSize, bufferSize - 1, format, args) >= 0;
}

void ResetDlogRecordCount() { g_dlogRecordCount.store(0); }

int32_t GetDlogRecordCount() { return g_dlogRecordCount.load(); }

void ResetLastDlogRecordMsg() { g_lastDlogRecordMsg[0] = '\0'; }

const char* GetLastDlogRecordMsg() { return g_lastDlogRecordMsg; }

void DlogErrorInner(int moduleId, const char* format, ...)
{
    va_list args;

    char buffer[LOG_BUFFER_SIZE] = {0};

    va_start(args, format);
    bool formatRet = FormatLog(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (!formatRet) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogErrorInner.");
        return;
    }
    printf("[ERROR]%s\n", buffer);
}

void DlogInfoInner(int moduleId, const char* format, ...)
{
    va_list args;

    char buffer[LOG_BUFFER_SIZE] = {0};

    va_start(args, format);
    bool formatRet = FormatLog(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (!formatRet) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogInfoInner.");
        return;
    }
    printf("[INFO]%s\n", buffer);
}

void DlogWarnInner(int moduleId, const char* format, ...)
{
    va_list args;

    char buffer[LOG_BUFFER_SIZE] = {0};

    va_start(args, format);
    bool formatRet = FormatLog(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (!formatRet) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogWarnInner.");
        return;
    }
    printf("[WARN]%s\n", buffer);
}

void DlogEventInner(int moduleId, const char* format, ...)
{
    va_list args;

    char buffer[LOG_BUFFER_SIZE] = {0};

    va_start(args, format);
    bool formatRet = FormatLog(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (!formatRet) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogEventInner.");
        return;
    }
    printf("[EVENT]%s\n", buffer);
}

void DlogDebugInner(int moduleId, const char* format, ...)
{
    va_list args;

    char buffer[LOG_BUFFER_SIZE] = {0};

    va_start(args, format);
    bool formatRet = FormatLog(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (!formatRet) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogDebugInner.");
        return;
    }
    printf("[DEBUG]%s\n", buffer);
}

void DlogRecord(int module_id, int level, const char* fmt, ...)
{
    g_dlogRecordCount.fetch_add(1, std::memory_order_relaxed);
    auto iter = LOG_LEVEL_INFO.find(level);
    std::string levelStr;
    if (iter != LOG_LEVEL_INFO.end()) {
        levelStr = iter->second;
    }

    va_list args;
    char buffer[LOG_BUFFER_SIZE] = {0};
    va_start(args, fmt);
    bool formatRet = FormatLog(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    if (!formatRet) {
        printf("[ERROR]Failed to execute vsnprintf_s for DlogRecord.");
        return;
    }
    if (snprintf_s(g_lastDlogRecordMsg, sizeof(g_lastDlogRecordMsg), sizeof(g_lastDlogRecordMsg) - 1U, "%s", buffer) <
        0) {
        g_lastDlogRecordMsg[0] = '\0';
    }
    printf("[%s][pid:%d]%s", levelStr.c_str(), getpid(), buffer);
}

void DlogFlush(void) {}

void ide_log(int priority, const char* format, ...)
{
    va_list args;

    char buffer[LOG_BUFFER_SIZE] = {0};

    va_start(args, format);
    bool formatRet = FormatLog(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (!formatRet) {
        printf("[ERROR]Failed to execute vsnprintf_s for ide_log.");
        return;
    }
    printf("[IDE]%s\n", buffer);
}

int CheckLogLevel(int moduleId, int level) { return 1; }
