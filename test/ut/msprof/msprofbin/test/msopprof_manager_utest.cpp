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

#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "msopprof_manager_tool.h"
#include "errno/error_code_tool.h"
#include "utils/utils_tool.h"
#include "cmd_log/cmd_log_tool.h"
#include "env_manager_tool.h"

using namespace analysis::dvvp::common::cmdlog;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::Msopprof;
using namespace Analysis::Dvvp::App;

class MSOPPROF_MANAGER_UTEST : public testing::Test {
protected:
    virtual void SetUp() override {}
    virtual void TearDown() override { GlobalMockObject::verify(); }
};

TEST_F(MSOPPROF_MANAGER_UTEST, CheckMsopprofIfExistWillReturnFalseWhenNotInputOpArgs)
{
    const char* argv[] = {"bin", "parse", "arg1"};
    int argc = 3;
    std::vector<std::string> args;
    bool ret = MsopprofManager::instance()->CheckMsopprofIfExist(argc, argv, args);
    EXPECT_FALSE(ret);
    EXPECT_TRUE(args.empty());
}

TEST_F(MSOPPROF_MANAGER_UTEST, CheckMsopprofIfExistWillReturnTrueWhenInputOpArgsAndOpprofNotExist)
{
    MsopprofManager::instance()->msopprofPath_ = "";
    const char* argv[] = {"bin", "op", "-a"};
    int argc = 3;
    std::vector<std::string> args;
    bool ret = MsopprofManager::instance()->CheckMsopprofIfExist(argc, argv, args);
    EXPECT_TRUE(ret);
    EXPECT_TRUE(args.empty());
}

TEST_F(MSOPPROF_MANAGER_UTEST, CheckMsopprofIfExistWillReturnTrueWhenInputOpArgsAndOpprofExists)
{
    MsopprofManager::instance()->msopprofPath_ = "/ut/test/msopprof/bin/msopprof";
    const char* argv[] = {"bin", "op", "-a"};
    int argc = 3;
    std::vector<std::string> args;
    bool ret = MsopprofManager::instance()->CheckMsopprofIfExist(argc, argv, args);
    EXPECT_TRUE(ret);
    ASSERT_EQ(args.size(), 1);
    EXPECT_STREQ(args[0].c_str(), "-a");
}

TEST_F(MSOPPROF_MANAGER_UTEST, CheckMsopprofIfExistWillParseAllArgsWhenInputOpArgsAndOpprofExists)
{
    MsopprofManager::instance()->msopprofPath_ = "/ut/test/msopprof/bin/msopprof";
    const char* argv[] = {"bin", "op", "--pid=123", "--time=10"};
    int argc = 4;
    std::vector<std::string> args;

    bool ret = MsopprofManager::instance()->CheckMsopprofIfExist(argc, argv, args);
    EXPECT_TRUE(ret);
    ASSERT_EQ(args.size(), 2);
    EXPECT_STREQ(args[0].c_str(), "--pid=123");
    EXPECT_STREQ(args[1].c_str(), "--time=10");
}

TEST_F(MSOPPROF_MANAGER_UTEST, MsopprofProcessWillReturnFailedWhrnCheckArgsFail)
{
    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::CheckInputArgsLength).stubs().will(returnValue(false));

    const char* argv[] = {"bin"};
    int argc = 1;
    int ret = MsopprofManager::instance()->MsopprofProcess(argc, argv);
    EXPECT_EQ(ret, PROFILING_FAILED);
}

TEST_F(MSOPPROF_MANAGER_UTEST, MsopprofProcessWillNotExecuteOpprofAndReturnFailedWhenInputNotOpCmd)
{
    MsopprofManager::instance()->msopprofPath_ = "";
    const char* argv[] = {"bin", "-a"};
    int argc = 2;
    int ret = MsopprofManager::instance()->MsopprofProcess(argc, argv);
    EXPECT_EQ(ret, PROFILING_FAILED);
}

TEST_F(MSOPPROF_MANAGER_UTEST, MsopprofProcessWillNotExecuteOpprofAndReturnSuccessWhenInputOpCmdAndOpprofNotExist)
{
    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::CheckBinValid).stubs().will(returnValue(false));

    MsopprofManager::instance()->msopprofPath_ = "/ut/test/msopprof/bin/msopprof";
    const char* argv[] = {"bin", "op", "-a"};
    int argc = 3;
    int ret = MsopprofManager::instance()->MsopprofProcess(argc, argv);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
}

TEST_F(MSOPPROF_MANAGER_UTEST, MsopprofProcessWillExecuteMsopprofAndReturnSuccessWhenInputOpCmdAndOpprofExists)
{
    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::CheckBinValid).stubs().will(returnValue(true));
    MOCKER_CPP(&Analysis::Dvvp::Msopprof::MsopprofManager::ExecuteMsopprof).stubs();

    MsopprofManager::instance()->msopprofPath_ = "/ut/test/msopprof/bin/msopprof";
    const char* argv[] = {"bin", "op", "-a"};
    int argc = 3;
    int ret = MsopprofManager::instance()->MsopprofProcess(argc, argv);
    EXPECT_EQ(ret, PROFILING_SUCCESS);
}

TEST_F(MSOPPROF_MANAGER_UTEST, ExecuteMsopprofWillExecuteOpprofFailWhenExecCmdFail)
{
    std::vector<std::string> params{"-a"};

    MOCKER_CPP(&Analysis::Dvvp::App::EnvManager::GetGlobalEnv).stubs().will(returnValue(std::vector<std::string>()));
    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::ExecCmd).stubs().will(returnValue(PROFILING_FAILED));

    MsopprofManager::instance()->ExecuteMsopprof(params);
}

TEST_F(MSOPPROF_MANAGER_UTEST, ExecuteMsopprofWillExecuteOpprofFailWhenWaitProcessFail)
{
    std::vector<std::string> params{"-a"};

    MOCKER_CPP(&Analysis::Dvvp::App::EnvManager::GetGlobalEnv).stubs().will(returnValue(std::vector<std::string>()));
    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::ExecCmd).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::WaitProcess).stubs().will(returnValue(PROFILING_FAILED));
    MsopprofManager::instance()->ExecuteMsopprof(params);
}

TEST_F(MSOPPROF_MANAGER_UTEST, IsMsopprofExistWillReturnValueWhenCheckMsopprofFileIfExists)
{
    MsopprofManager::instance()->msopprofPath_ = "";
    EXPECT_FALSE(MsopprofManager::instance()->IsMsopprofExist());

    MsopprofManager::instance()->msopprofPath_ = "/ut/test/msopprof/bin/msopprof";
    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::IsFileExist)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));
    EXPECT_FALSE(MsopprofManager::instance()->IsMsopprofExist());
    EXPECT_TRUE(MsopprofManager::instance()->IsMsopprofExist());
}
