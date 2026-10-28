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

#ifndef DVVP_ACP_ANALYZE_OP_ANALYZER_PC_SAMPLING_H
#define DVVP_ACP_ANALYZE_OP_ANALYZER_PC_SAMPLING_H
#include <string>
#include <unordered_map>
#include "utils/utils_tool.h"

namespace Dvvp {
namespace Acp {
namespace Analyze {
struct SamplingInstrTotalRecord {
    uint64_t pcAddr{0};
    uint64_t active{0};
    uint64_t ibufEmpty{0};
    uint64_t nopStall{0};
    uint64_t scoreboardNotReady{0};
    uint64_t registerBankConflict{0};
    uint64_t resourceConflict{0};
    uint64_t warpLevelSync{0};
    uint64_t divergenceStackSpill{0};
    uint64_t other{0};
};

struct PcSamplingAnalyzerData {
    std::string data{0};
    std::size_t size{0};
    std::size_t totalSize{0};
    std::unordered_map<uint64_t, SamplingInstrTotalRecord> pcSamplingRecord;
};

class OpAnalyzerPcSampling {
public:
    OpAnalyzerPcSampling() = default;
    ~OpAnalyzerPcSampling() = default;
    bool IsPcSamplingData(const std::string& fileName) const;
    void ParsePcSamplingData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void AnalyzePcSamplingDataAndSaveSummary(const std::string& output);
    bool IsPcSamplingMode() const;

private:
    void AnalyzeBinaryObject();
    void ReadObjdumpFile(const std::string& file);
    void GenerateSourceSummary(const std::string& output);
    void GeneratePcSummary(const std::string& output);
    void GenerateSummary(const std::string& output);
    bool isSamplingEnable_{false};
    uint64_t samplingByte_{0};
    std::unordered_map<std::string, PcSamplingAnalyzerData> pcSamplingData_;
    std::unordered_map<uint64_t, std::string> objectData_;
    std::unordered_map<uint64_t, SamplingInstrTotalRecord> pcSamplingRecord_;
};
} // namespace Analyze
} // namespace Acp
} // namespace Dvvp
#endif
