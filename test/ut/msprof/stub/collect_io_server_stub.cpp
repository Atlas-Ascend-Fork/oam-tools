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
#include "errno/error_code_tool.h"
#include "collect_io_server_stub.h"

using namespace analysis::dvvp::common::error;

int ProfilerServerInit(const std::string& local_sock_name) { return PROFILING_SUCCESS; }

int RegisterSendData(const std::string& name, int (*func)(CONST_VOID_PTR, uint32_t)) { return PROFILING_SUCCESS; }

int control_profiling(const char* uuid, const char* config, uint32_t config_len) { return PROFILING_SUCCESS; }

int profiler_server_send_data(const void* ctx, const void* pkt, uint32_t size) { return PROFILING_SUCCESS; }

int ProfilerServerDestroy() { return PROFILING_SUCCESS; }
