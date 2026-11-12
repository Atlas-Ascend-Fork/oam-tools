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
#ifndef MSPROF_FTRACE_COLLECTOR_FTRACE_PATH_H
#define MSPROF_FTRACE_COLLECTOR_FTRACE_PATH_H

#include <climits>
#include <cstdlib>
#include <string>

namespace Ftrace {
// Canonicalises the parent directory with realpath() and re-appends the leaf before the path is
// handed to open()/ifstream/ofstream: the resolved directory no longer contains "..", symlinks or
// a relative prefix, while a leaf that does not exist yet (output/lock files) still works.
inline std::string CanonicalizeFilePath(const std::string& path)
{
    if (path.empty()) {
        return path;
    }
    std::string dir = ".";
    std::string leaf = path;
    const size_t slash = path.find_last_of('/');
    if (slash != std::string::npos) {
        dir = (slash == 0) ? "/" : path.substr(0, slash);
        leaf = path.substr(slash + 1);
    }
    char resolved[PATH_MAX] = {0};
    if (realpath(dir.c_str(), resolved) == nullptr) {
        // Keep the original path so the caller's open() reports the real errno.
        return path;
    }
    if (leaf.empty()) {
        return std::string(resolved);
    }
    return std::string(resolved) + "/" + leaf;
}
} // namespace Ftrace

#endif // MSPROF_FTRACE_COLLECTOR_FTRACE_PATH_H
