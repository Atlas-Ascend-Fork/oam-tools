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
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "gtest/gtest.h"
#include "json_tool.h"

namespace {
constexpr int32_t JSON_INT_VALUE = 7;
constexpr double JSON_DOUBLE_VALUE = 1.5;
constexpr size_t JSON_ARRAY_SIZE = 2;

std::string MakeMixedJson()
{
    return "{\"name\":\"msprof\",\"id\":7,\"score\":1.5,\"active\":true,"
           "\"missing\":null,\"tags\":[1,2],\"child\":{\"key\":\"value\"}}";
}
} // namespace

class NANO_JSON_UTEST : public testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override {}
};

TEST_F(NANO_JSON_UTEST, ParseObjectAndReadTypedValues)
{
    NanoJson::Json json(MakeMixedJson());
    EXPECT_TRUE(json.Contains("name"));
    EXPECT_EQ("msprof", json["name"].GetValue<std::string>());
    EXPECT_EQ(JSON_INT_VALUE, json["id"].GetValue<int64_t>());
    EXPECT_DOUBLE_EQ(JSON_DOUBLE_VALUE, json["score"].GetValue<double>());
    EXPECT_TRUE(json["active"].GetValue<bool>());
    EXPECT_EQ(nullptr, json["missing"].GetValue<void*>());
    EXPECT_EQ(JSON_ARRAY_SIZE, json["tags"].GetValue<NanoJson::JsonArray>().size());
    EXPECT_EQ(1, json["tags"][0].GetValue<int64_t>());
    EXPECT_EQ(1U, json["child"].GetValue<NanoJson::JsonObj>().size());
    EXPECT_TRUE(json.Begin() != json.End());
    EXPECT_FALSE(json.GetJsonValue().Contains("not-exist"));
}

TEST_F(NANO_JSON_UTEST, RemoveKeyAndSerializeValues)
{
    NanoJson::Json json(MakeMixedJson());
    json.RemoveByKey("child");
    EXPECT_FALSE(json.Contains("child"));
    EXPECT_FALSE(json.ToString().empty());

    json["text"] = "value";
    json["number"] = static_cast<int32_t>(JSON_INT_VALUE);
    json["count"] = static_cast<uint32_t>(JSON_ARRAY_SIZE);
    json["ratio"] = JSON_DOUBLE_VALUE;
    json["valid"] = true;
    EXPECT_EQ("value", json["text"].GetValue<std::string>());
    EXPECT_EQ(JSON_INT_VALUE, json["number"].GetValue<int32_t>());
    EXPECT_EQ(JSON_ARRAY_SIZE, json["count"].GetValue<uint32_t>());
    EXPECT_DOUBLE_EQ(JSON_DOUBLE_VALUE, json["ratio"].GetValue<double>());
    EXPECT_TRUE(json["valid"].GetValue<bool>());
}

TEST_F(NANO_JSON_UTEST, BuildArrayAndObjectValues)
{
    std::vector<int32_t> nums = {1, 2};
    NanoJson::JsonValue array;
    array = nums;
    EXPECT_EQ(JSON_ARRAY_SIZE, array.GetValue<NanoJson::JsonArray>().size());
    array.PushBack(array[0]);
    EXPECT_EQ(JSON_ARRAY_SIZE + 1, array.GetValue<NanoJson::JsonArray>().size());

    std::unordered_map<std::string, int32_t> values = {{"x", 1}};
    NanoJson::JsonValue object;
    object = values;
    EXPECT_EQ(1U, object.GetValue<NanoJson::JsonObj>().size());
    EXPECT_TRUE(object.Contains("x"));

    NanoJson::Json json;
    json = object;
    EXPECT_TRUE(json.Contains("x"));
}

TEST_F(NANO_JSON_UTEST, JsonValueAccessors)
{
    NanoJson::JsonValue object(NanoJson::JsonValueType::OBJECT);
    object["name"] = "msprof";
    EXPECT_EQ("msprof", object["name"].GetValue<std::string>());

    NanoJson::JsonValue array;
    array.SetArraySize(1);
    array[0] = JSON_INT_VALUE;
    EXPECT_EQ(JSON_INT_VALUE, array[0].GetValue<int32_t>());

    const std::string jsonText = object();
    EXPECT_NE(std::string::npos, jsonText.find("msprof"));
    EXPECT_TRUE(jsonText.find('{') != std::string::npos);
}

TEST_F(NANO_JSON_UTEST, InvalidJsonThrowsRuntimeError)
{
    EXPECT_THROW(NanoJson::Json json("{\"key\":bad}"), std::runtime_error);
    EXPECT_THROW(NanoJson::Json json("[1,2]"), std::runtime_error);
    EXPECT_THROW(NanoJson::JsonValue value(NanoJson::JsonValueType::INVALID);
                 NanoJson::Json json(value), std::runtime_error);
}
