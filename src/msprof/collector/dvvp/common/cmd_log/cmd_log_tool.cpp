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
#include "cmd_log/cmd_log_tool.h"
#include <cstdarg>
#include "securec.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace cmdlog {
constexpr int32_t MSPROF_BIN_MAX_LOG_SIZE = 1024; // 1024 : 1k

void CmdLog::CmdLogNoLevel(CONST_CHAR_PTR format, ...)
{
    va_list args;
    char buffer[MSPROF_BIN_MAX_LOG_SIZE + 1] = {0};
    va_start(args, format);
    int ret = vsnprintf_truncated_s(buffer, sizeof(buffer), format, args);
    if (ret > 0) {
        std::cout << buffer << std::endl;
    }
    va_end(args);
}

void CmdLog::CmdErrorLog(CONST_CHAR_PTR format, ...)
{
    va_list args;
    char buffer[MSPROF_BIN_MAX_LOG_SIZE + 1] = {0};
    va_start(args, format);
    int ret = vsnprintf_truncated_s(buffer, sizeof(buffer), format, args);
    if (ret > 0) {
        std::cout << "[ERROR] " << buffer << std::endl;
    }
    va_end(args);
}

void CmdLog::CmdInfoLog(CONST_CHAR_PTR format, ...)
{
    va_list args;
    char buffer[MSPROF_BIN_MAX_LOG_SIZE + 1] = {0};
    va_start(args, format);
    int ret = vsnprintf_truncated_s(buffer, sizeof(buffer), format, args);
    if (ret > 0) {
        std::cout << "[INFO] " << buffer << std::endl;
    }
    va_end(args);
}

void CmdLog::CmdWarningLog(CONST_CHAR_PTR format, ...)
{
    va_list args;
    char buffer[MSPROF_BIN_MAX_LOG_SIZE + 1] = {0};
    va_start(args, format);
    int ret = vsnprintf_truncated_s(buffer, sizeof(buffer), format, args);
    if (ret > 0) {
        std::cout << "[WARNING] " << buffer << std::endl;
    }
    va_end(args);
}
} // namespace cmdlog
} // namespace common
} // namespace dvvp
} // namespace analysis
