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
#include "collection_job_tool.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
std::map<int32_t, std::function<SHARED_PTR_ALIA<ICollectionJob>()>> CollectionJobReflection::collectionJobMap_;
ICollectionJob::ICollectionJob() : collectionId_(0), fileName_("") {}

ICollectionJob::ICollectionJob(int32_t collectionId, const std::string& name)
    : collectionId_(collectionId), fileName_(name)
{}

ICollectionJob::~ICollectionJob() {}

bool ICollectionJob::IsGlobalJobLevel() { return false; }

int32_t ICollectionJob::GetCollectionId() { return collectionId_; }

std::string ICollectionJob::JobFileName() { return fileName_; }
} // namespace JobWrapper
} // namespace Dvvp
} // namespace Analysis
