/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"

#include "dyn_prof_client_tool.h"
#include "errno/error_code_tool.h"
#include "osal.h"
#include "socket/local_socket_tool.h"
#include "utils/utils_tool.h"

using namespace Collector::Dvvp::DynProf;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::socket;
using namespace analysis::dvvp::common::utils;

namespace {
class MSPROF_DYNAMIC_CLIENT_UTEST : public testing::Test {
protected:
    void TearDown() override
    {
        GlobalMockObject::verify();
        auto mgr = DynProfCliMgr::instance();
        mgr->enabled_ = false;
        mgr->isAppMode_ = false;
        mgr->keyPids_.clear();
        mgr->dynProfCli_ = nullptr;
    }
};

void MockSuccessResponse(DynProfMsgType msgType, DynProfMsgRsqCode statusCode)
{
    DynProfMsg rsqMsg = {msgType, statusCode};
    void* rsqData = &rsqMsg;
    MOCKER(LocalSocket::Recv, int(int, void*, int, int))
        .stubs()
        .with(any(), outBoundP(rsqData, sizeof(DynProfMsg)), any(), any())
        .will(returnValue(sizeof(DynProfMsg)));
}
} // namespace

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, SetParamsChecksLengthAndContent)
{
    auto dynProfClient = std::make_shared<DynProfClient>();

    dynProfClient->SetParams("");
    EXPECT_TRUE(dynProfClient->dynProfParams_.empty());

    dynProfClient->SetParams(std::string(DYN_PROF_PARAMS_MAX_LEN, 'x'));
    EXPECT_TRUE(dynProfClient->dynProfParams_.empty());

    dynProfClient->SetParams("valid_params");
    EXPECT_EQ("valid_params", dynProfClient->dynProfParams_);
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, StartHandlesStartedMissingParamsAndThreadCreateResult)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    dynProfClient->cliStarted_ = true;
    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->Start());

    dynProfClient->cliStarted_ = false;
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->Start());

    dynProfClient->SetParams("start");
    MOCKER_CPP(&DynProfClient::DynProfCliCreate)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS))
        .then(returnValue(PROFILING_SUCCESS))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->Start());

    MOCKER_CPP(&DynProfClient::DynProfCliSendParams)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS))
        .then(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->Start());

    MOCKER(OsalCreateTaskWithThreadAttr).stubs().will(returnValue(OSAL_EN_ERR)).then(returnValue(OSAL_EN_OK));
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->Start());
    EXPECT_FALSE(dynProfClient->cliStarted_);

    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->Start());
    EXPECT_TRUE(dynProfClient->cliStarted_);
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, StopReturnsSuccessWhenNotStartedAndJoinsWhenStarted)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->Stop());

    dynProfClient->cliStarted_ = true;
    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->Stop());
    EXPECT_FALSE(dynProfClient->cliStarted_);
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, InitProcFuncRegistersHandlers)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    dynProfClient->DynProfCliInitProcFunc();

    EXPECT_NE(nullptr, dynProfClient->procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_START]);
    EXPECT_NE(nullptr, dynProfClient->procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_STOP]);
    EXPECT_NE(nullptr, dynProfClient->procFuncMap_[DynProfCliCmd::DYN_PROF_CLI_CMD_QUIT]);
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, CreateFailsWhenNoPidOrSocketStepsFail)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->DynProfCliCreate());

    DynProfCliMgr::instance()->SetKeyPid({100});
    MOCKER(LocalSocket::Open).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->DynProfCliCreate());
    GlobalMockObject::verify();

    MOCKER(LocalSocket::Open).stubs().will(returnValue(10));
    MOCKER(LocalSocket::Connect).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->DynProfCliCreate());
    GlobalMockObject::verify();

    MOCKER(LocalSocket::Open).stubs().will(returnValue(11));
    MOCKER(LocalSocket::Connect).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(LocalSocket::SetRecvTimeOut).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->DynProfCliCreate());
    GlobalMockObject::verify();

    MOCKER(LocalSocket::Open).stubs().will(returnValue(12));
    MOCKER(LocalSocket::Connect).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(LocalSocket::SetRecvTimeOut).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(LocalSocket::SetSendTimeOut).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->DynProfCliCreate());
    GlobalMockObject::verify();

    MOCKER(LocalSocket::Open).stubs().will(returnValue(13));
    MOCKER(LocalSocket::Connect).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(LocalSocket::SetRecvTimeOut).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(LocalSocket::SetSendTimeOut).stubs().will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->DynProfCliCreate());
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
    EXPECT_EQ(100, dynProfClient->cliSockFdMap_[13]);
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, CreateAppModeRetriesUntilTimeout)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    DynProfCliMgr::instance()->SetKeyPid({101});
    DynProfCliMgr::instance()->SetAppMode();

    MOCKER(LocalSocket::Open).stubs().will(returnValue(10));
    MOCKER(LocalSocket::Connect).stubs().will(returnValue(PROFILING_FAILED));
    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    MOCKER_CPP(&Utils::UsleepInterupt).stubs().will(returnValue(0));

    EXPECT_EQ(PROFILING_FAILED, dynProfClient->DynProfCliCreate());
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, SendParamsHandlesEmptySocketsAndResponses)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    dynProfClient->SetParams("params");
    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->DynProfCliSendParams());

    dynProfClient->cliSockFds_.insert(20);
    dynProfClient->cliSockFdMap_[20] = 120;
    MOCKER(LocalSocket::Send, int(int, const void*, int, int)).stubs().will(returnValue(PROFILING_SUCCESS));
    MockSuccessResponse(DynProfMsgType::DYN_PROF_PARAMS_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->DynProfCliSendParams());
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, SendCmdChecksSendRecvAndResponseType)
{
    auto dynProfClient = std::make_shared<DynProfClient>();

    MOCKER(LocalSocket::Send, int(int, const void*, int, int)).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL, dynProfClient->DynProfCliSendCmd(30, DynProfMsgType::DYN_PROF_START_REQ));
    GlobalMockObject::verify();

    MOCKER(LocalSocket::Send, int(int, const void*, int, int)).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(LocalSocket::Recv, int(int, void*, int, int)).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL, dynProfClient->DynProfCliSendCmd(30, DynProfMsgType::DYN_PROF_START_REQ));
    GlobalMockObject::verify();

    MOCKER(LocalSocket::Send, int(int, const void*, int, int)).stubs().will(returnValue(PROFILING_SUCCESS));
    MockSuccessResponse(DynProfMsgType::DYN_PROF_STOP_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL, dynProfClient->DynProfCliSendCmd(30, DynProfMsgType::DYN_PROF_START_REQ));
    GlobalMockObject::verify();

    MOCKER(LocalSocket::Send, int(int, const void*, int, int)).stubs().will(returnValue(PROFILING_SUCCESS));
    MockSuccessResponse(DynProfMsgType::DYN_PROF_START_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS,
        dynProfClient->DynProfCliSendCmd(30, DynProfMsgType::DYN_PROF_START_REQ));
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, ProcStartStopQuitHandleResponseCodes)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    dynProfClient->cliSockFds_.insert(40);
    dynProfClient->cliSockFdMap_[40] = 140;

    MOCKER_CPP(&DynProfClient::DynProfCliSendCmd)
        .stubs()
        .will(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS))
        .then(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_ALREADY_START))
        .then(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_NOT_SET_DEVICE))
        .then(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL));
    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    dynProfClient->DynProfCliProcStart(40);
    dynProfClient->DynProfCliProcStart(40);
    dynProfClient->DynProfCliProcStart(40);
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
    dynProfClient->DynProfCliProcStart(40);
    EXPECT_TRUE(dynProfClient->cliSockFds_.empty());
    GlobalMockObject::verify();

    dynProfClient->cliSockFds_.insert(41);
    dynProfClient->cliSockFdMap_[41] = 141;
    MOCKER_CPP(&DynProfClient::DynProfCliSendCmd)
        .stubs()
        .will(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS))
        .then(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_NOT_START))
        .then(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL));
    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    dynProfClient->DynProfCliProcStop(41);
    dynProfClient->DynProfCliProcStop(41);
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
    dynProfClient->DynProfCliProcStop(41);
    EXPECT_TRUE(dynProfClient->cliSockFds_.empty());
    GlobalMockObject::verify();

    dynProfClient->cliSockFds_.insert(42);
    dynProfClient->cliSockFdMap_[42] = 142;
    MOCKER_CPP(&DynProfClient::DynProfCliSendCmd)
        .stubs()
        .will(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS))
        .then(returnValue(DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL));
    dynProfClient->DynProfCliProcQuit(42);
    dynProfClient->DynProfCliProcQuit(42);
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, ManagerStoresPidEnvAndState)
{
    auto mgr = DynProfCliMgr::instance();

    EXPECT_FALSE(mgr->IsDynProfCliEnable());
    EXPECT_EQ("", mgr->GetDynProfEnv());
    EXPECT_EQ("", mgr->GetKeyPidEnv());

    mgr->SetKeyPid({200, 201});
    EXPECT_EQ(std::set<int32_t>({200, 201}), mgr->GetKeyPid());

    mgr->EnableDynProfCli();
    EXPECT_TRUE(mgr->IsDynProfCliEnable());
    EXPECT_EQ("PROFILING_MODE=dynamic", mgr->GetDynProfEnv());

    mgr->SetAppMode();
    EXPECT_TRUE(mgr->IsAppMode());
    EXPECT_EQ("DYNAMIC_PROFILING_KEY_PID=200,201", mgr->GetKeyPidEnv());

    EXPECT_FALSE(mgr->IsCliStarted());
    mgr->dynProfCli_ = std::make_shared<DynProfClient>();
    mgr->dynProfCli_->cliStarted_ = true;
    EXPECT_TRUE(mgr->IsCliStarted());
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, ManagerStartStopAndWaitDelegateToClient)
{
    auto mgr = DynProfCliMgr::instance();

    EXPECT_EQ(PROFILING_FAILED, mgr->StartDynProfCli(""));

    MOCKER_CPP(&DynProfClient::DynProfCliCreate).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&DynProfClient::DynProfCliSendParams).stubs().will(returnValue(PROFILING_SUCCESS));
    MOCKER(OsalCreateTaskWithThreadAttr).stubs().will(returnValue(OSAL_EN_OK));
    EXPECT_EQ(PROFILING_SUCCESS, mgr->StartDynProfCli("params"));
    EXPECT_TRUE(mgr->IsCliStarted());
    GlobalMockObject::verify();

    mgr->StopDynProfCli();
    EXPECT_FALSE(mgr->IsCliStarted());

    mgr->dynProfCli_ = std::make_shared<DynProfClient>();
    mgr->WaitQuit();
}
