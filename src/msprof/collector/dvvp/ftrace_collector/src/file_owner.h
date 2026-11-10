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
#ifndef MSPROF_FTRACE_COLLECTOR_FILE_OWNER_H
#define MSPROF_FTRACE_COLLECTOR_FILE_OWNER_H

#include <string>

namespace Ftrace {
// The collector is started through sudo, so every artifact it creates belongs to root, but the
// artifacts are parsed later by the unprivileged profiling process. A root owned 0600 cpu file
// makes the parser fail to open it and report "footer missing or invalid" for every cpu, so the
// ownership of each created file is handed back to the user that started the profiling.
void GiveBackOwnership(const std::string& path);
} // namespace Ftrace

#endif // MSPROF_FTRACE_COLLECTOR_FILE_OWNER_H
