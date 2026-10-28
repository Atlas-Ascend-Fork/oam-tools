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
#include "msprof_error_manager_tool.h"

namespace Analysis {
namespace Dvvp {
namespace MsprofErrMgr {
error_message::ErrorManagerContext MsprofErrorManager::errorContext_{};

error_message::ErrorManagerContext& MsprofErrorManager::GetErrorManagerContext() const { return errorContext_; }

void MsprofErrorManager::SetErrorContext(const error_message::ErrorManagerContext errorContext) const
{
    (void)(errorContext);
}
} // namespace MsprofErrMgr
} // namespace Dvvp
} // namespace Analysis
