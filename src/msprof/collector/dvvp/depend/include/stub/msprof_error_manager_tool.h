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
#ifndef MSPROF_ERROR_MANAGER_STUB_H
#define MSPROF_ERROR_MANAGER_STUB_H

#include "base/err_mgr.h"
#include "common/singleton/singleton_tool.h"

#define MSPROF_INPUT_ERROR(error_code, key, value)
#define MSPROF_ENV_ERROR(error_code, key, value)
#define MSPROF_INNER_ERROR(error_code, fmt, ...)
#define MSPROF_CALL_ERROR MSPROF_INNER_ERROR

namespace Analysis {
namespace Dvvp {
namespace MsprofErrMgr {

class MsprofErrorManager : public analysis::dvvp::common::singleton::Singleton<MsprofErrorManager> {
public:
    void SetErrorContext(const error_message::ErrorManagerContext errorContext) const;
    error_message::ErrorManagerContext& GetErrorManagerContext() const;
    MsprofErrorManager() {}
    ~MsprofErrorManager() override {}

private:
    static error_message::ErrorManagerContext errorContext_;
};

} // namespace MsprofErrMgr
} // namespace Dvvp
} // namespace Analysis
#endif
