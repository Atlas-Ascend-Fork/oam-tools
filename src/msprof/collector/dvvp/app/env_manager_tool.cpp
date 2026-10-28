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

#include "env_manager_tool.h"
namespace Analysis {
namespace Dvvp {
namespace App {
void EnvManager::SetGlobalEnv(std::vector<std::string>& envList) { envList_ = envList; }

const std::vector<std::string> EnvManager::GetGlobalEnv() { return envList_; }

void EnvManager::SetParamEnv(std::string paramEnv) { paramEnv_ = paramEnv; }

std::string EnvManager::GetParamEnv() { return paramEnv_; }
} // namespace App
} // namespace Dvvp
} // namespace Analysis
