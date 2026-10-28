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
#ifndef DVVP_ACP_ANALYZE_OP_ANALYZER_PMU_H
#define DVVP_ACP_ANALYZE_OP_ANALYZER_PMU_H

#include "op_analyzer_base_tool.h"
#include "utils/utils_tool.h"
namespace Dvvp {
namespace Acp {
namespace Analyze {
// milan
constexpr uint32_t PMU_DATA_SIZE = 128;
constexpr uint8_t CORE_TYPE_AIC = 0;
constexpr uint8_t CORE_TYPE_AIV = 1;
constexpr uint8_t SUB_TASK_TYPE_AIC = 0;
constexpr uint8_t SUB_TASK_TYPE_MIXAIC = 6;
constexpr uint8_t SUB_TASK_TYPE_MIXAIV = 7;
constexpr uint8_t FFTS_TYPE_TRADITION_AIC = 0;
constexpr uint8_t FFTS_TYPE_FFTS = 4;
constexpr uint8_t FFTS_TYPE_MIX_AIC = 5;
constexpr uint8_t PMU_COUNT = 8;
constexpr uint16_t FUNC_TYPE_SUBTASK = 0b101000;
constexpr uint16_t FUNC_TYPE_BLOCK = 0b101001;
// david adapt
constexpr uint32_t DAVID_LOG_DATA_SIZE = 32;
constexpr uint32_t DAVID_PMU_NUM = 10;
constexpr uint16_t FUNC_TYPE_DAVID_TASK = 0b101010;
constexpr uint16_t FUNC_TYPE_DAVID_BLOCK = 0b101001;
constexpr uint16_t PLACE_HOLER_SQE = 3;
constexpr uint16_t NOTIFY_RECORD_SQE = 6;
constexpr uint16_t NOTIFY_WAIT_SQE = 7;
constexpr uint16_t WRITE_VALUE_SQE = 8;
constexpr uint16_t CONDITION_SQE = 20;
constexpr uint16_t END_SQE = 21;

class OpAnalyzerPmu : public OpAnalyzerBase {
public:
    OpAnalyzerPmu() : starsBytes_(0), fftsSubBytes_(0), fftsBlockBytes_(0) {};
    ~OpAnalyzerPmu() {};

public:
    bool IsStarsData(const std::string& fileName) const;
    bool IsFftsData(const std::string& fileName) const;
    void ParseStarsData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void ParseFftsData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void ParseDavidLogData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void ParseDavidProfileData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void PrintStats() const;
    bool IsExtPmu() const;

private:
    template <typename T>
    void HandleStarsAcsq(const T* logData, uint16_t logType);
    void HandleSubTaskThread(const void* data, uint16_t logType) const;
    template <typename T>
    void HandleSubtaskPmu(const T* data, uint8_t fftsType, uint8_t coreType, uint64_t cnt);
    template <typename T>
    void HandleBlockPmu(const T* data);
    bool IsAic(uint8_t fftsType, uint8_t contextType, uint8_t coreType) const;
    bool IsFftsAic(uint8_t fftsType, uint8_t contextType) const;
    bool IsTraditionAic(uint8_t fftsType) const;
    bool IsFftsMixAic(uint8_t fftsType, uint8_t contextType) const;
    bool IsFftsMixAiv(uint8_t fftsType, uint8_t contextType) const;
    bool IsMixType(uint8_t contextType) const;
    bool IsSlaveCore(uint8_t contextType, uint8_t coreType) const;
    bool IsSqeControl(uint16_t sqeType) const;

private:
    uint64_t starsBytes_;
    uint64_t fftsSubBytes_;
    uint64_t fftsBlockBytes_;
};
} // namespace Analyze
} // namespace Acp
} // namespace Dvvp

#endif
