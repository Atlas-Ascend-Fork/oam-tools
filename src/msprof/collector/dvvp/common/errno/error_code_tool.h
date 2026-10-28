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
#ifndef ANALYSIS_DVVP_COMMON_ERRNO_ERROR_CODE_H
#define ANALYSIS_DVVP_COMMON_ERRNO_ERROR_CODE_H

#include <stdint.h>

namespace analysis {
namespace dvvp {
namespace common {
namespace error {
constexpr int32_t PROFILING_CONTINUE = 1;
constexpr int32_t PROFILING_SUCCESS = 0;
constexpr int32_t PROFILING_FAILED = -1;
constexpr int32_t PROFILING_NOTSUPPORT = -2;
constexpr int32_t PROFILING_IN_WARMUP = -3;
} // namespace error
} // namespace common
} // namespace dvvp
} // namespace analysis

#endif
