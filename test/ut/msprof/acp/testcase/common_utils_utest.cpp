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
#include <cstdio>
#include <string>
#include <vector>
#include "gtest/gtest.h"
#include "utils/utils_tool.h"

using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::error;

namespace {
constexpr char TEST_DIR[] = "./acp_utils_test_dir";
constexpr char SUB_DIR[] = "./acp_utils_test_dir/sub";
constexpr char TEST_FILE[] = "./acp_utils_test_dir/a.txt";
constexpr char SUB_FILE[] = "./acp_utils_test_dir/sub/b.txt";
} // namespace

class CommonUtilsUtest : public testing::Test {
protected:
    void SetUp() override
    {
        Utils::CreateDir(SUB_DIR);
        FILE* fp = fopen(TEST_FILE, "w");
        if (fp != nullptr) {
            fprintf(fp, "hello");
            fclose(fp);
        }
        fp = fopen(SUB_FILE, "w");
        if (fp != nullptr) {
            fprintf(fp, "world");
            fclose(fp);
        }
    }
    void TearDown() override { Utils::RemoveDir(TEST_DIR); }
};

TEST_F(CommonUtilsUtest, GetVolumeSizeAllTypes)
{
    unsigned long long size = 0;
    for (auto type : {VolumeSize::AVAIL_SIZE, VolumeSize::FREE_SIZE, VolumeSize::TOTAL_SIZE}) {
        EXPECT_EQ(PROFILING_SUCCESS, Utils::GetVolumeSize(".", size, type));
        EXPECT_GT(size, 0U);
    }
    EXPECT_EQ(PROFILING_FAILED, Utils::GetVolumeSize("./not_exist_dir_xxx", size, VolumeSize::AVAIL_SIZE));
}

TEST_F(CommonUtilsUtest, GetFilesRecursiveAndPlain)
{
    std::vector<std::string> files;
    Utils::GetFiles(TEST_DIR, true, files, 0);
    EXPECT_EQ(2U, files.size());
    std::vector<std::string> plainFiles;
    Utils::GetFiles(TEST_DIR, false, plainFiles, 0);
    EXPECT_EQ(1U, plainFiles.size());

    std::vector<std::string> children;
    Utils::GetChildFilenames(SUB_DIR, children);
    EXPECT_EQ(1U, children.size());
}

TEST_F(CommonUtilsUtest, SplitWithFilterOut)
{
    auto res = Utils::Split("a,,b", true, "", ",");
    EXPECT_EQ(2U, res.size());
    auto keep = Utils::Split("a,,b", false, "", ",");
    EXPECT_EQ(3U, keep.size());
    EXPECT_TRUE(Utils::Split("", false, "", ",").empty());
}

TEST_F(CommonUtilsUtest, PathAndFileHelpers)
{
    EXPECT_TRUE(Utils::IsDir(TEST_DIR));
    EXPECT_FALSE(Utils::IsDir(TEST_FILE));
    EXPECT_TRUE(Utils::IsFileExist(TEST_FILE));
    EXPECT_FALSE(Utils::IsFileExist("./not_exist_xxx"));
    EXPECT_TRUE(Utils::IsDirAccessible(TEST_DIR));
    EXPECT_EQ(5, static_cast<int>(Utils::GetFileSize(TEST_FILE)));
    EXPECT_EQ(-1, Utils::GetFileSize("./not_exist_xxx"));

    EXPECT_EQ(SUB_DIR, Utils::DirName(SUB_FILE));
    EXPECT_EQ("b.txt", Utils::BaseName(SUB_FILE));
    std::string dir;
    std::string base;
    EXPECT_EQ(PROFILING_SUCCESS, Utils::SplitPath(SUB_FILE, dir, base));
    EXPECT_EQ(SUB_DIR, dir);
    EXPECT_EQ("b.txt", base);
    EXPECT_EQ("./a/b", Utils::JoinPath({".", "a", "b"}));
    EXPECT_TRUE(Utils::IsAllDigit("123"));
    EXPECT_FALSE(Utils::IsAllDigit("12a"));
}
