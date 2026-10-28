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
#ifndef ANALYSIS_DVVP_COMMON_SINGLETON_SINGLETON_H
#define ANALYSIS_DVVP_COMMON_SINGLETON_SINGLETON_H

#include <mutex>

namespace analysis {
namespace dvvp {
namespace common {
namespace singleton {
template <class T>
class Singleton {
public:
    static T* instance()
    {
        static T value;
        return &value;
    }
    virtual ~Singleton() {} // dtor hidden

protected:
    Singleton() {}                          // ctor hidden
    Singleton(Singleton const&);            // copy ctor hidden
    Singleton& operator=(Singleton const&); // assign op. hidden
};
} // namespace singleton
} // namespace common
} // namespace dvvp
} // namespace analysis

#endif
