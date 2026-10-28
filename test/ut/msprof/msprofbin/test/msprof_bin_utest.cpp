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
#include <iostream>
#include <fstream>

#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "errno/error_code_tool.h"
#include "running_mode_tool.h"
#include "msprof_manager_tool.h"
#include "config_manager_tool.h"
#include "platform/platform_tool.h"

#include "../../../../../src/msprof/collector/dvvp/msprofbin/src/msprof_bin_tool.cpp"

using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Msprof;
using namespace Analysis::Dvvp::Common::Platform;

namespace {
constexpr size_t ARGS_CAPACITY = 10;
constexpr size_t BASIC_ENV_INDEX = 0;
constexpr size_t SECOND_ENV_INDEX = 1;
constexpr size_t END_ENV_INDEX = 2;
constexpr size_t APP_ARG_INDEX = 2;
constexpr size_t TASK_TIME_ARG_INDEX = 3;
constexpr size_t SYS_DEVICES_ARG_INDEX = 4;
constexpr size_t OUTPUT_ARG_INDEX = 5;
constexpr size_t SYS_PERIOD_ARG_INDEX = 6;
constexpr size_t SYS_PID_ARG_INDEX = 7;
constexpr int INVALID_ARGC = 2;
constexpr int APP_ARGC = 4;
constexpr int SYS_ARGC = 8;
constexpr size_t MAX_ENVP_LEN = 4096;
constexpr size_t ENVP_CAPACITY = MAX_ENVP_LEN + 1;

class MSPROF_BIN_UTEST : public testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override {}
};

TEST_F(MSPROF_BIN_UTEST, LltMain)
{
    GlobalMockObject::verify();
    const char* argv[ARGS_CAPACITY];
    argv[BASIC_ENV_INDEX] = "--help";
    argv[SECOND_ENV_INDEX] = "--test";
    const char* envp[] = {"test=a", "a=b", nullptr};

    EXPECT_EQ(PROFILING_FAILED, LltMain(1, argv, envp));
    EXPECT_EQ(PROFILING_FAILED, LltMain(INVALID_ARGC, argv, envp));

    std::ofstream test_file("prof_bin_test");
    test_file << "echo test" << std::endl;
    test_file.close();
    argv[APP_ARG_INDEX] = "--app=./prof_bin_test";
    argv[TASK_TIME_ARG_INDEX] = "--task-time=on";
    EXPECT_EQ(PROFILING_FAILED, LltMain(APP_ARGC, argv, envp));
    std::remove("prof_bin_test");
    argv[SYS_DEVICES_ARG_INDEX] = "--sys-devices=0";
    argv[OUTPUT_ARG_INDEX] = "--output=./msprof_bin_utest";
    argv[SYS_PERIOD_ARG_INDEX] = "--sys-period=1";
    argv[SYS_PID_ARG_INDEX] = "--sys-pid-profiling=on";
    EXPECT_EQ(PROFILING_FAILED, LltMain(SYS_ARGC, argv, envp));
}

TEST_F(MSPROF_BIN_UTEST, SetEnvList)
{
    GlobalMockObject::verify();
    const char* envp[ENVP_CAPACITY];
    const char str[] = "a=a";
    for (size_t i = 0; i < ENVP_CAPACITY; i++) {
        envp[i] = str;
    }
    envp[MAX_ENVP_LEN] = nullptr;
    std::vector<std::string> envpList;
    SetEnvList(*envp, envpList);
    EXPECT_EQ(envpList.size(), MAX_ENVP_LEN);
    if (envpList.size() == MAX_ENVP_LEN) {
        EXPECT_EQ(envpList[0], "a=a");
    }
}

} // namespace
