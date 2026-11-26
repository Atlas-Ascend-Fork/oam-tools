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
#include "running_mode_tool.h"
#include <algorithm>
#include <cctype>
#include <iterator>
#include <chrono>
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include "errno/error_code_tool.h"
#include "input_parser_tool.h"
#include "cmd_log/cmd_log_tool.h"
#include "msprof_dlog_tool.h"
#include "ai_drv_dev_api.h"
#include "msprof_params_adapter_tool.h"
#include "config_manager_tool.h"
#include "application_tool.h"
#include "osal.h"
#include "platform/platform_tool.h"
#include "env_manager_tool.h"
#include "dyn_prof_client_tool.h"
#include "prof_api_loader.h"

namespace Collector {
namespace Dvvp {
namespace Msprofbin {
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;

namespace {
constexpr int32_t ENV_OVERWRITE = 1;
constexpr int32_t OPEN_FAILED = -1;

bool IsSingleLevelDirName(const std::string& dirName)
{
    if (dirName.empty() || dirName == "." || dirName == ".." || dirName.size() > MAX_PATH_LENGTH ||
        dirName.find('/') != std::string::npos || dirName.find('\\') != std::string::npos) {
        return false;
    }
    return std::all_of(dirName.begin(), dirName.end(), [](unsigned char ch) { return std::iscntrl(ch) == 0; });
}

int32_t ReadRecordFile(const std::string& absolutePath, const std::string& recordFile, std::string& content)
{
    content.clear();
    const int32_t fd = open(absolutePath.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK | O_NOCTTY);
    if (fd < 0) {
        const int32_t openErrno = errno;
        MSPROF_LOGE("Failed to open %s, errno=%d, err=%s", recordFile.c_str(), openErrno, strerror(openErrno));
        return PROFILING_FAILED;
    }
    struct stat fileStat;
    if (fstat(fd, &fileStat) != 0 || !S_ISREG(fileStat.st_mode) || fileStat.st_uid != geteuid() ||
        fileStat.st_size <= 0 || fileStat.st_size > MSVP_SMALL_FILE_MAX_LEN) {
        (void)close(fd);
        MSPROF_LOGE("Record file %s is invalid", recordFile.c_str());
        return PROFILING_FAILED;
    }
    const int32_t flags = fcntl(fd, F_GETFL);
    if (flags < 0 ||
        fcntl(fd, F_SETFL, static_cast<int32_t>(static_cast<uint32_t>(flags) & ~static_cast<uint32_t>(O_NONBLOCK))) !=
            0) {
        const int32_t flagsErrno = errno;
        (void)close(fd);
        MSPROF_LOGE(
            "Failed to reset flags for %s, errno=%d, err=%s", recordFile.c_str(), flagsErrno, strerror(flagsErrno));
        return PROFILING_FAILED;
    }

    std::vector<char> buffer(static_cast<size_t>(fileStat.st_size));
    size_t readSize = 0;
    while (readSize < buffer.size()) {
        const ssize_t onceSize = read(fd, buffer.data() + readSize, buffer.size() - readSize);
        if (onceSize < 0 && errno == EINTR) {
            continue;
        }
        if (onceSize <= 0) {
            break;
        }
        readSize += static_cast<size_t>(onceSize);
    }
    const int32_t readErrno = errno;
    const int32_t closeRet = close(fd);
    if (readSize != buffer.size() || closeRet != 0) {
        MSPROF_LOGE("Failed to read %s, errno=%d, err=%s", recordFile.c_str(), readErrno, strerror(readErrno));
        return PROFILING_FAILED;
    }
    content.assign(buffer.data(), readSize);
    return PROFILING_SUCCESS;
}

int32_t ParseRecordContent(
    const std::string& resultDir, const std::string& content, std::set<std::string>& jobResultDirList)
{
    std::string canonicalResultDir = Utils::CanonicalizePath(resultDir);
    if (canonicalResultDir.empty()) {
        MSPROF_LOGE("The output dir is invalid");
        return PROFILING_FAILED;
    }
    const int32_t rootFd = open(canonicalResultDir.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (rootFd == OPEN_FAILED) {
        MSPROF_LOGE("Failed to open output dir %s", canonicalResultDir.c_str());
        return PROFILING_FAILED;
    }

    std::istringstream contentStream(content);
    std::string baseDir;
    std::set<std::string> parsedDirs;
    while (std::getline(contentStream, baseDir)) {
        Utils::RemoveEndCharacter(baseDir, '\r');
        int32_t dirFd = OPEN_FAILED;
        struct stat dirStat;
        if (!IsSingleLevelDirName(baseDir) ||
            (dirFd = openat(rootFd, baseDir.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)) == OPEN_FAILED ||
            fstat(dirFd, &dirStat) != 0 || !S_ISDIR(dirStat.st_mode) || dirStat.st_uid != geteuid()) {
            if (dirFd != OPEN_FAILED) {
                (void)close(dirFd);
            }
            MSPROF_LOGW("Invalid record dir in output record");
            continue;
        }
        (void)close(dirFd);
        parsedDirs.insert(resultDir + baseDir);
    }
    (void)close(rootFd);
    if (parsedDirs.empty()) {
        MSPROF_LOGW("Output record is empty");
        return PROFILING_FAILED;
    }
    jobResultDirList.insert(parsedDirs.begin(), parsedDirs.end());
    return PROFILING_SUCCESS;
}

bool IsSecureResultDir(const std::string& resultDir)
{
    const int32_t dirFd = open(resultDir.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (dirFd < 0) {
        return false;
    }
    struct stat dirStat;
    const bool isValid = fstat(dirFd, &dirStat) == 0 && S_ISDIR(dirStat.st_mode) && dirStat.st_uid == geteuid();
    (void)close(dirFd);
    return isValid;
}

void RestoreSampleConfigEnv(const std::string& originalValue, bool originalValueExist)
{
    if (originalValueExist) {
        (void)setenv(PROFILER_SAMPLE_CONFIG_ENV, originalValue.c_str(), ENV_OVERWRITE);
        return;
    }
    (void)unsetenv(PROFILER_SAMPLE_CONFIG_ENV);
}

// 临时把本进程的 stderr 指向空设备。子进程创建只重定向 fd 1（stdoutRedirectFile），
// 而 argparse 的参数错误走 stderr，因此探测这类会打报错的命令时需要一并屏蔽 fd 2。
// 恢复到析构时进行，作用域应尽量只包住 fork 本身，避免影响其它线程的输出。
class ScopedStderrSilencer {
public:
    ScopedStderrSilencer()
    {
        int32_t nullFd = open("/dev/null", O_WRONLY);
        if (nullFd < 0) {
            return;
        }
        int32_t savedFd = dup(STDERR_FILENO);
        if (savedFd < 0) {
            (void)close(nullFd);
            return;
        }
        if (dup2(nullFd, STDERR_FILENO) < 0) {
            (void)close(savedFd);
            (void)close(nullFd);
            return;
        }
        nullFd_ = nullFd;
        savedFd_ = savedFd;
    }

    ~ScopedStderrSilencer()
    {
        if (savedFd_ >= 0) {
            (void)dup2(savedFd_, STDERR_FILENO);
            (void)close(savedFd_);
        }
        if (nullFd_ >= 0) {
            (void)close(nullFd_);
        }
    }

    ScopedStderrSilencer(const ScopedStderrSilencer&) = delete;
    ScopedStderrSilencer& operator=(const ScopedStderrSilencer&) = delete;

private:
    int32_t nullFd_ = -1;
    int32_t savedFd_ = -1;
};
} // namespace
using namespace analysis::dvvp::message;
using namespace analysis::dvvp::common::cmdlog;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::driver;
using namespace Analysis::Dvvp::Msprof;
using namespace Analysis::Dvvp::Common::Config;
using namespace Analysis::Dvvp::Common::Platform;
using namespace analysis::dvvp::common::utils;
using namespace Collector::Dvvp::DynProf;

namespace {
// App mode accepts every profiling switch; a file scope table keeps the constructor short while the
// list itself stays easy to extend next to the other mode definitions.
// clang-format off
const int32_t APP_MODE_WHITE_SET[] = {
    ARGS_OUTPUT,
    ARGS_STORAGE_LIMIT,
    ARGS_APPLICATION,
    ARGS_ENVIRONMENT,
    ARGS_DYNAMIC_PROF,
    ARGS_DYNAMIC_PROF_PID,
    ARGS_AIC_MODE,
    ARGS_AIC_METRICS,
    ARGS_AIV_MODE,
    ARGS_AIV_METRICS,
    ARGS_NPU_EVENTS,
    ARGS_LLC_PROFILING,
    ARGS_ASCENDCL,
    ARGS_AI_CORE,
    ARGS_AIV,
    ARGS_MODEL_EXECUTION,
    ARGS_TASK_MEMORY,
    ARGS_SYS_LOW_POWER,
    ARGS_RUNTIME_API,
    ARGS_TASK_TSFW,
    ARGS_TASK_TIME,
    ARGS_GE_API,
    ARGS_AICPU,
    ARGS_CPU_PROFILING,
    ARGS_SYS_PROFILING,
    ARGS_PID_PROFILING,
    ARGS_HARDWARE_MEM,
    ARGS_IO_PROFILING,
    ARGS_INTERCONNECTION_PROFILING,
    ARGS_DVPP_PROFILING,
    ARGS_TASK_BLOCK,
    ARGS_L2_PROFILING,
    ARGS_AIC_FREQ,
    ARGS_AIV_FREQ,
    ARGS_INSTR_PROFILING_FREQ,
    ARGS_INSTR_PROFILING,
    ARGS_HCCL,
    ARGS_SYS_SAMPLING_FREQ,
    ARGS_PID_SAMPLING_FREQ,
    ARGS_HARDWARE_MEM_SAMPLING_FREQ,
    ARGS_MEM_SERVICEFLOW,
    ARGS_IO_SAMPLING_FREQ,
    ARGS_DVPP_FREQ,
    ARGS_CPU_SAMPLING_FREQ,
    ARGS_INTERCONNECTION_FREQ,
    ARGS_HOST_SYS,
    ARGS_PYTHON_PATH,
    ARGS_MSPROFTX,
    ARGS_DELAY_PROF,
    ARGS_DURATION_PROF,
    ARGS_OP_TYPE,
    ARGS_EXPORT_TYPE,
    ARGS_MSTX_DOMAIN_INCLUDE,
    ARGS_MSTX_DOMAIN_EXCLUDE,
    ARGS_NTS_METRICS,
    ARGS_AICORE_SHAPE,
    ARGS_FTRACE,
    ARGS_FTRACE_PERIOD,
    ARGS_FTRACE_BUFSIZE,
    // Host CPU PMU counting works in app mode too: it measures the host counters of the machine the
    // application runs on, and the application is what makes the run worth measuring.
    ARGS_HOST_PMU_SAMPLE,
    ARGS_HOST_PMU_EVENTS,
    ARGS_HOST_PMU_OS_EVENTS,
    ARGS_HOST_PMU_INTERVAL};
// clang-format on

std::set<int32_t> BuildAppModeWhiteSet()
{
    return std::set<int32_t>(std::begin(APP_MODE_WHITE_SET), std::end(APP_MODE_WHITE_SET));
}
} // namespace

bool IsAppProcessUsage(const std::string& processUsage) { return processUsage == "App" || processUsage == "app"; }

bool IsSignalTerminationStatus(uint32_t waitStatus) { return WIFSIGNALED(waitStatus); }

RunningMode::RunningMode(std::string preCheckParams, std::string modeName, SHARED_PTR_ALIA<ProfileParams> params)
    : isQuit_(false),
      modeName_(modeName),
      taskPid_(MSVP_PROCESS),
      preCheckParams_(preCheckParams),
      blackSet_(),
      whiteSet_(),
      neccessarySet_(),
      params_(params)
{}

RunningMode::~RunningMode() {}

std::string RunningMode::ConvertParamsSetToString(std::set<int32_t>& srcSet) const
{
    std::string result;
    if (srcSet.empty()) {
        return result;
    }
    std::stringstream ssParams;
    for (int32_t paramId : srcSet) {
        ssParams << "--" << LONG_OPTIONS[paramId].name << " ";
    }
    result = ssParams.str();
    Utils::RemoveEndCharacter(result, ' ');
    return result;
}

int32_t RunningMode::CheckForbiddenParams() const
{
    if (params_ == nullptr || params_->usedParams.empty()) {
        return PROFILING_FAILED;
    }
    std::set<int32_t> usedForbiddenParams;
    set_intersection(
        params_->usedParams.begin(), params_->usedParams.end(), blackSet_.begin(), blackSet_.end(),
        inserter(usedForbiddenParams, usedForbiddenParams.begin()));
    if (!usedForbiddenParams.empty()) {
        std::string forbiddenParamsStr = ConvertParamsSetToString(usedForbiddenParams);
        CmdLog::CmdErrorLog(
            "The argument %s is forbidden when --%s is not empty", forbiddenParamsStr.c_str(), preCheckParams_.c_str());
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

int32_t RunningMode::CheckNeccessaryParams() const
{
    if (params_ == nullptr || params_->usedParams.empty()) {
        return PROFILING_FAILED;
    }
    std::set<int32_t> moreReqParams;
    set_difference(
        neccessarySet_.begin(), neccessarySet_.end(), params_->usedParams.begin(), params_->usedParams.end(),
        inserter(moreReqParams, moreReqParams.begin()));
    if (!moreReqParams.empty()) {
        std::string reqParams = ConvertParamsSetToString(moreReqParams);
        CmdLog::CmdErrorLog(
            "The argument %s is necessary when --%s is not empty", reqParams.c_str(), preCheckParams_.c_str());
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

void RunningMode::OutputUselessParams() const
{
    if (params_ == nullptr || params_->usedParams.empty()) {
        return;
    }
    std::set<int32_t> uselessParams;
    set_difference(
        params_->usedParams.begin(), params_->usedParams.end(), whiteSet_.begin(), whiteSet_.end(),
        inserter(uselessParams, uselessParams.begin()));
    if (!uselessParams.empty()) {
        std::string noEffectParams = ConvertParamsSetToString(uselessParams);
        CmdLog::CmdWarningLog(
            "The argument %s is useless when --%s is not empty", noEffectParams.c_str(), preCheckParams_.c_str());
    }
}

void RunningMode::UpdateOutputDirInfo()
{
    int32_t ret = GetOutputDirInfoFromRecord();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGW("Unable to get output info from RunningMode.");
    }
}

int32_t RunningMode::GetOutputDirInfoFromParams()
{
    if (!jobResultDir_.empty()) {
        MSPROF_LOGW("Unable to get output info from params, exist output info before.");
        return PROFILING_FAILED;
    }
    jobResultDir_ = params_->result_dir;
    return PROFILING_SUCCESS;
}

int32_t RunningMode::GetOutputDirInfoFromRecord()
{
    if (!jobResultDir_.empty()) {
        MSPROF_LOGW("Unable to get output info from record, exist output info before.");
        return PROFILING_FAILED;
    }
    std::string resultDirTmp = params_->result_dir;
    Utils::EnsureEndsInSlash(resultDirTmp);
    std::string pidStr = std::to_string(Utils::GetPid());
    std::string recordFile = pidStr + MSVP_UNDERLINE + OUTPUT_RECORD;
    std::string outPut = resultDirTmp + recordFile;
    std::string content;
    if (ReadRecordFile(outPut, recordFile, content) != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }

    const int32_t parseRet = ParseRecordContent(resultDirTmp, content, jobResultDirList_);
    if (parseRet == PROFILING_SUCCESS) {
        RemoveRecordFile(outPut);
    }
    return parseRet;
}

void RunningMode::RemoveRecordFile(const std::string& fileName) const
{
    if (!(Utils::IsFileExist(fileName))) {
        return;
    }
    if (remove(fileName.c_str()) != EOK) {
        MSPROF_LOGE("Remove file: %s failed!", Utils::BaseName(fileName).c_str());
        return;
    }
    return;
}

void RunningMode::StopRunningTasks() const
{
    if (taskPid_ == MSVP_PROCESS) {
        return;
    }
    static const std::string ENV_PATH = "PATH=/usr/bin/:/usr/sbin:/var:/bin";
    std::vector<std::string> envsV;
    envsV.push_back(ENV_PATH);
    std::string cmd = "kill";
    ExecCmdParams execCmdParams(cmd, true, "");
    std::vector<std::string> argsV;
    argsV.push_back("-s");
    argsV.push_back("SIGINT");
    argsV.push_back(std::to_string(static_cast<int32_t>(taskPid_)));
    int32_t exitCode = INVALID_EXIT_CODE;
    OsalProcess killProces = MSVP_PROCESS;
    int32_t ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsV, envsV, exitCode, killProces);
    MSPROF_LOGI(
        "[%s mode] Stop %s Process:%d, ret=%d", modeName_.c_str(), taskName_.c_str(), static_cast<int32_t>(taskPid_),
        ret);
}

void RunningMode::SetEnvList(std::vector<std::string>& envsV) const
{
    envsV = Analysis::Dvvp::App::EnvManager::instance()->GetGlobalEnv();
}

int32_t RunningMode::StartAnalyzeTask()
{
    if (isQuit_) {
        MSPROF_LOGE("Start analyze task error, msprofbin has quit.");
        return PROFILING_FAILED;
    }

    if (taskPid_ != MSVP_PROCESS) {
        MSPROF_LOGE(
            "Start analyze task error, process %d is running,"
            "only one child process can run at the same time.",
            static_cast<int32_t>(taskPid_));
        return PROFILING_FAILED;
    }

    if (jobResultDir_.empty() || analysisPath_.empty()) {
        MSPROF_LOGE("Start analyze task error, get output dir and msprof.py script failed.");
        return PROFILING_FAILED;
    }

    CmdLog::CmdInfoLog("Start analyze data in %s.", Utils::BaseName(jobResultDir_).c_str());
    taskName_ = "Analyze";
    std::string cmd = params_->pythonPath;
    ExecCmdParams execCmdParams(cmd, true, "");
    std::vector<std::string> envsV;
    int32_t exitCode = INVALID_EXIT_CODE;
    SetEnvList(envsV);
    std::vector<std::string> argsV = {
        analysisPath_, "analyze", "-dir=" + jobResultDir_, "-r=" + params_->analyzeRuleSwitch};
    if (params_->clearSwitch == "on") {
        argsV.push_back("--clear");
    }
    if (params_->exportType == "db") {
        argsV.push_back("--type=db");
    }

    int32_t ret = Utils::ExecCmd(execCmdParams, argsV, envsV, exitCode, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch analyze task, data path: %s", Utils::BaseName(jobResultDir_).c_str());
        return PROFILING_FAILED;
    }

    ret = WaitRunningProcess(taskName_);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to wait analyze process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
        return PROFILING_FAILED;
    }

    taskPid_ = MSVP_PROCESS;
    exitCode = INVALID_EXIT_CODE;
    CmdLog::CmdInfoLog("Analyze all data in %s done.", Utils::BaseName(jobResultDir_).c_str());
    return PROFILING_SUCCESS;
}

int32_t RunningMode::StartParseTask()
{
    if (isQuit_) {
        MSPROF_LOGE("Start parse task error, msprofbin has quit");
        return PROFILING_FAILED;
    }
    if (taskPid_ != MSVP_PROCESS) {
        MSPROF_LOGE(
            "Start parse task error, process %d is running,"
            "only one child process can run at the same time.",
            static_cast<int32_t>(taskPid_));
        return PROFILING_FAILED;
    }
    if (jobResultDir_.empty() || analysisPath_.empty()) {
        MSPROF_LOGE("Start parse task error, get output dir and msprof.py script failed.");
        return PROFILING_FAILED;
    }
    CmdLog::CmdInfoLog("Start parse data in %s.", Utils::BaseName(jobResultDir_).c_str());
    taskName_ = "Parse";

    std::string cmd = params_->pythonPath;
    ExecCmdParams execCmdParams(cmd, true, "");
    std::vector<std::string> envsV;
    int32_t exitCode = INVALID_EXIT_CODE;
    SetEnvList(envsV);
    std::vector<std::string> argsV = {analysisPath_, "import", "-dir=" + jobResultDir_};
    int32_t ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsV, envsV, exitCode, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch parse task, data path: %s", Utils::BaseName(jobResultDir_).c_str());
        return PROFILING_FAILED;
    }
    ret = WaitRunningProcess(taskName_);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to wait parse process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
        return PROFILING_FAILED;
    }
    taskPid_ = MSVP_PROCESS;
    exitCode = INVALID_EXIT_CODE;
    CmdLog::CmdInfoLog("Parse all data in %s done.", Utils::BaseName(jobResultDir_).c_str());
    return PROFILING_SUCCESS;
}

int32_t RunningMode::StartQueryTask()
{
    if (isQuit_) {
        MSPROF_LOGE("Start query task error, msprofbin has quit");
        return PROFILING_FAILED;
    }
    if (taskPid_ != MSVP_PROCESS) {
        MSPROF_LOGE(
            "Start query task error, process %d is running,"
            "only one child process can run at the same time.",
            static_cast<int32_t>(taskPid_));
        return PROFILING_FAILED;
    }
    if (jobResultDir_.empty() || analysisPath_.empty()) {
        MSPROF_LOGE("Start query task error, get output dir and msprof.py script failed.");
        return PROFILING_FAILED;
    }
    CmdLog::CmdInfoLog("Start query data in %s.", Utils::BaseName(jobResultDir_).c_str());
    taskName_ = "Query";

    std::string cmd = params_->pythonPath;
    ExecCmdParams execCmdParams(cmd, true, "");
    std::vector<std::string> envsV;
    int32_t exitCode = INVALID_EXIT_CODE;
    SetEnvList(envsV);
    std::vector<std::string> argsV = {analysisPath_, "query", "-dir=" + jobResultDir_};
    int32_t ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsV, envsV, exitCode, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch query task, data path: %s", Utils::BaseName(jobResultDir_).c_str());
        return PROFILING_FAILED;
    }
    ret = WaitRunningProcess(taskName_);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to wait query process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
        return PROFILING_FAILED;
    }
    taskPid_ = MSVP_PROCESS;
    exitCode = INVALID_EXIT_CODE;
    CmdLog::CmdInfoLog("Query all data in %s done.", Utils::BaseName(jobResultDir_).c_str());
    return PROFILING_SUCCESS;
}

int32_t RunningMode::RunExportDbTask(
    const ExecCmdParams& execCmdParams, std::vector<std::string>& envsV, int32_t& exitCode, bool exportAllSupported)
{
    std::vector<std::string> argsDbV = {analysisPath_, "export", "db", "-dir=" + jobResultDir_};
    // export 子命令上的 -reports 与 export all 由同一新版本引入，all 与 report 同时支持，
    // 因此以 exportAllSupported 作为唯一判据；老包传入会以参数非法失败。
    // 注意 export timeline 自始支持 -reports，不受此约束。
    if (exportAllSupported && !params_->reportsPath.empty()) {
        argsDbV.emplace_back("-reports=" + params_->reportsPath);
    }

    int32_t ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsDbV, envsV, exitCode, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch export db task, data path: %s", Utils::BaseName(jobResultDir_).c_str());
        return PROFILING_FAILED;
    }
    ret = WaitRunningProcess(taskName_ + " db");
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to wait export db process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
        return PROFILING_FAILED;
    }
    taskPid_ = MSVP_PROCESS;
    exitCode = INVALID_EXIT_CODE;
    return PROFILING_SUCCESS;
}

int32_t RunningMode::RunExportSummaryTask(
    const ExecCmdParams& execCmdParams, std::vector<std::string>& envsV, int32_t& exitCode, bool exportAllSupported)
{
    std::vector<std::string> argsSummaryV = {
        analysisPath_, "export", "summary", "-dir=" + jobResultDir_, "--format=" + params_->exportSummaryFormat};
    if (params_->clearSwitch == "on") {
        argsSummaryV.emplace_back("--clear");
    }
    if (params_->exportModelId != DEFAULT_MODEL_ID) {
        argsSummaryV.emplace_back("--model-id=" + params_->exportModelId);
    }
    if (params_->exportIterationId != DEFAULT_INTERATION_ID) {
        argsSummaryV.emplace_back("--iteration-id=" + params_->exportIterationId);
    }
    // export 子命令上的 -reports 与 export all 由同一新版本引入，all 与 report 同时支持，
    // 因此以 exportAllSupported 作为唯一判据；老包传入会以参数非法失败。
    if (exportAllSupported && !params_->reportsPath.empty()) {
        argsSummaryV.emplace_back("-reports=" + params_->reportsPath);
    }
    int32_t ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsSummaryV, envsV, exitCode, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch export summary task, data path: %s", Utils::BaseName(jobResultDir_).c_str());
        return PROFILING_FAILED;
    }
    ret = WaitRunningProcess(taskName_ + " summary");
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to wait export summary process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
        return PROFILING_FAILED;
    }
    taskPid_ = MSVP_PROCESS;
    exitCode = INVALID_EXIT_CODE;
    return PROFILING_SUCCESS;
}
int32_t RunningMode::RunExportTimelineTask(
    const ExecCmdParams& execCmdParams, std::vector<std::string>& envsV, int32_t& exitCode)
{
    std::vector<std::string> argsTimelineV = {analysisPath_, "export", "timeline", "-dir=" + jobResultDir_};
    if (params_->exportModelId != DEFAULT_MODEL_ID) {
        argsTimelineV.emplace_back("--model-id=" + params_->exportModelId);
    }
    if (params_->exportIterationId != DEFAULT_INTERATION_ID) {
        argsTimelineV.emplace_back("--iteration-id=" + params_->exportIterationId);
    }
    if (!params_->reportsPath.empty()) {
        argsTimelineV.emplace_back("-reports=" + params_->reportsPath);
    }
    int32_t ret =
        analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsTimelineV, envsV, exitCode, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch export timeline task, data path: %s", Utils::BaseName(jobResultDir_).c_str());
        return PROFILING_FAILED;
    }
    ret = WaitRunningProcess(taskName_ + " timeline");
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to wait export timeline process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
        return PROFILING_FAILED;
    }
    taskPid_ = MSVP_PROCESS;
    exitCode = INVALID_EXIT_CODE;
    return PROFILING_SUCCESS;
}

int32_t RunningMode::RunExportAllTask(
    const ExecCmdParams& execCmdParams, std::vector<std::string>& envsV, int32_t& exitCode)
{
    std::vector<std::string> argsAllV = {analysisPath_, "export", "all", "-dir=" + jobResultDir_};
    if (params_->clearSwitch == "on") {
        argsAllV.emplace_back("--clear");
    }
    if (params_->exportModelId != DEFAULT_MODEL_ID) {
        argsAllV.emplace_back("--model-id=" + params_->exportModelId);
    }
    if (params_->exportIterationId != DEFAULT_INTERATION_ID) {
        argsAllV.emplace_back("--iteration-id=" + params_->exportIterationId);
    }
    if (!params_->reportsPath.empty()) {
        argsAllV.emplace_back("-reports=" + params_->reportsPath);
    }
    // --summary-format 仍然透传：export all 接受该参数但恒按 csv 产出 summary。
    argsAllV.emplace_back("--format=" + params_->exportSummaryFormat);

    int32_t ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsAllV, envsV, exitCode, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch export all task, data path: %s", Utils::BaseName(jobResultDir_).c_str());
        return PROFILING_FAILED;
    }
    ret = WaitRunningProcess(taskName_ + " all");
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to wait export all process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
        return PROFILING_FAILED;
    }
    taskPid_ = MSVP_PROCESS;
    exitCode = INVALID_EXIT_CODE;
    return PROFILING_SUCCESS;
}

bool RunningMode::IsExportAllSupported() const
{
    if (analysisPath_.empty() || params_ == nullptr) {
        return false;
    }
    // 以子命令是否被解析器接受作为判定依据：支持时退出码为 0，旧版本会以参数非法退出。
    // 探测输出对用户无意义：--help 正文走 stdout，由 stdoutRedirectFile 丢弃；老包的
    // invalid choice 报错走 stderr，需在 fork 前临时屏蔽 fd 2，避免污染 msprof 输出流。
    static const std::string NULL_DEVICE = "/dev/null";
    // 与仓库其余调用点一致使用异步路径：同步路径会在父进程内 chdir，改变本进程的工作目录，
    // 进而影响后续 fork 的导出/查询子进程对相对路径的解析。
    ExecCmdParams execCmdParams(params_->pythonPath, true, NULL_DEVICE);
    std::vector<std::string> envsV;
    SetEnvList(envsV);
    std::vector<std::string> argsV = {analysisPath_, "export", "all", "--help"};
    // 探测不属于导出任务，使用独立句柄，避免占用 taskPid_。
    OsalProcess probePid = MSVP_PROCESS;
    int32_t exitCode = 0;
    int32_t ret = PROFILING_SUCCESS;
    {
        // 只包住 fork 本身：子进程在此处继承指向空设备的 fd 2，随后立即恢复本进程的 stderr。
        ScopedStderrSilencer silencer;
        ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsV, envsV, exitCode, probePid);
    }
    if (ret != PROFILING_SUCCESS) {
        // 仅记录不支持；探测自身异常属内部细节，INFO 日志不体现失败措辞。
        MSPROF_LOGI("[Export Mode] export all is not supported by the analysis package.");
        return false;
    }
    // 异步模式只返回子进程句柄，退出码需自行回收进程后从 wait status 解析。
    bool isExited = false;
    int32_t waitStatus = 0;
    ret = analysis::dvvp::common::utils::Utils::WaitProcess(probePid, isExited, waitStatus, true);
    if (ret != PROFILING_SUCCESS || !isExited) {
        MSPROF_LOGI("[Export Mode] export all is not supported by the analysis package.");
        return false;
    }
    // 被信号终止时 wait status 不是退出码，判为不支持。
    const uint32_t status = static_cast<uint32_t>(waitStatus);
    const bool terminatedBySignal = IsSignalTerminationStatus(status);
    const bool supported = !terminatedBySignal && (WEXITSTATUS(status) == 0);
    if (!supported) {
        MSPROF_LOGI("[Export Mode] export all is not supported by the analysis package.");
        return false;
    }
    MSPROF_LOGI("[Export Mode] export all is supported by the analysis package.");
    return true;
}

int32_t RunningMode::StartExportTask()
{
    if (isQuit_) {
        MSPROF_LOGE("Start export task error, msprofbin has quit");
        return PROFILING_FAILED;
    }
    if (taskPid_ != MSVP_PROCESS) {
        MSPROF_LOGE(
            "Start export task error, process %d is running,"
            "only one child process can run at the same time.",
            static_cast<int32_t>(taskPid_));
        return PROFILING_FAILED;
    }
    if (jobResultDir_.empty() || analysisPath_.empty()) {
        MSPROF_LOGE("Start export task error, get output dir and msprof.py script failed.");
        return PROFILING_FAILED;
    }
    CmdLog::CmdInfoLog("Start export data in %s.", Utils::BaseName(jobResultDir_).c_str());
    taskName_ = "Export";

    std::string cmd = params_->pythonPath;
    ExecCmdParams execCmdParams(cmd, true, "");
    std::vector<std::string> envsV;
    int32_t exitCode = INVALID_EXIT_CODE;
    SetEnvList(envsV);
    // 分析包是否支持 export all 子命令：--type=all 是对应的上层开关。
    // -reports 与 export all 由同一新版本引入（all 与 report 同时支持），因此 summary、db 的
    // -reports 门控同样以该探测为准。
    const bool exportAllSupported = IsExportAllSupported();
    if (params_->exportType == "db") {
        if (RunExportDbTask(execCmdParams, envsV, exitCode, exportAllSupported) != PROFILING_SUCCESS) {
            MSPROF_LOGE("Export db failed in %s.", Utils::BaseName(jobResultDir_).c_str());
            return PROFILING_FAILED;
        }
    } else if (params_->exportType == "all" && exportAllSupported) {
        if (RunExportAllTask(execCmdParams, envsV, exitCode) != PROFILING_SUCCESS) {
            // export all 失败说明分析包支持该能力但执行出错，不回退到两次调用，避免重复解析并掩盖真实错误。
            MSPROF_LOGE("Export all failed in %s.", Utils::BaseName(jobResultDir_).c_str());
            return PROFILING_FAILED;
        }
    } else {
        if (params_->exportType == "all") {
            // --type=all 但解析包不支持 export all：回退到 timeline + summary 两次调用。
            // 回退原因只记录到日志，不向用户打屏。
            MSPROF_LOGW(
                "The analysis package does not support 'export all', fall back to export timeline and summary.");
        }
        if (RunExportTimelineTask(execCmdParams, envsV, exitCode) != PROFILING_SUCCESS) {
            MSPROF_LOGE("Export timeline failed in %s.", Utils::BaseName(jobResultDir_).c_str());
            return PROFILING_FAILED;
        }
        if (RunExportSummaryTask(execCmdParams, envsV, exitCode, exportAllSupported) != PROFILING_SUCCESS) {
            MSPROF_LOGE("Export summary failed in %s.", Utils::BaseName(jobResultDir_).c_str());
            return PROFILING_FAILED;
        }
    }
    CmdLog::CmdInfoLog("Export all data in %s done.", Utils::BaseName(jobResultDir_).c_str());
    return PROFILING_SUCCESS;
}

void RunningMode::StopNoWait()
{
    CmdLog::CmdWarningLog("Receive stop signal.");
    DynProfCliMgr::instance()->StopDynProfCli();
    StopRunningTasks();
    UpdateOutputDirInfo();
}

int32_t RunningMode::WaitRunningProcess(std::string processUsage)
{
    if (taskPid_ == MSVP_PROCESS) {
        MSPROF_LOGE("[WaitRunningProcess] Invalid task pid.");
        return PROFILING_FAILED;
    }
    bool isExited = false;
    int32_t exitCode = 0;
    int32_t ret = PROFILING_SUCCESS;
    static const int32_t SLEEP_INTEVAL_US = 1000000;
    for (;;) {
        ret = analysis::dvvp::common::utils::Utils::WaitProcess(taskPid_, isExited, exitCode, false);
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE(
                "Failed to wait %s process %d to exit, ret=%d", processUsage.c_str(), static_cast<int32_t>(taskPid_),
                ret);
            return ret;
        }
        if (isExited) {
            const uint32_t waitStatus = static_cast<uint32_t>(exitCode);
            const bool terminatedBySignal = IsSignalTerminationStatus(waitStatus);
            const int32_t realExitCode = terminatedBySignal ? WTERMSIG(waitStatus) : WEXITSTATUS(waitStatus);
            MSPROF_EVENT(
                "%s process %d exited, wait status:%d, exit code:%d", processUsage.c_str(),
                static_cast<int32_t>(taskPid_), waitStatus, realExitCode);
            if (!isQuit_ && exitCode != 0) {
                if (terminatedBySignal) {
                    MSPROF_LOGW(
                        "An exception has occurred in process %s, terminated by signal: %d.", processUsage.c_str(),
                        realExitCode);
                    CmdLog::CmdWarningLog(
                        "An exception has occurred in process %s, terminated by signal: %d.", processUsage.c_str(),
                        realExitCode);
                } else {
                    MSPROF_LOGW(
                        "An exception has occurred in process %s, exit code: %d.", processUsage.c_str(), realExitCode);
                    CmdLog::CmdWarningLog(
                        "An exception has occurred in process %s, exit code: %d.", processUsage.c_str(), realExitCode);
                }
                if (IsAppProcessUsage(processUsage)) {
                    CmdLog::CmdWarningLog(
                        "The application exited before profiling completed. If it calls aclprofInit or aclprofStart, "
                        "remove these APIs or stop msprof tool-based profiling because only one profiling "
                        "configuration can exist at a time. Check the application output and logs under "
                        "PROF_*/mindstudio_profiler_log/ for details.");
                }
            }
            if (!isQuit_ && realExitCode != 0 && !IsAppProcessUsage(processUsage)) {
                return PROFILING_FAILED;
            }
            return PROFILING_SUCCESS;
        }
        if (isQuit_) {
            StopNoWait();
        }
        analysis::dvvp::common::utils::Utils::UsleepInterupt(SLEEP_INTEVAL_US);
    }
}

int32_t RunningMode::CheckAnalysisEnv()
{
    if (isQuit_) {
        MSPROF_LOGE("Check Analysis env failed, msprofbin has quit");
        return PROFILING_FAILED;
    }
    if (Platform::instance()->RunSocSide()) {
        CmdLog::CmdWarningLog("Not in host side, analysis is not supported");
        return PROFILING_FAILED;
    }
    if (params_->pythonPath.empty()) {
        const std::string PYTHON_CMD{"python3"};
        params_->pythonPath = PYTHON_CMD;
    }
    // check analysis scripts
    std::string absolutePath = Utils::GetSelfPath();
    std::string dirName = Utils::DirName(absolutePath);
    std::string msprofToolsPath;
    std::string binPath;
    if (Utils::SplitPath(dirName, msprofToolsPath, binPath) != PROFILING_SUCCESS) {
        CmdLog::CmdWarningLog("Get profiler path failed.");
        return PROFILING_FAILED;
    }
    Utils::EnsureEndsInSlash(msprofToolsPath);
    const std::string ANALYSIS_SCRIPT_PATH{"profiler_tool/analysis/msprof/msprof.py"};
    analysisPath_ = msprofToolsPath + ANALYSIS_SCRIPT_PATH;
    if (!Utils::IsFileExist(analysisPath_)) {
        CmdLog::CmdWarningLog("No analysis script found in %s", Utils::BaseName(analysisPath_).c_str());
        return PROFILING_FAILED;
    }
    if (OsalAccess2(analysisPath_.c_str(), OSAL_X_OK) != OSAL_EN_OK) {
        CmdLog::CmdWarningLog("Analysis script permission denied, path: %s", Utils::BaseName(analysisPath_).c_str());
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("Found available analysis script, script path: %s", Utils::BaseName(ANALYSIS_SCRIPT_PATH).c_str());

    return PROFILING_SUCCESS;
}

int32_t RunningMode::HandleProfilingParams() const
{
    if (params_ == nullptr) {
        MSPROF_LOGE("ProfileParams is not valid!");
        return PROFILING_FAILED;
    }
    if (params_->devices.compare("all") == 0) {
        params_->devices = DrvGetDevIdsStr();
    }
    std::string aiCoreMetrics;
    std::string aiVectMetrics;
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_V3_TYPE ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_TINY_V1 ||
        Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_AICORE_EXCT_DEFAULT)) {
        aiCoreMetrics = params_->ai_core_metrics.empty() ? PIPE_EXECUTION_UTILIZATION : params_->ai_core_metrics;
    } else {
        aiCoreMetrics = params_->ai_core_metrics.empty() ? PIPE_UTILIZATION : params_->ai_core_metrics;
    }
    if (Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_AIV_INDEPENDENT_CONFIG)) {
        aiVectMetrics = params_->aiv_metrics.empty() ? PIPE_UTILIZATION : params_->aiv_metrics;
    } else {
        aiVectMetrics = aiCoreMetrics;
    }
    ConfigManager::instance()->GetVersionSpecificMetrics(aiCoreMetrics);
    int32_t ret = Platform::instance()->GetAicoreEvents(aiCoreMetrics, params_->ai_core_profiling_events);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to get AI Core PMU events for metrics [%s] on current platform.", aiCoreMetrics.c_str());
        return PROFILING_FAILED;
    }
    if (params_->ntsMetrics == PIPE_UTILIZATION) {
        ret = Platform::instance()->GetAicoreEvents(PIPE_UTILIZATION_EXCT, params_->ntsPmuEvents);
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE(
                "Failed to get NTS PMU events for metrics [%s] on current platform.", params_->ntsMetrics.c_str());
            return PROFILING_FAILED;
        }
    }
    params_->ai_core_metrics = aiCoreMetrics;
    ret = Platform::instance()->GetAicoreEvents(aiVectMetrics, params_->aiv_profiling_events);
    params_->aiv_metrics = aiVectMetrics;
    Platform::instance()->L2CacheAdaptor(
        params_->npuEvents, params_->l2CacheTaskProfiling, params_->l2CacheTaskProfilingEvents);
    Analysis::Dvvp::Msprof::MsprofParamsAdapter::instance()->GenerateLlcEvents(params_);
    params_->msprofBinPid = Utils::GetPid();
    return MsprofParamsAdapter::instance()->UpdateParams(params_);
}

AppMode::~AppMode() {}

AppMode::AppMode(std::string preCheckParams, SHARED_PTR_ALIA<ProfileParams> params)
    : RunningMode(preCheckParams, "app", params)
{
    whiteSet_ = BuildAppModeWhiteSet();
}

int32_t AppMode::ModeParamsCheck()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[App Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    OutputUselessParams();
    if (HandleProfilingParams() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[App Mode] HandleProfilingParams failed");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

int32_t AppMode::RunModeTasks()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[App Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    SetDefaultParams();
    if (DynProfCliMgr::instance()->IsDynProfCliEnable()) {
        return StartAppTaskForDynProf();
    }

    auto startTime = std::chrono::high_resolution_clock::now();
    if (StartAppTask() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[App Mode] Run application task failed.");
        return PROFILING_FAILED;
    }
    auto endTime = std::chrono::high_resolution_clock::now();
    UpdateOutputDirInfo();

    if (isQuit_) {
        isQuit_ = false;
        MSPROF_LOGI("reset isQuit_=false to analyze data");
    }

    if (jobResultDirList_.empty()) {
        const auto duration = std::chrono::duration_cast<std::chrono::seconds>(endTime - startTime);
        return ReportEmptyResult(static_cast<uint64_t>(duration.count()));
    }

    if (CheckAnalysisEnv() != PROFILING_SUCCESS) {
        MSPROF_LOGW("[App Mode] Analysis environment is not OK, auto parse will not start.");
        return PROFILING_SUCCESS;
    }

    return ExportAndQueryResults();
}

int32_t AppMode::ExportAndQueryResults()
{
    for (auto iter = jobResultDirList_.begin(); iter != jobResultDirList_.end(); ++iter) {
        jobResultDir_ = *iter;
        if (!IsSecureResultDir(jobResultDir_)) {
            MSPROF_LOGW("[App Mode] Invalid result dir before export task: %s", Utils::BaseName(jobResultDir_).c_str());
            return PROFILING_FAILED;
        }
        if (StartExportTask() != PROFILING_SUCCESS) {
            if (isQuit_) {
                MSPROF_LOGI("[App Mode] Export skipped because msprofbin received a stop signal.");
                return PROFILING_SUCCESS;
            }
            MSPROF_LOGE("[App Mode] The export task did not complete successfully.");
            CmdLog::CmdErrorLog(
                "Export profiling data failed. Check the logs under PROF_*/mindstudio_profiler_log/ for details.");
            return PROFILING_FAILED;
        }
        if (StartQueryTask() != PROFILING_SUCCESS) {
            MSPROF_LOGW("[App Mode] The query task did not complete successfully.");
            return PROFILING_SUCCESS;
        }
    }
    return PROFILING_SUCCESS;
}

int32_t AppMode::ReportEmptyResult(uint64_t elapsedSeconds) const
{
    if (!params_->delayTime.empty() && elapsedSeconds <= std::stoull(params_->delayTime)) {
        MSPROF_LOGW("[App Mode] Before delay time, the app process has exited.");
        return PROFILING_SUCCESS;
    }
    MSPROF_LOGE("[App Mode] Failed to find profiling data");
    CmdLog::CmdErrorLog("Failed to find profiling data,"
                        " please check that the application executes AI-related business,"
                        " or ensure that aclInit/GEInitialize is invoked in the application");
    return PROFILING_FAILED;
}

void AppMode::SetDefaultParams() const
{
    if (params_->acl.empty()) {
        params_->acl = "on";
    }
    if (params_->ts_keypoint.empty()) {
        params_->ts_keypoint = "on";
    }
    if (params_->ai_core_profiling.empty()) {
        params_->ai_core_lpm = "on";
        params_->ai_core_profiling = "on";
    }
    if (params_->ai_core_profiling_mode.empty()) {
        params_->ai_core_profiling_mode = PROFILING_MODE_TASK_BASED;
    }
    if (params_->ai_core_profiling == "on" && params_->aiv_profiling.empty()) {
        params_->ai_core_lpm = "on";
        params_->aiv_profiling = "on";
    }
    if (params_->aiv_profiling_mode.empty()) {
        params_->aiv_profiling_mode = PROFILING_MODE_TASK_BASED;
    }
    if (params_->aiv_profiling_mode == PROFILING_MODE_SAMPLE_BASED ||
        !Platform::instance()->CheckIfSupport(PLATFORM_TASK_AICORE_LPM)) {
        params_->ai_core_lpm = "off";
    }

    SetDefaultParamsByPlatformType();
}

int32_t AppMode::StartAppTaskForDynProf()
{
    if (isQuit_) {
        MSPROF_LOGE("Failed to launch app, msprofbin has quit");
        return PROFILING_FAILED;
    }
    if (DynProfCliMgr::instance()->IsAppMode()) {
        if (analysis::dvvp::app::Application::LaunchApp(params_, taskPid_) != PROFILING_SUCCESS) {
            MSPROF_LOGE("Dynamic profiling failed to launch application.");
            return PROFILING_FAILED;
        }
        // wait server start
        const int32_t sleepUs = 2 * 1000 * 1000; // 2s
        Utils::UsleepInterupt(sleepUs);
    }

    if (DynProfCliMgr::instance()->StartDynProfCli(params_->ToString()) != PROFILING_SUCCESS) {
        MSPROF_LOGE("Dynamic profiling start client thread fail.");
        // 关闭app
        StopRunningTasks();
        return PROFILING_FAILED;
    }

    MSPROF_LOGI("Dynamic profiling start client success.");
    DynProfCliMgr::instance()->WaitQuit();

    taskName_ = "app";
    if (DynProfCliMgr::instance()->IsAppMode() && !isQuit_) {
        CmdLog::CmdInfoLog("waiting for app process exit......");
        // wait app exit
        auto ret = WaitRunningProcess(taskName_);
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("Failed to wait process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
            return PROFILING_FAILED;
        }
    }
    taskPid_ = MSVP_PROCESS;
    return PROFILING_SUCCESS;
}

int32_t AppMode::StartAppTask(bool needWait)
{
    if (isQuit_) {
        MSPROF_LOGE("Failed to launch app, msprofbin has quit");
        return PROFILING_FAILED;
    }
    int32_t ret = analysis::dvvp::app::Application::LaunchApp(params_, taskPid_);
    if (ret == PROFILING_FAILED) {
        MSPROF_LOGE("Failed to launch app");
        return PROFILING_FAILED;
    }
    taskName_ = "app";
    if (needWait) {
        // wait app exit
        ret = WaitRunningProcess("App");
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("Failed to wait process %d to exit, ret=%d", static_cast<int32_t>(taskPid_), ret);
            return PROFILING_FAILED;
        }
    }
    taskPid_ = MSVP_PROCESS;
    return PROFILING_SUCCESS;
}

void AppMode::SetDefaultParamsByPlatformType() const
{
    if (Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_AIV_INDEPENDENT_CONFIG)) {
        if (params_->aiv_profiling.empty()) {
            params_->aiv_profiling = "on";
        }
    }
    if (params_->taskTrace == "off" || params_->taskTime == "off") {
        return;
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_STARS_ACSQ)) {
        if (params_->stars_acsq_task.empty()) {
            params_->stars_acsq_task = MSVP_PROF_ON;
        }
    } else {
        if (params_->hwts_log.empty()) {
            params_->hwts_log = "on";
        }
        if (params_->hwts_log1.empty()) {
            params_->hwts_log1 = "on";
        }
    }
    if (params_->ts_memcpy.empty()) {
        params_->ts_memcpy = "on";
    }
}

SystemMode::~SystemMode() {}

SystemMode::SystemMode(std::string preCheckParams, SHARED_PTR_ALIA<ProfileParams> params)
    : RunningMode(preCheckParams, "system", params)
{
    // clang-format off
    whiteSet_ = {
        ARGS_OUTPUT,
        ARGS_STORAGE_LIMIT,
        ARGS_AIC_MODE,
        ARGS_SYS_DEVICES,
        ARGS_AIC_METRICS,
        ARGS_AIV_MODE,
        ARGS_AIV_METRICS,
        ARGS_LLC_PROFILING,
        ARGS_AI_CORE,
        ARGS_AIV,
        ARGS_CPU_PROFILING,
        ARGS_SYS_PROFILING,
        ARGS_PID_PROFILING,
        ARGS_HARDWARE_MEM,
        ARGS_IO_PROFILING,
        ARGS_INTERCONNECTION_PROFILING,
        ARGS_DVPP_PROFILING,
        ARGS_AIC_FREQ,
        ARGS_AIV_FREQ,
        ARGS_SYS_LOW_POWER,
        ARGS_SYS_LOW_POWER_FREQ,
        ARGS_INSTR_PROFILING_FREQ,
        ARGS_INSTR_PROFILING,
        ARGS_SYS_SAMPLING_FREQ,
        ARGS_PID_SAMPLING_FREQ,
        ARGS_HARDWARE_MEM_SAMPLING_FREQ,
        ARGS_IO_SAMPLING_FREQ,
        ARGS_DVPP_FREQ,
        ARGS_CPU_SAMPLING_FREQ,
        ARGS_INTERCONNECTION_FREQ,
        ARGS_HOST_SYS,
        ARGS_SYS_PERIOD,
        ARGS_HOST_SYS_PID,
        ARGS_HOST_SYS_USAGE,
        ARGS_HOST_SYS_USAGE_FREQ,
        // System mode collects the same host PMU counters, so these switches belong in this
        // whitelist too. Without them a PMU-only system-mode run does collect data but prints
        // "--cpu-core-events is useless when --sys-devices is not empty", which reads as if the
        // request had been ignored.
        ARGS_HOST_PMU_SAMPLE,
        ARGS_HOST_PMU_EVENTS,
        ARGS_HOST_PMU_OS_EVENTS,
        ARGS_HOST_PMU_INTERVAL,
        ARGS_PYTHON_PATH,
        ARGS_MEM_SERVICEFLOW};
    // clang-format on
    neccessarySet_ = {ARGS_SYS_PERIOD};
}

int32_t SystemMode::CheckIfDeviceOnline() const
{
    if (params_->devices.compare("all") == 0) {
        return PROFILING_SUCCESS;
    }
    auto devIds = Utils::Split(params_->devices, false, "", ",");
    const int32_t numDevices = DrvGetDevNum();
    if (numDevices <= 0) {
        CmdLog::CmdErrorLog("Get dev's num %d failed", numDevices);
        return PROFILING_FAILED;
    }
    std::vector<int32_t> devices;
    int32_t ret = DrvGetDevIds(numDevices, devices);
    if (ret != PROFILING_SUCCESS) {
        CmdLog::CmdErrorLog("Get dev's id failed");
        return PROFILING_FAILED;
    }
    UtilsStringBuilder<int32_t> builder;
    builder.Join(devices, ",");
    std::set<std::string> validIds;
    std::vector<std::string> invalidIds;
    for (auto devId : devIds) {
        if (!Utils::CheckStringIsNonNegativeIntNum(devId)) {
            CmdLog::CmdErrorLog("The device (%s) is not valid, please check it!", devId.c_str());
            return PROFILING_FAILED;
        }
        int32_t devIdInt = 0;
        FUNRET_CHECK_EXPR_ACTION(
            !Utils::StrToInt32(devIdInt, devId), return PROFILING_FAILED, "devId %s is invalid", devId.c_str());
        auto it = find(devices.begin(), devices.end(), devIdInt);
        if (it == devices.end()) {
            invalidIds.push_back(devId);
        } else {
            validIds.insert(devId);
        }
    }
    UtilsStringBuilder<std::string> strBuilder;
    if (!invalidIds.empty()) {
        CmdLog::CmdWarningLog(
            "The following devices(%s) are offline and will not collect.", strBuilder.Join(invalidIds, ",").c_str());
    }
    if (validIds.empty()) {
        CmdLog::CmdErrorLog("Argument --sys-devices is invalid,"
                            "Please enter a valid --sys-devices value.");
        return PROFILING_FAILED;
    }
    std::vector<std::string> validIdList;
    validIdList.assign(validIds.begin(), validIds.end());
    params_->devices = strBuilder.Join(validIdList, ",");
    return PROFILING_SUCCESS;
}

int32_t SystemMode::CheckHostSysParams() const
{
    if (params_->host_sys.empty() && params_->hostSysUsage.empty() && CheckIfDeviceOnline() != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }
    if (!params_->host_sys.empty() && params_->host_sys_pid < 0) {
        CmdLog::CmdErrorLog("The argument --host-sys-pid"
                            " are required when app is empty and --host-sys is on.");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

bool SystemMode::DataWillBeCollected() const
{
    if (params_ == nullptr || params_->usedParams.empty()) {
        return false;
    }
    std::set<int32_t> necessaryParams = neccessarySet_;
    necessaryParams.insert(ARGS_OUTPUT);
    std::set<int32_t> unneccessaryParams;
    set_difference(
        params_->usedParams.begin(), params_->usedParams.end(), necessaryParams.begin(), necessaryParams.end(),
        inserter(unneccessaryParams, unneccessaryParams.begin()));
    set_intersection(
        params_->usedParams.begin(), params_->usedParams.end(), unneccessaryParams.begin(), unneccessaryParams.end(),
        inserter(unneccessaryParams, unneccessaryParams.begin()));
    if (unneccessaryParams.size() == 1 && *(unneccessaryParams.begin()) == ARGS_SYS_DEVICES) {
        CmdLog::CmdWarningLog("No collection data type is specified, profiling will not start");
        return false;
    }
    return true;
}

int32_t SystemMode::ModeParamsCheck()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[System Mode] Invalid params!");
        return PROFILING_FAILED;
    }

    if (CheckNeccessaryParams() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[System Mode] Check necessary params failed!");
        return PROFILING_FAILED;
    }
    if (!DataWillBeCollected()) {
        MSPROF_LOGE("[System Mode] No data will be collected!");
        return PROFILING_FAILED;
    }
    OutputUselessParams();

    if (CheckHostSysParams() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[System Mode] Check host sys params failed!");
        return PROFILING_FAILED;
    }

    if (HandleProfilingParams() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[System Mode] HandleProfilingParams failed");
        return PROFILING_FAILED;
    }

    return PROFILING_SUCCESS;
}

int32_t SystemMode::RunModeTasks()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[System Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    SetSysDefaultParams();
    int32_t ret = StartSysTaskByProfApi();
    if (ret != PROFILING_SUCCESS) {
        if (ret != PROFILING_NOTSUPPORT) {
            MSPROF_LOGE("[System Mode] Run system task failed.");
        } else {
            UpdateOutputDirInfo();
        }
        return ret;
    }
    if (isQuit_) {
        isQuit_ = false;
        MSPROF_LOGI("reset isQuit_=false to analyze data");
    }
    UpdateOutputDirInfo();
    if (CheckAnalysisEnv() != PROFILING_SUCCESS) {
        MSPROF_LOGW("[System Mode] Analysis environment is not OK, auto parse will not start.");
        return PROFILING_SUCCESS;
    }

    std::set<std::string>::iterator iter;
    for (iter = jobResultDirList_.begin(); iter != jobResultDirList_.end(); ++iter) {
        jobResultDir_ = *iter;
        if (!IsSecureResultDir(jobResultDir_)) {
            MSPROF_LOGW(
                "[System Mode] Invalid result dir before export task: %s", Utils::BaseName(jobResultDir_).c_str());
            return PROFILING_FAILED;
        }
        if (StartExportTask() != PROFILING_SUCCESS) {
            if (isQuit_) {
                MSPROF_LOGI("[System Mode] Export skipped because msprofbin received a stop signal.");
                return PROFILING_SUCCESS;
            }
            MSPROF_LOGW("[System Mode] The export task did not complete successfully.");
            return PROFILING_FAILED;
        }
        if (StartQueryTask() != PROFILING_SUCCESS) {
            MSPROF_LOGW("[System Mode] The query task did not complete successfully.");
            return PROFILING_SUCCESS;
        }
    }
    return PROFILING_SUCCESS;
}

void SystemMode::SetSysDefaultParams() const
{
    if (params_->ai_core_profiling == "on") {
        params_->ai_core_lpm = "on";
        params_->aiv_profiling = "on";
        params_->ai_core_profiling_mode = PROFILING_MODE_SAMPLE_BASED;
        params_->aiv_profiling_mode = PROFILING_MODE_SAMPLE_BASED;
    }
    params_->profMode = MSVP_PROF_SYSTEM_MODE;
    params_->appMemProfiling = MSVP_PROF_OFF;
}

int32_t SystemMode::StartSysTaskByProfApi()
{
    std::string originalValue;
    bool originalValueExist = false;
    CONST_CHAR_PTR originalEnv = getenv(PROFILER_SAMPLE_CONFIG_ENV);
    if (originalEnv != nullptr) {
        originalValue = originalEnv;
        originalValueExist = true;
    }
    const std::string sampleConfig = params_->ToString();
    if (sampleConfig.empty()) {
        CmdLog::CmdErrorLog("Generate sample config failed.");
        return PROFILING_FAILED;
    }
    if (setenv(PROFILER_SAMPLE_CONFIG_ENV, sampleConfig.c_str(), ENV_OVERWRITE) != 0) {
        CmdLog::CmdErrorLog("Set PROFILER_SAMPLECONFIG failed.");
        return PROFILING_FAILED;
    }
    ProfApiLoader profApiLoader;
    int32_t ret = profApiLoader.Load();
    if (ret != PROFILING_SUCCESS) {
        RestoreSampleConfigEnv(originalValue, originalValueExist);
        return ret;
    }
    ret = profApiLoader.Init();
    RestoreSampleConfigEnv(originalValue, originalValueExist);
    if (ret != PROFILING_SUCCESS) {
        return ret;
    }
    return PROFILING_SUCCESS;
}

ParseMode::ParseMode(std::string preCheckParams, SHARED_PTR_ALIA<ProfileParams> params)
    : RunningMode(preCheckParams, "parse", params)
{
    whiteSet_ = {ARGS_OUTPUT, ARGS_PARSE, ARGS_PYTHON_PATH};
    neccessarySet_ = {ARGS_OUTPUT, ARGS_PARSE};
    blackSet_ = {ARGS_QUERY, ARGS_EXPORT, ARGS_ANALYZE, ARGS_RULE, ARGS_CLEAR};
}

ParseMode::~ParseMode() {}

int32_t ParseMode::ModeParamsCheck()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[Parse Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    if (CheckForbiddenParams() != PROFILING_SUCCESS || CheckNeccessaryParams() != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }
    OutputUselessParams();

    return PROFILING_SUCCESS;
}

void ParseMode::UpdateOutputDirInfo()
{
    int32_t ret = GetOutputDirInfoFromParams();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGW("Unable to get output info from ParseMode.");
    }
}

int32_t ParseMode::RunModeTasks()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[Parse Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    if (CheckAnalysisEnv() != PROFILING_SUCCESS) {
        MSPROF_LOGW("[Parse Mode] Analysis environment is not OK, parse will not start.");
        return PROFILING_FAILED;
    }
    UpdateOutputDirInfo();
    if (StartParseTask() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[Parse Mode] Run parse task failed.");
        return PROFILING_FAILED;
    }
    if (StartQueryTask() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[Parse Mode] Run query task failed.");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

QueryMode::QueryMode(std::string preCheckParams, SHARED_PTR_ALIA<ProfileParams> params)
    : RunningMode(preCheckParams, "query", params)
{
    whiteSet_ = {ARGS_OUTPUT, ARGS_QUERY, ARGS_PYTHON_PATH};
    neccessarySet_ = {ARGS_OUTPUT, ARGS_QUERY};
    blackSet_ = {ARGS_PARSE, ARGS_EXPORT, ARGS_ANALYZE, ARGS_RULE, ARGS_CLEAR};
}

QueryMode::~QueryMode() {}

int32_t QueryMode::ModeParamsCheck()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[Query Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    if (CheckForbiddenParams() != PROFILING_SUCCESS || CheckNeccessaryParams() != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }
    OutputUselessParams();

    return PROFILING_SUCCESS;
}

void QueryMode::UpdateOutputDirInfo()
{
    int32_t ret = GetOutputDirInfoFromParams();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGW("Unable to get output info from QueryMode.");
    }
}

int32_t QueryMode::RunModeTasks()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[Query Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    UpdateOutputDirInfo();
    if (CheckAnalysisEnv() != PROFILING_SUCCESS) {
        MSPROF_LOGW("[Query Mode] Analysis environment is not OK, query will not start.");
        return PROFILING_FAILED;
    }
    if (StartQueryTask() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[Query Mode] Run query task failed.");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

ExportMode::ExportMode(std::string preCheckParams, SHARED_PTR_ALIA<ProfileParams> params)
    : RunningMode(preCheckParams, "export", params)
{
    whiteSet_ = {ARGS_OUTPUT,      ARGS_EXPORT, ARGS_EXPORT_ITERATION_ID, ARGS_EXPORT_MODEL_ID, ARGS_SUMMARY_FORMAT,
                 ARGS_PYTHON_PATH, ARGS_CLEAR,  ARGS_EXPORT_TYPE,         ARGS_REPORTS};
    neccessarySet_ = {ARGS_OUTPUT, ARGS_EXPORT};
    blackSet_ = {ARGS_QUERY, ARGS_PARSE, ARGS_ANALYZE, ARGS_RULE};
}

ExportMode::~ExportMode() {}

int32_t ExportMode::ModeParamsCheck()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[Export Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    if (params_->exportType == "db") {
        preCheckParams_ = "export and --type";
        whiteSet_ = {ARGS_OUTPUT, ARGS_EXPORT, ARGS_EXPORT_TYPE, ARGS_PYTHON_PATH};
        neccessarySet_ = {ARGS_OUTPUT, ARGS_EXPORT, ARGS_EXPORT_TYPE};
        blackSet_ = {ARGS_QUERY,           ARGS_PARSE,          ARGS_ANALYZE, ARGS_RULE,   ARGS_EXPORT_ITERATION_ID,
                     ARGS_EXPORT_MODEL_ID, ARGS_SUMMARY_FORMAT, ARGS_CLEAR,   ARGS_REPORTS};
    }
    if (CheckForbiddenParams() != PROFILING_SUCCESS || CheckNeccessaryParams() != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }
    OutputUselessParams();

    return PROFILING_SUCCESS;
}

void ExportMode::UpdateOutputDirInfo()
{
    int32_t ret = GetOutputDirInfoFromParams();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGW("Unable to get output info from ExportMode.");
    }
}

int32_t ExportMode::RunModeTasks()
{
    if (params_ == nullptr) {
        MSPROF_LOGE("[Export Mode] Invalid params!");
        return PROFILING_FAILED;
    }
    UpdateOutputDirInfo();
    if (CheckAnalysisEnv() != PROFILING_SUCCESS) {
        MSPROF_LOGW("[Export Mode] Analysis environment is not OK, export will not start.");
        return PROFILING_FAILED;
    }
    if (StartExportTask() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[Export Mode] Run export task failed.");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

AnalyzeMode::AnalyzeMode(std::string preCheckParams, SHARED_PTR_ALIA<ProfileParams> params)
    : RunningMode(preCheckParams, "analyze", params)
{
    whiteSet_ = {ARGS_OUTPUT, ARGS_ANALYZE, ARGS_PYTHON_PATH, ARGS_RULE, ARGS_CLEAR, ARGS_EXPORT_TYPE};
    neccessarySet_ = {ARGS_OUTPUT, ARGS_ANALYZE};
    blackSet_ = {ARGS_QUERY, ARGS_EXPORT, ARGS_PARSE};
}

AnalyzeMode::~AnalyzeMode() {}

int32_t AnalyzeMode::ModeParamsCheck()
{
    MSPROF_LOGI("[AnalyzeMode] ModeParamsCheck");
    if (params_ == nullptr) {
        MSPROF_LOGE("[Analyze Mode] Invalid params!");
        return PROFILING_FAILED;
    }

    if (CheckForbiddenParams() != PROFILING_SUCCESS || CheckNeccessaryParams() != PROFILING_SUCCESS) {
        return PROFILING_FAILED;
    }

    OutputUselessParams();
    return PROFILING_SUCCESS;
}

void AnalyzeMode::UpdateOutputDirInfo()
{
    MSPROF_LOGI("[AnalyzeMode] UpdateOutputDirInfo");
    int32_t ret = GetOutputDirInfoFromParams();
    FUNRET_CHECK_EXPR_LOGW(ret != PROFILING_SUCCESS, "Unable to get output info from AnalyzeMode.");
}

int32_t AnalyzeMode::RunModeTasks()
{
    MSPROF_LOGI("[AnalyzeMode] RunModeTasks");
    if (params_ == nullptr) {
        MSPROF_LOGE("[Analyze Mode] Invalid params!");
        return PROFILING_FAILED;
    }

    if (CheckAnalysisEnv() != PROFILING_SUCCESS) {
        MSPROF_LOGW("[Analyze Mode] Analysis environment is not OK, parse will not start.");
        return PROFILING_FAILED;
    }

    UpdateOutputDirInfo();
    if (StartAnalyzeTask() != PROFILING_SUCCESS) {
        MSPROF_LOGE("[Analyze Mode] Run analyze task failed.");
        return PROFILING_FAILED;
    }

    return PROFILING_SUCCESS;
}
} // namespace Msprofbin
} // namespace Dvvp
} // namespace Collector
