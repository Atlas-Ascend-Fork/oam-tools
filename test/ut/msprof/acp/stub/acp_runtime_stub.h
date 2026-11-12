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
#ifndef ST_REPORT_STUB_H
#define ST_REPORT_STUB_H

#include "acl/acl_prof.h"
#include "runtime/base.h"
#include "runtime/kernel.h"
#include "runtime/rts/rts_kernel.h"

extern "C" MSVP_PROF_API rtError_t rtGetBinaryDeviceBaseAddr(void* handle, void** launchBase);
extern "C" MSVP_PROF_API rtError_t
rtLaunchKernelWithArgsArray(void* func, uint32_t numBlocks, rtStream_t stm, rtKernelLaunchCfg_t* cfg, void** args);
#endif
