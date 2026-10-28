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
#ifndef MSPROF_DLOG_H
#define MSPROF_DLOG_H

#include <sys/syscall.h>
#include <unistd.h>
#include "dlog_pub.h"

#if (defined(linux) || defined(__linux__))
#include <syslog.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define MSPROF_MODULE_NAME PROFILING
#ifdef OSAL

#define MSPROF_EVENT(format, ...)                                                                             \
    do {                                                                                                      \
        DlogRecord(MSPROF_MODULE_NAME, DLOG_EVENT, "[%s:%d]" format "\n", __FILE__, __LINE__, ##__VA_ARGS__); \
    } while (0)
#define MSPROF_LOGE(format, ...)                                                                              \
    do {                                                                                                      \
        DlogRecord(MSPROF_MODULE_NAME, DLOG_ERROR, "[%s:%d]" format "\n", __FILE__, __LINE__, ##__VA_ARGS__); \
    } while (0)
#define MSPROF_LOGW(format, ...)                                                                             \
    do {                                                                                                     \
        DlogRecord(MSPROF_MODULE_NAME, DLOG_WARN, "[%s:%d]" format "\n", __FILE__, __LINE__, ##__VA_ARGS__); \
    } while (0)
#define MSPROF_LOGI(format, ...)                                                                             \
    do {                                                                                                     \
        DlogRecord(MSPROF_MODULE_NAME, DLOG_INFO, "[%s:%d]" format "\n", __FILE__, __LINE__, ##__VA_ARGS__); \
    } while (0)
#define MSPROF_LOGD(format, ...)                                                                              \
    do {                                                                                                      \
        DlogRecord(MSPROF_MODULE_NAME, DLOG_DEBUG, "[%s:%d]" format "\n", __FILE__, __LINE__, ##__VA_ARGS__); \
    } while (0)

#else

#define MSPROF_LOGD(format, ...)                                                                       \
    do {                                                                                               \
        dlog_debug(MSPROF_MODULE_NAME, " (tid:%ld) " format "\n", syscall(SYS_gettid), ##__VA_ARGS__); \
    } while (0)
#define MSPROF_LOGI(format, ...)                                                                      \
    do {                                                                                              \
        dlog_info(MSPROF_MODULE_NAME, " (tid:%ld) " format "\n", syscall(SYS_gettid), ##__VA_ARGS__); \
    } while (0)
#define MSPROF_LOGW(format, ...)                                                                      \
    do {                                                                                              \
        dlog_warn(MSPROF_MODULE_NAME, " (tid:%ld) " format "\n", syscall(SYS_gettid), ##__VA_ARGS__); \
    } while (0)
#define MSPROF_LOGE(format, ...)                                                                       \
    do {                                                                                               \
        dlog_error(MSPROF_MODULE_NAME, " (tid:%ld) " format "\n", syscall(SYS_gettid), ##__VA_ARGS__); \
    } while (0)
#define MSPROF_EVENT(format, ...)                                                                                      \
    do {                                                                                                               \
        dlog_info(                                                                                                     \
            static_cast<int32_t>(static_cast<uint32_t>(MSPROF_MODULE_NAME) | RUN_LOG_MASK), " (tid:%ld) " format "\n", \
            syscall(SYS_gettid), ##__VA_ARGS__);                                                                       \
    } while (0)

#endif

#ifdef __cplusplus
}
#endif

#endif // MSPROF_LOG_H
