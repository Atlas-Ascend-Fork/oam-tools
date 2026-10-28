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

#ifndef ANALYSIS_DVVP_MSPROFBIN_MSOPPROF_MANAGER_H_
#define ANALYSIS_DVVP_MSPROFBIN_MSOPPROF_MANAGER_H_

#include <vector>
#include <string>
#include "utils/utils_tool.h"
#include "config/config.h"
#include "singleton/singleton_tool.h"

namespace Analysis {
namespace Dvvp {
namespace Msopprof {
using CONST_CHAR_PTR = const char*;
using namespace analysis::dvvp::common::config;

class MsopprofManager : public analysis::dvvp::common::singleton::Singleton<MsopprofManager> {
public:
    MsopprofManager();
    ~MsopprofManager() override {}
    int MsopprofProcess(int argc, CONST_CHAR_PTR argv[]);
    OsalProcess GetMsopprofPid() const { return msopprofPid_; }
    bool IsMsopprofExist() const;

private:
    bool CheckMsopprofIfExist(int argc, CONST_CHAR_PTR argv[], std::vector<std::string>& opArgv) const;
    void ExecuteMsopprof(const std::vector<std::string>& opArgv);

private:
    std::string msopprofPath_;
    OsalProcess msopprofPid_;
};

} // namespace Msopprof
} // namespace Dvvp
} // namespace Analysis

#endif // ANALYSIS_DVVP_MSPROFBIN_MSOPPROF_MANAGER_H_
