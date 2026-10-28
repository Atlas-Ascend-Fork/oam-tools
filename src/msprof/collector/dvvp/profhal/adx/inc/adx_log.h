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

#ifndef ADX_LOG_H
#define ADX_LOG_H
#include "msprof_dlog_tool.h"
#define IDE_CTRL_VALUE_FAILED(err, action, logText, ...) \
    do {                                                 \
        if (!(err)) {                                    \
            MSPROF_LOGE(logText, ##__VA_ARGS__);         \
            action;                                      \
        }                                                \
    } while (0)

#define IDE_CTRL_VALUE_WARN(err, action, logText, ...) \
    do {                                               \
        if (!(err)) {                                  \
            MSPROF_LOGW(logText, ##__VA_ARGS__);       \
            action;                                    \
        }                                              \
    } while (0)

#define IDE_CTRL_VALUE_WARN_EX(err, action, logText, ...) \
    do {                                                  \
        if (err) {                                        \
            MSPROF_LOGW(logText, ##__VA_ARGS__);          \
            action;                                       \
        }                                                 \
    } while (0)

#endif
