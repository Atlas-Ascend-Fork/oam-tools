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

#include "prof_api_loader.h"
#include <dlfcn.h>
#include <cstdlib>
#include "cmd_log/cmd_log_tool.h"

namespace Collector {
namespace Dvvp {
namespace Msprofbin {
namespace {
const char* const PROF_API_LIBRARY = "libprofapi.so";
}
using namespace analysis::dvvp::common::cmdlog;
using namespace analysis::dvvp::common::error;

ProfApiLoader::~ProfApiLoader() { Close(); }

int32_t ProfApiLoader::Load()
{
    handle_ = dlopen(PROF_API_LIBRARY, RTLD_NOW | RTLD_LOCAL);
    if (handle_ == nullptr) {
        CmdLog::CmdErrorLog("Load %s failed: %s", PROF_API_LIBRARY, dlerror());
        return PROFILING_FAILED;
    }
    initFunc_ = reinterpret_cast<MsprofInitFunc>(dlsym(handle_, "MsprofInit"));
    if (initFunc_ == nullptr) {
        CmdLog::CmdErrorLog("Find MsprofInit in %s failed: %s", PROF_API_LIBRARY, dlerror());
        Close();
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

int32_t ProfApiLoader::Init()
{
    if (initFunc_ == nullptr) {
        return PROFILING_FAILED;
    }
    const int32_t ret = initFunc_(MSPROF_CTRL_INIT_ACL_ENV, nullptr, 0);
    if (ret == MSPROF_ERROR_NONE) {
        return PROFILING_SUCCESS;
    }
    return (ret == MSPROF_ERROR_UNINITIALIZE) ? PROFILING_NOTSUPPORT : PROFILING_FAILED;
}

void ProfApiLoader::Close()
{
    if (handle_ != nullptr) {
        dlclose(handle_);
        handle_ = nullptr;
    }
    initFunc_ = nullptr;
}
} // namespace Msprofbin
} // namespace Dvvp
} // namespace Collector
