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
#include "file_owner.h"

#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>
#include <cstdlib>
#include <string>

#include "ftrace_constants.h"

namespace Ftrace {
namespace {
// sudo exports the real ids of the caller; they are the only way to know which user owns the
// profiling process once the collector runs as root.
bool ParseId(const std::string& text, unsigned long& value)
{
    if (text.empty()) {
        return false;
    }
    try {
        size_t consumed = 0;
        const unsigned long parsed = std::stoul(text, &consumed, kDecimalBase);
        if (consumed != text.size()) {
            return false;
        }
        value = parsed;
    } catch (const std::exception&) {
        return false;
    }
    return true;
}

std::string EnvOrEmpty(const char* name)
{
    const char* value = getenv(name);
    return (value == nullptr) ? std::string() : std::string(value);
}
} // namespace

void GiveBackOwnership(const std::string& path)
{
    if (geteuid() != 0) {
        return; // started by the profiling user directly, nothing to hand back
    }
    // Read access is what the parser needs; the chown below additionally lets the user clean up.
    (void)chmod(path.c_str(), kDataFileMode);

    unsigned long uid = 0;
    unsigned long gid = 0;
    if (!ParseId(EnvOrEmpty("SUDO_UID"), uid) || !ParseId(EnvOrEmpty("SUDO_GID"), gid)) {
        return; // real root without sudo: root ownership is the expected outcome
    }
    if (chown(path.c_str(), static_cast<uid_t>(uid), static_cast<gid_t>(gid)) != 0) {
        // Read access is already granted by chmod above; only the convenience of the user being
        // able to delete the file is lost, which must not fail the collection.
        return;
    }
}
} // namespace Ftrace
