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
#include <cctype>
#include <string>
#include "utils_tool.h"

using namespace analysis::dvvp::common::utils;

static void ExpectTimestampFormat(const std::string& ret)
{
    ASSERT_EQ(26U, ret.size());
    EXPECT_EQ('-', ret[4]);
    EXPECT_EQ('-', ret[7]);
    EXPECT_EQ(' ', ret[10]);
    EXPECT_EQ(':', ret[13]);
    EXPECT_EQ(':', ret[16]);
    EXPECT_EQ('.', ret[19]);
    for (size_t i = 0; i < ret.size(); i++) {
        if (i == 4 || i == 7 || i == 10 || i == 13 || i == 16 || i == 19) {
            continue;
        }
        EXPECT_TRUE(isdigit(static_cast<unsigned char>(ret[i])) != 0) << "pos " << i << ": " << ret;
    }
}

TEST(COMMON_UTILS_TEST, TimestampToTimeKeepsMicrosecondFractionBeyondUint32)
{
    // 微秒级时间戳超出 uint32 范围（issue #231）：小数部分不得因先截断到 uint32 再取模而失真
    const std::string ret = Utils::TimestampToTime("1700000000123456", 1000000);
    EXPECT_NE(std::string::npos, ret.find(".123456")) << "fraction lost: " << ret;
    ExpectTimestampFormat(ret);
}

TEST(COMMON_UTILS_TEST, TimestampToTimePadsFractionWithTrailingZeros)
{
    const std::string ret = Utils::TimestampToTime("1700000000123000", 1000000);
    EXPECT_NE(std::string::npos, ret.find(".123000")) << ret;
    ExpectTimestampFormat(ret);
}

TEST(COMMON_UTILS_TEST, TimestampToTimeSupportsMillisecondUnit)
{
    const std::string ret = Utils::TimestampToTime("1700000000123", 1000);
    EXPECT_NE(std::string::npos, ret.find(".000123")) << ret;
    ExpectTimestampFormat(ret);
}

TEST(COMMON_UTILS_TEST, TimestampToTimeInvalidInputReturnsZero)
{
    EXPECT_EQ("0", Utils::TimestampToTime("", 1000000));
    EXPECT_EQ("0", Utils::TimestampToTime("12a3", 1000000));
    EXPECT_EQ("0", Utils::TimestampToTime("-123", 1000000));
    EXPECT_EQ("0", Utils::TimestampToTime("123", 0));
    EXPECT_EQ("0", Utils::TimestampToTime("123", -1));
    EXPECT_EQ("0", Utils::TimestampToTime("99999999999999999999", 1000000));
}
