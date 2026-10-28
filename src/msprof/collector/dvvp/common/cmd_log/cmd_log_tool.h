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
#ifndef COLLECTOR_DVVP_COMMON_CMD_LOG_CMD_LOG_H
#define COLLECTOR_DVVP_COMMON_CMD_LOG_CMD_LOG_H
#include <iostream>

namespace analysis {
namespace dvvp {
namespace common {
namespace cmdlog {
using CONST_CHAR_PTR = const char*;

class CmdLog {
public:
    static void CmdLogNoLevel(CONST_CHAR_PTR format, ...);
    static void CmdErrorLog(CONST_CHAR_PTR format, ...);
    static void CmdInfoLog(CONST_CHAR_PTR format, ...);
    static void CmdWarningLog(CONST_CHAR_PTR format, ...);
};
} // namespace cmdlog
} // namespace common
} // namespace dvvp
} // namespace analysis
#endif
