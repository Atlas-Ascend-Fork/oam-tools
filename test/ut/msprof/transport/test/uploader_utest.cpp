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
#include "uploader_tool.h"
#include "uploader_mgr_tool.h"
#include "pipe_transport_tool.h"
#include "errno/error_code_tool.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::Common::Statistics;
using namespace Analysis::Dvvp::MsprofErrMgr;

class UPLOADER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        _transport = std::shared_ptr<analysis::dvvp::transport::MsptiPipeTransport>(
            new analysis::dvvp::transport::MsptiPipeTransport());
    }
    virtual void TearDown()
    {
        GlobalMockObject::reset();
        _transport.reset();
    }

public:
    std::shared_ptr<analysis::dvvp::transport::MsptiPipeTransport> _transport;
};

TEST_F(UPLOADER_TEST, Uploader_destructor)
{
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::transport::Uploader> uploader(new analysis::dvvp::transport::Uploader(_transport));
    uploader->isInited_ = false;
    EXPECT_EQ(PROFILING_SUCCESS, uploader->Uinit());
    uploader.reset();
}

TEST_F(UPLOADER_TEST, Init)
{
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::transport::Uploader> uploader(new analysis::dvvp::transport::Uploader(_transport));

    EXPECT_EQ(PROFILING_SUCCESS, uploader->Init());
    EXPECT_TRUE(uploader->isInited_);
}

TEST_F(UPLOADER_TEST, Uinit)
{
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::transport::Uploader> uploader(new analysis::dvvp::transport::Uploader(_transport));

    EXPECT_EQ(PROFILING_SUCCESS, uploader->Uinit());
    EXPECT_FALSE(uploader->isInited_);
}

TEST_F(UPLOADER_TEST, UploadData)
{
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::transport::Uploader> uploader(new analysis::dvvp::transport::Uploader(_transport));

    std::string buffer("123456");

    EXPECT_EQ(PROFILING_FAILED, uploader->UploadData(buffer.c_str(), buffer.size()));

    EXPECT_EQ(PROFILING_SUCCESS, uploader->Init());
    EXPECT_EQ(PROFILING_SUCCESS, uploader->UploadData(buffer.c_str(), buffer.size()));
}

TEST_F(UPLOADER_TEST, run_uploader_not_init)
{
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::transport::Uploader> uploader(new analysis::dvvp::transport::Uploader(_transport));
    EXPECT_NE(nullptr, uploader);
    auto errorContext = MsprofErrorManager::instance()->GetErrorManagerContext();
    uploader->Run(errorContext);
}

TEST_F(UPLOADER_TEST, run_no_data)
{
    GlobalMockObject::verify();
    using namespace analysis::dvvp::transport;

    std::shared_ptr<Uploader> uploader(new Uploader(_transport));

    MOCKER_CPP_VIRTUAL(*_transport.get(), &MsptiPipeTransport::SendBuffer, int(MsptiPipeTransport::*)(const void*, int))
        .stubs()
        .will(returnValue(PROFILING_FAILED));

    EXPECT_EQ(PROFILING_SUCCESS, uploader->Init());

    uploader->forceQuit_ = true;
    uploader->queue_->Quit();
    auto errorContext = MsprofErrorManager::instance()->GetErrorManagerContext();
    uploader->Run(errorContext);
    uploader.reset();
    GlobalMockObject::reset();
}

TEST_F(UPLOADER_TEST, run_with_data)
{
    GlobalMockObject::verify();
    using namespace analysis::dvvp::transport;

    std::shared_ptr<Uploader> uploader(new Uploader(_transport));
    MOCKER_CPP_VIRTUAL(*_transport.get(), &MsptiPipeTransport::SendBuffer, int(MsptiPipeTransport::*)(const void*, int))
        .stubs()
        .will(returnValue(PROFILING_FAILED));

    std::string buffer("123456");
    EXPECT_EQ(PROFILING_SUCCESS, uploader->Init());
    EXPECT_EQ(PROFILING_SUCCESS, uploader->UploadData(buffer.c_str(), buffer.size()));
    uploader->forceQuit_ = true;
    uploader->queue_->Quit();
    auto errorContext = MsprofErrorManager::instance()->GetErrorManagerContext();
    uploader->Run(errorContext);
    uploader.reset();
    GlobalMockObject::reset();
}

TEST_F(UPLOADER_TEST, Flush)
{
    GlobalMockObject::verify();

    std::shared_ptr<analysis::dvvp::transport::Uploader> uploader(new analysis::dvvp::transport::Uploader(_transport));

    MOCKER_CPP(&analysis::dvvp::transport::UploaderQueue::Size)
        .stubs()
        .will(returnValue((unsigned long)1))
        .then(returnValue((unsigned long)0));
    EXPECT_EQ(uploader->Init(), PROFILING_SUCCESS);
    uploader->Flush();
    uploader->Flush();
}

TEST_F(UPLOADER_TEST, UploaderMgrJobMap)
{
    using namespace analysis::dvvp::transport;
    auto& manager = *UploaderMgr::instance();
    manager.Uninit();

    manager.AddMapByDevIdMode(1, "", "job-default");
    manager.AddMapByDevIdMode(2, "training", "job-training");
    EXPECT_EQ("job-default", manager.GetJobId(1, ""));
    EXPECT_EQ("job-training", manager.GetJobId(2, "training"));
    EXPECT_TRUE(manager.GetJobId(3, "training").empty());
    manager.Uninit();
}

TEST_F(UPLOADER_TEST, UploaderMgrUploaderMap)
{
    using namespace analysis::dvvp::transport;
    auto& manager = *UploaderMgr::instance();
    manager.Uninit();

    auto uploader = std::make_shared<Uploader>(_transport);
    manager.AddUploader("host", uploader);
    manager.AddUploader("", nullptr);

    std::shared_ptr<Uploader> found;
    manager.GetUploader("host", found);
    EXPECT_EQ(uploader, found);
    manager.GetUploader("missing", found);
    EXPECT_EQ(uploader, found);

    manager.DelUploader("host");
    manager.SetAllUploaderTransportStopped();
    EXPECT_EQ(PROFILING_SUCCESS, manager.SetAllUploaderRegisterPipeTransportCallback(nullptr));
    EXPECT_EQ(PROFILING_SUCCESS, manager.SetAllUploaderUnRegisterPipeTransportCallback());
    manager.RegisterAllUploaderTransportGenHashIdFuncPtr(nullptr);
    manager.DelAllUploader();
    manager.Uninit();
}

TEST_F(UPLOADER_TEST, UploaderMgrUploadDataStartPolicy)
{
    using namespace analysis::dvvp::transport;
    auto& manager = *UploaderMgr::instance();
    manager.SetUploadDataIfStart(false);

    auto chunk = std::make_shared<analysis::dvvp::ProfileFileChunk>();
    chunk->fileName = std::to_string(analysis::dvvp::common::utils::DEFAULT_HOST_ID) + ".cfg";
    EXPECT_EQ(PROFILING_FAILED, manager.UploadData("host", chunk));
    chunk->fileName = "data/aicpu.data";
    EXPECT_EQ(PROFILING_FAILED, manager.UploadData("host", chunk));
    chunk->fileName = "data/ts_track.0";
    EXPECT_EQ(PROFILING_FAILED, manager.UploadData("host", chunk));
    chunk->fileName = "data/device.data";
    EXPECT_EQ(PROFILING_IN_WARMUP, manager.UploadData("host", chunk));

    manager.SetUploadDataIfStart(true);
    manager.Uninit();
}

TEST_F(UPLOADER_TEST, UploaderMgrUploadCtrlFileData)
{
    using namespace analysis::dvvp::transport;
    using analysis::dvvp::common::config::PROFILING_IS_CTRL_DATA;
    auto& manager = *UploaderMgr::instance();
    manager.Uninit();

    auto jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();
    jobCtx->job_id = "job-control";
    jobCtx->dev_id = DEFAULT_HOST_ID;
    const FileDataParams params("host.cfg", true, PROFILING_IS_CTRL_DATA);
    const FileDataParams deviceParams("data/device.cfg", true, PROFILING_IS_CTRL_DATA);

    EXPECT_EQ(PROFILING_FAILED, manager.UploadCtrlFileData("host", "", params, jobCtx));
    EXPECT_EQ(PROFILING_FAILED, manager.UploadCtrlFileData("host", "cfg", params, nullptr));
    EXPECT_EQ(PROFILING_FAILED, manager.UploadCtrlFileData("host", "cfg", params, jobCtx));

    manager.SetUploadDataIfStart(false);
    EXPECT_EQ(PROFILING_IN_WARMUP, manager.UploadCtrlFileData("host", "cfg", deviceParams, jobCtx));
    manager.SetUploadDataIfStart(true);
    manager.Uninit();
}
