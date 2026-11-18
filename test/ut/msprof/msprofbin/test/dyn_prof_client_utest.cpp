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

#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <thread>

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

    // 批量收执用 poll 等待，这里用 socketpair 保证 poll 立即就绪，避免用例长时间阻塞
    int32_t pair[2] = {-1, -1};
    ASSERT_EQ(0, socketpair(AF_UNIX, SOCK_STREAM, 0, pair));
    (void)LocalSocket::SetRecvTimeOut(pair[0], 1, 0);
    dynProfClient->cliSockFds_.insert(pair[0]);
    dynProfClient->cliSockFdMap_[pair[0]] = 120;
    const uint8_t dummy = 'x';
    ASSERT_EQ(static_cast<ssize_t>(1), write(pair[1], &dummy, sizeof(dummy)));

    MOCKER(LocalSocket::Send, int(int, const void*, int, int)).stubs().will(returnValue(PROFILING_SUCCESS));
    MockSuccessResponse(DynProfMsgType::DYN_PROF_PARAMS_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    EXPECT_EQ(PROFILING_SUCCESS, dynProfClient->DynProfCliSendParams());
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());

    dynProfClient->cliSockFds_.clear();
    dynProfClient->cliSockFdMap_.clear();
    close(pair[0]);
    close(pair[1]);
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, SendReqAndRecvRsqCheckFailureAndResponseType)
{
    auto dynProfClient = std::make_shared<DynProfClient>();

    // 发送失败
    MOCKER(LocalSocket::Send, int(int, const void*, int, int)).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(PROFILING_FAILED, dynProfClient->DynProfCliSendReq(30, DynProfMsgType::DYN_PROF_START_REQ));
    GlobalMockObject::verify();

    // 对端断开，Recv 返回 0
    MOCKER(LocalSocket::Recv, int(int, void*, int, int)).stubs().will(returnValue(0));
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL, dynProfClient->DynProfCliRecvRsq(30, DynProfMsgType::DYN_PROF_START_REQ));
    GlobalMockObject::verify();

    // 接收出错
    MOCKER(LocalSocket::Recv, int(int, void*, int, int)).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL, dynProfClient->DynProfCliRecvRsq(30, DynProfMsgType::DYN_PROF_START_REQ));
    GlobalMockObject::verify();

    // 回执类型与请求不匹配
    MockSuccessResponse(DynProfMsgType::DYN_PROF_STOP_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL, dynProfClient->DynProfCliRecvRsq(30, DynProfMsgType::DYN_PROF_START_REQ));
    GlobalMockObject::verify();

    // 正常回执
    MockSuccessResponse(DynProfMsgType::DYN_PROF_START_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    EXPECT_EQ(
        DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS,
        dynProfClient->DynProfCliRecvRsq(30, DynProfMsgType::DYN_PROF_START_REQ));
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, RecvFullWaitsForSplitReply)
{
    // 回执被拆成两次写：poll 只保证"有数据"，单次 Recv 会只收到 4 字节并误判失败。
    // 本用例锁定 RecvFull 的循环收满语义。
    int32_t pair[2] = {-1, -1};
    ASSERT_EQ(0, socketpair(AF_UNIX, SOCK_STREAM, 0, pair));
    (void)LocalSocket::SetRecvTimeOut(pair[0], 2, 0);

    DynProfMsg rsq = {DynProfMsgType::DYN_PROF_START_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS};
    const uint8_t* raw = reinterpret_cast<const uint8_t*>(&rsq);
    ASSERT_EQ(static_cast<ssize_t>(4), write(pair[1], raw, 4));

    std::thread writer([&pair, raw]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        (void)write(pair[1], raw + 4, 4);
    });

    DynProfMsg got = {};
    auto dynProfClient = std::make_shared<DynProfClient>();
    EXPECT_EQ(static_cast<int32_t>(sizeof(got)), dynProfClient->RecvFull(pair[0], &got, sizeof(got)));
    EXPECT_EQ(DynProfMsgType::DYN_PROF_START_RSQ, got.msgType);
    EXPECT_EQ(DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS, got.statusCode);

    writer.join();
    close(pair[0]);
    close(pair[1]);
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, DispatchDropsClosedPeerWithoutBurningBudget)
{
    // 对端已关闭时：poll 应以 POLLIN|POLLHUP 立即就绪，回执被判失败，连接从两个容器摘除，
    // 整个过程不能拖到 60 秒总预算耗尽。
    int32_t pair[2] = {-1, -1};
    ASSERT_EQ(0, socketpair(AF_UNIX, SOCK_STREAM, 0, pair));
    (void)LocalSocket::SetRecvTimeOut(pair[0], 1, 0);
    ASSERT_EQ(0, close(pair[1]));

    auto dynProfClient = std::make_shared<DynProfClient>();
    dynProfClient->DynProfCliInitProcFunc();
    dynProfClient->cliSockFds_.insert(pair[0]);
    dynProfClient->cliSockFdMap_[pair[0]] = 401;

    const auto begin = std::chrono::steady_clock::now();
    dynProfClient->DynProfCliDispatch(DynProfCliCmd::DYN_PROF_CLI_CMD_START);
    const auto elapsedMs =
        std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - begin).count();

    EXPECT_TRUE(dynProfClient->cliSockFds_.empty());
    EXPECT_TRUE(dynProfClient->cliSockFdMap_.empty());
    EXPECT_LT(elapsedMs, 5000);
    // pair[0] 已被 DynProfCliStopSocket 关闭，此处不再重复 close，避免误关复用的 fd 号
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, ProcStartStopQuitHandleResponseCodes)
{
    auto dynProfClient = std::make_shared<DynProfClient>();
    dynProfClient->cliSockFds_.insert(40);
    dynProfClient->cliSockFdMap_[40] = 140;

    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    dynProfClient->DynProfCliProcStart(40, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    dynProfClient->DynProfCliProcStart(40, DynProfMsgRsqCode::DYN_PROF_RSQ_ALREADY_START);
    dynProfClient->DynProfCliProcStart(40, DynProfMsgRsqCode::DYN_PROF_RSQ_NOT_SET_DEVICE);
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
    dynProfClient->DynProfCliProcStart(40, DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL);
    EXPECT_TRUE(dynProfClient->cliSockFds_.empty());
    EXPECT_TRUE(dynProfClient->cliSockFdMap_.empty());
    GlobalMockObject::verify();

    dynProfClient->cliSockFds_.insert(41);
    dynProfClient->cliSockFdMap_[41] = 141;
    MOCKER(LocalSocket::Close).stubs().will(ignoreReturnValue());
    dynProfClient->DynProfCliProcStop(41, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    dynProfClient->DynProfCliProcStop(41, DynProfMsgRsqCode::DYN_PROF_RSQ_NOT_START);
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
    dynProfClient->DynProfCliProcStop(41, DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL);
    EXPECT_TRUE(dynProfClient->cliSockFds_.empty());
    GlobalMockObject::verify();

    dynProfClient->cliSockFds_.insert(42);
    dynProfClient->cliSockFdMap_[42] = 142;
    dynProfClient->DynProfCliProcQuit(42, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS);
    dynProfClient->DynProfCliProcQuit(42, DynProfMsgRsqCode::DYN_PROF_RSQ_FAIL);
    EXPECT_EQ(1U, dynProfClient->cliSockFds_.size());
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, StopSocketErasesFdBeforeClosing)
{
    // 故意不 mock LocalSocket::Close：Close 的入参是引用并把 fd 改写成 -1，
    // 本用例用于锁定“先按原 fd 摘除、再关闭”的顺序，回归失效 fd 残留问题。
    auto dynProfClient = std::make_shared<DynProfClient>();
    const int32_t fd = LocalSocket::Open();
    ASSERT_GE(fd, 0);
    dynProfClient->cliSockFds_.insert(fd);
    dynProfClient->cliSockFdMap_[fd] = 202;

    dynProfClient->DynProfCliStopSocket(fd);
    EXPECT_TRUE(dynProfClient->cliSockFds_.empty());
    EXPECT_TRUE(dynProfClient->cliSockFdMap_.empty());
}

TEST_F(MSPROF_DYNAMIC_CLIENT_UTEST, DispatchSendsToAllPidsThenCollectsRsq)
{
    int32_t pair1[2] = {-1, -1};
    int32_t pair2[2] = {-1, -1};
    ASSERT_EQ(0, socketpair(AF_UNIX, SOCK_STREAM, 0, pair1));
    ASSERT_EQ(0, socketpair(AF_UNIX, SOCK_STREAM, 0, pair2));

    // 两个“服务端”各自预先写好回执，客户端侧已可读，poll 会立即返回
    DynProfMsg rsq = {DynProfMsgType::DYN_PROF_START_RSQ, DynProfMsgRsqCode::DYN_PROF_RSQ_SUCCESS};
    ASSERT_EQ(static_cast<ssize_t>(sizeof(rsq)), write(pair1[1], &rsq, sizeof(rsq)));
    ASSERT_EQ(static_cast<ssize_t>(sizeof(rsq)), write(pair2[1], &rsq, sizeof(rsq)));

    auto dynProfClient = std::make_shared<DynProfClient>();
    dynProfClient->DynProfCliInitProcFunc();
    (void)LocalSocket::SetRecvTimeOut(pair1[0], 1, 0);
    (void)LocalSocket::SetRecvTimeOut(pair2[0], 1, 0);
    dynProfClient->cliSockFds_.insert(pair1[0]);
    dynProfClient->cliSockFds_.insert(pair2[0]);
    dynProfClient->cliSockFdMap_[pair1[0]] = 301;
    dynProfClient->cliSockFdMap_[pair2[0]] = 302;

    dynProfClient->DynProfCliDispatch(DynProfCliCmd::DYN_PROF_CLI_CMD_START);

    // 两个 pid 的 start 均成功，连接应全部保留
    EXPECT_EQ(2U, dynProfClient->cliSockFds_.size());
    // 请求已先于回执处理被写出，服务端侧可以读到 START_REQ
    DynProfMsg req = {};
    ASSERT_EQ(static_cast<ssize_t>(sizeof(req)), read(pair1[1], &req, sizeof(req)));
    EXPECT_EQ(DynProfMsgType::DYN_PROF_START_REQ, req.msgType);

    dynProfClient->cliSockFds_.clear();
    dynProfClient->cliSockFdMap_.clear();
    close(pair1[0]);
    close(pair2[0]);
    close(pair1[1]);
    close(pair2[1]);
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
