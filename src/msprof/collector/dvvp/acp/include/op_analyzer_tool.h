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
#ifndef ANALYSIS_DVVP_ANALYZE_OP_ANALYZER_H
#define ANALYSIS_DVVP_ANALYZE_OP_ANALYZER_H

#include <vector>
#include <mutex>
#include <condition_variable>
#include <fstream>
#include <iostream>
#include <iomanip>
#include "data_struct_tool.h"
#include "utils/utils_tool.h"
#include "op_analyzer_pmu_tool.h"
#include "op_analyzer_base_tool.h"
#include "op_analyzer_pc_sampling_tool.h"
#include "op_analyzer_biu_tool.h"

namespace Dvvp {
namespace Acp {
namespace Analyze {
using namespace analysis::dvvp::common::utils;
class OpAnalyzer : public OpAnalyzerBase {
public:
    explicit OpAnalyzer();
    ~OpAnalyzer();

public:
    void InitAnalyzerByDeviceId(const std::string& deviceId);
    void OnOpData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void PrintStats();
    void WaitOpDone();

private:
    void DispatchOpData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void FlushOpData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    std::string CreateOpFile(const std::string& path, const std::string& name) const;
    void WriteOpTitle(std::ofstream& file) const;
    void WriteOpData(std::ofstream& file);
    void WriteOpBaseData(std::ofstream& file, std::vector<std::vector<KernelDetail>>& dataVec);
    void HandleOpTotalTime(KernelDetail& data, float& aicTotalTimeAvg, float& aivTotalTimeAvg) const;
    void WriteOpPmuData(std::ofstream& file, std::vector<std::vector<KernelDetail>>& dataVec);
    void HandleOpPmuData(const std::string& name, KernelDetail& data, float* avg, uint32_t avgLen) const;
    void OpAssociation(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void PreAssociation(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void BlockAssociation();
    void BlockInfoMatch(std::string key, KernelDetail& value);
    void SubTaskAssociation();
    void SubTaskInfoMatch(KernelDetail& value);
    void StoreAssociation() const;
    float CeilPrecision(float value) const;
    void WriteFloatDataToFile(std::ofstream& file, float& data);

private:
    bool inited_;
    uint32_t metricsPmuNum_;
    int64_t aicCoreNum_;
    int64_t aivCoreNum_;
    double aicFreq_;
    uint16_t highBlockDim_;
    uint16_t lowBlockDim_;
    uint32_t replayTime_;
    std::mutex flushMtx_;
    std::condition_variable flushCv_;
    SHARED_PTR_ALIA<OpAnalyzerPmu> analyzerPmu_;
    SHARED_PTR_ALIA<OpAnalyzerBiu> analyzerBiu_;
    OpAnalyzerPcSampling pcSampling_;
};
} // namespace Analyze
} // namespace Acp
} // namespace Dvvp

#endif
