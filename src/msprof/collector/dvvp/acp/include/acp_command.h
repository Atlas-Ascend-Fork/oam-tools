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

#ifndef COLLECTOR_DVVP_ACP_COMMAND_H
#define COLLECTOR_DVVP_ACP_COMMAND_H
#include "argparser_tool.h"
#include "message/prof_params.h"

namespace Collector {
namespace Dvvp {
namespace Acp {
using namespace analysis::dvvp::common::argparse;
Argparser AcpCommandBuild(const std::string commandName);
int32_t ProfileCommandRun(Argparser& profCommand);
int32_t WaitRunningProcess(std::string processUsage, int32_t& taskPid);
int32_t PreCheckPlatform();
int32_t CheckOutputValid(std::string& output);
int32_t CheckAcpMetricsIsValid(std::string& metrics);
int32_t CheckCustomEventIsValid(std::string::size_type pos, std::string& metrics, std::vector<std::string>& metricsVec);
int32_t CheckGroupMetricsIsValid(std::string& metrics, std::vector<std::string>& metricsVec);
void DeduplicateAcpMetrics(std::string::size_type pos, std::string& metrics, std::vector<std::string>& metricsVec);
} // namespace Acp
} // namespace Dvvp
} // namespace Collector
#endif
