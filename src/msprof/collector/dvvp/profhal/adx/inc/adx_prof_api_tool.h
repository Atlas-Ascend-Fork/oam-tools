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
#ifndef ANALYSIS_DVVP_DEVICE_ADX_API_H
#define ANALYSIS_DVVP_DEVICE_ADX_API_H
#include "utils/utils_tool.h"
#include "hdc_api.h"
namespace Analysis {
namespace Dvvp {
namespace Adx {
using namespace analysis::dvvp::common::utils;
using HDC_SESSION_PTR = HDC_SESSION*;
int32_t AdxIdeCreatePacket(CONST_VOID_PTR buffer, int32_t length, IdeBuffT& outPut, int32_t& outLen);
void AdxIdeFreePacket(IdeBuffT& out);
HDC_CLIENT AdxHdcClientCreate(drvHdcServiceType type);
int32_t AdxHdcClientDestroy(HDC_CLIENT client);
HDC_SERVER AdxHdcServerCreate(int32_t logDevId, drvHdcServiceType type);
void AdxHdcServerDestroy(HDC_SERVER server);
HDC_SESSION AdxHdcServerAccept(HDC_SERVER server);
int32_t AdxHdcSessionConnect(int32_t peerNode, int32_t peerDevid, HDC_CLIENT client, HDC_SESSION_PTR session);
int32_t AdxHalHdcSessionConnect(
    int32_t peerNode, int32_t peerDevid, int32_t hostPid, HDC_CLIENT client, HDC_SESSION_PTR session);
int32_t AdxHdcSessionClose(HDC_SESSION session);
int32_t AdxIdeGetDevIdBySession(HDC_SESSION session, IdeI32Pt devId);
int32_t AdxIdeGetVfIdBySession(HDC_SESSION session, int32_t& vfId);
int32_t AdxHdcSessionDestroy(HDC_SESSION session);
int32_t AdxHdcWrite(HDC_SESSION session, IdeSendBuffT buf, int32_t len);
int32_t AdxHdcRead(HDC_SESSION session, IdeRecvBuffT recvBuf, IdeI32Pt recvLen, uint32_t timeout = 0);
int32_t DoAdxIdeCreatePacket(CmdClassT type, IdeString value, uint32_t valueLen, IdeRecvBuffT buf, IdeI32Pt bufLen);
} // namespace Adx
} // namespace Dvvp
} // namespace Analysis
#endif
