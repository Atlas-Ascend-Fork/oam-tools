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
#include "memory_utils.h"
#include "securec.h"
#include "msprof_dlog_tool.h"

namespace Analysis {
namespace Dvvp {
namespace Adx {
IdeMemHandle IdeXmalloc(size_t size)
{
    errno_t err;

    if (size == 0) {
        return nullptr;
    }

    IdeMemHandle val = malloc(size);
    if (val == nullptr) {
        MSPROF_LOGE("ran out of memory while trying to allocate %lu bytes", size);
        return nullptr;
    }

    err = memset_s(val, size, 0, size);
    if (err != EOK) {
        MSPROF_LOGE("[IdeXmalloc]memory clear failed, err: %d", err);
        free(val);
        val = nullptr;
        return nullptr;
    }
    return val;
}

IdeMemHandle IdeXrmalloc(const IdeMemHandle ptr, size_t ptrsize, size_t size)
{
    if (size == 0) {
        return nullptr;
    }

    if (ptr == nullptr) {
        return IdeXmalloc(size);
    }
    size_t cpLen = (ptrsize > size) ? size : ptrsize;
    IdeMemHandle val = IdeXmalloc(size);
    if (val != nullptr) {
        errno_t err = memcpy_s(val, size, ptr, cpLen);
        if (err != EOK) {
            IDE_XFREE_AND_SET_NULL(val);
            return nullptr;
        }
    }
    return val;
}

void IdeXfree(IdeMemHandle ptr)
{
    if (ptr != nullptr) {
        free(ptr);
        ptr = nullptr;
    }
}
} // namespace Adx
} // namespace Dvvp
} // namespace Analysis
