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

#ifndef ANALYSIS_DVVP_MESSAGE_CODEC_H
#define ANALYSIS_DVVP_MESSAGE_CODEC_H

#include <memory>
#include <string>
#include <google/protobuf/descriptor.h>
#include <google/protobuf/message.h>
#include "utils/utils_tool.h"

namespace analysis {
namespace dvvp {
namespace message {
using namespace analysis::dvvp::common::utils;
enum class E_CODEC_FORMAT {
    CODEC_FORMAT_JSON = 0,
    CODEC_FORMAT_BINARY = 1,
};
const google::protobuf::Descriptor* FindMessageTypeByName(const std::string& name);
SHARED_PTR_ALIA<google::protobuf::Message> CreateMessage(const std::string& name);
bool AppendMessage(std::string& out, SHARED_PTR_ALIA<google::protobuf::Message> message);
SHARED_PTR_ALIA<std::string> EncodeMessageShared(SHARED_PTR_ALIA<google::protobuf::Message> message = nullptr);
std::string EncodeMessage(SHARED_PTR_ALIA<google::protobuf::Message> message = nullptr);
SHARED_PTR_ALIA<google::protobuf::Message> DecodeMessage(const std::string& buf);
} // namespace message
} // namespace dvvp
} // namespace analysis

#endif
