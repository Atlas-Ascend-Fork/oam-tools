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
#ifndef COLLECTOR_DVVP_MSPROFBIN_RUNNING_MODE_H
#define COLLECTOR_DVVP_MSPROFBIN_RUNNING_MODE_H
#include <set>
#include <vector>
#include <atomic>
#include "message/prof_params.h"
#include "utils/utils_tool.h"

namespace Collector {
namespace Dvvp {
namespace Msprofbin {

bool IsAppProcessUsage(const std::string& processUsage);
bool IsSignalTerminationStatus(int32_t waitStatus);

class RunningMode {
public:
    // check params dependence in specific mode
    virtual int32_t ModeParamsCheck() = 0;
    virtual int32_t RunModeTasks() = 0;
    virtual void UpdateOutputDirInfo();
    void StopRunningTasks() const;
    void RemoveRecordFile(const std::string& fileName) const;

    // marked when unexcepted quit
    std::atomic<bool> isQuit_;
    std::string jobResultDir_;
    std::set<std::string> jobResultDirList_;

protected:
    RunningMode(
        std::string preCheckParams, std::string modeName,
        SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    virtual ~RunningMode();
    int32_t CheckForbiddenParams() const;
    int32_t CheckNeccessaryParams() const;
    void OutputUselessParams() const;
    int32_t StartAnalyzeTask();
    int32_t StartParseTask();
    int32_t StartQueryTask();
    int32_t StartExportTask();
    int32_t RunExportSummaryTask(
        const analysis::dvvp::common::utils::ExecCmdParams& execCmdParams, std::vector<std::string>& envsV,
        int32_t& exitCode);
    int32_t RunExportTimelineTask(
        const analysis::dvvp::common::utils::ExecCmdParams& execCmdParams, std::vector<std::string>& envsV,
        int32_t& exitCode);
    int32_t RunExportDbTask(
        const analysis::dvvp::common::utils::ExecCmdParams& execCmdParams, std::vector<std::string>& envsV,
        int32_t& exitCode);
    int32_t CheckAnalysisEnv();
    int32_t WaitRunningProcess(std::string processUsage);
    // for parse, export, query mode
    int32_t GetOutputDirInfoFromParams();
    // for app, system mode
    int32_t GetOutputDirInfoFromRecord();
    int32_t HandleProfilingParams() const;
    void StopNoWait();

    std::string modeName_;
    // In any time, at most one child task Process is running in all the mode except system
    OsalProcess taskPid_;
    std::string taskName_;
    std::string preCheckParams_;
    // forbidden params
    std::set<int32_t> blackSet_;
    // useful params
    std::set<int32_t> whiteSet_;
    std::set<int32_t> neccessarySet_;
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params_;

private:
    std::string ConvertParamsSetToString(std::set<int32_t>& srcSet) const;
    void SetEnvList(std::vector<std::string>& envsV) const;

    std::string analysisPath_;
};

class AppMode : public RunningMode {
public:
    AppMode(std::string preCheckParams, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    ~AppMode() override;
    int32_t ModeParamsCheck() override;
    int32_t RunModeTasks() override;

private:
    int32_t StartAppTask(bool needWait = true);
    int32_t StartAppTaskForDynProf();
    void SetDefaultParams() const;
    void SetDefaultParamsByPlatformType() const;
};

class SystemMode : public RunningMode {
public:
    SystemMode(std::string preCheckParams, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    ~SystemMode() override;
    int32_t ModeParamsCheck() override;
    int32_t RunModeTasks() override;

private:
    bool DataWillBeCollected() const;
    int32_t CheckIfDeviceOnline() const;
    int32_t CheckHostSysParams() const;
    int32_t StartSysTaskByProfApi();
    void SetSysDefaultParams() const;
};

class ParseMode : public RunningMode {
public:
    ParseMode(std::string preCheckParams, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    ~ParseMode() override;
    int32_t ModeParamsCheck() override;
    int32_t RunModeTasks() override;
    void UpdateOutputDirInfo() override;
};

class QueryMode : public RunningMode {
public:
    QueryMode(std::string preCheckParams, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    ~QueryMode() override;
    int32_t ModeParamsCheck() override;
    int32_t RunModeTasks() override;
    void UpdateOutputDirInfo() override;
};

class ExportMode : public RunningMode {
public:
    ExportMode(std::string preCheckParams, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    ~ExportMode() override;
    int32_t ModeParamsCheck() override;
    int32_t RunModeTasks() override;
    void UpdateOutputDirInfo() override;
};

class AnalyzeMode : public RunningMode {
public:
    AnalyzeMode(std::string preCheckParams, SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);
    ~AnalyzeMode() override;
    int32_t ModeParamsCheck() override;
    int32_t RunModeTasks() override;
    void UpdateOutputDirInfo() override;
};
} // namespace Msprofbin
} // namespace Dvvp
} // namespace Collector

#endif
