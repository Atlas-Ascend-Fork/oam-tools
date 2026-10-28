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
#ifndef ANALYSIS_DVVP_COMMON_JSON_H
#define ANALYSIS_DVVP_COMMON_JSON_H

#include <string>
#include <vector>
#include <stdexcept>
#include <unordered_map>
#include "msprof_dlog_tool.h"

namespace NanoJson {
constexpr size_t TRUE_STRING_LEN = 4;
constexpr size_t FALSE_STRING_LEN = 5;
constexpr size_t MAX_STR_SIZE = 1024 * 1024;

enum JsonValueType {
    STRING = 0,
    ARRAY = 1,
    OBJECT = 2,
    DOUBLE = 3,
    INT = 4,
    UINT = 5,
    BOOLEAN = 6,
    NULL_TYPE = 7,
    INVALID = 0xFF
};

// Macro for creating object value, instance sholud be a JsonValue type value
// If the allocation is failed, the type of instance will be set as JsonValueType::INVALID
#define JSONVALUE_STRING_DEFINE(instance, action, args...)                   \
    do {                                                                     \
        (instance).type = NanoJson::JsonValueType::STRING;                   \
        (instance).value.stringValue = new (std::nothrow) std::string(args); \
        if ((instance).value.stringValue == nullptr) {                       \
            (instance).type = NanoJson::JsonValueType::INVALID;              \
            MSPROF_LOGE("Fail allocating stack memory");                     \
            action;                                                          \
        }                                                                    \
    } while (0)

#define JSONVALUE_ARRAY_DEFINE(instance, action, args...)                                        \
    do {                                                                                         \
        (instance).type = NanoJson::JsonValueType::ARRAY;                                        \
        (instance).value.arrayValue = new (std::nothrow) std::vector<NanoJson::JsonValue>(args); \
        if ((instance).value.arrayValue == nullptr) {                                            \
            (instance).type = NanoJson::JsonValueType::INVALID;                                  \
            MSPROF_LOGE("Fail allocating stack memory");                                         \
            action;                                                                              \
        }                                                                                        \
    } while (0)

#define JSONVALUE_OBJECT_DEFINE(instance, action)                                                               \
    do {                                                                                                        \
        (instance).type = NanoJson::JsonValueType::OBJECT;                                                      \
        (instance).value.objectValue = new (std::nothrow) std::unordered_map<std::string, NanoJson::JsonValue>; \
        if ((instance).value.objectValue == nullptr) {                                                          \
            (instance).type = NanoJson::JsonValueType::INVALID;                                                 \
            MSPROF_LOGE("Fail allocating stack memory");                                                        \
            action;                                                                                             \
        }                                                                                                       \
    } while (0)

// JsonValue is the basic data type of this lib. It could be defined by user for some user defined struction
struct JsonValue {
    NanoJson::JsonValueType type;
    union {
        std::string* stringValue;
        std::vector<JsonValue>* arrayValue;
        std::unordered_map<std::string, JsonValue>* objectValue;
        double doubleValue;
        int64_t intValue;
        uint64_t uintValue;
        bool boolValue;
    } value;
    explicit JsonValue(NanoJson::JsonValueType jsonType = NanoJson::JsonValueType::INVALID);
    JsonValue& operator=(const int64_t& val);
    JsonValue& operator=(const uint64_t& val);
    JsonValue& operator=(const int32_t& val);
    JsonValue& operator=(const uint32_t& val);
    JsonValue& operator=(const double& val);
    JsonValue& operator=(const bool& val);
    JsonValue& operator=(const std::string& val);
    template <size_t N>
    JsonValue& operator=(const char (&str)[N])
    {
        const std::string tmp(str);
        return operator=(tmp);
    }

    // Only valid for vector with int64_t, int32_t, uint32_t, uint64_t, double, bool, string
    template <typename T>
    JsonValue& operator=(const std::vector<T>& array)
    {
        size_t size = array.size();
        JSONVALUE_ARRAY_DEFINE(*this, return *this, size);

        for (size_t i = 0; i < size; i++) {
            (*value.arrayValue)[i] = array[i];
        }
        return *this;
    }

    // Only valid for vector with int64_t, int32_t, uint32_t, uint64_t, double, bool, string
    template <typename T, std::size_t N>
    JsonValue& operator=(const T (&array)[N])
    {
        std::vector<T> tmp(array, array + N);
        return operator=(tmp);
    }

    // Only valid for unordered_map with int64_t, int32_t, uint32_t, uint64_t, double, bool, string
    template <typename T>
    JsonValue& operator=(const std::unordered_map<std::string, T>& obj)
    {
        size_t size = obj.size();
        auto iter = obj.cbegin();
        JSONVALUE_OBJECT_DEFINE(*this, return *this);
        for (size_t i = 0; i < size; i++, iter++) {
            (*value.objectValue)[iter->first] = iter->second;
        }
        return *this;
    }

    JsonValue& operator[](const std::string& key);
    JsonValue& operator[](const size_t& idx);
    std::string operator()() const; // TransFer the value of JsonValue to String

    template <typename T>
    T GetValue() const;
    void SetArraySize(const size_t& size); // Only valid for JsonValue with Array type
    void PushBack(JsonValue& val);         // Only valid for JsonValue with Array type
    bool Contains(const std::string& key) const;
};

using JsonArray = std::vector<JsonValue>;
using JsonObj = std::unordered_map<std::string, JsonValue>;
class Json {
public:
    Json();
    explicit Json(const JsonValue& val);    // It may throw error
    explicit Json(const std::string& json); // It may throw error
    ~Json();
    void Parse(const std::string& json); // It may throw error
    void Insert(const JsonValue& val);
    Json& RemoveByKey(const std::string& key);
    JsonValue& operator[](const std::string& key);
    void operator=(const JsonValue& val);
    std::string ToString() const;
    JsonValue GetJsonValue() const;
    bool Contains(const std::string& key) const;
    std::unordered_map<std::string, JsonValue>::iterator Begin() const;
    std::unordered_map<std::string, JsonValue>::iterator End() const;

private:
    JsonValue value_;
};
} // namespace NanoJson

#endif
