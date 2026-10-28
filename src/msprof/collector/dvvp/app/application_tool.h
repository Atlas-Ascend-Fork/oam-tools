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

#ifndef ANALYSIS_DVVP_APP_APPLICATION_H
#define ANALYSIS_DVVP_APP_APPLICATION_H

#include <memory>
#include <sstream>
#include <string>
#include <vector>
#include "message/prof_params.h"
#include "transport_tool.h"

namespace analysis {
namespace dvvp {
namespace app {
class Application {
public:
    static int32_t LaunchApp(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, OsalProcess& appProcess);

private:
    static int32_t ResolveAppCmd(
        SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::vector<std::string>& paramsCmd,
        std::string& cmd);
    static int32_t PrepareAppEnvs(
        SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::vector<std::string>& envsV);
    static int32_t PrepareLaunchAppCmd(
        std::stringstream& ssCmdApp, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);

    static void PrepareAppArgs(const std::vector<std::string>& params, std::vector<std::string>& argsV);

    static int32_t PrepareAclEnvs(
        SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::vector<std::string>& envsV);

    static void SetAppEnv(
        SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::vector<std::string>& envsV);
    static void SourceEnv(std::vector<std::string>& argsVec);
    static std::string GetCmdString(const std::string paramsName);
};
} // namespace app
} // namespace dvvp
} // namespace analysis

#endif
