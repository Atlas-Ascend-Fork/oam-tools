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
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include "gtest/gtest.h"
#include "task_relationship_mgr_tool.h"

using Analysis::Dvvp::TaskHandle::TaskRelationshipMgr;

TEST(TASK_RELATIONSHIP_MGR_TEST, HostDeviceRelationship)
{
    auto mgr = TaskRelationshipMgr::instance();

    EXPECT_EQ(17, mgr->GetDevIdByHostId(17));
    EXPECT_EQ(3, mgr->GetHostIdByDevId(3));

    mgr->AddHostIdDevIdRelationship(100, 0);
    mgr->AddHostIdDevIdRelationship(101, 1);

    EXPECT_EQ(0, mgr->GetDevIdByHostId(100));
    EXPECT_EQ(1, mgr->GetDevIdByHostId(101));
    EXPECT_EQ(100, mgr->GetHostIdByDevId(0));
    EXPECT_EQ(101, mgr->GetHostIdByDevId(1));
}

TEST(TASK_RELATIONSHIP_MGR_TEST, LocalFlushJobUsesIndexId)
{
    auto mgr = TaskRelationshipMgr::instance();
    mgr->AddHostIdDevIdRelationship(200, 2);

    EXPECT_EQ(200, mgr->GetFlushSuffixDevId("remote_job", 2));

    mgr->AddLocalFlushJobId("local_job");
    EXPECT_EQ(2, mgr->GetFlushSuffixDevId("local_job", 2));
}
