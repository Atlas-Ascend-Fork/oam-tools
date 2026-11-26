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
#include <set>
#include <algorithm>
#include "mockcpp/mockcpp.hpp"
#include "gtest/gtest.h"
#include <iostream>
#include "errno/error_code_tool.h"
#include "running_mode_tool.h"
#include "prof_api_loader.h"
#include "ai_drv_dev_api.h"
#include "utils/utils_tool.h"
#include "config/config.h"
#include "config_manager_tool.h"
#include "transport/uploader_mgr_tool.h"
#include "input_parser_tool.h"
#include "application_tool.h"
#include "platform/platform_tool.h"
#include <fstream>
#include <unistd.h>
#include <sys/wait.h>
#include <unistd.h>
#include <memory>
#include "dyn_prof_client_tool.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::transport;
using namespace Analysis::Dvvp::Common::Config;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Analysis::Dvvp::Msprof;
using namespace Collector::Dvvp::Msprofbin;
using namespace Collector::Dvvp::DynProf;

class RUNNING_MODE_UTEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() { GlobalMockObject::verify(); }
};

namespace {
constexpr uintptr_t FAKE_PROF_API_HANDLE = 1;
constexpr int ENV_OVERWRITE_FOR_TEST = 1;

std::string g_sampleConfigForTest;

int32_t FakeMsprofInitSuccess(uint32_t dataType, void* data, uint32_t dataLen)
{
    CONST_CHAR_PTR sampleConfig = getenv(PROFILER_SAMPLE_CONFIG_ENV);
    g_sampleConfigForTest = sampleConfig == nullptr ? "" : sampleConfig;
    return ((dataType == MSPROF_CTRL_INIT_ACL_ENV) && (data == nullptr) && (dataLen == 0)) ? PROFILING_SUCCESS :
                                                                                             PROFILING_FAILED;
}

int32_t FakeMsprofInitFailed(uint32_t dataType, void* data, uint32_t dataLen)
{
    return (dataType == MSPROF_CTRL_INIT_ACL_ENV) && (data == nullptr) && (dataLen == 0) ? MSPROF_ERROR_CONFIG_INVALID :
                                                                                           MSPROF_ERROR_NONE;
}

int32_t FakeMsprofInitNotSupport(uint32_t dataType, void* data, uint32_t dataLen)
{
    return (dataType == MSPROF_CTRL_INIT_ACL_ENV) && (data == nullptr) && (dataLen == 0) ? MSPROF_ERROR_UNINITIALIZE :
                                                                                           MSPROF_ERROR_NONE;
}

void MockProfApi(void* initFunc)
{
    MOCKER(dlopen).stubs().will(returnValue((void*)FAKE_PROF_API_HANDLE));
    MOCKER(dlsym).stubs().will(returnValue(initFunc));
    MOCKER(dlclose).stubs().will(returnValue(0));
}
} // namespace

TEST_F(RUNNING_MODE_UTEST, ConvertParamsSetToString)
{
    std::set<int> srcSet;
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    EXPECT_EQ("", rMode.ConvertParamsSetToString(srcSet));
    srcSet = {0, 1};
    EXPECT_EQ("--help --output", rMode.ConvertParamsSetToString(srcSet));
}

TEST_F(RUNNING_MODE_UTEST, CheckForbiddenParams)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckForbiddenParams());
    params->app = "123";
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckForbiddenParams());
    params->usedParams = {1, 2, 3};
    rMode.blackSet_ = {1, 5, 6};
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckForbiddenParams());
    rMode.blackSet_.clear();
    rMode.blackSet_ = {5, 6};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.CheckForbiddenParams());
}

TEST_F(RUNNING_MODE_UTEST, CheckNeccessaryParams)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckNeccessaryParams());
    params->app = "123";
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckNeccessaryParams());
    params->usedParams = {1, 2, 3};
    rMode.neccessarySet_ = {1, 5, 6};
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckNeccessaryParams());
    params->usedParams.clear();
    params->usedParams = {1, 5, 6, 0};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.CheckNeccessaryParams());
}

TEST_F(RUNNING_MODE_UTEST, OutputUselessParams)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.OutputUselessParams();
    params->usedParams = {1, 2, 3};
    rMode.whiteSet_ = {1, 5, 6};

    std::stringstream output;
    std::streambuf* oldCoutBuffer = std::cout.rdbuf();
    std::cout.rdbuf(output.rdbuf());

    rMode.OutputUselessParams();
    std::vector<std::string> expectedList = {
        "The argument --storage-limit --application is useless when --app is not empty"};

    std::cout.rdbuf(oldCoutBuffer);
    for (auto expectedPrint : expectedList) {
        EXPECT_NE(output.str().find(expectedPrint), std::string::npos) << "Screen print:" << std::endl
                                                                       << output.str() << std::endl
                                                                       << "Missing expected: " + expectedPrint;
    }
    rMode.UpdateOutputDirInfo();
}

TEST_F(RUNNING_MODE_UTEST, GetOutputDirInfoFromParams)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    params->result_dir = "123";
    EXPECT_EQ(PROFILING_SUCCESS, rMode.GetOutputDirInfoFromParams());
    EXPECT_EQ("123", rMode.jobResultDir_);
    EXPECT_EQ(PROFILING_FAILED, rMode.GetOutputDirInfoFromParams());
}

TEST_F(RUNNING_MODE_UTEST, GetOutputDirInfoFromRecord)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    std::string result = "/tmp/running_mode_ut";
    rMode.jobResultDir_ = "123";
    EXPECT_EQ(PROFILING_FAILED, rMode.GetOutputDirInfoFromRecord());
    rMode.jobResultDir_.clear();
    MOCKER(Utils::GetPid).stubs().will(returnValue(1));
    MOCKER(Utils::GetFileSize).stubs().will(returnValue((2 * 1024 * 1024 + 1)));
    EXPECT_EQ(PROFILING_FAILED, rMode.GetOutputDirInfoFromRecord());
    GlobalMockObject::verify();

    MOCKER(Utils::GetPid).stubs().will(returnValue(1));
    params->result_dir = result;
    Utils::CreateDir(result);
    std::ofstream out;
    out.open(result + '/' + "1_" + OUTPUT_RECORD);
    Utils::CreateDir(result + "/PROF_000001_20211211194055303_DANEQIJKACHMDGNB");
    Utils::CreateDir(result + "/JOB44444444444");
    out << "PROF_000001_20211211194055303_DANEQIJKACHMDGNB" << std::endl << "JOB44444444444" << std::endl;
    out.close();
    EXPECT_EQ(PROFILING_SUCCESS, rMode.GetOutputDirInfoFromRecord());

    rMode.jobResultDir_.clear();
    params->result_dir = "/tmp/profiling_output_r";
    EXPECT_EQ(PROFILING_FAILED, rMode.GetOutputDirInfoFromRecord());
    Utils::RemoveDir(result);
}

TEST_F(RUNNING_MODE_UTEST, GetOutputDirInfoFromRecordRejectInvalidInput)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    MOCKER(Utils::GetPid).stubs().will(returnValue(1));
    const std::string result = "/tmp/running_mode_record_invalid_ut";
    const std::string profDir = "PROF_000001_20211211194055303_DANEQIJKACHMDGNB";
    const std::string record = result + "/1_" + OUTPUT_RECORD;
    const std::string cleanup = "rm -rf " + result;
    const std::string prepare = cleanup + " && mkdir -p " + result + "/" + profDir;
    (void)system(prepare.c_str());

    const std::vector<std::string> invalidContents = {"../evil", "/absolute/path", "a/b", ".", "..", "", "\n"};
    for (const auto& content : invalidContents) {
        std::ofstream out(record);
        out << content;
        out.close();
        params->result_dir = result;
        rMode.jobResultDir_.clear();
        rMode.jobResultDirList_.clear();
        EXPECT_EQ(PROFILING_FAILED, rMode.GetOutputDirInfoFromRecord()) << "content: [" << content << "]";
        EXPECT_TRUE(Utils::IsFileExist(record));
    }

    std::ofstream out(record);
    out << "invalid\n" << profDir << "\n";
    out.close();
    params->result_dir = result;
    rMode.jobResultDir_.clear();
    rMode.jobResultDirList_.clear();
    EXPECT_EQ(PROFILING_SUCCESS, rMode.GetOutputDirInfoFromRecord());
    EXPECT_EQ(1U, rMode.jobResultDirList_.size());
    EXPECT_FALSE(Utils::IsFileExist(record));
    (void)system(cleanup.c_str());
}

TEST_F(RUNNING_MODE_UTEST, GetOutputDirInfoFromRecordRejectSoftLink)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    MOCKER(Utils::GetPid).stubs().will(returnValue(1));
    const std::string result = "/tmp/running_mode_record_link_ut";
    const std::string profDir = "PROF_000001_20211211194055303_DANEQIJKACHMDGNB";
    const std::string target = result + "/target";
    const std::string record = result + "/1_" + OUTPUT_RECORD;
    const std::string cleanup = "rm -rf " + result;
    const std::string prepare = cleanup + " && mkdir -p " + result + "/" + profDir;
    (void)system(prepare.c_str());
    std::ofstream targetFile(target);
    targetFile << profDir << std::endl;
    targetFile.close();
    ASSERT_EQ(0, symlink(target.c_str(), record.c_str()));

    params->result_dir = result;
    EXPECT_EQ(PROFILING_FAILED, rMode.GetOutputDirInfoFromRecord());
    EXPECT_TRUE(Utils::IsFileExist(target));

    (void)unlink(record.c_str());
    (void)system(cleanup.c_str());
}

TEST_F(RUNNING_MODE_UTEST, GetOutputDirInfoFromRecordRejectFifo)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    MOCKER(Utils::GetPid).stubs().will(returnValue(1));
    const std::string result = "/tmp/running_mode_record_fifo_ut";
    const std::string record = result + "/1_" + OUTPUT_RECORD;
    const std::string cleanup = "rm -rf " + result;
    (void)system((cleanup + " && mkdir -p " + result).c_str());
    ASSERT_EQ(0, mkfifo(record.c_str(), 0600));

    params->result_dir = result;
    EXPECT_EQ(PROFILING_FAILED, rMode.GetOutputDirInfoFromRecord());

    (void)unlink(record.c_str());
    (void)system(cleanup.c_str());
}

int32_t g_remove = 0;
int32_t removeStub(const char* data)
{
    g_remove++;
    return EOK;
}

TEST_F(RUNNING_MODE_UTEST, RemoveRecordFile)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    std::string filename = "123";
    rMode.RemoveRecordFile(filename);
    MOCKER(Utils::IsFileExist).stubs().will(returnValue(true));
    rMode.RemoveRecordFile(filename);
    MOCKER(remove).stubs().will(invoke(removeStub));
    rMode.RemoveRecordFile(filename);
    EXPECT_EQ(g_remove, 1);
}

static int _drv_get_dev_ids(int num_devices, std::vector<int>& dev_ids)
{
    static int phase = 0;
    if (phase == 0) {
        phase++;
        return PROFILING_FAILED;
    }

    if (phase >= 1) {
        dev_ids.push_back(0);
        dev_ids.push_back(1);
        return PROFILING_SUCCESS;
    }
}

TEST_F(RUNNING_MODE_UTEST, HandleProfilingParams)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.HandleProfilingParams());
    rMode.params_ = params;
    params->devices = "all";
    std::string resStr = "0,1";
    MOCKER(&analysis::dvvp::driver::DrvGetDevIdsStr).stubs().will(returnValue(resStr));
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::GetAicoreEvents)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.HandleProfilingParams());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.HandleProfilingParams());
    MOCKER_CPP(&ConfigManager::GetPlatformType).stubs().will(returnValue(2)).then(returnValue(5)).then(returnValue(7));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.HandleProfilingParams());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.HandleProfilingParams());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.HandleProfilingParams());
}

std::vector<std::string> g_argv;
int32_t ExecCmdStub(
    const ExecCmdParams& execCmdParams, const std::vector<std::string>& argv, const std::vector<std::string>& envp,
    int& exitCodeP, OsalProcess& childProcess)
{
    g_argv = argv;
    return PROFILING_SUCCESS;
}

// 记录每次 ExecCmd 的 argv 与参数形态，并返回可控退出码，用于校验探测与 -reports 的拼装。
std::vector<std::vector<std::string>> g_exportArgvList;
ExecCmdParams g_exportCmdParams("", true, "");
int32_t g_exportExitCode = 0;
bool g_exportTerminatedBySignal = false;
// fork 时刻本进程 fd 2 指向的目标，用于确认探测期间子进程 stderr 已被屏蔽。
std::string g_stderrTargetAtExec = "";
std::string ReadStderrTarget()
{
    char target[256] = {0};
    ssize_t len = readlink("/proc/self/fd/2", target, sizeof(target) - 1);
    return len > 0 ? std::string(target, static_cast<size_t>(len)) : std::string();
}

int32_t ExecCmdCaptureStub(
    const ExecCmdParams& execCmdParams, const std::vector<std::string>& argv, const std::vector<std::string>& envp,
    int& exitCodeP, OsalProcess& childProcess)
{
    g_exportArgvList.push_back(argv);
    g_exportCmdParams = execCmdParams;
    g_stderrTargetAtExec = ReadStderrTarget();
    childProcess = 1;
    return PROFILING_SUCCESS;
}

// 按 g_exportExitCode / g_exportTerminatedBySignal 构造真实 wait status，
// 保证被信号终止与正常退出两种形态都能被生产代码的 WIFSIGNALED/WEXITSTATUS 正确解析。
int32_t WaitProcessStub(OsalProcess, bool& isExited, int32_t& exitCode, bool)
{
    isExited = true;
    exitCode = g_exportTerminatedBySignal ? g_exportExitCode : static_cast<int32_t>(g_exportExitCode << 8);
    return PROFILING_SUCCESS;
}

class ExportArgvHelper {
public:
    static void Reset() { g_exportArgvList.clear(); }

    static size_t Count() { return g_exportArgvList.size(); }

    static bool Contains(const std::vector<std::string>& argv, const std::string& value)
    {
        return std::find(argv.begin(), argv.end(), value) != argv.end();
    }

    static bool HasReports(const std::vector<std::string>& argv)
    {
        return std::any_of(
            argv.begin(), argv.end(), [](const std::string& arg) { return arg.rfind("-reports=", 0) == 0; });
    }
};
TEST_F(RUNNING_MODE_UTEST, StopRunningTasks)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.StopRunningTasks();

    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdStub));
    rMode.taskPid_ = 11111;
    rMode.StopRunningTasks();
    EXPECT_EQ(g_argv.size(), 3);
    if (g_argv.size() == 3) {
        EXPECT_EQ(g_argv[0], "-s");
        EXPECT_EQ(g_argv[1], "SIGINT");
        EXPECT_EQ(g_argv[2], "11111");
    }
}

TEST_F(RUNNING_MODE_UTEST, StartParseTask)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.isQuit_ = true;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartParseTask());
    rMode.isQuit_ = false;
    rMode.taskPid_ = 1111;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartParseTask());
    rMode.taskPid_ = MSVP_PROCESS;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartParseTask());
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    MOCKER(Utils::ExecCmd).stubs().will(returnValue(PROFILING_FAILED)).then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartParseTask());
    MOCKER_CPP(&RunningMode::WaitRunningProcess)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartParseTask());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartParseTask());
}

TEST_F(RUNNING_MODE_UTEST, StartQueryTask)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.isQuit_ = true;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartQueryTask());
    rMode.isQuit_ = false;
    rMode.taskPid_ = 1111;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartQueryTask());
    rMode.taskPid_ = MSVP_PROCESS;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartQueryTask());
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    MOCKER(Utils::ExecCmd).stubs().will(returnValue(PROFILING_FAILED)).then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartQueryTask());
    MOCKER_CPP(&RunningMode::WaitRunningProcess)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartQueryTask());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartQueryTask());
}

TEST_F(RUNNING_MODE_UTEST, StartExportTask)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.isQuit_ = true;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    rMode.isQuit_ = false;
    rMode.taskPid_ = 1111;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    rMode.taskPid_ = MSVP_PROCESS;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    params->exportModelId = 1;
    params->exportIterationId = 1;
    // 缺省导出类型 text：走 timeline + summary 两次调用。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(false));
    MOCKER_CPP(
        &RunningMode::RunExportSummaryTask,
        int32_t(RunningMode::*)(const ExecCmdParams&, std::vector<std::string>&, int32_t&, bool))
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    MOCKER_CPP(&RunningMode::RunExportTimelineTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    GlobalMockObject::verify();

    // export summary
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(false));
    MOCKER(Utils::ExecCmd).stubs().will(returnValue(PROFILING_FAILED)).then(returnValue(PROFILING_SUCCESS));

    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    MOCKER_CPP(&RunningMode::WaitRunningProcess).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());

    GlobalMockObject::verify();
    // export timeline
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(false));
    MOCKER(Utils::ExecCmd)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS))
        .then(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&RunningMode::WaitRunningProcess)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS))
        .then(returnValue(PROFILING_SUCCESS))
        .then(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
}

TEST_F(RUNNING_MODE_UTEST, StartExportTaskWithDefaultTypeKeepsTwoCalls)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", params);
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    // 缺省导出类型为 text，不因解析包支持 export all 而改变：不得走单次导出。
    EXPECT_EQ(params->exportType, "text");

    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(true));
    // export all 若被调用会失败，从而暴露"默认不开 all"被破坏。
    MOCKER_CPP(&RunningMode::RunExportAllTask).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER_CPP(&RunningMode::RunExportTimelineTask).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(
        &RunningMode::RunExportSummaryTask,
        int32_t(RunningMode::*)(const ExecCmdParams&, std::vector<std::string>&, int32_t&, bool))
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, StartExportTaskWithExportTypeAll)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", params);
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    params->exportType = "all";

    // --type=all 且解析包支持时，一次调用完成导出。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(true));
    MOCKER_CPP(&RunningMode::RunExportAllTask).stubs().will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    GlobalMockObject::verify();

    // export all 执行失败时直接失败：text 分支不参与，不会因它返回成功而掩盖失败。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(true));
    MOCKER_CPP(&RunningMode::RunExportAllTask).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER_CPP(&RunningMode::RunExportTimelineTask).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(
        &RunningMode::RunExportSummaryTask,
        int32_t(RunningMode::*)(const ExecCmdParams&, std::vector<std::string>&, int32_t&, bool))
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, StartExportTaskWithExportTypeAllUnsupportedPackage)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", params);
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    params->exportType = "all";

    // 解析包不支持 export all 时，--type=all 必须回退到 timeline + summary 两次调用。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(false));
    // export all 若被调用会失败，从而暴露"未回退"的实现错误。
    MOCKER_CPP(&RunningMode::RunExportAllTask).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER_CPP(&RunningMode::RunExportTimelineTask).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(
        &RunningMode::RunExportSummaryTask,
        int32_t(RunningMode::*)(const ExecCmdParams&, std::vector<std::string>&, int32_t&, bool))
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    GlobalMockObject::verify();

    // 回退路径中 timeline 失败时整体失败，不能因回退而吞掉错误。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(false));
    MOCKER_CPP(&RunningMode::RunExportTimelineTask).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER_CPP(
        &RunningMode::RunExportSummaryTask,
        int32_t(RunningMode::*)(const ExecCmdParams&, std::vector<std::string>&, int32_t&, bool))
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartExportTask());
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, StartExportTaskWithExportTypeDbSkipsExportAll)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", params);
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    params->exportType = "db";

    // --type=db 只导出统一 db；export all 若被调用会返回失败，从而暴露分支错误。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(true));
    MOCKER_CPP(&RunningMode::RunExportAllTask).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER_CPP(
        &RunningMode::RunExportDbTask,
        int32_t(RunningMode::*)(const ExecCmdParams&, std::vector<std::string>&, int32_t&, bool))
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, IsExportAllSupportedJudgesByExitCode)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);

    // 分析路径缺失时不得探测，直接判为不支持。
    EXPECT_FALSE(rMode.IsExportAllSupported());
    rMode.analysisPath_ = "path_test";

    // 探测命令行固定为 export all --help，且走异步路径避免父进程 chdir。
    g_exportExitCode = 0;
    ExportArgvHelper::Reset();
    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdCaptureStub));
    MOCKER(Utils::WaitProcess).stubs().will(invoke(WaitProcessStub));
    EXPECT_TRUE(rMode.IsExportAllSupported());
    EXPECT_EQ(ExportArgvHelper::Count(), 1);
    if (ExportArgvHelper::Count() == 1) {
        const std::vector<std::string>& argv = g_exportArgvList[0];
        EXPECT_EQ(argv.size(), 4);
        if (argv.size() == 4) {
            EXPECT_EQ(argv[1], "export");
            EXPECT_EQ(argv[2], "all");
            EXPECT_EQ(argv[3], "--help");
        }
    }
    // 探测必须使用异步路径：同步路径会在父进程内 chdir，污染后续子进程的工作目录。
    EXPECT_TRUE(g_exportCmdParams.async);
    // 输出重定向到空设备，避免 --help 正文与 argparse 报错污染 msprof 输出流。
    EXPECT_EQ(g_exportCmdParams.stdoutRedirectFile, "/dev/null");
    // fork 时刻子进程的 stderr 必须也被屏蔽：老包 argparse 的 invalid choice 写 fd 2，
    // 只重定向 stdout 会让报错泄漏到屏幕。同时确认探测结束后已恢复，未污染后续输出。
    EXPECT_EQ(g_stderrTargetAtExec, "/dev/null");
    EXPECT_NE(ReadStderrTarget(), "/dev/null");
    GlobalMockObject::verify();

    // 老分析包不认识 all，argparse 以非 0 退出，必须判为不支持。
    g_exportExitCode = 2;
    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdCaptureStub));
    MOCKER(Utils::WaitProcess).stubs().will(invoke(WaitProcessStub));
    EXPECT_FALSE(rMode.IsExportAllSupported());
    GlobalMockObject::verify();

    // 子进程被信号终止时 wait status 不是退出码，必须判为不支持而非误读成 0。
    g_exportExitCode = 9;
    g_exportTerminatedBySignal = true;
    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdCaptureStub));
    MOCKER(Utils::WaitProcess).stubs().will(invoke(WaitProcessStub));
    EXPECT_FALSE(rMode.IsExportAllSupported());
    g_exportTerminatedBySignal = false;
    GlobalMockObject::verify();

    // 探测进程启动失败时直接判为不支持，不再等待。
    MOCKER(Utils::ExecCmd).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_FALSE(rMode.IsExportAllSupported());
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, ExportReportsIsOnlySentWhereAnalysisPackageAcceptsIt)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", params);
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    params->reportsPath = "reports.json";

    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(true));
    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdCaptureStub));
    MOCKER_CPP(&RunningMode::WaitRunningProcess).stubs().will(returnValue(PROFILING_SUCCESS));

    // 新分析包：export all 与 export db 都接受 -reports，必须下发。
    params->exportType = "all";
    ExportArgvHelper::Reset();
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    EXPECT_EQ(ExportArgvHelper::Count(), 1);
    if (ExportArgvHelper::Count() == 1) {
        EXPECT_TRUE(ExportArgvHelper::Contains(g_exportArgvList[0], "all"));
        EXPECT_TRUE(ExportArgvHelper::HasReports(g_exportArgvList[0]));
    }

    params->exportType = "db";
    ExportArgvHelper::Reset();
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    EXPECT_EQ(ExportArgvHelper::Count(), 1);
    if (ExportArgvHelper::Count() == 1) {
        EXPECT_TRUE(ExportArgvHelper::Contains(g_exportArgvList[0], "db"));
        EXPECT_TRUE(ExportArgvHelper::HasReports(g_exportArgvList[0]));
    }
    GlobalMockObject::verify();

    // text 走 timeline + summary 两次调用：-reports 由 all/report 是否同时支持决定，
    // 新包（支持 export all）两条命令都下发，老包只有 timeline 自始支持、summary 不得下发。
    // verify() 已清除上面的桩，此处必须重新注册，否则会走真实探测并因 analysisPath_ 不存在而失败。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(true));
    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdCaptureStub));
    MOCKER_CPP(&RunningMode::WaitRunningProcess).stubs().will(returnValue(PROFILING_SUCCESS));

    params->exportType = "text";
    ExportArgvHelper::Reset();
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    EXPECT_EQ(ExportArgvHelper::Count(), 2);
    if (ExportArgvHelper::Count() == 2) {
        EXPECT_TRUE(ExportArgvHelper::Contains(g_exportArgvList[0], "timeline"));
        EXPECT_TRUE(ExportArgvHelper::HasReports(g_exportArgvList[0]));
        EXPECT_TRUE(ExportArgvHelper::Contains(g_exportArgvList[1], "summary"));
        EXPECT_TRUE(ExportArgvHelper::HasReports(g_exportArgvList[1]));
    }
    GlobalMockObject::verify();

    // 老分析包：summary 不接受 -reports，不得下发；timeline 自始支持，仍按原样下发。
    MOCKER_CPP(&RunningMode::IsExportAllSupported, bool(RunningMode::*)(void) const).stubs().will(returnValue(false));
    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdCaptureStub));
    MOCKER_CPP(&RunningMode::WaitRunningProcess).stubs().will(returnValue(PROFILING_SUCCESS));

    ExportArgvHelper::Reset();
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartExportTask());
    EXPECT_EQ(ExportArgvHelper::Count(), 2);
    if (ExportArgvHelper::Count() == 2) {
        EXPECT_TRUE(ExportArgvHelper::Contains(g_exportArgvList[0], "timeline"));
        EXPECT_TRUE(ExportArgvHelper::HasReports(g_exportArgvList[0]));
        EXPECT_TRUE(ExportArgvHelper::Contains(g_exportArgvList[1], "summary"));
        EXPECT_FALSE(ExportArgvHelper::HasReports(g_exportArgvList[1]));
    }
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, StopNoWait)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    std::shared_ptr<Collector::Dvvp::Msprofbin::AppMode> rMode(new Collector::Dvvp::Msprofbin::AppMode("app", params));

    MOCKER_CPP_VIRTUAL(
        (Collector::Dvvp::Msprofbin::RunningMode*)rMode.get(),
        &Collector::Dvvp::Msprofbin::AppMode::UpdateOutputDirInfo)
        .stubs();

    std::stringstream output;
    std::streambuf* oldCoutBuffer = std::cout.rdbuf();
    std::cout.rdbuf(output.rdbuf());
    rMode->StopNoWait();
    std::vector<std::string> expectedList = {"Receive stop signal."};
    std::cout.rdbuf(oldCoutBuffer);
    for (auto expectedPrint : expectedList) {
        EXPECT_NE(output.str().find(expectedPrint), std::string::npos) << "Screen print:" << std::endl
                                                                       << output.str() << std::endl
                                                                       << "Missing expected: " + expectedPrint;
    }
}

static int _wait_process(int taskPid_, bool& isExited, int& exitCode, bool s)
{
    static int phase2 = 0;
    if (phase2 == 0) {
        phase2++;
        return PROFILING_FAILED;
    }

    if (phase2 == 4) {
        isExited = true;
        return PROFILING_SUCCESS;
    }

    if (phase2 == 3) {
        phase2++;
        return PROFILING_SUCCESS;
    }

    if (phase2 == 2) {
        isExited = true;
        exitCode = 1;
        phase2++;
        return PROFILING_SUCCESS;
    }

    if (phase2 == 1) {
        isExited = true;
        phase2++;
        return PROFILING_SUCCESS;
    }
}

static int _wait_process_exit_8(int, bool& isExited, int& exitCode, bool)
{
    isExited = true;
    exitCode = 8 << 8;
    return PROFILING_SUCCESS;
}

static int _wait_process_exit_255(int, bool& isExited, int& exitCode, bool)
{
    isExited = true;
    exitCode = 255 << 8;
    return PROFILING_SUCCESS;
}

static AppMode* _app_mode_for_quit = nullptr;

static int _wait_process_exit_1_when_quit(int, bool& isExited, int& exitCode, bool)
{
    isExited = true;
    exitCode = 1 << 8;
    _app_mode_for_quit->isQuit_ = true;
    return PROFILING_SUCCESS;
}

static int _wait_process_exit_status(int, bool& isExited, int& exitCode, bool)
{
    isExited = true;
    exitCode = 255 << 8;
    return PROFILING_SUCCESS;
}

static int _wait_process_signal_status(int, bool& isExited, int& exitCode, bool)
{
    isExited = true;
    exitCode = SIGTERM;
    return PROFILING_SUCCESS;
}

static int _set_quit_and_return_failed()
{
    _app_mode_for_quit->isQuit_ = true;
    return PROFILING_FAILED;
}

static SystemMode* _system_mode_for_quit = nullptr;

static int _set_system_quit_and_return_failed()
{
    _system_mode_for_quit->isQuit_ = true;
    return PROFILING_FAILED;
}

TEST_F(RUNNING_MODE_UTEST, WaitRunningProcess)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    EXPECT_EQ(PROFILING_FAILED, rMode.WaitRunningProcess("a"));
    rMode.taskPid_ = 11111;
    rMode.isQuit_ = false;
    MOCKER(Utils::WaitProcess).stubs().will(invoke(_wait_process));
    MOCKER_CPP(&AppMode::StopNoWait).stubs();
    EXPECT_EQ(PROFILING_FAILED, rMode.WaitRunningProcess("a"));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.WaitRunningProcess("a"));
    EXPECT_EQ(PROFILING_FAILED, rMode.WaitRunningProcess("a"));
    rMode.isQuit_ = true;
    EXPECT_EQ(PROFILING_SUCCESS, rMode.WaitRunningProcess("a"));
}

TEST_F(RUNNING_MODE_UTEST, WaitRunningProcessPropagatesNonAppExitCode)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.taskPid_ = 11111;
    rMode.isQuit_ = false;

    for (const auto& processUsage : {"Analyze", "Parse", "Query", "Export db", "Export summary", "Export timeline"}) {
        MOCKER(Utils::WaitProcess).stubs().will(invoke(_wait_process_exit_8));
        EXPECT_EQ(PROFILING_FAILED, rMode.WaitRunningProcess(processUsage)) << "processUsage: " << processUsage;
        GlobalMockObject::verify();
    }
}

TEST_F(RUNNING_MODE_UTEST, WaitRunningProcessTreatsUserQuitAsSuccess)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    _app_mode_for_quit = &rMode;
    rMode.taskPid_ = 11111;
    rMode.isQuit_ = false;

    MOCKER(Utils::WaitProcess).stubs().will(invoke(_wait_process_exit_1_when_quit));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.WaitRunningProcess("Export timeline"));
    GlobalMockObject::verify();
    _app_mode_for_quit = nullptr;
}

TEST_F(RUNNING_MODE_UTEST, WaitRunningProcessContinuesAfterApplicationExitCode)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.taskPid_ = 11111;
    rMode.isQuit_ = false;

    MOCKER(Utils::WaitProcess).stubs().will(invoke(_wait_process_exit_255));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.WaitRunningProcess("App"));
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, WaitRunningProcessContinuesAfterApplicationExitStatus)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.taskPid_ = 11111;
    rMode.isQuit_ = false;

    MOCKER(Utils::WaitProcess).stubs().will(invoke(_wait_process_exit_status));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.WaitRunningProcess("app"));
    GlobalMockObject::verify();

    MOCKER(Utils::WaitProcess).stubs().will(invoke(_wait_process_signal_status));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.WaitRunningProcess("app"));
    GlobalMockObject::verify();
}

TEST_F(RUNNING_MODE_UTEST, WaitRunningProcessDistinguishesSignalTermination)
{
    EXPECT_TRUE(Collector::Dvvp::Msprofbin::IsSignalTerminationStatus(SIGTERM));
    EXPECT_TRUE(Collector::Dvvp::Msprofbin::IsSignalTerminationStatus(SIGSEGV));
    EXPECT_FALSE(Collector::Dvvp::Msprofbin::IsSignalTerminationStatus(0));
    EXPECT_FALSE(Collector::Dvvp::Msprofbin::IsSignalTerminationStatus(255U << 8U));
}

TEST_F(RUNNING_MODE_UTEST, WaitRunningProcessShowsAppConflictHintForDynamicProfiling)
{
    EXPECT_TRUE(Collector::Dvvp::Msprofbin::IsAppProcessUsage("app"));
    EXPECT_TRUE(Collector::Dvvp::Msprofbin::IsAppProcessUsage("App"));
    EXPECT_FALSE(Collector::Dvvp::Msprofbin::IsAppProcessUsage("app timeline"));
    EXPECT_FALSE(Collector::Dvvp::Msprofbin::IsAppProcessUsage("Export timeline"));
}

TEST_F(RUNNING_MODE_UTEST, AppModeRunModeTasksTreatsUserQuitDuringExportAsSuccess)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    _app_mode_for_quit = &rMode;
    const std::string result = "/tmp/running_mode_app_quit_secure_ut";
    const std::string cleanup = "rm -rf " + result;
    const std::string prepare = cleanup + " && mkdir -p " + result;
    (void)system(prepare.c_str());
    rMode.jobResultDirList_.insert(result);
    MOCKER_CPP(&AppMode::StartAppTask).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AppMode::CheckAnalysisEnv).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AppMode::StartExportTask).stubs().will(invoke(_set_quit_and_return_failed));

    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    _app_mode_for_quit = nullptr;
    (void)system(cleanup.c_str());
}

TEST_F(RUNNING_MODE_UTEST, SystemModeRunModeTasksPropagatesExportFailure)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    rMode.jobResultDirList_.insert("PROF");
    MOCKER_CPP(&SystemMode::StartSysTaskByProfApi).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::CheckAnalysisEnv).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::StartExportTask).stubs().will(returnValue(PROFILING_FAILED));

    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
}

TEST_F(RUNNING_MODE_UTEST, SystemModeRunModeTasksTreatsUserQuitDuringExportAsSuccess)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    _system_mode_for_quit = &rMode;
    const std::string result = "/tmp/running_mode_system_quit_secure_ut";
    const std::string cleanup = "rm -rf " + result;
    const std::string prepare = cleanup + " && mkdir -p " + result;
    (void)system(prepare.c_str());
    rMode.jobResultDirList_.insert(result);
    MOCKER_CPP(&SystemMode::StartSysTaskByProfApi).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::CheckAnalysisEnv).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::StartExportTask).stubs().will(invoke(_set_system_quit_and_return_failed));

    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    _system_mode_for_quit = nullptr;
    (void)system(cleanup.c_str());
}

static int _get_cmd_print_info(
    const std::string& cmd, std::string& output, const unsigned int dataLength = MAX_CMD_PRINT_MESSAGE_LEN)
{
    static int phase3 = 0;
    if (phase3 == 0) {
        phase3++;
        return PROFILING_FAILED;
    }
    if (phase3 == 1) {
        phase3++;
        output = "Python\n";
        return PROFILING_SUCCESS;
    }
    if (phase3 == 2) {
        phase3++;
        output = "Python 3.a.3\n";
        return PROFILING_SUCCESS;
    }
    if (phase3 == 3) {
        phase3++;
        output = "Python 3.5.3\n";
        return PROFILING_SUCCESS;
    }
    if (phase3 == 4) {
        output = "Python 3.7.5\n";
        return PROFILING_SUCCESS;
    }
}

TEST_F(RUNNING_MODE_UTEST, CheckAnalysisEnv)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.isQuit_ = true;
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckAnalysisEnv());
    rMode.isQuit_ = false;
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::RunSocSide)
        .stubs()
        .will(returnValue(true))
        .then(returnValue(false));
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckAnalysisEnv());

    std::string resValue = "/tmp/test/msprof";
    MOCKER(Utils::GetSelfPath).stubs().will(returnValue(resValue));

    MOCKER(Utils::SplitPath).stubs().will(returnValue(PROFILING_FAILED)).then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckAnalysisEnv());
    MOCKER(Utils::IsFileExist).stubs().will(returnValue(false)).then(returnValue(true));
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckAnalysisEnv());
    MOCKER(mmAccess2).stubs().will(returnValue(EN_ERR)).then(returnValue(EN_OK));
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckAnalysisEnv());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.CheckAnalysisEnv());
}

TEST_F(RUNNING_MODE_UTEST, AppModeModeParamsCheck)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    rMode.params_ = params;
    MOCKER_CPP(&RunningMode::HandleProfilingParams)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
}

TEST_F(RUNNING_MODE_UTEST, AppModeRunModeTasks)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    rMode.params_ = params;
    const std::string result = "/tmp/running_mode_app_secure_ut";
    const std::string cleanup = "rm -rf " + result;
    const std::string prepare = cleanup + " && mkdir -p " + result;
    (void)system(prepare.c_str());
    rMode.jobResultDirList_.insert(result);
    MOCKER_CPP(&AppMode::StartAppTask).stubs().will(returnValue(PROFILING_FAILED)).then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AppMode::CheckAnalysisEnv)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AppMode::StartExportTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AppMode::StartQueryTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    rMode.jobResultDirList_.clear();
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    (void)system(cleanup.c_str());
}

TEST_F(RUNNING_MODE_UTEST, AppModeRunModeTasksPropagatesExportFailure)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.jobResultDirList_.insert("PROF");
    MOCKER_CPP(&AppMode::StartAppTask).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AppMode::CheckAnalysisEnv).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&AppMode::StartExportTask).stubs().will(returnValue(PROFILING_FAILED));

    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
}

TEST_F(RUNNING_MODE_UTEST, AppModeSetDefaultParams)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::CHIP_V4_1_0));
    Platform::instance()->Init();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    params->taskTsfw = "on";
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.SetDefaultParams();
    EXPECT_EQ(params->acl, "on");
    EXPECT_EQ(params->ts_keypoint, "on");
    EXPECT_EQ(params->ai_core_profiling, "on");
    EXPECT_EQ(params->ai_core_profiling_mode, "task-based");

    params->ai_core_profiling = "on";
    EXPECT_EQ(params->aiv_profiling, "on");
    EXPECT_EQ(params->aiv_profiling_mode, "task-based");
    EXPECT_EQ(params->hwts_log, "");
    Platform::instance()->Uninit();
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(PlatformType::DC_TYPE));
    Platform::instance()->Init();
    rMode.SetDefaultParams();
    Platform::instance()->Uninit();
}

TEST_F(RUNNING_MODE_UTEST, AppModeStartAppTask)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);
    rMode.isQuit_ = true;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAppTask(true));
    rMode.isQuit_ = false;
    MOCKER(&analysis::dvvp::app::Application::LaunchApp)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&RunningMode::WaitRunningProcess)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAppTask(true));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAppTask(true));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartAppTask(true));
}

TEST_F(RUNNING_MODE_UTEST, AppModeStartAppTaskForDynProf)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AppMode rMode("app", params);

    MOCKER_CPP(&DynProfCliMgr::IsAppMode).stubs().will(returnValue(true));
    MOCKER(&analysis::dvvp::app::Application::LaunchApp)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&DynProfCliMgr::StartDynProfCli)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&DynProfCliMgr::WaitQuit).stubs().will(ignoreReturnValue());
    MOCKER_CPP(&RunningMode::WaitRunningProcess)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAppTaskForDynProf());
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAppTaskForDynProf());
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAppTaskForDynProf());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartAppTaskForDynProf());
}

static int _drv_get_dev_ids_rmu(int numDevices, std::vector<int>& devIds)
{
    devIds = {0, 1};
    return PROFILING_SUCCESS;
}

TEST_F(RUNNING_MODE_UTEST, SystemModeCheckIfDeviceOnline)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    params->devices = "all";
    EXPECT_EQ(PROFILING_SUCCESS, rMode.CheckIfDeviceOnline());
    params->devices = "a,1";
    MOCKER(analysis::dvvp::driver::DrvGetDevNum).stubs().will(returnValue(-1)).then(returnValue(2));
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckIfDeviceOnline());
    MOCKER(analysis::dvvp::driver::DrvGetDevIds)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(invoke(_drv_get_dev_ids_rmu));
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckIfDeviceOnline());
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckIfDeviceOnline());
    params->devices = "3,4";
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckIfDeviceOnline());
    params->devices = "0";
    EXPECT_EQ(PROFILING_SUCCESS, rMode.CheckIfDeviceOnline());
    params->devices = "0,2";
    EXPECT_EQ(PROFILING_SUCCESS, rMode.CheckIfDeviceOnline());
}

TEST_F(RUNNING_MODE_UTEST, SystemModeStopRunningTasks)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    MOCKER(Utils::ExecCmd).stubs().will(invoke(ExecCmdStub));
    g_argv.clear();
    rMode.taskPid_ = 11111;
    rMode.StopRunningTasks();
    EXPECT_EQ(g_argv.size(), 3);
    if (g_argv.size() == 3) {
        EXPECT_EQ(g_argv[0], "-s");
        EXPECT_EQ(g_argv[1], "SIGINT");
        EXPECT_EQ(g_argv[2], "11111");
    }
}

TEST_F(RUNNING_MODE_UTEST, SystemModeCheckHostSysParams)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckHostSysParams());
    params->host_sys = "on";
    EXPECT_EQ(PROFILING_FAILED, rMode.CheckHostSysParams());
    params->host_sys_pid = 100;
    EXPECT_EQ(PROFILING_SUCCESS, rMode.CheckHostSysParams());
}

TEST_F(RUNNING_MODE_UTEST, DataWillBeCollected)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    EXPECT_EQ(false, rMode.DataWillBeCollected());
    params->usedParams = {ARGS_OUTPUT, ARGS_SYS_PERIOD, ARGS_SYS_DEVICES, ARGS_SYS_PROFILING};
    EXPECT_EQ(true, rMode.DataWillBeCollected());
    params->usedParams = {ARGS_OUTPUT, ARGS_SYS_PERIOD, ARGS_SYS_DEVICES};
}

TEST_F(RUNNING_MODE_UTEST, SystemModeModeParamsCheck)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    rMode.params_ = params;
    MOCKER_CPP(&SystemMode::CheckNeccessaryParams)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::DataWillBeCollected).stubs().will(returnValue(false)).then(returnValue(true));
    MOCKER_CPP(&SystemMode::CheckHostSysParams)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::HandleProfilingParams)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());

    GlobalMockObject::verify();
    MOCKER_CPP(&SystemMode::CheckHostSysParams).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::HandleProfilingParams).stubs().will(returnValue(PROFILING_SUCCESS));
    params->usedParams = {ARGS_OUTPUT};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_SYS_PERIOD, ARGS_PYTHON_PATH};
    params->usedParams = {ARGS_OUTPUT, ARGS_SYS_PERIOD, ARGS_EXPORT};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_SYS_PERIOD, ARGS_EXPORT};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
}

TEST_F(RUNNING_MODE_UTEST, SystemModeRunModeTasks)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    rMode.params_ = params;
    rMode.params_->ai_core_profiling = "on";
    const std::string result = "/tmp/running_mode_system_secure_ut";
    const std::string cleanup = "rm -rf " + result;
    const std::string prepare = cleanup + " && mkdir -p " + result;
    (void)system(prepare.c_str());
    rMode.jobResultDirList_.insert(result);
    MOCKER_CPP(&SystemMode::StartSysTaskByProfApi)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_NOTSUPPORT))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::CheckAnalysisEnv)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::StartExportTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&SystemMode::StartQueryTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));

    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_NOTSUPPORT, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
    EXPECT_EQ("on", rMode.params_->aiv_profiling);
    EXPECT_EQ("sample-based", rMode.params_->aiv_profiling_mode);
    (void)system(cleanup.c_str());
}

TEST_F(RUNNING_MODE_UTEST, SystemModeStartSysTaskByProfApi)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);

    CONST_CHAR_PTR originalEnv = getenv(PROFILER_SAMPLE_CONFIG_ENV);
    const bool originalExist = originalEnv != nullptr;
    const std::string originalValue = originalExist ? originalEnv : "";

    (void)setenv(PROFILER_SAMPLE_CONFIG_ENV, "old_config", ENV_OVERWRITE_FOR_TEST);
    MOCKER(dlopen).stubs().will(returnValue((void*)FAKE_PROF_API_HANDLE));
    MOCKER(dlsym).stubs().will(returnValue((void*)&FakeMsprofInitFailed));
    MOCKER(dlclose).stubs().will(returnValue(0));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartSysTaskByProfApi());
    EXPECT_EQ(std::string("old_config"), getenv(PROFILER_SAMPLE_CONFIG_ENV));
    GlobalMockObject::verify();

    MOCKER(dlopen).stubs().will(returnValue((void*)FAKE_PROF_API_HANDLE));
    MOCKER(dlsym).stubs().will(returnValue((void*)&FakeMsprofInitSuccess));
    MOCKER(dlclose).stubs().will(returnValue(0));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartSysTaskByProfApi());
    EXPECT_EQ(std::string("old_config"), getenv(PROFILER_SAMPLE_CONFIG_ENV));

    if (originalExist) {
        (void)setenv(PROFILER_SAMPLE_CONFIG_ENV, originalValue.c_str(), ENV_OVERWRITE_FOR_TEST);
    } else {
        (void)unsetenv(PROFILER_SAMPLE_CONFIG_ENV);
    }
}

TEST_F(RUNNING_MODE_UTEST, SystemModeStartSysTaskByProfApiRestoresMissingEnv)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    CONST_CHAR_PTR originalEnv = getenv(PROFILER_SAMPLE_CONFIG_ENV);
    const bool originalExist = originalEnv != nullptr;
    const std::string originalValue = originalExist ? originalEnv : "";

    (void)unsetenv(PROFILER_SAMPLE_CONFIG_ENV);
    MOCKER(dlopen).stubs().will(returnValue((void*)nullptr));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartSysTaskByProfApi());
    EXPECT_EQ(nullptr, getenv(PROFILER_SAMPLE_CONFIG_ENV));

    if (originalExist) {
        (void)setenv(PROFILER_SAMPLE_CONFIG_ENV, originalValue.c_str(), ENV_OVERWRITE_FOR_TEST);
    }
}

TEST_F(RUNNING_MODE_UTEST, SystemModeStartSysTaskByProfApiContainsOpType)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    params->opType = "MatMul,Index";
    Collector::Dvvp::Msprofbin::SystemMode rMode("system", params);
    CONST_CHAR_PTR originalEnv = getenv(PROFILER_SAMPLE_CONFIG_ENV);
    const bool originalExist = originalEnv != nullptr;
    const std::string originalValue = originalExist ? originalEnv : "";

    (void)unsetenv(PROFILER_SAMPLE_CONFIG_ENV);
    g_sampleConfigForTest.clear();
    MOCKER(dlopen).stubs().will(returnValue((void*)FAKE_PROF_API_HANDLE));
    MOCKER(dlsym).stubs().will(returnValue((void*)&FakeMsprofInitSuccess));
    MOCKER(dlclose).stubs().will(returnValue(0));
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartSysTaskByProfApi());
    EXPECT_NE(std::string::npos, g_sampleConfigForTest.find("opType"));
    EXPECT_NE(std::string::npos, g_sampleConfigForTest.find("MatMul,Index"));
    if (originalExist) {
        (void)setenv(PROFILER_SAMPLE_CONFIG_ENV, originalValue.c_str(), ENV_OVERWRITE_FOR_TEST);
    } else {
        (void)unsetenv(PROFILER_SAMPLE_CONFIG_ENV);
    }
}

TEST_F(RUNNING_MODE_UTEST, ProfApiLoaderInitWithoutLoad)
{
    Collector::Dvvp::Msprofbin::ProfApiLoader loader;
    EXPECT_EQ(PROFILING_FAILED, loader.Init());
}

TEST_F(RUNNING_MODE_UTEST, ProfApiLoaderLoadFailedWhenDlopenFailed)
{
    Collector::Dvvp::Msprofbin::ProfApiLoader loader;
    MOCKER(dlopen).stubs().will(returnValue((void*)nullptr));
    EXPECT_EQ(PROFILING_FAILED, loader.Load());
}

TEST_F(RUNNING_MODE_UTEST, ProfApiLoaderLoadFailedWhenSymbolNotFound)
{
    Collector::Dvvp::Msprofbin::ProfApiLoader loader;
    MockProfApi(nullptr);
    EXPECT_EQ(PROFILING_FAILED, loader.Load());
}

TEST_F(RUNNING_MODE_UTEST, ProfApiLoaderInitFailed)
{
    Collector::Dvvp::Msprofbin::ProfApiLoader loader;
    MockProfApi((void*)&FakeMsprofInitFailed);
    EXPECT_EQ(PROFILING_SUCCESS, loader.Load());
    EXPECT_EQ(PROFILING_FAILED, loader.Init());
}

TEST_F(RUNNING_MODE_UTEST, ProfApiLoaderInitNotSupport)
{
    Collector::Dvvp::Msprofbin::ProfApiLoader loader;
    MockProfApi((void*)&FakeMsprofInitNotSupport);
    EXPECT_EQ(PROFILING_SUCCESS, loader.Load());
    EXPECT_EQ(PROFILING_NOTSUPPORT, loader.Init());
}

TEST_F(RUNNING_MODE_UTEST, ProfApiLoaderLoadInitAndClose)
{
    Collector::Dvvp::Msprofbin::ProfApiLoader loader;
    MockProfApi((void*)&FakeMsprofInitSuccess);
    EXPECT_EQ(PROFILING_SUCCESS, loader.Load());
    EXPECT_EQ(PROFILING_SUCCESS, loader.Init());
    loader.Close();
}

TEST_F(RUNNING_MODE_UTEST, ProfApiLoaderCloseIsIdempotent)
{
    Collector::Dvvp::Msprofbin::ProfApiLoader loader;
    loader.Close();
    loader.Close();
}

TEST_F(RUNNING_MODE_UTEST, ParseModeModeParamsCheck)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ParseMode rMode("parse", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    rMode.params_ = params;

    GlobalMockObject::verify();
    params->usedParams = {ARGS_QUERY};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_PARSE, ARGS_PYTHON_PATH};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_PARSE, ARGS_SYS_PROFILING};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
}

TEST_F(RUNNING_MODE_UTEST, ParseModeUpdateOutputDirInfo)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    params->result_dir = "hello";
    Collector::Dvvp::Msprofbin::ParseMode rMode("parse", params);
    rMode.jobResultDir_ = "123";
    rMode.UpdateOutputDirInfo();

    rMode.jobResultDir_ = "";
    rMode.UpdateOutputDirInfo();
    EXPECT_EQ(rMode.jobResultDir_, "hello");
}

TEST_F(RUNNING_MODE_UTEST, ParseModeRunModeTasks)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ParseMode rMode("parse", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    rMode.params_ = params;
    MOCKER_CPP(&SystemMode::CheckAnalysisEnv)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    MOCKER_CPP(&SystemMode::StartParseTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    MOCKER_CPP(&SystemMode::StartQueryTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
}

TEST_F(RUNNING_MODE_UTEST, QueryModeUpdateOutputDirInfo)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    params->result_dir = "hello";
    Collector::Dvvp::Msprofbin::QueryMode rMode("query", params);
    rMode.jobResultDir_ = "123";
    rMode.UpdateOutputDirInfo();

    rMode.jobResultDir_ = "";
    rMode.UpdateOutputDirInfo();
    EXPECT_EQ(rMode.jobResultDir_, "hello");
}

TEST_F(RUNNING_MODE_UTEST, QueryModeModeParamsCheck)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::QueryMode rMode("query", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    rMode.params_ = params;

    GlobalMockObject::verify();
    params->usedParams = {ARGS_EXPORT};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_QUERY, ARGS_PYTHON_PATH};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_QUERY, ARGS_SYS_PROFILING};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
}

TEST_F(RUNNING_MODE_UTEST, QueryModeRunModeTasks)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::QueryMode rMode("query", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    rMode.params_ = params;
    MOCKER_CPP(&SystemMode::CheckAnalysisEnv)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    MOCKER_CPP(&SystemMode::StartQueryTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
}

TEST_F(RUNNING_MODE_UTEST, ExportModeUpdateOutputDirInfo)
{
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    params->result_dir = "hello";
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", params);
    rMode.jobResultDir_ = "123";
    rMode.UpdateOutputDirInfo();

    rMode.jobResultDir_ = "";
    rMode.UpdateOutputDirInfo();
    EXPECT_EQ(rMode.jobResultDir_, "hello");
}

TEST_F(RUNNING_MODE_UTEST, ExportModeModeParamsCheck)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    rMode.params_ = params;

    GlobalMockObject::verify();
    params->usedParams = {ARGS_QUERY};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_EXPORT, ARGS_PYTHON_PATH};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_EXPORT, ARGS_SYS_PROFILING, ARGS_EXPORT_ITERATION_ID, ARGS_EXPORT_MODEL_ID};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
}

TEST_F(RUNNING_MODE_UTEST, ExportModeRunModeTasks)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::ExportMode rMode("export", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    rMode.params_ = params;
    MOCKER_CPP(&SystemMode::CheckAnalysisEnv)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    MOCKER_CPP(&SystemMode::StartExportTask)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.RunModeTasks());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.RunModeTasks());
}

TEST_F(RUNNING_MODE_UTEST, StartAnalyzeTask)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AnalyzeMode rMode("analyze", params);
    rMode.isQuit_ = true;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAnalyzeTask());
    rMode.isQuit_ = false;
    rMode.taskPid_ = 1111;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAnalyzeTask());
    rMode.taskPid_ = MSVP_PROCESS;
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAnalyzeTask());
    rMode.jobResultDir_ = "123";
    rMode.analysisPath_ = "path_test";
    MOCKER(Utils::ExecCmd).stubs().will(returnValue(PROFILING_FAILED)).then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAnalyzeTask());
    MOCKER_CPP(&RunningMode::WaitRunningProcess)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, rMode.StartAnalyzeTask());
    EXPECT_EQ(PROFILING_SUCCESS, rMode.StartAnalyzeTask());
}

TEST_F(RUNNING_MODE_UTEST, AnalyzeModeModeParamsCheck)
{
    GlobalMockObject::verify();
    std::shared_ptr<analysis::dvvp::message::ProfileParams> params(new analysis::dvvp::message::ProfileParams);
    Collector::Dvvp::Msprofbin::AnalyzeMode rMode("analyze", nullptr);
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    rMode.params_ = params;
    params->usedParams = {};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_QUERY};
    EXPECT_EQ(PROFILING_FAILED, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_ANALYZE, ARGS_PYTHON_PATH};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
    params->usedParams = {ARGS_OUTPUT, ARGS_ANALYZE, ARGS_PYTHON_PATH, ARGS_RULE};
    EXPECT_EQ(PROFILING_SUCCESS, rMode.ModeParamsCheck());
}
