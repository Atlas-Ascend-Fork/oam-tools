/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
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
#ifndef MSPROFBIN_TEST_HELPER_H
#define MSPROFBIN_TEST_HELPER_H

#include <cstdint>
#include <vector>

#include "errno/error_code_tool.h"

namespace Analysis {
namespace Dvvp {
namespace MsprofbinTest {
inline int32_t PopResult(std::vector<int32_t>& results)
{
    if (results.empty()) {
        return analysis::dvvp::common::error::PROFILING_SUCCESS;
    }
    int32_t result = results.front();
    results.erase(results.begin());
    return result;
}
} // namespace MsprofbinTest
} // namespace Dvvp
} // namespace Analysis

#endif // MSPROFBIN_TEST_HELPER_H
