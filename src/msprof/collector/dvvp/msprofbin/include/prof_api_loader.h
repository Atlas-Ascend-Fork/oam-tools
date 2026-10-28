/**
 * Copyright (c) 2026 Huawei Technologies Co., Ltd. All rights reserved.
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

#ifndef PROFILING_PROF_API_LOADER_H
#define PROFILING_PROF_API_LOADER_H

#include <string>
#include <cstdint>
#include "aprof_pub.h"
#include "errno/error_code_tool.h"

namespace Collector {
namespace Dvvp {
namespace Msprofbin {
using MsprofInitFunc = int32_t (*)(uint32_t dataType, void* data, uint32_t dataLen);
class ProfApiLoader {
public:
    ProfApiLoader() = default;
    ~ProfApiLoader();

    int32_t Load();
    int32_t Init();
    void Close();

private:
    void* handle_{nullptr};
    MsprofInitFunc initFunc_{nullptr};
};
} // namespace Msprofbin
} // namespace Dvvp
} // namespace Collector

#endif
