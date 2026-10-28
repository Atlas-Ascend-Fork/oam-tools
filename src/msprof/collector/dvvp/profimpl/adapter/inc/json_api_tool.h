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

#ifndef INC_CDLS_JSON_API_H
#define INC_CDLS_JSON_API_H

#include <fstream>
#include <typeinfo>
#include "json/json_tool.h"
#include "msprof_dlog_tool.h"
#include "utils/utils_tool.h"

#define JSON_PARSE_FILE_FAILED -1

using Json = NanoJson::Json;
using JsonValue = NanoJson::JsonValue;

namespace Msprofiler {
namespace Parser {
using namespace analysis::dvvp::common::utils;
template <typename T>
inline void CatchException(T item, const std::exception& e)
{
    if (typeid(item) == typeid(int8_t) || typeid(item) == typeid(uint8_t) || typeid(item) == typeid(int16_t) ||
        typeid(item) == typeid(uint16_t) || typeid(item) == typeid(int32_t) || typeid(item) == typeid(uint32_t) ||
        typeid(item) == typeid(int64_t) || typeid(item) == typeid(uint64_t)) {
        MSPROF_LOGE("\"%ld\" in config file has exception, which is \"%s\"", item, e.what());
    } else if (typeid(item) == typeid(const char*)) {
        MSPROF_LOGE("\"%s\" in config file has exception, which is \"%s\"", item, e.what());
    } else {
        MSPROF_LOGE("unknown type in config file has exception, which is \"%s\"", e.what());
    }
}

template <>
inline void CatchException(const std::string& item, const std::exception& e)
{
    MSPROF_LOGE("\"%s\" in config file has exception, which is \"%s\"", item.c_str(), e.what());
}

inline void LoadConfigFlie(const std::string& configPath, Json& jsonConfigRoot, bool& flag)
{
    std::string configPathString(configPath);
    configPathString = Utils::CanonicalizePath(configPathString);
    if (configPathString.empty()) {
        MSPROF_LOGW("The configPathString path: [%s] does not exist or permission denied.", configPathString.c_str());
        flag = false;
        return;
    }
    configPathString = Utils::CanonicalizePath(configPathString);
    FUNRET_CHECK_EXPR_ACTION_LOGW(
        configPathString.empty(), return, "The configPathString: %s does not exist or permission denied.",
        configPathString.c_str());
    std::ifstream jsonConfigFileStream(configPathString, std::ifstream::in);
    if (jsonConfigFileStream.is_open()) {
        try {
            std::istreambuf_iterator<char> beg(jsonConfigFileStream), end;
            std::string str(beg, end);
            jsonConfigRoot.Parse(str);
        } catch (std::runtime_error& e) {
            MSPROF_LOGW("Json file config load fail, path:%s", configPathString.c_str());
            flag = false;
        }
        jsonConfigFileStream.close();
        flag = true;
    } else {
        MSPROF_LOGW("Json file path cannot open, path: %s", configPathString.c_str());
        flag = false;
    }
}

} // namespace Parser
} // namespace Msprofiler
#endif // INC_CDLS_JSON_API_H
