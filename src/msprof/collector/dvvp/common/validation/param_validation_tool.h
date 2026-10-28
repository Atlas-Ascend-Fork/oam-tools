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
#ifndef ANALYSIS_DVVP_COMMON_PARAM_VALIDATION_H
#define ANALYSIS_DVVP_COMMON_PARAM_VALIDATION_H

#include <string>
#include "message/prof_params.h"
#include "singleton/singleton_tool.h"
#include "utils/utils_tool.h"
#include "errno/error_code_tool.h"
#include "osal.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace validation {
enum class ProfSocPmuType {
    PMU_TYPE_MATA = 0,
    PMU_TYPE_HA = 1,
    PMU_TYPE_SMMU = 2,
    PMU_TYPE_NOC = 3,
    PMU_TYPE_HA_NO_HEAD = 4,
    PMU_TYPE_UNKNOWN
};

class ParamValidation : public analysis::dvvp::common::singleton::Singleton<ParamValidation> {
public:
    ParamValidation();
    ~ParamValidation() override;

    int32_t Init() const;
    int32_t Uninit() const;
    bool CheckProfilingParams(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
    bool CheckParamsDevices(
        const std::string& app, const std::string& paramsDevices, const std::string& paramsHostSys) const;
    bool CheckParamsJobIdRegexMatch(const std::string& paramsJobId) const;
    bool CheckParamsModeRegexMatch(const std::string& paramsMode) const;
    bool CheckLlcEventsIsValid(const std::string& events) const;
    bool CheckProfilingSwitchIsValid(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
    bool CheckAiCoreEventsIsValid(const std::vector<std::string>& events) const;
    bool CheckAiCoreEventCoresIsValid(const std::vector<int32_t>& coreId) const;
    bool CheckDdrEventsIsValid(const std::vector<std::string>& events) const;
    bool CheckHbmEventsIsValid(const std::vector<std::string>& events) const;
    bool CheckAivEventsIsValid(const std::vector<std::string>& events) const;
    bool CheckAivEventCoresIsValid(const std::vector<int32_t>& coreId) const;
    bool CheckAppNameIsValid(const std::string& appName) const;
    bool CheckDataTagIsValid(const std::string& tag) const;
    bool CheckTsCpuEventIsValid(const std::vector<std::string>& events) const;
    bool CheckCtrlCpuEventIsValid(const std::vector<std::string>& events) const;
    bool CheckPmuEventSizeIsValid(const size_t eventSize) const;
    bool CheckCoreIdSizeIsValid(const int32_t eventSize) const;
    bool CheckDeviceIdIsValid(const std::string& devId) const;
    bool CheckAicoreMetricsIsValid(const std::string& aicoreMetrics) const;
    int32_t CheckEventsSize(const std::string& events) const;
    bool CheckHexOrDec(std::string& events, const size_t mode) const;
    int32_t CustomHexCharConfig(std::string& aicoreEvents, const std::string& pattern) const;
    bool IsValidSleepPeriod(const int32_t period) const;
    bool CheckHostSysOptionsIsValid(const std::string& hostSysOptions) const;
    bool CheckHostSysPidIsValid(const int32_t hostSysPid) const;
    bool CheckHostSysUsageOptionsIsValid(const std::string& hostSysUsageOptions) const;
    bool ProfStarsAcsqParamIsValid(const std::string& param) const;
    bool IsValidSwitch(const std::string& switchStr) const;
    bool CheckParamL0L1Invalid(const std::string& switchName, const std::string& switchStr) const;
    bool CheckParamEmptyInvalid(const std::string& switchName, const std::string& switchStr) const;
    bool CheckStorageLimit(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
    bool CheckInstrProfilingFreqValid(const uint32_t instrFreq) const;
    bool CheckArgRange(const std::string& switchName, const std::string& value, uint32_t min, uint32_t max) const;
    bool CheckLlcConfigValid(const std::string& config) const;
    bool CheckFreqIsValid(const std::string& switchName, uint32_t freq) const;
    bool CheckMemServiceflowValid(const std::string& switchName, const std::string& config) const;
    bool CheckDuplicateSocPmu(const std::string& oriStr) const;
    ProfSocPmuType GetSocPmuInfo(std::string& socPmuStr, std::string& eventStr) const;
    bool CheckSocPmuEventsValid(ProfSocPmuType type, const std::vector<std::string>& events) const;
    bool CheckSocPmuEventsSizeValid(ProfSocPmuType type, uint32_t eventSize, int32_t& maxEvent) const;
    bool CheckOpTypeIsValid(const std::string& opTypeInput, std::string& opType, std::string& errInfo) const;
    bool CheckDynaPidIsValid(const int32_t pid) const;

private:
    bool CheckControlSwitchProfiling(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
    bool CheckTsSwitchProfiling(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
    bool CheckPmuSwitchProfiling(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
    bool IsValidInterval(
        const int32_t interval, const std::string& logKey, std::string* invalidKey = nullptr,
        int32_t* invalidValue = nullptr) const;
    bool CheckProfilingIntervalIsValid(
        SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::string* invalidKey = nullptr,
        int32_t* invalidValue = nullptr) const;
    bool CheckProfilingIntervalIsValidTWO(
        SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params, std::string* invalidKey = nullptr,
        int32_t* invalidValue = nullptr) const;
    bool CheckSystemTraceSwitchProfiling(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) const;
};
} // namespace validation
} // namespace common
} // namespace dvvp
} // namespace analysis
#endif
