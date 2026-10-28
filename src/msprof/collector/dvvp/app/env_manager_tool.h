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

#ifndef ANALYSIS_DVVP_ENV_MANAGER_H
#define ANALYSIS_DVVP_ENV_MANAGER_H
#include <iostream>
#include <vector>
#include <string>
#include "singleton/singleton_tool.h"
namespace Analysis {
namespace Dvvp {
namespace App {
class EnvManager : public analysis::dvvp::common::singleton::Singleton<EnvManager> {
public:
    void SetGlobalEnv(std::vector<std::string>& envList);
    const std::vector<std::string> GetGlobalEnv();
    void SetParamEnv(std::string paramEnv);
    std::string GetParamEnv();

private:
    std::vector<std::string> envList_;
    std::string paramEnv_;
};
} // namespace App
} // namespace Dvvp
} // namespace Analysis
#endif
