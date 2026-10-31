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
#include "input_parser_tool.h"
#include <cstdio>
#include <cstdlib>
#include <map>
#include <memory>
#include <stdexcept>
#include <cstring>
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <sys/stat.h>
#include "cmd_log/cmd_log_tool.h"
#include "errno/error_code_tool.h"
#include "param_validation_tool.h"
#include "utils/utils_tool.h"
#include "config_manager_tool.h"
#include "ai_drv_dev_api.h"
#include "platform/platform_tool.h"
#include "config/config.h"
#include "msprof_dlog_tool.h"
#include "osal.h"
#include "dyn_prof_client_tool.h"
#include "msopprof_manager_tool.h"

namespace Analysis {
namespace Dvvp {
namespace Msprof {
using namespace analysis::dvvp::driver;
using namespace analysis::dvvp::common::validation;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::cmdlog;
using namespace Analysis::Dvvp::Common::Config;
using namespace Analysis::Dvvp::Common::Platform;
using namespace analysis::dvvp::common::config;
using namespace Collector::Dvvp::Msprofbin;
using namespace Collector::Dvvp::DynProf;
using namespace Analysis::Dvvp::Msopprof;

namespace {
using ProfileParamsPtr = SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams>;

bool HasArg(const std::vector<MsprofArgsType>& argsList, MsprofArgsType arg)
{
    return std::find(argsList.begin(), argsList.end(), arg) != argsList.end();
}

// Extension platforms describe their own hidden switches by msprof long option name, so this tool
// maps a name back to its argument id. Names this tool does not provide are reported and skipped
// instead of failing the whole profiling command.
MsprofArgsType CliNameToArg(const std::string& name)
{
    for (uint32_t i = 0; i < NR_ARGS; i++) {
        if (LONG_OPTIONS[i].name == nullptr) {
            continue;
        }
        std::string option = LONG_OPTIONS[i].name;
        if (!option.empty() && option.back() == ' ') {
            option.pop_back();
        }
        if (option == name) {
            return static_cast<MsprofArgsType>(LONG_OPTIONS[i].val);
        }
    }
    return NR_ARGS;
}

void AppendHiddenCliArgs(std::vector<MsprofArgsType>& argsList)
{
    for (const auto& name : Platform::instance()->GetHiddenCliArgs()) {
        MsprofArgsType arg = CliNameToArg(name);
        if (arg == NR_ARGS) {
            MSPROF_LOGE("Ignore the hidden argument %s that this tool does not provide.", name.c_str());
            continue;
        }
        if (!HasArg(argsList, arg)) {
            argsList.push_back(arg);
        }
    }
}

// A platform declaring a long option as hidden means it does not offer that option at all, so the
// cmdline help entry owned by this tool is skipped for the very same reason.
bool IsHiddenCliArg(const std::string& name)
{
    const std::vector<std::string> hiddenArgs = Platform::instance()->GetHiddenCliArgs();
    return std::find(hiddenArgs.begin(), hiddenArgs.end(), name) != hiddenArgs.end();
}

void ParamsSwitchValid4(const struct MsprofCmdInfo& cmdInfo, int32_t opt, const ProfileParamsPtr& params)
{
    if (params == nullptr) {
        return;
    }
    switch (opt) {
        case ARGS_PARSE:
            params->parseSwitch = cmdInfo.args[opt];
            break;
        case ARGS_QUERY:
            params->querySwitch = cmdInfo.args[opt];
            break;
        case ARGS_EXPORT:
            params->exportSwitch = cmdInfo.args[opt];
            break;
        case ARGS_CLEAR:
            params->clearSwitch = cmdInfo.args[opt];
            break;
        case ARGS_MSPROFTX:
            params->msproftx = cmdInfo.args[opt];
            break;
        case ARGS_MSTX_DOMAIN_INCLUDE:
            params->mstxDomainInclude = cmdInfo.args[opt];
            break;
        case ARGS_MSTX_DOMAIN_EXCLUDE:
            params->mstxDomainExclude = cmdInfo.args[opt];
            break;
        default:
            break;
    }
}
} // namespace

constexpr int32_t MSPROF_DAEMON_ERROR = -1;
constexpr int32_t MSPROF_DAEMON_OK = 0;
constexpr int32_t FILE_FIND_REPLAY = 100;
const std::string TASK_BASED = "task-based";
const std::string SAMPLE_BASED = "sample-based";
const std::string ALL = "all";
const std::string ON = "on";
const std::string OFF = "off";
const std::string L0 = "l0";
const std::string L1 = "l1";
const std::string L2 = "l2";
const std::string L3 = "l3";
const std::string LLC_CAPACITY = "capacity";
const std::string LLC_BANDWIDTH = "bandwidth";
const std::string LLC_READ = "read";
const std::string LLC_WRITE = "write";
const std::string TOOL_NAME_PERF = "perf";
const std::string TOOL_NAME_LTRACE = "ltrace";
const std::string TOOL_NAME_IOTOP = "iotop";
const std::string CSV_FORMAT = "csv";
const std::string JSON_FORMAT = "json";
const std::string TEXT_EXPORT_TYPE = "text";
const std::string DB_EXPORT_TYPE = "db";
const std::string NTS_PIPE_UTILIZATION = "PipeUtilization";
const std::string NTS_CUSTOM_PREFIX = "Custom:";
constexpr uint64_t NTS_EVENT_MAX = 0x71b;
constexpr size_t NTS_EVENT_MAX_NUM = 10;
constexpr int32_t DECIMAL_BASE = 10;
constexpr int32_t HEX_BASE = 16;
constexpr size_t HEX_PREFIX_LEN = 2;

namespace {
bool ParseNtsEvent(const std::string& rawEvent, uint64_t& eventValue, bool& isNegative)
{
    std::string event = Utils::Trim(rawEvent);
    if (event.empty()) {
        return false;
    }
    isNegative = event[0] == '-';
    const bool hasSign = isNegative || event[0] == '+';
    const size_t signOffset = hasSign ? 1 : 0;
    if (signOffset == event.size()) {
        return false;
    }
    int32_t base = DECIMAL_BASE;
    size_t start = signOffset;
    if (event.size() > start + HEX_PREFIX_LEN && event[start] == '0' &&
        (event[start + 1] == 'x' || event[start + 1] == 'X')) {
        base = HEX_BASE;
        start += HEX_PREFIX_LEN;
        if (event.size() == start) {
            return false;
        }
    }
    for (size_t i = start; i < event.size(); ++i) {
        const auto ch = static_cast<unsigned char>(event[i]);
        if ((base == HEX_BASE && std::isxdigit(ch) == 0) || (base == DECIMAL_BASE && std::isdigit(ch) == 0)) {
            return false;
        }
    }
    if (isNegative) {
        eventValue = 0;
        return true;
    }
    const std::string unsignedEvent = event.substr(signOffset);
    size_t pos = 0;
    try {
        eventValue = std::stoull(unsignedEvent, &pos, base);
    } catch (const std::invalid_argument&) {
        return false;
    } catch (const std::out_of_range&) {
        return false;
    }
    if (pos != unsignedEvent.size()) {
        return false;
    }
    return true;
}

std::string FormatNtsEvent(uint64_t eventValue)
{
    std::stringstream eventStream;
    eventStream << "0x" << std::hex << std::nouppercase << eventValue;
    return eventStream.str();
}

std::string JoinNtsEvents(const std::vector<std::string>& events)
{
    std::stringstream eventStream;
    for (size_t i = 0; i < events.size(); ++i) {
        if (i != 0) {
            eventStream << ",";
        }
        eventStream << events[i];
    }
    return eventStream.str();
}
} // namespace

InputParser::InputParser() { MSVP_MAKE_SHARED0(params_, analysis::dvvp::message::ProfileParams, return); }

InputParser::~InputParser() {}

void InputParser::MsprofCmdUsage(const std::string msg)
{
    if (!msg.empty()) {
        std::cout << "err: " << const_cast<CHAR_PTR>(msg.c_str()) << std::endl;
    }
    ArgsManager::instance()->PrintHelp();
}

bool InputParser::HasHelpParamOnly() const
{
    return params_ != nullptr && params_->usedParams.size() == 1 && params_->usedParams.count(ARGS_HELP) == 1;
}

int32_t InputParser::PreCheckPlatform(int32_t opt, CONST_CHAR_PTR argv[])
{
    std::vector<MsprofArgsType> socBlackSwith = {ARGS_HOST_SYS,
                                                 ARGS_HOST_SYS_PID,
                                                 ARGS_HOST_SYS_USAGE,
                                                 ARGS_HOST_SYS_USAGE_FREQ,
                                                 ARGS_PARSE,
                                                 ARGS_QUERY,
                                                 ARGS_EXPORT,
                                                 ARGS_EXPORT_ITERATION_ID,
                                                 ARGS_EXPORT_MODEL_ID,
                                                 ARGS_SUMMARY_FORMAT,
                                                 ARGS_PYTHON_PATH,
                                                 ARGS_ANALYZE,
                                                 ARGS_RULE,
                                                 ARGS_MEM_SERVICEFLOW,
                                                 ARGS_OP_TYPE};
    Analysis::Dvvp::Common::Config::PlatformType platformType = ConfigManager::instance()->GetPlatformType();
    if (platformType < PlatformType::MINI_TYPE || platformType >= PlatformType::END_TYPE) {
        return PROFILING_FAILED;
    }
    std::vector<MsprofArgsType> platSwithList = GeneratePlatSwithList();
    if (Platform::instance()->RunSocSide()) {
        platSwithList.insert(platSwithList.end(), socBlackSwith.begin(), socBlackSwith.end());
    }
    if (std::find(platSwithList.begin(), platSwithList.end(), opt) != platSwithList.end()) {
        std::cout << Utils::GetSelfPath() << ": unrecognized option '" << argv[OsalGetOptInd() - 1] << "'" << std::endl;
        std::cout << "PlatformType:" << static_cast<uint32_t>(platformType) << std::endl;
        MsprofCmdUsage("");
        return PROFILING_FAILED;
    }

    return PROFILING_SUCCESS;
}

std::vector<MsprofArgsType> InputParser::GeneratePlatSwithList() const
{
    Analysis::Dvvp::Common::Config::PlatformType platformType = ConfigManager::instance()->GetPlatformType();
    std::vector<MsprofArgsType> miniBlackSwith = {
        ARGS_INTERCONNECTION_PROFILING,
        ARGS_INTERCONNECTION_FREQ,
        ARGS_L2_PROFILING,
        ARGS_AIV,
        ARGS_AIV_FREQ,
        ARGS_AIV_MODE,
        ARGS_AIV_METRICS,
        ARGS_STORAGE_LIMIT,
        ARGS_TASK_BLOCK,
        ARGS_INSTR_PROFILING,
        ARGS_INSTR_PROFILING_FREQ,
        ARGS_DYNAMIC_PROF,
        ARGS_DYNAMIC_PROF_PID,
        ARGS_NPU_EVENTS,
        ARGS_DELAY_PROF,
        ARGS_DURATION_PROF,
        ARGS_SYS_LOW_POWER,
        ARGS_SYS_LOW_POWER_FREQ,
        ARGS_MEM_SERVICEFLOW,
        ARGS_OP_TYPE};
    std::vector<MsprofArgsType> cloudBlackSwith = {ARGS_AIV,
                                                   ARGS_AIV_FREQ,
                                                   ARGS_AIV_MODE,
                                                   ARGS_AIV_METRICS,
                                                   ARGS_TASK_BLOCK,
                                                   ARGS_SYS_LOW_POWER,
                                                   ARGS_SYS_LOW_POWER_FREQ,
                                                   ARGS_INSTR_PROFILING,
                                                   ARGS_INSTR_PROFILING_FREQ,
                                                   ARGS_MEM_SERVICEFLOW,
                                                   ARGS_OP_TYPE};

    std::vector<MsprofArgsType> dcBlackSwith = {ARGS_AIV,           ARGS_AIV_FREQ,           ARGS_AIV_MODE,
                                                ARGS_AIV_METRICS,   ARGS_IO_PROFILING,       ARGS_IO_SAMPLING_FREQ,
                                                ARGS_TASK_BLOCK,    ARGS_INSTR_PROFILING,    ARGS_INSTR_PROFILING_FREQ,
                                                ARGS_SYS_LOW_POWER, ARGS_SYS_LOW_POWER_FREQ, ARGS_MEM_SERVICEFLOW,
                                                ARGS_OP_TYPE};
    std::vector<MsprofArgsType> cloudBlackSwithV2 = {ARGS_AIV,         ARGS_AIV_FREQ,      ARGS_AIV_MODE,
                                                     ARGS_AIV_METRICS, ARGS_SYS_LOW_POWER, ARGS_SYS_LOW_POWER_FREQ};
    std::vector<MsprofArgsType> miniV3BlackSwith = {
        ARGS_AIV,
        ARGS_AIV_FREQ,
        ARGS_AIV_MODE,
        ARGS_AIV_METRICS,
        ARGS_INTERCONNECTION_PROFILING,
        ARGS_INTERCONNECTION_FREQ,
        ARGS_INSTR_PROFILING,
        ARGS_INSTR_PROFILING_FREQ,
        ARGS_SYS_LOW_POWER,
        ARGS_SYS_LOW_POWER_FREQ,
        ARGS_MEM_SERVICEFLOW};

    std::vector<MsprofArgsType> davidBlackSwith = {
        ARGS_AIV, ARGS_AIV_FREQ, ARGS_AIV_MODE, ARGS_AIV_METRICS, ARGS_INSTR_PROFILING_FREQ};
    std::vector<MsprofArgsType> david121BlackSwith = {
        ARGS_AIV,      ARGS_AIV_FREQ, ARGS_AIV_MODE, ARGS_AIV_METRICS, ARGS_INSTR_PROFILING_FREQ, ARGS_DVPP_PROFILING,
        ARGS_DVPP_FREQ};
    std::vector<MsprofArgsType> tinyBlackSwith = {
        ARGS_AICPU,
        ARGS_AIV,
        ARGS_AIV_FREQ,
        ARGS_AIV_MODE,
        ARGS_QUERY,
        ARGS_AIV_METRICS,
        ARGS_INTERCONNECTION_PROFILING,
        ARGS_INTERCONNECTION_FREQ,
        ARGS_DYNAMIC_PROF,
        ARGS_EXPORT,
        ARGS_HOST_SYS,
        ARGS_HOST_SYS_PID,
        ARGS_EXPORT_ITERATION_ID,
        ARGS_INSTR_PROFILING,
        ARGS_INSTR_PROFILING_FREQ,
        ARGS_MODEL_EXECUTION,
        ARGS_EXPORT_MODEL_ID,
        ARGS_PYTHON_PATH,
        ARGS_PARSE,
        ARGS_DYNAMIC_PROF_PID,
        ARGS_SUMMARY_FORMAT,
        ARGS_IO_PROFILING,
        ARGS_IO_SAMPLING_FREQ,
        ARGS_TASK_BLOCK,
        ARGS_MEM_SERVICEFLOW,
        ARGS_ANALYZE,
        ARGS_RULE,
        ARGS_DELAY_PROF,
        ARGS_DURATION_PROF,
        ARGS_SYS_LOW_POWER,
        ARGS_SYS_LOW_POWER_FREQ};
    std::map<Analysis::Dvvp::Common::Config::PlatformType, std::vector<MsprofArgsType>> platformArgsType = {
        {PlatformType::MINI_TYPE, miniBlackSwith},
        {PlatformType::CLOUD_TYPE, cloudBlackSwith},
        {PlatformType::DC_TYPE, dcBlackSwith},
        {PlatformType::CHIP_V4_1_0, cloudBlackSwithV2},
        {PlatformType::MINI_V3_TYPE, miniV3BlackSwith},
        {PlatformType::CHIP_TINY_V1, tinyBlackSwith},
        {PlatformType::CHIP_CLOUD_V3, davidBlackSwith},
        {PlatformType::CHIP_CLOUD_V3_LITE, davidBlackSwith},
        {PlatformType::CHIP_CLOUD_V4, david121BlackSwith}};
    std::vector<MsprofArgsType> platSwithList = platformArgsType[platformType];
    // Extension platforms contribute their own hidden switches on top of the table above.
    AppendHiddenCliArgs(platSwithList);
    return platSwithList;
}

int32_t InputParser::CheckSampleModeValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt) const
{
    std::map<int32_t, std::string> sampleMap = {
        {ARGS_AIC_MODE, "--aic-mode"},
        {ARGS_AIV_MODE, "--aiv-mode"},
    };

    if (cmdInfo.args[opt] == nullptr) {
        CmdLog::CmdErrorLog("Argument %s: expected one argument", sampleMap[opt].c_str());
        return MSPROF_DAEMON_ERROR;
    }

    if (std::string(cmdInfo.args[opt]) != TASK_BASED && std::string(cmdInfo.args[opt]) != SAMPLE_BASED) {
        CmdLog::CmdErrorLog(
            "Argument %s: invalid value: %s."
            "Please input 'task-based' or 'sample-based'.",
            sampleMap[opt].c_str(), cmdInfo.args[opt]);
        return MSPROF_DAEMON_ERROR;
    }

    if (Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_AIV_INDEPENDENT_CONFIG)) {
        params_->aiv_profiling_mode =
            (opt == ARGS_AIV_MODE) ? cmdInfo.args[ARGS_AIV_MODE] : params_->aiv_profiling_mode;
    } else {
        params_->aiv_profiling_mode =
            (opt == ARGS_AIC_MODE) ? cmdInfo.args[ARGS_AIC_MODE] : params_->aiv_profiling_mode;
    }
    params_->ai_core_profiling_mode =
        (opt == ARGS_AIC_MODE) ? cmdInfo.args[ARGS_AIC_MODE] : params_->ai_core_profiling_mode;
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckAiCoreMetricsValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt) const
{
    std::map<int32_t, std::string> metricsMap = {
        {ARGS_AIC_METRICS, "--aic-metrics"},
        {ARGS_AIV_METRICS, "--aiv-metrics"},
    };

    if (cmdInfo.args[opt] == nullptr) {
        CmdLog::CmdErrorLog("Argument %s: expected one argument", metricsMap[opt].c_str());
        return MSPROF_DAEMON_ERROR;
    }
    std::string metricsRange = GeneratePrompts();
    std::string aicoreMetrics = std::string(cmdInfo.args[opt]);
    if (aicoreMetrics.empty()) {
        CmdLog::CmdErrorLog(
            "Argument %s is empty. Please input in the range of %s", metricsMap[opt].c_str(), metricsRange.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    if (!ParamValidation::instance()->CheckAicoreMetricsIsValid(aicoreMetrics)) {
        CmdLog::CmdErrorLog(
            "Argument %s: invalid value:%s. Please input in the range of %s", metricsMap[opt].c_str(),
            aicoreMetrics.c_str(), metricsRange.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    params_->ai_core_metrics = (opt == ARGS_AIC_METRICS) ? cmdInfo.args[opt] : params_->ai_core_metrics;
    if (Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_AIV_INDEPENDENT_CONFIG)) {
        params_->aiv_metrics = (opt == ARGS_AIV_METRICS) ? cmdInfo.args[opt] : params_->aiv_metrics;
    } else {
        params_->aiv_metrics = (opt == ARGS_AIC_METRICS) ? cmdInfo.args[opt] : params_->aiv_metrics;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckLlcProfilingIsValid(const std::string& llcProfiling) const
{
    std::vector<std::string> llcProfilingWhiteList = {LLC_READ, LLC_WRITE};
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_TYPE) {
        llcProfilingWhiteList = {LLC_CAPACITY, LLC_BANDWIDTH};
    }
    if (llcProfiling.empty()) {
        CmdLog::CmdErrorLog(
            "Argument --llc-profiling is empty."
            "Please input in the range of '%s|%s'",
            llcProfilingWhiteList[0].c_str(), llcProfilingWhiteList[1].c_str());
        return MSPROF_DAEMON_ERROR;
    }

    for (size_t j = 0; j < llcProfilingWhiteList.size(); j++) {
        if (llcProfiling.compare(llcProfilingWhiteList[j]) == 0) {
            return MSPROF_DAEMON_OK;
        }
    }

    CmdLog::CmdErrorLog(
        "Argument --llc-profiling: invalid value: %s. "
        "Please input in the range of '%s|%s'",
        llcProfiling.c_str(), llcProfilingWhiteList[0].c_str(), llcProfilingWhiteList[1].c_str());
    return MSPROF_DAEMON_ERROR;
}

void InputParser::AiCoreFreqCheckValid(const int32_t intervalTransfer)
{
    if (Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_AIV_INDEPENDENT_CONFIG)) {
        params_->aicore_sampling_interval = intervalTransfer;
    } else {
        params_->aicore_sampling_interval = intervalTransfer;
        params_->aiv_sampling_interval = intervalTransfer;
    }
}

static int32_t compareSwitchStr(
    const std::vector<std::string>& cmpCode, const std::string switchStr, const std::string& errorMsg, int32_t opt,
    const struct MsprofCmdInfo& cmdInfo)
{
    if (std::find(cmpCode.begin(), cmpCode.end(), switchStr) == cmpCode.end()) {
        CmdLog::CmdErrorLog(errorMsg.c_str(), LONG_OPTIONS[opt].name, cmdInfo.args[opt]);
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
};

int32_t InputParser::CheckOptionValueNotNull(const struct MsprofCmdInfo& cmdInfo, int32_t opt) const
{
    if (opt < ARGS_HELP || opt >= NR_ARGS || cmdInfo.args[opt] != nullptr) {
        return MSPROF_DAEMON_OK;
    }
    CmdLog::CmdErrorLog(
        "Argument --%s: expected one argument. Please use --%s=<value>.", LONG_OPTIONS[opt].name,
        LONG_OPTIONS[opt].name);
    return MSPROF_DAEMON_ERROR;
}

int32_t InputParser::CheckArgOnOff(const struct MsprofCmdInfo& cmdInfo, int32_t opt) const
{
    if (CheckOptionValueNotNull(cmdInfo, opt) != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    if (opt == ARGS_MSTX_DOMAIN_INCLUDE || opt == ARGS_MSTX_DOMAIN_EXCLUDE) {
        return MSPROF_DAEMON_OK;
    }
    std::string switchStr = std::string(cmdInfo.args[opt]);
    switch (opt) {
        case ARGS_GE_API: {
            const std::vector<std::string> cmpCode = {OFF, L0, L1};
            const std::string errorMsg = "Argument --%s: invalid value: %s. Please input 'off', 'l0' or 'l1'.";
            return compareSwitchStr(cmpCode, switchStr, errorMsg, opt, cmdInfo);
        }
        case ARGS_TASK_BLOCK: {
            return CheckTaskBlockValid("--task-block", switchStr);
        }
        case ARGS_TASK_TIME: {
            const bool supportL3 = Platform::instance()->CheckIfSupport(PLATFORM_TASK_TRACE_L3);
            const std::vector<std::string> cmpCode = {OFF, L0, L2, L3, L1, ON};
            std::string msgEnd = supportL3 ? ", 'l2' or 'l3'" : " or 'l2'.";
            std::string errorMsg = "Argument --%s: invalid value: %s. Please input 'on', 'off', 'l0', 'l1'" + msgEnd;

            if (compareSwitchStr(cmpCode, switchStr, errorMsg, opt, cmdInfo) != MSPROF_DAEMON_OK) {
                return MSPROF_DAEMON_ERROR;
            }
            if (switchStr.compare(L3) == 0 && !supportL3) {
                CmdLog::CmdErrorLog("l3 is not supported on this platform.");
                return MSPROF_DAEMON_ERROR;
            }
            return MSPROF_DAEMON_OK;
        }
        case ARGS_DVPP_PROFILING: {
            if (!Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_DVPP) &&
                !Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_DVPP_EX)) {
                CmdLog::CmdWarningLog("The argument: dvpp-profiling is useless on this platform.");
                return MSPROF_DAEMON_OK;
            }
            const std::vector<std::string> cmpCode = {OFF, ON};
            const std::string errorMsg = "Argument --%s: invalid value: %s. Please input 'on' or 'off'.";
            return compareSwitchStr(cmpCode, switchStr, errorMsg, opt, cmdInfo);
        }
        default: {
            const std::vector<std::string> cmpCode = {OFF, ON};
            const std::string errorMsg = "Argument --%s: invalid value: %s. Please input 'on' or 'off'.";
            return compareSwitchStr(cmpCode, switchStr, errorMsg, opt, cmdInfo);
        }
    }
}

void InputParser::ParamsSwitchValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    if (opt >= NR_ARGS) {
        return;
    }
    if (SetBasicSwitchParam(cmdInfo, opt)) {
        return;
    }

    switch (opt) {
        case ARGS_TASK_TSFW:
            params_->taskTsfw = cmdInfo.args[opt];
            break;
        default:
            ParamsSwitchValid2(cmdInfo, opt);
            break;
    }
}

int32_t InputParser::CheckNpuEventsValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt) const
{
    if (CheckOptionValueNotNull(cmdInfo, opt) != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    params_->npuEvents = cmdInfo.args[opt];
    if (!Platform::instance()->CheckIfSupport(PLATFORM_TASK_L2_CACHE_REG) &&
        !Platform::instance()->CheckIfSupport(PLATFORM_TASK_SOC_PMU)) {
        MSPROF_LOGE("Soc pmu not support on this platform.");
        return MSPROF_DAEMON_ERROR;
    }
    static std::string singleEventsHead = "0x";
    if (params_->npuEvents.compare(0, singleEventsHead.length(), singleEventsHead) == 0 &&
        params_->npuEvents.find(";") != std::string::npos) {
        MSPROF_LOGE("Failed to check soc pmu events, if you want to collect multiple soc pmu type, "
                    "please input prefix like [HA:] before events.");
        CmdLog::CmdErrorLog("Failed to check soc pmu events, if you want to collect multiple soc pmu type, "
                            "please input prefix like [HA:] before events.");
        return MSPROF_DAEMON_ERROR;
    }
    if (!ParamValidation::instance()->CheckDuplicateSocPmu(params_->npuEvents)) {
        MSPROF_LOGE("Failed to check soc pmu events, please check if input duplicate soc pmu type.");
        CmdLog::CmdErrorLog("Failed to check soc pmu events, please check if input duplicate soc pmu type.");
        return MSPROF_DAEMON_ERROR;
    }
    std::vector<std::string> registerList = Utils::Split(params_->npuEvents, false, "", ";");
    for (size_t i = 0; i < registerList.size(); ++i) {
        std::string eventStr = "";
        ProfSocPmuType eventType = ParamValidation::instance()->GetSocPmuInfo(registerList[i], eventStr);
        if (eventStr.empty()) {
            MSPROF_LOGE("Failed to check empty soc pmu events, type: %u.", static_cast<uint32_t>(eventType));
            CmdLog::CmdErrorLog("Empty npu-events detected, please input valid npu-events.");
            return MSPROF_DAEMON_ERROR;
        }
        std::vector<std::string> eventsList = Utils::Split(eventStr, false, "", ",");
        if (!ParamValidation::instance()->CheckSocPmuEventsValid(eventType, eventsList)) {
            MSPROF_LOGE(
                "Failed to check soc pmu events, type: %u, event: %s", static_cast<uint32_t>(eventType),
                registerList[i].c_str());
            CmdLog::CmdErrorLog(
                "The npu-events[%s] is invalid or exceeds the specified length, "
                "please check ERROR information in host plog.",
                params_->npuEvents.c_str());
            return MSPROF_DAEMON_ERROR;
        }
    }

    return MSPROF_DAEMON_OK;
}

int32_t InputParser::MsprofCmdCheckValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    int32_t ret = MSPROF_DAEMON_OK;
    if (opt > NR_ARGS) {
        return MSPROF_DAEMON_ERROR;
    }
    switch (opt) {
        case ARGS_OUTPUT:
            break;
        case ARGS_STORAGE_LIMIT:
            ret = CheckStorageLimitValid(cmdInfo);
            break;
        case ARGS_APPLICATION:
            ret = CheckAppValid(cmdInfo);
            break;
        case ARGS_ENVIRONMENT:
            ret = CheckEnvironmentValid(cmdInfo);
            break;
        case ARGS_AIC_MODE:
        case ARGS_AIV_MODE:
            ret = CheckSampleModeValid(cmdInfo, opt);
            break;
        case ARGS_AIC_METRICS:
        case ARGS_AIV_METRICS:
            ret = CheckAiCoreMetricsValid(cmdInfo, opt);
            break;
        case ARGS_NPU_EVENTS:
            ret = CheckNpuEventsValid(cmdInfo, opt);
            break;
        case ARGS_SYS_DEVICES:
            ret = CheckSysDevicesValid(cmdInfo);
            break;
        case ARGS_NTS_METRICS:
            ret = CheckNtsMetricsValid(cmdInfo);
            break;
        default:
            ret = MsprofCmdCheckValid2(cmdInfo, opt);
            break;
    }

    if (ret == MSPROF_DAEMON_OK) {
        return MsprofDynamicCheckValid(cmdInfo, opt);
    }

    return ret;
}

void InputParser::ParamsSwitchValid2(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    switch (opt) {
        case ARGS_IO_PROFILING:
            params_->io_profiling = cmdInfo.args[opt];
            break;
        case ARGS_INTERCONNECTION_PROFILING:
            params_->interconnection_profiling = cmdInfo.args[opt];
            break;
        case ARGS_DVPP_PROFILING:
            params_->dvpp_profiling = cmdInfo.args[opt];
            break;
        case ARGS_TASK_BLOCK:
            if (strcmp(cmdInfo.args[opt], MSVP_PROF_ALL) == 0) {
                params_->taskBlock = MSVP_PROF_ON;
                params_->taskBlockShink = MSVP_PROF_OFF;
            } else {
                params_->taskBlock = cmdInfo.args[opt];
                params_->taskBlockShink = params_->taskBlock.compare(MSVP_PROF_ON) == 0 ? MSVP_PROF_ON : MSVP_PROF_OFF;
            }
            break;
        case ARGS_SYS_LOW_POWER:
            params_->sysLp = cmdInfo.args[opt];
            break;
        case ARGS_L2_PROFILING:
            params_->l2CacheTaskProfiling = cmdInfo.args[opt];
            break;
        case ARGS_AICPU:
            params_->aicpuTrace = cmdInfo.args[opt];
            break;
        case ARGS_ANALYZE:
            params_->analyzeSwitch = cmdInfo.args[opt];
            break;
        default:
            ParamsSwitchValid4(cmdInfo, opt, params_);
            ParamsSwitchValid3(cmdInfo, opt);
            break;
    }
}

int32_t InputParser::CheckMemServiceflow(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_MEM_SERVICEFLOW] == nullptr) {
        CmdLog::CmdErrorLog("Argument --sys-mem-serviceflow: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    std::string memServiceflow = std::string(cmdInfo.args[ARGS_MEM_SERVICEFLOW]);
    if (memServiceflow.empty()) {
        CmdLog::CmdErrorLog("Argument --sys-mem-serviceflow: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    params_->memServiceflow = memServiceflow;
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::MsprofCmdCheckValid2(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    int32_t ret = MSPROF_DAEMON_OK;
    switch (opt) {
        case ARGS_LLC_PROFILING:
            ret = CheckLlcProfilingValid(cmdInfo);
            break;
        case ARGS_PYTHON_PATH:
            ret = CheckPythonPathValid(cmdInfo);
            break;
        case ARGS_SUMMARY_FORMAT:
            ret = CheckExportSummaryFormat(cmdInfo);
            break;
        case ARGS_EXPORT_TYPE:
            ret = CheckExportType(cmdInfo);
            break;
        case ARGS_REPORTS:
            ret = CheckReports(cmdInfo);
            break;
        case ARGS_MEM_SERVICEFLOW:
            ret = CheckMemServiceflow(cmdInfo);
            break;
        case ARGS_RULE:
            ret = CheckAnalyzeRuleSwitch(cmdInfo);
            break;
        case ARGS_OP_TYPE:
            ret = CheckCmdOpTypeIsValid(cmdInfo);
            break;
        default:
            break;
    }

    return ret;
}

int32_t InputParser::MsprofFreqCheckValidTwo(const struct MsprofCmdInfo& cmdInfo, int32_t opt) const
{
    int32_t ret = MSPROF_DAEMON_OK;
    switch (opt) {
        case ARGS_HARDWARE_MEM_SAMPLING_FREQ:
            if (Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_US)) {
                ret = CheckArgRange(cmdInfo, opt, 1, HZ_TEN_THOUSAND);
            } else {
                ret = CheckArgRange(cmdInfo, opt, 1, HZ_HUNDRED);
            }
            break;
        case ARGS_EXPORT_ITERATION_ID:
        case ARGS_EXPORT_MODEL_ID:
            ret = CheckArgsIsNumber(cmdInfo, opt);
            break;
        case ARGS_SYS_LOW_POWER_FREQ:
            ret = CheckArgRange(cmdInfo, opt, 1, HZ_HUNDRED);
            break;
        default:
            ret = MSPROF_DAEMON_ERROR;
            break;
    }

    return ret;
}

void InputParser::MsprofFreqTransferParams(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    int32_t interval = 0;
    FUNRET_CHECK_EXPR_ACTION(
        !Utils::StrToInt32(interval, cmdInfo.args[opt]), return, "interval %s is invalid", cmdInfo.args[opt]);
    if (interval < 1) {
        return;
    }

    int32_t intervalTransfer = HZ_CONVERT_MS / interval;
    switch (opt) {
        case ARGS_AIC_FREQ:
            AiCoreFreqCheckValid(intervalTransfer);
            break;
        case ARGS_AIV_FREQ:
            params_->aiv_sampling_interval = intervalTransfer;
            break;
        case ARGS_SYS_SAMPLING_FREQ:
            params_->sys_sampling_interval = intervalTransfer;
            break;
        case ARGS_PID_SAMPLING_FREQ:
            params_->pid_sampling_interval = intervalTransfer;
            break;
        case ARGS_IO_SAMPLING_FREQ:
            params_->io_sampling_interval = intervalTransfer;
            break;
        case ARGS_DVPP_FREQ:
            params_->dvpp_sampling_interval = intervalTransfer;
            break;
        case ARGS_CPU_SAMPLING_FREQ:
            params_->cpu_sampling_interval = intervalTransfer;
            break;
        case ARGS_HARDWARE_MEM_SAMPLING_FREQ:
            params_->hardware_mem_sampling_interval = HZ_CONVERT_US / interval;
            break;
        case ARGS_INTERCONNECTION_FREQ:
            params_->interconnection_sampling_interval = intervalTransfer;
            break;
        case ARGS_HOST_SYS_USAGE_FREQ:
            params_->hostProfilingSamplingInterval = intervalTransfer;
            break;
        case ARGS_SYS_LOW_POWER_FREQ:
            params_->sysLpFreq = HZ_CONVERT_US / interval;
            break;
        default:
            break;
    }
}

SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> InputParser::MsprofGetOpts(int32_t argc, CONST_CHAR_PTR argv[])
{
    if (!Utils::CheckInputArgsLength(argc, argv)) {
        return nullptr;
    }

    int32_t argCount = 1; // argv[0] is msprof
    SplitApplicationArgv(argc, argv, argCount);

    int32_t opt = 0;
    int32_t optionIndex = 0;
    bool setOutput = false;
    MsprofString optString = "";
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    while (
        (opt = OsalGetOptLong(argCount, const_cast<MsprofStrBufAddrT>(argv), optString, LONG_OPTIONS, &optionIndex)) !=
        MSPROF_DAEMON_ERROR) {
        if (opt == ARGS_HELP) {
            params_->usedParams.clear();
            params_->usedParams.insert(opt);
            MsprofCmdUsage("");
            return params_;
        }
        setOutput = (opt == ARGS_OUTPUT) ? true : setOutput;
        if (PreCheckPlatform(opt, argv) == PROFILING_FAILED) {
            return nullptr;
        }
        if (ProcessOptions(opt, cmdInfo) != MSPROF_DAEMON_OK) {
            return nullptr;
        }
    }

    if (!params_->application.empty()) {
        HandleApp();
    }

    if (CheckDynProfValid(cmdInfo) != MSPROF_DAEMON_OK) {
        return nullptr;
    }

    if (CheckMstxValid() != MSPROF_DAEMON_OK) {
        return nullptr;
    }

    if (setOutput && CheckOutputValid(cmdInfo) != MSPROF_DAEMON_OK) {
        return nullptr;
    }

    return ParamsCheck() == MSPROF_DAEMON_OK ? params_ : nullptr;
}

/**
 * @brief find msprof command parameter and user parameter splits
 * @param [in] argc: argc
 * @param [in] argv: argv
 * @param [out] argCount: msprof parameter count
 */
void InputParser::SplitApplicationArgv(int32_t argc, CONST_CHAR_PTR argv[], int32_t& argCount)
{
    const int32_t argWithSpaceNum = 2;
    for (int32_t i = 1; i < argc; i++) {
        if (argv[i][0] == '-' && argv[i][1] == '-') {
            if (std::strchr(argv[i], '=') != nullptr) {
                argCount++;
            } else if (i + 1 >= argc || argv[i + 1][0] == '-') {
                argCount++;
            } else {
                argCount += argWithSpaceNum;
                i++;
            }
        } else {
            for (; i < argc; i++) {
                params_->application.emplace_back(argv[i]);
            }
            return;
        }
    }
}

/**
 * @brief handle new application cmd style
 */
void InputParser::HandleApp()
{
    if (!params_->app.empty()) { // --application has a higher priority.
        params_->application.clear();
        return;
    }
    params_->app = Utils::BaseName(params_->application[0]); // start with app mode by check param_->app if empty
    return;
}

int32_t InputParser::ProcessOptions(int32_t opt, struct MsprofCmdInfo& cmdInfo)
{
    int32_t ret = MSPROF_DAEMON_ERROR;
    // opt range validate
    if (opt < ARGS_HELP || opt >= NR_ARGS || opt == static_cast<int32_t>(ARGS_INVALID)) {
        MsprofCmdUsage("");
        return ret;
    }

    cmdInfo.args[opt] = OsalGetOptArg();
    params_->usedParams.insert(opt);

    if ((opt >= ARGS_OUTPUT && opt <= ARGS_RULE) || opt == ARGS_NTS_METRICS) {
        ret = MsprofCmdCheckValid(cmdInfo, opt);
    } else if (opt >= ARGS_ASCENDCL && opt <= ARGS_ANALYZE) {
        ret = MsprofSwitchCheckValid(cmdInfo, opt);
    } else if (opt >= ARGS_AIC_FREQ && opt <= ARGS_EXPORT_MODEL_ID) {
        ret = MsprofFreqCheckValid(cmdInfo, opt);
    } else if (opt >= ARGS_HOST_SYS && opt <= ARGS_HOST_SYS_USAGE) {
        ret = MsprofHostCheckValid(cmdInfo, opt);
    } else {
        MsprofCmdUsage("");
    }
    return ret;
}

int32_t InputParser::CheckNtsMetricsValid(const struct MsprofCmdInfo& cmdInfo)
{
    const std::string ntsMetrics = cmdInfo.args[ARGS_NTS_METRICS] == nullptr ? "" : cmdInfo.args[ARGS_NTS_METRICS];
    if (!Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_TASK_NTS)) {
        CmdLog::CmdErrorLog("Argument --nts-metrics %s is not supported on current platform.", ntsMetrics.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    if (ntsMetrics.empty()) {
        CmdLog::CmdErrorLog("Argument --nts-metrics is empty. Please input in the range of PipeUtilization or "
                            "Custom:<event-list>.");
        return MSPROF_DAEMON_ERROR;
    }
    if (ntsMetrics == NTS_PIPE_UTILIZATION) {
        params_->ntsMetrics = ntsMetrics;
        // PipeUtilization is expanded to platform-specific PMU events in RunningMode.
        params_->ntsPmuEvents.clear();
        return MSPROF_DAEMON_OK;
    }
    if (ntsMetrics.compare(0, NTS_CUSTOM_PREFIX.size(), NTS_CUSTOM_PREFIX) != 0) {
        CmdLog::CmdErrorLog(
            "Argument --nts-metrics: invalid value:%s. Only PipeUtilization or Custom:<event-list> "
            "is supported.",
            ntsMetrics.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    return CheckNtsCustomMetricsValid(ntsMetrics);
}

int32_t InputParser::CheckNtsCustomMetricsValid(const std::string& ntsMetrics)
{
    const std::string eventList = ntsMetrics.substr(NTS_CUSTOM_PREFIX.size());
    if (eventList.empty()) {
        CmdLog::CmdErrorLog(
            "Argument --nts-metrics: invalid value:%s. Custom event list is empty.", ntsMetrics.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    std::vector<std::string> events = Utils::Split(eventList, false, "", ",");
    if (events.size() > NTS_EVENT_MAX_NUM) {
        CmdLog::CmdErrorLog(
            "Argument --nts-metrics: invalid value:%s. The number of custom events should be in "
            "the range of [1, 10].",
            ntsMetrics.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    std::vector<std::string> normalizedEvents;
    for (const auto& event : events) {
        uint64_t eventValue = 0;
        bool isNegative = false;
        const std::string trimmedEvent = Utils::Trim(event);
        if (!ParseNtsEvent(trimmedEvent, eventValue, isNegative)) {
            CmdLog::CmdErrorLog(
                "Argument --nts-metrics: invalid value:%s. Hexadecimal or decimal parameters are "
                "allowed in custom mode.",
                trimmedEvent.c_str());
            return MSPROF_DAEMON_ERROR;
        }
        if (isNegative || eventValue > NTS_EVENT_MAX) {
            CmdLog::CmdErrorLog(
                "Argument --nts-metrics: invalid value:%s. The event is out of range [0x0, 0x71b].",
                trimmedEvent.c_str());
            return MSPROF_DAEMON_ERROR;
        }
        normalizedEvents.emplace_back(FormatNtsEvent(eventValue));
    }

    params_->ntsMetrics = ntsMetrics;
    // Custom events are validated and normalized during command parsing.
    params_->ntsPmuEvents = JoinNtsEvents(normalizedEvents);
    return MSPROF_DAEMON_OK;
}

std::string InputParser::ResolveScriptDir() const
{
    if (params_ == nullptr || params_->app.empty() || params_->app_parameters.empty()) {
        return "";
    }
    // 仅解释器场景(如 bash/python/sh/pmupload)；直接可执行文件(./main)由 app_dir 自身决定，不做改动
    if (Utils::IsAppName(params_->app)) {
        return "";
    }
    // 跳过前置 flag(如 -x/-m/-c)，取第一个非 flag 参数作为脚本候选
    std::vector<std::string> args = Utils::Split(params_->app_parameters, false, "", " ");
    std::string script;
    for (const auto& arg : args) {
        if (!arg.empty() && arg[0] != '-') {
            script = arg;
            break;
        }
    }
    // 无脚本或脚本无目录部分(如 "bash run.sh")时沿用当前目录
    if (script.empty() || script.find('/') == std::string::npos) {
        return "";
    }
    std::string dir = Utils::DirName(Utils::RelativePathToAbsolutePath(script));
    if (dir.empty()) {
        return "";
    }
    // 目录不存在/不可访问时 CanonicalizePath 返回空，调用方回退到 app_dir
    return Utils::CanonicalizePath(dir);
}

int32_t InputParser::ParamsCheck() const
{
    if (params_ == nullptr) {
        return MSPROF_DAEMON_ERROR;
    }

    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_SCALE) && params_->taskBlock == "on" &&
        params_->taskBlockShink == "off" && params_->opType.empty()) {
        CmdLog::CmdErrorLog("Argument --task-block: when set to 'all', --optype must not be empty.");
        return MSPROF_DAEMON_ERROR;
    }

    if (!params_->result_dir.empty()) {
        return MSPROF_DAEMON_OK;
    }
    std::string ascendWorkPath;
    MSPROF_GET_ENV(MM_ENV_ASCEND_WORK_PATH, ascendWorkPath);
    if (!ascendWorkPath.empty()) {
        std::string path = Utils::RelativePathToAbsolutePath(ascendWorkPath) + MSVP_SLASH + PROFILING_RESULT_PATH;
        if (Utils::CreateDir(path) != PROFILING_SUCCESS) {
            char errBuf[MAX_ERR_STRING_LEN + 1] = {0};
            CmdLog::CmdErrorLog(
                "Create output dir failed.ErrorCode: %d, ErrorInfo: %s.", OsalGetErrorCode(),
                OsalGetErrorFormatMessage(OsalGetErrorCode(), errBuf, MAX_ERR_STRING_LEN));
            return MSPROF_DAEMON_ERROR;
        }
        if (!Utils::IsDirAccessible(path)) {
            CmdLog::CmdErrorLog("Profiling output path %s is not a dir or can not accessible.", path.c_str());
            return MSPROF_DAEMON_ERROR;
        }
        params_->result_dir = Utils::CanonicalizePath(path);
        if (params_->result_dir.empty()) {
            CmdLog::CmdErrorLog("Profiling output path is invalid because of"
                                " get the canonicalized absolute pathname failed");
            return MSPROF_DAEMON_ERROR;
        }
    } else {
        if (!params_->application.empty()) {
            // new cmd save result in current dir when output not set
            params_->result_dir = Utils::CanonicalizePath("./");
            return MSPROF_DAEMON_OK;
        }
        if (!params_->app_dir.empty()) {
            // 解释器场景(如 bash train/run.sh)优先用脚本所在目录，避免数据落到调用目录；
            // 其余场景(直接可执行文件/脚本无目录部分)仍用 app_dir，保持原行为
            std::string scriptDir = ResolveScriptDir();
            params_->result_dir = scriptDir.empty() ? params_->app_dir : scriptDir;
        } else {
            params_->result_dir = Utils::CanonicalizePath("./");
        }
    }

    return MSPROF_DAEMON_OK;
}

bool InputParser::SetBasicSwitchParam(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    switch (opt) {
        case ARGS_ASCENDCL:
            params_->acl = cmdInfo.args[opt];
            return true;
        case ARGS_RUNTIME_API:
            params_->runtimeApi = cmdInfo.args[opt];
            return true;
        case ARGS_TASK_TIME:
            params_->taskTime = cmdInfo.args[opt];
            SetTaskTimeSwitch(cmdInfo.args[opt]);
            return true;
        case ARGS_AICORE_SHAPE:
            params_->aicoreShape = cmdInfo.args[opt];
            return true;
        case ARGS_TASK_MEMORY:
            params_->taskMemory = cmdInfo.args[opt];
            return true;
        case ARGS_GE_API:
            params_->geApi = cmdInfo.args[opt];
            return true;
        case ARGS_AI_CORE:
            params_->ai_core_profiling = cmdInfo.args[opt];
            return true;
        case ARGS_AIV:
            params_->aiv_profiling = cmdInfo.args[opt];
            return true;
        case ARGS_CPU_PROFILING:
            params_->cpu_profiling = cmdInfo.args[opt];
            return true;
        case ARGS_SYS_PROFILING:
            params_->sys_profiling = cmdInfo.args[opt];
            return true;
        case ARGS_PID_PROFILING:
            params_->pid_profiling = cmdInfo.args[opt];
            return true;
        default:
            return false;
    }
}

int32_t InputParser::CheckHostSysUsageValid(const struct MsprofCmdInfo& cmdInfo)
{
#if (defined(_WIN32) || defined(_WIN64) || defined(_MSC_VER))
    CmdLog::CmdErrorLog("Currently, --host-sys-usage can be used only in the Linux environment.");
#endif
    if (Platform::instance()->RunSocSide()) {
        CmdLog::CmdErrorLog("Not in host side, --host-sys-usage is not supported.");
        return MSPROF_DAEMON_ERROR;
    }
    if (cmdInfo.args[ARGS_HOST_SYS_USAGE] == nullptr) {
        CmdLog::CmdErrorLog("Argument --host-sys-usage is empty. Please input in the range of "
                            "'cpu|mem'.");
        return MSPROF_DAEMON_ERROR;
    }
    std::vector<std::string> hostSysUsageArray = Utils::Split(cmdInfo.args[ARGS_HOST_SYS_USAGE], false, "", ",");
    for (size_t i = 0; i < hostSysUsageArray.size(); ++i) {
        if (!ParamValidation::instance()->CheckHostSysUsageOptionsIsValid(hostSysUsageArray[i])) {
            MSPROF_LOGE(
                "Argument --host-sys-usage: invalid value:%s. Please input in the range of "
                "'cpu|mem'.",
                hostSysUsageArray[i].c_str());
            CmdLog::CmdErrorLog(
                "Argument --host-sys-usage=%s is invalid. Please input in the range of "
                "'cpu|mem'.",
                cmdInfo.args[ARGS_HOST_SYS_USAGE]);
            return MSPROF_DAEMON_ERROR;
        }
        SetHostSysUsageParam(hostSysUsageArray[i]);
    }
    params_->hostSysUsage = cmdInfo.args[ARGS_HOST_SYS_USAGE];
    return MSPROF_DAEMON_OK;
}

void InputParser::SetHostSysUsageParam(const std::string& hostSysUsageParam)
{
    if (hostSysUsageParam.compare(HOST_SYS_CPU) == 0) {
        params_->hostAllPidCpuProfiling = ON;
    } else if (hostSysUsageParam.compare(HOST_SYS_MEM) == 0) {
        params_->hostAllPidMemProfiling = ON;
    }
}

/**
 * @brief check host-sys parameter is valid or not
 * @param cmd_info: command info
 *
 * @return
 *        MSPROF_DAEMON_OK: succ
 *        MSPROF_DAEMON_ERROR: failed
 */
int32_t InputParser::CheckHostSysValid(const struct MsprofCmdInfo& cmdInfo)
{
#if (defined(_WIN32) || defined(_WIN64) || defined(_MSC_VER))
    CmdLog::CmdErrorLog("Currently, --host-sys can be used only in the Linux environment.");
#endif
    if (Platform::instance()->RunSocSide()) {
        CmdLog::CmdErrorLog("Not in host side, --host-sys is not supported");
    }
    if (cmdInfo.args[ARGS_HOST_SYS] == nullptr) {
        CmdLog::CmdErrorLog("Argument --host-sys: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    std::string hostSys = std::string(cmdInfo.args[ARGS_HOST_SYS]);
    if (hostSys.empty()) {
        CmdLog::CmdErrorLog("Argument --host-sys is empty. Please input in the range of "
                            "'cpu|mem|disk|network|osrt|numa|threads-sync|cache'");
        return MSPROF_DAEMON_ERROR;
    }
    std::vector<std::string> hostSysArray = Utils::Split(cmdInfo.args[ARGS_HOST_SYS], false, "", ",");
    for (size_t i = 0; i < hostSysArray.size(); ++i) {
        if (!(ParamValidation::instance()->CheckHostSysOptionsIsValid(hostSysArray[i]))) {
            CmdLog::CmdErrorLog(
                "Argument --host-sys: invalid value:%s. Please input in the range of "
                "'cpu|mem|disk|network|osrt|numa|threads-sync|cache'",
                hostSysArray[i].c_str());
            return MSPROF_DAEMON_ERROR;
        }
        SetHostSysParam(hostSysArray[i]);
    }
    if (CheckHostSysToolsValid() != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    params_->host_sys = cmdInfo.args[ARGS_HOST_SYS];
    params_->host_disk_freq = 50; // host_disk_freq the default value is 50 Hz.
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckHostSysToolsValid() const
{
    if (params_->host_osrt_profiling.compare(ON) == 0) {
        MSPROF_LOGI("Start the detection tool.");
        if (CheckHostSysToolsIsExist(TOOL_NAME_PERF, PROF_SCRIPT_FILE_PATH) != MSPROF_DAEMON_OK) {
            CmdLog::CmdErrorLog("The tool perf is invalid, please check"
                                " if the tool and sudo are available.");
            return MSPROF_DAEMON_ERROR;
        }
        if (CheckHostSysToolsIsExist(TOOL_NAME_LTRACE, PROF_SCRIPT_FILE_PATH) != MSPROF_DAEMON_OK) {
            CmdLog::CmdErrorLog("The tool ltrace is invalid, please check"
                                " if the tool and sudo are available.");
            return MSPROF_DAEMON_ERROR;
        }
    }
    if (params_->host_disk_profiling.compare(ON) == 0) {
        if (CheckHostSysToolsIsExist(TOOL_NAME_IOTOP, PROF_SCRIPT_FILE_PATH) != MSPROF_DAEMON_OK) {
            CmdLog::CmdErrorLog("The tool iotop is invalid, please check if"
                                " the tool and sudo are available.");
            return MSPROF_DAEMON_ERROR;
        }
    }
    return MSPROF_DAEMON_OK;
}

void InputParser::SetHostSysParam(const std::string hostSysParam)
{
    if (hostSysParam.compare(HOST_SYS_CPU) == 0) {
        params_->host_cpu_profiling = ON;
        params_->host_cpu_freq_profiling = ON;
    } else if (hostSysParam.compare(HOST_SYS_MEM) == 0) {
        params_->host_mem_profiling = ON;
    } else if (hostSysParam.compare(HOST_SYS_NETWORK) == 0) {
        params_->host_network_profiling = ON;
    } else if (hostSysParam.compare(HOST_SYS_DISK) == 0) {
        params_->host_disk_profiling = ON;
    } else if (hostSysParam.compare(HOST_SYS_OSRT) == 0) {
        params_->host_osrt_profiling = ON;
    } else if (hostSysParam.compare(HOST_SYS_NUMA) == 0) {
        params_->host_numa_profiling = ON;
    } else if (hostSysParam.compare(HOST_SYS_THREADS_SYNC) == 0) {
        params_->host_threads_sync_profiling = ON;
    } else if (hostSysParam.compare(HOST_SYS_CACHE) == 0) {
        params_->host_cache_profiling = ON;
    }
}

int32_t InputParser::CheckHostSysToolsIsExist(const std::string toolName, const std::string exeCmd) const
{
    std::string tmpDir = analysis::dvvp::common::utils::Utils::IdeGetHomedir();
    static const std::string ENV_PATH = "PATH=/usr/bin/:/usr/sbin:/var";
    std::vector<std::string> envV;
    envV.push_back(ENV_PATH);
    std::vector<std::string> argsV;
    if (exeCmd.compare(PROF_SCRIPT_PROF) == 0) {
        argsV.push_back(PROF_SCRIPT_PROF);
        argsV.push_back("--version");
    } else {
        argsV.push_back(exeCmd);
        argsV.push_back("get-version");
        argsV.push_back(toolName);
    }
    unsigned long long startRealtime = analysis::dvvp::common::utils::Utils::GetClockRealtime();
    tmpDir += "/tmpPrint" + std::to_string(startRealtime);
    int32_t exitCode = analysis::dvvp::common::utils::INVALID_EXIT_CODE;
    static const std::string CMD = "sudo";
    OsalProcess tmpProcess = MSVP_PROCESS;
    ExecCmdParams execCmdParams(CMD, true, tmpDir);
    int32_t ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsV, envV, exitCode, tmpProcess);
    FUNRET_CHECK_FAIL_PRINT(ret != PROFILING_SUCCESS);
    ret = CheckHostSysCmdOutIsExist(tmpDir, toolName, tmpProcess);
    return ret;
}

int32_t InputParser::CheckHostSysCmdOutIsExist(
    const std::string tmpDir, const std::string toolName, const OsalProcess tmpProcess) const
{
    MSPROF_LOGI("Start to check whether the file exists.");
    for (int32_t i = 0; i < FILE_FIND_REPLAY; i++) {
        if (!(Utils::IsFileExist(tmpDir))) {
            OsalSleep(20); // If the file is not found, the delay is 20 ms.
            continue;
        } else {
            break;
        }
    }
    for (int32_t i = 0; i < FILE_FIND_REPLAY; i++) {
        int64_t len = analysis::dvvp::common::utils::Utils::GetFileSize(tmpDir);
        if (len < static_cast<int64_t>(toolName.length())) {
            OsalSleep(5); // If the file has no content, the delay is 5 ms.
            continue;
        } else {
            break;
        }
    }
    std::string tmpDirPath = Utils::CanonicalizePath(tmpDir);
    FUNRET_CHECK_EXPR_ACTION(
        tmpDirPath.empty(), return MSPROF_DAEMON_ERROR, "The tmpDir path: %s does not exist or permission denied.",
        tmpDirPath.c_str());
    std::ifstream in(tmpDirPath);
    std::ostringstream tmp;
    tmp << in.rdbuf();
    std::string tmpStr = tmp.str();
    OsalUnlink(tmpDirPath.c_str());
    int32_t ret = CheckHostOutString(tmpStr, toolName);
    if (ret != MSPROF_DAEMON_OK) {
        ret = UninitCheckHostSysCmd(tmpProcess); // stop check process.
        if (ret != MSPROF_DAEMON_OK) {
            MSPROF_LOGE("Failed to kill the process.");
        }
        MSPROF_LOGE("The tool %s useless", toolName.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    return ret;
}

/**
 * Check the first word in the string is tool name.
 */
int32_t InputParser::CheckHostOutString(const std::string tmpStr, const std::string toolName) const
{
    std::vector<std::string> checkToolArray = Utils::Split(tmpStr.c_str());
    if (checkToolArray.size() > 0) {
        if (checkToolArray[0].compare(toolName) == 0) {
            MSPROF_LOGI("The returned value is correct.%s", checkToolArray[0].c_str());
            return MSPROF_DAEMON_OK;
        } else {
            MSPROF_LOGE("The return value is incorrect.%s", checkToolArray[0].c_str());
            return MSPROF_DAEMON_ERROR;
        }
    }
    MSPROF_LOGE("The file has no content.");
    return MSPROF_DAEMON_ERROR;
}

int32_t InputParser::UninitCheckHostSysCmd(const OsalProcess checkProcess) const
{
    if (!(ParamValidation::instance()->CheckHostSysPidIsValid(static_cast<int32_t>(checkProcess)))) {
        return MSPROF_DAEMON_ERROR;
    }
    if (!analysis::dvvp::common::utils::Utils::ProcessIsRuning(checkProcess)) {
        MSPROF_LOGI("Process:%d does not exist", static_cast<int32_t>(checkProcess));
        return MSPROF_DAEMON_OK;
    }
    static const std::string ENV_PATH = "PATH=/usr/bin/:/usr/sbin:/var:/bin";
    std::vector<std::string> envV;
    envV.push_back(ENV_PATH);
    std::vector<std::string> argsV;
    std::string killCmd = "kill -2 " + std::to_string(static_cast<int32_t>(checkProcess));
    argsV.push_back("-c");
    argsV.push_back(killCmd);
    int32_t exitCode = analysis::dvvp::common::utils::VALID_EXIT_CODE;
    static const std::string CMD = "sh";
    OsalProcess tmpProcess = MSVP_PROCESS;
    ExecCmdParams execCmdParams(CMD, true, "");
    int32_t ret = MSPROF_DAEMON_OK;
    for (int32_t i = 0; i < FILE_FIND_REPLAY; i++) {
        if (ParamValidation::instance()->CheckHostSysPidIsValid(static_cast<int32_t>(checkProcess))) {
            ret = analysis::dvvp::common::utils::Utils::ExecCmd(execCmdParams, argsV, envV, exitCode, tmpProcess);
            OsalSleep(20); // If failed stop check process, the delay is 20 ms.
            continue;
        } else {
            break;
        }
    }
    if (checkProcess > 0) {
        bool isExited = false;
        ret = analysis::dvvp::common::utils::Utils::WaitProcess(checkProcess, isExited, exitCode, true);
        if (ret != PROFILING_SUCCESS) {
            ret = MSPROF_DAEMON_ERROR;
            MSPROF_LOGE("Failed to wait process %d, ret=%d", static_cast<int32_t>(checkProcess), ret);
        } else {
            ret = MSPROF_DAEMON_OK;
            MSPROF_LOGI("Process %d exited, exit code=%d", static_cast<int32_t>(checkProcess), exitCode);
        }
    }
    return ret;
}

int32_t InputParser::CheckHostSysPidValid(const struct MsprofCmdInfo& cmdInfo)
{
    if (cmdInfo.args[ARGS_HOST_SYS_PID] == nullptr) {
        CmdLog::CmdErrorLog("Argument --host-sys-pid is empty,"
                            "Please enter a valid --host-sys-pid value.");
        return MSPROF_DAEMON_ERROR;
    }

    if (Utils::CheckStringIsNonNegativeIntNum(cmdInfo.args[ARGS_HOST_SYS_PID])) {
        int32_t hostSysRet = 0;
        FUNRET_CHECK_EXPR_ACTION(
            !Utils::StrToInt32(hostSysRet, cmdInfo.args[ARGS_HOST_SYS_PID]), return MSPROF_DAEMON_ERROR,
            "ARGS_HOST_SYS_PID %s is invalid", cmdInfo.args[ARGS_HOST_SYS_PID]);
        if (!(ParamValidation::instance()->CheckHostSysPidIsValid(hostSysRet))) {
            CmdLog::CmdErrorLog(
                "Argument --host-sys-pid: invalid int value: %d."
                "The process cannot be found, please enter a correct host-sys-pid.",
                hostSysRet);
            return MSPROF_DAEMON_ERROR;
        } else {
            params_->host_sys_pid = hostSysRet;
            return MSPROF_DAEMON_OK;
        }
    } else {
        CmdLog::CmdErrorLog(
            "Argument --host-sys-pid: invalid value: %s."
            "Please input an integer value.The min value is 0.",
            cmdInfo.args[ARGS_HOST_SYS_PID]);
        return MSPROF_DAEMON_ERROR;
    }
}

int32_t InputParser::CheckAnalysisOutputValid(const std::string& path, const struct MsprofCmdInfo& cmdInfo) const
{
    std::vector<int> analysisOpts = {ARGS_EXPORT, ARGS_PARSE, ARGS_QUERY, ARGS_ANALYZE};
    for (auto& opt : analysisOpts) {
        if (cmdInfo.args[opt] == nullptr) {
            continue;
        }
        if (std::string(cmdInfo.args[opt]) == ON) {
            if (!Utils::IsFileExist(path)) {
                CmdLog::CmdErrorLog("Analysis output path(%s) does not exist.", path.c_str());
                return MSPROF_DAEMON_ERROR;
            }
            if (Utils::IsSoftLink(path)) {
                CmdLog::CmdErrorLog("Analysis output path(%s) is soft link.", path.c_str());
                return MSPROF_DAEMON_ERROR;
            }
        }
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckOutputValid(const struct MsprofCmdInfo& cmdInfo)
{
    if (cmdInfo.args[ARGS_OUTPUT] == nullptr) {
        CmdLog::CmdErrorLog("Argument --output: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    std::string path = Utils::RelativePathToAbsolutePath(cmdInfo.args[ARGS_OUTPUT]);
    if (!path.empty()) {
        if (CheckAnalysisOutputValid(path, cmdInfo) != MSPROF_DAEMON_OK) {
            return MSPROF_DAEMON_ERROR;
        }
        if (path.size() > MAX_PATH_LENGTH) {
            CmdLog::CmdErrorLog(
                "Argument --output is invalid because of exceeds"
                " the maximum length of %d",
                MAX_PATH_LENGTH);
            return MSPROF_DAEMON_ERROR;
        }
        if (!Utils::CheckPathWithInvalidChar(path)) {
            CmdLog::CmdErrorLog("Argument --output %s contains invalid character.", path.c_str());
            return MSPROF_DAEMON_ERROR;
        }
        if (Utils::CreateDir(path) != PROFILING_SUCCESS) {
            char errBuf[MAX_ERR_STRING_LEN + 1] = {0};
            CmdLog::CmdErrorLog(
                "Create output dir failed.ErrorCode: %d, ErrorInfo: %s.", OsalGetErrorCode(),
                OsalGetErrorFormatMessage(OsalGetErrorCode(), errBuf, MAX_ERR_STRING_LEN));
            return MSPROF_DAEMON_ERROR;
        }
        if (!Utils::IsDir(path)) {
            CmdLog::CmdErrorLog("Argument --output %s is not a dir.", params_->result_dir.c_str());
            return MSPROF_DAEMON_ERROR;
        }
        if (OsalAccess2(path.c_str(), OSAL_W_OK) != OSAL_EN_OK) {
            CmdLog::CmdErrorLog("Argument --output %s permission denied.", params_->result_dir.c_str());
            return MSPROF_DAEMON_ERROR;
        }
        params_->result_dir = Utils::CanonicalizePath(path);
        if (params_->result_dir.empty()) {
            CmdLog::CmdErrorLog("Argument --output is invalid because of"
                                " get the canonicalized absolute pathname failed");
            return MSPROF_DAEMON_ERROR;
        }
    } else {
        CmdLog::CmdErrorLog("Argument --output: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckStorageLimitValid(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_STORAGE_LIMIT] == nullptr) {
        return MSPROF_DAEMON_OK;
    }
    params_->storageLimit = cmdInfo.args[ARGS_STORAGE_LIMIT];
    if (params_->storageLimit.empty()) {
        CmdLog::CmdErrorLog("Argument --storage-limit: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    const std::string storageLimit = params_->storageLimit;
    if (!ParamValidation::instance()->CheckStorageLimit(params_)) {
        CmdLog::CmdErrorLog(
            "Argument --storage-limit %s is invalid, valid range is %dMB~%uMB", storageLimit.c_str(),
            STORAGE_LIMIT_DOWN_THD, UINT32_MAX);
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::GetAppParam(const std::string& appParams)
{
    if (appParams.empty()) {
        CmdLog::CmdErrorLog("Argument --application: expected one script");
        return MSPROF_DAEMON_ERROR;
    }
    size_t index = appParams.find_first_of(" ");
    if (index != std::string::npos) {
        params_->app_parameters = appParams.substr(index + 1);
    }
    std::string appPath = appParams.substr(0, index);
    appPath = Utils::CanonicalizePath(appPath);
    if (appPath.empty()) {
        CmdLog::CmdErrorLog("Script params are invalid");
        return MSPROF_DAEMON_ERROR;
    }
    if (Utils::IsSoftLink(appPath)) {
        MSPROF_LOGE("Script(%s) is soft link.", Utils::BaseName(appPath).c_str());
        return MSPROF_DAEMON_ERROR;
    }
    std::string appDir;
    std::string appName;
    int32_t ret = Utils::SplitPath(appPath, appDir, appName);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to get app dir");
        return MSPROF_DAEMON_ERROR;
    }
    params_->app_dir = appDir;
    params_->app = appName;
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckUserCmdValid(const std::string& usrCmdPath)
{
    std::string cmdPath = Utils::RelativePathToAbsolutePath(usrCmdPath);
    std::string cmdDir;
    std::string cmdName;
    if (Utils::SplitPath(cmdPath, cmdDir, cmdName) != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to get cmd dir and cmd name");
        return MSPROF_DAEMON_ERROR;
    }
    if (PreCheckApp(cmdDir, cmdName) == MSPROF_DAEMON_OK) {
        params_->app_dir = cmdDir;
        params_->app = cmdName;
        params_->cmdPath = cmdPath;
        return MSPROF_DAEMON_OK;
    }
    return MSPROF_DAEMON_ERROR;
}

int32_t InputParser::CheckAppParamValid(std::string& appParam) const
{
    if (appParam.empty()) {
        CmdLog::CmdErrorLog("Argument --application: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    if (appParam.length() > MAX_APP_LEN) {
        CmdLog::CmdErrorLog("Argument --application: expected param length less than %d", MAX_APP_LEN);
        return MSPROF_DAEMON_ERROR;
    }
    // delete head spaces
    appParam.erase(0, appParam.find_first_not_of(" \t\n\r"));
    // delete tail spaces
    appParam.erase(appParam.find_last_not_of(" \t\n\r") + 1);
    if (appParam.empty()) {
        CmdLog::CmdErrorLog("Argument --application: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckAppValid(const struct MsprofCmdInfo& cmdInfo)
{
    if (cmdInfo.args[ARGS_APPLICATION] == nullptr) {
        CmdLog::CmdErrorLog("Argument --application: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    std::string appParam = cmdInfo.args[ARGS_APPLICATION];
    if (CheckAppParamValid(appParam) != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    std::string tmpAppParamers;
    size_t index = appParam.find_first_of(" ");
    if (index != std::string::npos) {
        tmpAppParamers = appParam.substr(index + 1);
    }
    std::string cmdPath = appParam.substr(0, index);
    cmdPath = Utils::IdeReplaceWaveWithHomedir(cmdPath);
    params_->app_parameters = tmpAppParamers;
    if (!Utils::IsAppName(cmdPath)) {
        // e.g: bash xx.sh args or python xx.py args or python -m xx args or /usr/bin/python xx.py args
        // set app_dir to './' to set result_dir to current dir when --output not set, and set app to cmd to avoid empty
        // app error in HandleApp, and save all app parameters to app_parameters.
        if (tmpAppParamers.empty()) {
            CmdLog::CmdErrorLog(
                "Argument --application: an interpreter (python/bash/sh) requires a script or module argument");
            return MSPROF_DAEMON_ERROR;
        }
        if (cmdPath.find('/') != std::string::npos) {
            std::string canPath = Utils::CanonicalizePath(cmdPath);
            if (canPath.empty()) {
                CmdLog::CmdErrorLog("Script path(%s) does not exist or permission denied.", cmdPath.c_str());
                return MSPROF_DAEMON_ERROR;
            }
            if (OsalAccess2(canPath.c_str(), OSAL_X_OK) != OSAL_EN_OK) {
                CmdLog::CmdErrorLog("This app(%s) has no executable permission!", canPath.c_str());
                return MSPROF_DAEMON_ERROR;
            }
            cmdPath = canPath;
        }
        params_->cmdPath = cmdPath;
        params_->app_dir = Utils::GetCwdString();
        params_->app = Utils::BaseName(cmdPath);
        return MSPROF_DAEMON_OK;
    }
    // e.g: ./main args
    // set app_dir to cmdPath dir to set result_dir to app dir when --output not set, and set app to cmdPath base name
    // to avoid empty app error in HandleApp, and save all app parameters to app_parameters.
    return CheckUserCmdValid(cmdPath);
}

/**
 * Check validation of app name and app dir before launch.
 */
int32_t InputParser::PreCheckApp(const std::string& appDir, const std::string& appName) const
{
    if (appDir.empty() || appName.empty()) {
        return MSPROF_DAEMON_ERROR;
    }
    // check app name
    if (!ParamValidation::instance()->CheckAppNameIsValid(appName)) {
        CmdLog::CmdErrorLog("Argument --application(%s) is invalid, appName.", appName.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    // check app path
    const std::string appPath = appDir + MSVP_SLASH + appName;
    if (Utils::CanonicalizePath(appPath).empty()) {
        CmdLog::CmdErrorLog("App path(%s) does not exist or permission denied!!!", appPath.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    if (Utils::IsSoftLink(appPath)) {
        CmdLog::CmdErrorLog("App path(%s) is soft link, which is not support!", appPath.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    // check app permisiion
    if (OsalAccess2(appPath.c_str(), OSAL_X_OK) != OSAL_EN_OK) {
        CmdLog::CmdErrorLog("This app(%s) has no executable permission!", appPath.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    if (Utils::IsDir(appPath)) {
        CmdLog::CmdErrorLog(
            "Argument --application:%s is a directory, "
            "please enter the executable file path.",
            appPath.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckEnvironmentValid(const struct MsprofCmdInfo& cmdInfo)
{
    if (cmdInfo.args[ARGS_ENVIRONMENT] == nullptr) {
        CmdLog::CmdErrorLog("Argument --environment: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    params_->app_env = cmdInfo.args[ARGS_ENVIRONMENT];
    if (params_->app_env.empty()) {
        CmdLog::CmdErrorLog("Argument --environment: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckDynProfValid(struct MsprofCmdInfo& cmdInfo) const
{
    const auto app = params_->app;
    const auto dynamic = params_->dynamic;
    const auto pid = params_->pid;
    MSPROF_LOGD("app:%s, dynamic:%s, pid:%s", app.c_str(), dynamic.c_str(), pid.c_str());
    // --dynamic empty
    if (dynamic.empty() || dynamic == OFF) {
        // --dynamic empty && --pid not empty
        if (!pid.empty()) {
            CmdLog::CmdErrorLog("Argument --dynamic=off, but --pid is set.");
            MSPROF_LOGE("Argument --dynamic=off, but --pid is set.");
            return MSPROF_DAEMON_ERROR;
        } else {
            return MSPROF_DAEMON_OK;
        }
    }
    // --pid and --application is both empty
    if (app.empty() && pid.empty()) {
        CmdLog::CmdErrorLog("Argument --dynamic=on, but --application/--pid is all empty.");
        MSPROF_LOGE("Argument --dynamic=on, but --application/--pid is all empty.");
        return MSPROF_DAEMON_ERROR;
    }
    // --pid and --application is both non-empty
    if (!app.empty() && !pid.empty()) {
        CmdLog::CmdErrorLog("Argument --dynamic=on, can not set --application/--pid at the same time.");
        MSPROF_LOGE("Argument --dynamic=on, can not set --application/--pid at the same time.");
        return MSPROF_DAEMON_ERROR;
    }
    // Check whether the switch parameter conflicts with the dynamic parameter.
    FUNRET_CHECK_EXPR_ACTION(
        CheckDynConflict(cmdInfo), return MSPROF_DAEMON_ERROR,
        "Failed to check the parameter conflict about dynamic mode.");

    // --pid is non-empty, save pid to DynProfCliMgr
    std::vector<int32_t> pids;
    if (!pid.empty()) {
        if (!CheckDynaProfPidValid(pid, pids)) {
            return MSPROF_DAEMON_ERROR;
        }
        DynProfCliMgr::instance()->SetKeyPid(pids);
    } else { // app mode, set msprofbin pid
        DynProfCliMgr::instance()->SetAppMode();
        pids.push_back(Utils::GetPid());
        DynProfCliMgr::instance()->SetKeyPid(pids);
    }
    DynProfCliMgr::instance()->EnableDynProfCli();
    return MSPROF_DAEMON_OK;
}

bool InputParser::CheckDynaProfPidValid(const std::string& pid, std::vector<int32_t>& validPids) const
{
    int32_t pidInt = 0;
    std::vector<std::string> nonNumPidVec;
    std::vector<std::string> invalidPidVec;
    auto pidStrVec = Utils::Split(pid, false, "", ",");
    for (auto& pidStr : pidStrVec) {
        if (pidStr.empty()) {
            continue;
        }
        if (!Utils::StrToInt32(pidInt, pidStr)) {
            nonNumPidVec.push_back(pidStr);
        } else if (!ParamValidation::instance()->CheckDynaPidIsValid(pidInt)) {
            invalidPidVec.push_back(pidStr);
        } else {
            validPids.push_back(pidInt);
        }
    }
    UtilsStringBuilder<std::string> builder;
    if (!nonNumPidVec.empty()) {
        CmdLog::CmdErrorLog(
            "Argument --pid: invalid non-numeric pid value: %s, stop profiling.",
            builder.Join(nonNumPidVec, ",").c_str());
        return false;
    }
    if (validPids.empty()) {
        CmdLog::CmdErrorLog("Argument --pid: no valid pid values, stop profiling.");
        return false;
    }
    if (!invalidPidVec.empty()) {
        CmdLog::CmdWarningLog(
            "Argument --pid: invalid pid value: %s, "
            "will not collect profiling data for these process.",
            builder.Join(invalidPidVec, ",").c_str());
    }
    return true;
}

bool InputParser::CheckDynConflict(struct MsprofCmdInfo& cmdInfo) const
{
    FUNRET_CHECK_EXPR_ACTION(
        ConflictChecking(cmdInfo, ARGS_SYS_DEVICES, "dynamic"), return true,
        "Failed to check availability of argument --%s", LONG_OPTIONS[ARGS_SYS_DEVICES].name);
    FUNRET_CHECK_EXPR_ACTION(
        ConflictChecking(cmdInfo, ARGS_SYS_PERIOD, "dynamic"), return true,
        "Failed to check availability of argument --%s", LONG_OPTIONS[ARGS_SYS_PERIOD].name);
    FUNRET_CHECK_EXPR_ACTION(
        ConflictChecking(cmdInfo, ARGS_CPU_PROFILING, "dynamic"), return true,
        "Failed to check availability of argument --%s", LONG_OPTIONS[ARGS_CPU_PROFILING].name);
    return false;
}

bool InputParser::ConflictChecking(struct MsprofCmdInfo& cmdInfo, int32_t opt, const std::string& conflictArgs) const
{
    if (cmdInfo.args[opt] != nullptr) {
        CmdLog::CmdErrorLog(
            "Argument --%s and --%s cannot be configured at the same time.", conflictArgs.c_str(),
            LONG_OPTIONS[opt].name);
        MSPROF_LOGE(
            "Argument --%s and --%s cannot be configured at the same time.", conflictArgs.c_str(),
            LONG_OPTIONS[opt].name);
        return true;
    }
    return false;
}

int32_t InputParser::CheckPythonPathValid(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_PYTHON_PATH] == nullptr) {
        CmdLog::CmdErrorLog("Argument --python-path: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    params_->pythonPath = cmdInfo.args[ARGS_PYTHON_PATH];
    if (params_->pythonPath.empty()) {
        CmdLog::CmdErrorLog("Argument --python-path: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }

    if (params_->pythonPath.size() > MAX_PATH_LENGTH) {
        CmdLog::CmdErrorLog(
            "Argument --python-path is invalid because of exceeds"
            " the maximum length of %d",
            MAX_PATH_LENGTH);
        return MSPROF_DAEMON_ERROR;
    }

    std::string absolutePythonPath = Utils::CanonicalizePath(params_->pythonPath);
    if (absolutePythonPath.empty()) {
        CmdLog::CmdErrorLog(
            "Argument --python-path %s does not exist or permission denied!!!", params_->pythonPath.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    if (OsalAccess2(absolutePythonPath.c_str(), OSAL_X_OK) != OSAL_EN_OK) {
        CmdLog::CmdErrorLog("Argument --python-path %s permission denied.", params_->pythonPath.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    if (Utils::IsDir(absolutePythonPath)) {
        CmdLog::CmdErrorLog(
            "Argument --python-path %s is a directory, "
            "please enter the executable file path.",
            params_->pythonPath.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckExportSummaryFormat(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_SUMMARY_FORMAT] == nullptr) {
        CmdLog::CmdErrorLog("Argument --summary-format: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    params_->exportSummaryFormat = cmdInfo.args[ARGS_SUMMARY_FORMAT];
    if (params_->exportSummaryFormat != JSON_FORMAT && params_->exportSummaryFormat != CSV_FORMAT) {
        CmdLog::CmdErrorLog(
            "Argument --summary-format: invalid value: %s. "
            "Please input 'json' or 'csv'.",
            cmdInfo.args[ARGS_SUMMARY_FORMAT]);
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckExportType(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_EXPORT_TYPE] == nullptr) {
        CmdLog::CmdErrorLog("Argument --type: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    params_->exportType = cmdInfo.args[ARGS_EXPORT_TYPE];
    if (params_->exportType != TEXT_EXPORT_TYPE && params_->exportType != DB_EXPORT_TYPE) {
        CmdLog::CmdErrorLog(
            "Argument --type: invalid value: %s. "
            "Please input 'text' or 'db'.",
            cmdInfo.args[ARGS_EXPORT_TYPE]);
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckReports(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_REPORTS] == nullptr) {
        CmdLog::CmdErrorLog("Argument --type: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }
    params_->reportsPath = cmdInfo.args[ARGS_REPORTS];
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckAnalyzeRuleSwitch(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_RULE] == nullptr) {
        CmdLog::CmdErrorLog("Argument --rule: expected one argument");
        return MSPROF_DAEMON_ERROR;
    }

    std::vector<std::string> ruleVal = Utils::Split(cmdInfo.args[ARGS_RULE], false, "", ",");
    for (size_t i = 0; i < ruleVal.size(); ++i) {
        if (ruleVal[i].compare("communication") != 0 && ruleVal[i].compare("communication_matrix") != 0) {
            CmdLog::CmdErrorLog(
                "Argument --rule: invalid value: %s. "
                "Please input 'communication' or 'communication_matrix'.",
                ruleVal[i].c_str());
            return MSPROF_DAEMON_ERROR;
        }
    }

    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckCmdOpTypeIsValid(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_OP_TYPE] == nullptr) {
        CmdLog::CmdErrorLog("Argument --optype: expected one argument, please enter a valid value.");
        return MSPROF_DAEMON_ERROR;
    }
    std::string errInfo = "";
    if (!ParamValidation::instance()->CheckOpTypeIsValid(cmdInfo.args[ARGS_OP_TYPE], params_->opType, errInfo)) {
        CmdLog::CmdErrorLog("%s", errInfo.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    return MSPROF_DAEMON_OK;
}

std::string InputParser::GeneratePrompts() const
{
    // Generate the ERROR print. Consider changing to another file location.
    std::vector<std::string> metricsHint;
    std::stringstream result;
    metricsHint.push_back("[ArithmeticUtilization|PipeUtilization|Memory|MemoryL0|MemoryUB");
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_L2_CACHE_PMU)) {
        metricsHint.push_back("|L2Cache");
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_RCR_PMU)) {
        metricsHint.push_back("|ResourceConflictRatio");
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_PEU_PMU)) {
        metricsHint.push_back("|PipelineExecuteUtilization");
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_MEMORY_ACCESS_PMU)) {
        metricsHint.push_back("|MemoryAccess");
    }
    for (auto metrics : metricsHint) {
        result << metrics;
    }
    result << "]";
    return result.str();
}

int32_t InputParser::CheckLlcProfilingValid(const struct MsprofCmdInfo& cmdInfo)
{
    if (cmdInfo.args[ARGS_LLC_PROFILING] == nullptr) {
        CmdLog::CmdErrorLog("Argument --llc-profiling: expected one argument.");
        return MSPROF_DAEMON_ERROR;
    }

    std::string llcProfiling = std::string(cmdInfo.args[ARGS_LLC_PROFILING]);
    if (CheckLlcProfilingIsValid(llcProfiling) != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    params_->llc_profiling = llcProfiling;
    return MSPROF_DAEMON_OK;
}

/**
 * @brief check sys-period parameter is valid or not
 * @param cmd_info: command info
 *
 * @return
 *        MSPROF_DAEMON_OK: succ
 *        MSPROF_DAEMON_ERROR: failed
 */
int32_t InputParser::CheckSysPeriodValid(const struct MsprofCmdInfo& cmdInfo) const
{
    if (cmdInfo.args[ARGS_SYS_PERIOD] == nullptr) {
        CmdLog::CmdErrorLog("Argument --sys-period is empty,"
                            "Please enter a valid --sys-period value.");
        return MSPROF_DAEMON_ERROR;
    }

    if (Utils::CheckStringIsNonNegativeIntNum(cmdInfo.args[ARGS_SYS_PERIOD])) {
        int32_t syspeRet = 0;
        FUNRET_CHECK_EXPR_ACTION(
            !Utils::StrToInt32(syspeRet, cmdInfo.args[ARGS_SYS_PERIOD]), return MSPROF_DAEMON_ERROR,
            "syspeRet %s is invalid", cmdInfo.args[ARGS_SYS_PERIOD]);
        if (!(ParamValidation::instance()->IsValidSleepPeriod(syspeRet))) {
            CmdLog::CmdErrorLog(
                "Argument --sys-period: invalid int value: %d."
                "The range of period is 1~2592000 seconds.",
                syspeRet);
            return MSPROF_DAEMON_ERROR;
        } else {
            return MSPROF_DAEMON_OK;
        }
    } else {
        CmdLog::CmdErrorLog(
            "Argument --sys-period: invalid value: %s."
            "Please input an integer value.The range of period is 1~2592000 seconds.",
            cmdInfo.args[ARGS_SYS_PERIOD]);
        return MSPROF_DAEMON_ERROR;
    }
}

/**
 * @brief check sys-devices parameter is valid or not
 * @param cmd_info: command info
 *
 * @return
 *        MSPROF_DAEMON_OK: succ
 *        MSPROF_DAEMON_ERROR: failed
 */
int32_t InputParser::CheckSysDevicesValid(const struct MsprofCmdInfo& cmdInfo)
{
    if (CheckOptionValueNotNull(cmdInfo, ARGS_SYS_DEVICES) != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    params_->devices = cmdInfo.args[ARGS_SYS_DEVICES];
    if (params_->devices.empty()) {
        CmdLog::CmdErrorLog("Argument --sys-devices is empty,"
                            "Please enter a valid --sys-devices value.");
        return MSPROF_DAEMON_ERROR;
    }
    if (std::string(cmdInfo.args[ARGS_SYS_DEVICES]) == ALL) {
        return MSPROF_DAEMON_OK;
    }

    std::vector<std::string> devices = Utils::Split(cmdInfo.args[ARGS_SYS_DEVICES], false, "", ",");
    for (size_t i = 0; i < devices.size(); ++i) {
        if (!(ParamValidation::instance()->CheckDeviceIdIsValid(devices[i]))) {
            CmdLog::CmdErrorLog(
                "Argument --sys-devices: invalid value: %s."
                "Please input a valid device id.",
                devices[i].c_str());
            return MSPROF_DAEMON_ERROR;
        }
    }

    return MSPROF_DAEMON_OK;
}

/**
 * @brief  : Check task block is valid
 * @param  : [in] switchName : the switch name
 * @param  : [in] config : task block config
 * @return : MSPROF_DAEMON_OK: succ
 *           MSPROF_DAEMON_ERROR: failed
 */
int32_t InputParser::CheckTaskBlockValid(const std::string& switchName, const std::string& config) const
{
    if (!Platform::instance()->CheckIfSupport(PLATFORM_TASK_BLOCK)) {
        CmdLog::CmdErrorLog("Argument %s is not supported", switchName.c_str());
        MSPROF_LOGE("Argument %s is not supported", switchName.c_str());
        return MSPROF_DAEMON_ERROR;
    }

    if (config.compare(MSVP_PROF_OFF) != 0 && config.compare(MSVP_PROF_ON) != 0 && config.compare(MSVP_PROF_ALL) != 0) {
        std::string taskBlockRanges;
        const auto platformType = Platform::instance()->GetPlatformType();
        if (platformType == CHIP_CLOUD_V3 || platformType == CHIP_CLOUD_V3_LITE || platformType == CHIP_CLOUD_V4 ||
            Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_TASK_BLOCK_ON)) {
            taskBlockRanges = "'all', 'on', 'off'.";
        } else {
            taskBlockRanges = "'all', 'off'.";
        }
        CmdLog::CmdErrorLog(
            "Argument %s: invalid value: %s. Please input %s", switchName.c_str(), config.c_str(),
            taskBlockRanges.c_str());
        MSPROF_LOGE(
            "Argument %s: invalid value: %s. Please input %s", switchName.c_str(), config.c_str(),
            taskBlockRanges.c_str());
        return MSPROF_DAEMON_ERROR;
    }
    if (config.compare(MSVP_PROF_ON) == 0) {
        const auto platformType = Platform::instance()->GetPlatformType();
        if (platformType == CHIP_CLOUD_V3 || platformType == CHIP_CLOUD_V3_LITE || platformType == CHIP_CLOUD_V4 ||
            Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_TASK_BLOCK_ON)) {
            return MSPROF_DAEMON_OK;
        }
        CmdLog::CmdErrorLog(
            "The 'on' option is not supported on this platform, please use 'all' to collect block data.");
        MSPROF_LOGE("The 'on' option is not supported on this platform, please use 'all' to collect block data.");
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckArgRange(const struct MsprofCmdInfo& cmdInfo, int32_t opt, uint32_t min, uint32_t max) const
{
    if (CheckOptionValueNotNull(cmdInfo, opt) != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    if (Utils::CheckStringIsUnsignedIntNum(cmdInfo.args[opt])) {
        uint32_t optRet = std::stoul(cmdInfo.args[opt]);
        if ((optRet >= min) && (optRet <= max)) {
            return MSPROF_DAEMON_OK;
        } else {
            CmdLog::CmdErrorLog(
                "Argument --%s: invalid int value: %d."
                "Please input an integer value in %u-%u.",
                LONG_OPTIONS[opt].name, optRet, min, max);
            return MSPROF_DAEMON_ERROR;
        }
    } else {
        CmdLog::CmdErrorLog(
            "Argument --%s: invalid value: %s."
            "Please input an integer value in %u-%u.",
            LONG_OPTIONS[opt].name, cmdInfo.args[opt], min, max);
        return MSPROF_DAEMON_ERROR;
    }
}

int32_t InputParser::CheckArgsIsNumber(const struct MsprofCmdInfo& cmdInfo, int32_t opt) const
{
    if (CheckOptionValueNotNull(cmdInfo, opt) != MSPROF_DAEMON_OK) {
        return MSPROF_DAEMON_ERROR;
    }
    if (!Utils::CheckStringIsUnsignedIntNum(cmdInfo.args[opt])) {
        CmdLog::CmdErrorLog(
            "Argument --%s: invalid value: %s."
            "Please input an integer value.",
            LONG_OPTIONS[opt].name, cmdInfo.args[opt]);
        return MSPROF_DAEMON_ERROR;
    }
    return MSPROF_DAEMON_OK;
}

void InputParser::SetTaskTimeSwitch(const std::string timeSwitch)
{
    if (params_->taskTrace == OFF || params_->taskTime == OFF) {
        return;
    }
    params_->prof_level = (params_->prof_level.compare(OFF) == 0) ? timeSwitch : params_->prof_level;
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_STARS_ACSQ)) {
        params_->stars_acsq_task = ON;
    } else {
        params_->hwts_log = ON;
        params_->hwts_log1 = ON;
    }

    params_->ts_memcpy = ON;
}

void InputParser::ParamsSwitchValid3(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    switch (opt) {
        case ARGS_INSTR_PROFILING:
            params_->instrProfiling = cmdInfo.args[opt];
            break;
        case ARGS_HARDWARE_MEM:
            params_->hardware_mem = cmdInfo.args[opt];
            break;
        case ARGS_HCCL:
            CmdLog::CmdWarningLog("[Note] [hccl] This option will be discarded in later versions.");
            params_->hcclTrace = cmdInfo.args[opt];
            break;
        case ARGS_MODEL_EXECUTION:
            CmdLog::CmdWarningLog("[Note] [model-execution] This option will be discarded in later versions.");
            break;
        default:
            break;
    }
}

int32_t InputParser::MsprofSwitchCheckValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    int32_t ret = CheckArgOnOff(cmdInfo, opt);
    if (ret == MSPROF_DAEMON_OK) {
        ParamsSwitchValid(cmdInfo, opt);
        if (opt == ARGS_CPU_PROFILING) {
            ret = CheckSysCpu();
        }
    }
    return ret;
}

int32_t InputParser::CheckSysCpu()
{
    if (!Platform::instance()->RunSocSide()) {
        MSPROF_LOGI("In host side, --sys-cpu-profiling don't check perf.");
        return MSPROF_DAEMON_OK;
    }
    if (params_->cpu_profiling.compare(ON) == 0) {
        MSPROF_LOGI("Start the detection tool.");
        if (CheckHostSysToolsIsExist(TOOL_NAME_PERF, PROF_SCRIPT_PROF) != MSPROF_DAEMON_OK) {
            CmdLog::CmdErrorLog("The tool perf is invalid, please check"
                                " if the tool and sudo are available.");
            return MSPROF_DAEMON_ERROR;
        }
    }
    return MSPROF_DAEMON_OK;
}

int32_t InputParser::CheckMstxValid()
{
    if (params_->msproftx.compare(ON) != 0) {
        if (params_->mstxDomainInclude.empty() && params_->mstxDomainExclude.empty()) {
            return MSPROF_DAEMON_OK;
        } else {
            CmdLog::CmdErrorLog("Argument --mstx-domain-include/--mstx-domain-exclude "
                                "must be used with --msproftx=on.");
            return MSPROF_DAEMON_ERROR;
        }
    } else {
        if (!params_->mstxDomainInclude.empty() && !params_->mstxDomainExclude.empty()) {
            CmdLog::CmdErrorLog("Argument --mstx-domain-include and --mstx-domain-exclude "
                                "cannot be used at the same time.");
            return MSPROF_DAEMON_ERROR;
        }
        return MSPROF_DAEMON_OK;
    }
}

int32_t InputParser::MsprofFreqCheckValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    int32_t ret = MSPROF_DAEMON_OK;
    if (opt > NR_ARGS) {
        return MSPROF_DAEMON_ERROR;
    }
    switch (opt) {
        case ARGS_SYS_PERIOD:
            ret = CheckSysPeriodValid(cmdInfo);
            break;
        case ARGS_SYS_SAMPLING_FREQ:
        case ARGS_PID_SAMPLING_FREQ:
            // 1 - 10
            ret = CheckArgRange(cmdInfo, opt, 1, 10); // 10 : max length
            break;
        case ARGS_CPU_SAMPLING_FREQ:
        case ARGS_INTERCONNECTION_FREQ:
        case ARGS_HOST_SYS_USAGE_FREQ:
            // 1 - 50
            ret = CheckArgRange(cmdInfo, opt, 1, 50); // 50 : max length
            break;
        case ARGS_AIC_FREQ:
        case ARGS_AIV_FREQ:
        case ARGS_IO_SAMPLING_FREQ:
            // 1 - 100
            ret = CheckArgRange(cmdInfo, opt, 1, 100); // 100 : max length
            break;
        case ARGS_DVPP_FREQ:
            if (!Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_DVPP) &&
                !Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_DVPP_EX)) {
                CmdLog::CmdWarningLog("The argument: dvpp-freq is useless on this platform.");
                return ret;
            }
            // 1 - 100
            ret = CheckArgRange(cmdInfo, opt, 1, 100); // 100 : max length
            break;
        case ARGS_INSTR_PROFILING_FREQ:
            // 300 - 30000
            if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_INSTR_PROFILING)) {
                CmdLog::CmdWarningLog("The argument: instr-profiling-freq is useless on this platform.");
                return ret;
            }
            ret = CheckArgRange(cmdInfo, opt, INSTR_PROFILING_SAMPLE_FREQ_MIN, INSTR_PROFILING_SAMPLE_FREQ_MAX);
            break;
        default:
            ret = MsprofFreqCheckValidTwo(cmdInfo, opt);
            break;
    }

    if (ret == MSPROF_DAEMON_OK) {
        MsprofFreqUpdateParams(cmdInfo, opt);
    }
    return ret;
}

void InputParser::MsprofFreqUpdateParams(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    switch (opt) {
        case ARGS_INSTR_PROFILING_FREQ: {
            int32_t instrProfilingFreq = 0;
            FUNRET_CHECK_EXPR_ACTION(
                !Utils::StrToInt32(instrProfilingFreq, cmdInfo.args[opt]), return, "instrProfilingFreq %s is invalid",
                cmdInfo.args[opt]);
            params_->instrProfilingFreq = instrProfilingFreq;
        } break;
        case ARGS_SYS_PERIOD: {
            int32_t period = 0;
            FUNRET_CHECK_EXPR_ACTION(
                !Utils::StrToInt32(period, cmdInfo.args[opt]), return, "profiling_period %s is invalid",
                cmdInfo.args[opt]);
            params_->profiling_period = period;
        } break;
        case ARGS_EXPORT_ITERATION_ID:
            params_->exportIterationId = cmdInfo.args[opt];
            break;
        case ARGS_EXPORT_MODEL_ID:
            params_->exportModelId = cmdInfo.args[opt];
            break;
        default:
            MsprofFreqTransferParams(cmdInfo, opt);
            break;
    }
}

int32_t InputParser::MsprofHostCheckValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    int32_t ret = MSPROF_DAEMON_ERROR;
    if (opt > NR_ARGS) {
        return MSPROF_DAEMON_ERROR;
    }
    switch (opt) {
        case ARGS_HOST_SYS:
            ret = CheckHostSysValid(cmdInfo);
            break;
        case ARGS_HOST_SYS_PID:
            ret = CheckHostSysPidValid(cmdInfo);
            break;
        case ARGS_HOST_SYS_USAGE:
            ret = CheckHostSysUsageValid(cmdInfo);
            break;
        default:
            break;
    }
    return ret;
}

int32_t InputParser::MsprofDynamicCheckValid(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    int32_t ret = MSPROF_DAEMON_OK;
    switch (opt) {
        case ARGS_DYNAMIC_PROF:
            ret = CheckArgOnOff(cmdInfo, opt);
            break;
        case ARGS_DYNAMIC_PROF_PID:
            ret = CheckOptionValueNotNull(cmdInfo, opt);
            break;
        case ARGS_DELAY_PROF:
            ret = CheckArgRange(cmdInfo, opt, 1, PROF_MAX_DYNAMIC_TIME);
            break;
        case ARGS_DURATION_PROF:
            ret = CheckArgRange(cmdInfo, opt, 1, PROF_MAX_DYNAMIC_TIME);
            break;
        default:
            break;
    }
    if (ret == MSPROF_DAEMON_OK) {
        MsprofDynamicUpdateParams(cmdInfo, opt);
    }
    return ret;
}

void InputParser::MsprofDynamicUpdateParams(const struct MsprofCmdInfo& cmdInfo, int32_t opt)
{
    switch (opt) {
        case ARGS_DYNAMIC_PROF:
            params_->dynamic = cmdInfo.args[opt];
            break;
        case ARGS_DYNAMIC_PROF_PID:
            params_->pid = cmdInfo.args[opt];
            break;
        case ARGS_DELAY_PROF:
            params_->delayTime = cmdInfo.args[opt];
            break;
        case ARGS_DURATION_PROF:
            params_->durationTime = cmdInfo.args[opt];
            break;
        default:
            break;
    }
}

Args::Args(const std::string& name, const std::string& detail)
    : name_(name), detail_(detail), optional_(OSAL_OPTIONAL_ARG)
{}

Args::Args(const std::string& name, const std::string& detail, const std::string& defaultValue)
    : name_(name), defaultValue_(defaultValue), detail_(detail), optional_(OSAL_OPTIONAL_ARG)
{}

Args::Args(const std::string& name, const std::string& detail, const std::string& defaultValue, int32_t optional)
    : name_(name), defaultValue_(defaultValue), detail_(detail), optional_(optional)
{}

Args::~Args() {}

void Args::PrintHelp()
{
    std::string ifOptional = (optional_ == OSAL_OPTIONAL_ARG) ? "<Optional>" : "<Mandatory>";
    std::cout << std::right << std::setw(8) << "--";                // 8 space
    std::cout << std::left << std::setw(32) << name_ << ifOptional; // 32 space for option
    std::cout << " " << detail_ << std::endl << std::flush;
}

void Args::SetDetail(const std::string& detail) { detail_ = detail; }

ArgsManager::~ArgsManager() { argsList_.clear(); }

void ArgsManager::AddAicMetricsArgs()
{
    std::string option = "PipeUtilization";
    std::string pipExe = "";
    std::string l2Cache = "";
    std::string resource = "";
    std::string memoryAccess = "";
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_PEU_PMU)) {
        option = "PipelineExecuteUtilization";
        pipExe = ", PipelineExecuteUtilization";
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_L2_CACHE_PMU)) {
        l2Cache = ", L2Cache";
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_RCR_PMU)) {
        resource = ", ResourceConflictRatio";
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_MEMORY_ACCESS_PMU)) {
        memoryAccess = ", MemoryAccess";
    }
    Args aicMetricsArgs = {
        "aic-metrics",
        "The aic metrics groups, include ArithmeticUtilization, PipeUtilization" + pipExe + ", Memory, MemoryL0" +
            resource + ", MemoryUB" + l2Cache + memoryAccess + ".\n" + "\t\t\t\t\t\t   the default value is " + option +
            ".",
        option};
    argsList_.push_back(aicMetricsArgs);
}

void ArgsManager::AddAnalysisArgs()
{
    if (Platform::instance()->RunSocSide()) {
        return;
    }
    std::string typeDesc = "The export type, only used when argument `export` is on \n"
                           "\t\t\t\t\t\t   or when collecting data, include text, db.\n"
                           "\t\t\t\t\t\t   the default value is text.";
    if (Platform::instance()->CheckIfSupport(PLATFORM_EXPORT_TYPE)) {
        typeDesc = "The export type, only used when argument `export` is on \n"
                   "\t\t\t\t\t\t   or when collecting data, include text, db.\n"
                   "\t\t\t\t\t\t   the default value is text(which will also export the database).";
    }
    std::vector<Args> argsList;
    argsList = {
        {"python-path",
         "Specify the python interpreter path that is used for analysis, please ensure the python version"
         " is 3.7.5 or later."},
        {"parse", "Switch for using msprof to parse collecting data, the default value is off.", OFF},
        {"query", "Switch for using msprof to query collecting data, the default value is off.", OFF},
        {"export", "Switch for using msprof to export collecting data, the default value is off.", OFF},
        {"clear", "Switch for using msprof to analyze or export data in clear mode, the default value is off.", OFF},
        {"analyze", "Switch for using msprof to analyze collecting data, the default value is off.", OFF},
        {"rule", "Switch specified rule for using msprof to analyze collecting data, "
                 "include communication, communication_matrix.\n"
                 "\t\t\t\t\t\t   the default value is communication,communication_matrix."},
        {"iteration-id", "The export iteration id, only used when argument export is on, the default value is 1.", "1"},
        {"model-id",
         "The export model id, only used when argument export is on, "
         "msprof will export minimum accessible model by default.",
         "-1"},
        {"summary-format",
         "The export summary file format, only used when argument export is on, "
         "include csv, json, the default value is csv.",
         "csv"},
        {"type", typeDesc, "text"},
        {"reports", "Specify the path that is used for controlling the export scope of collecting results"}};
    argsList_.insert(argsList_.end(), argsList.begin(), argsList.end());
}

void ArgsManager::AddInstrArgs()
{
    if (Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_INSTR_PROFILING)) {
        Args instrProfiling = {"instr-profiling", "Show instr profiling data, the default value is off.", OFF};
        Args instrProfilingFreq = {
            "instr-profiling-freq",
            "The instr profiling sampling period in clock-cycle, "
            "the default value is 1000 cycle, the range is 300 to 30000 cycle.",
            "1000"};
        argsList_.push_back(instrProfiling);
        argsList_.push_back(instrProfilingFreq);
    } else if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_INSTR_PROFILING)) {
        Args instrProfiling = {"instr-profiling", "Show instr profiling data, the default value is off.", OFF};
        argsList_.push_back(instrProfiling);
    }
}

void ArgsManager::AddCpuArgs()
{
    Args cpu = Args(
        "sys-cpu-profiling",
        "The CPU acquisition switch, optional on / off,"
        "the default value is off.",
        OFF);
    if (Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_AICPU_HSCB)) {
        cpu.SetDetail("CPU and HSCB acquisition switch, optional on / off, the default value is off.");
    }
    Args cpuFreq = {
        "sys-cpu-freq",
        "The cpu sampling frequency in hertz. "
        "the default value is 50 Hz, the range is 1 to 50 Hz.",
        "50"};
    argsList_.push_back(cpu);
    argsList_.push_back(cpuFreq);
}

void ArgsManager::AddSysArgs()
{
    Args sysProfiling = {
        "sys-profiling",
        "The System CPU usage and system memory acquisition switch,"
        "the default value is off.",
        OFF};
    Args sysFreq = {
        "sys-sampling-freq",
        "The sys sampling frequency in hertz. "
        "the default value is 10 Hz, the range is 1 to 10 Hz.",
        "10"};
    Args pidProfiling = {
        "sys-pid-profiling",
        "The CPU usage of the process and the memory acquisition switch of the process,"
        "the default value is off.",
        OFF};
    Args pidFreq = {
        "sys-pid-sampling-freq",
        "The pid sampling frequency in hertz. "
        "the default value is 10 Hz, the range is 1 to 10 Hz.",
        "10"};
    argsList_.push_back(sysProfiling);
    argsList_.push_back(sysFreq);
    argsList_.push_back(pidProfiling);
    argsList_.push_back(pidFreq);
}

void ArgsManager::AddDvvpArgs()
{
    if (!Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_DVPP) &&
        !Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_DVPP_EX)) {
        return;
    }
    Args dvpp = {"dvpp-profiling", "DVPP acquisition switch, the default value is off.", OFF};
    Args dvppFreq = {
        "dvpp-freq",
        "DVPP acquisition frequency, range 1 ~ 100, "
        "the default value is 50, unit Hz.",
        "50"};
    argsList_.push_back(dvpp);
    argsList_.push_back(dvppFreq);
}

void ArgsManager::PrintMsopprofHelp() const
{
    if (!MsopprofManager::instance()->IsMsopprofExist()) {
        return;
    }
    std::cout << "This is subcommand for operator optimization situation:" << std::endl;
    const int optionWidth = 34;
    std::cout << "      ";
    std::cout << std::left << std::setw(optionWidth) << "op";
    std::cout << "Use binary msopprof to operator optimization (msprof op ...)" << std::endl << std::endl;
}

void ArgsManager::PrintHelp()
{
    std::cout << std::endl << "Usage:" << std::endl;
    std::cout << "      msprof [--options]" << std::endl << std::endl;
    PrintMsopprofHelp();
    std::cout << "Options:" << std::endl;
    for (auto args : argsList_) {
        args.PrintHelp();
    }
}

void ArgsManager::AddHostArgs()
{
    if (Platform::instance()->RunSocSide()) {
        return;
    }
#if (defined(_WIN32) || defined(_WIN64) || defined(_MSC_VER))
    return;
#endif
    Args hostSys = {
        "host-sys", "The host-sys data type, include cpu, mem, disk, network, osrt, numa, threads-sync, cache",
        HOST_SYS_CPU};
    Args hostSysPid = {
        "host-sys-pid", "Set the PID of the app process for "
                        "which you want to collect performance data."};
    Args hostSysUsage = {
        "host-sys-usage", "The host-sys-usage data type, include cpu, mem.(full-platform)", HOST_SYS_CPU};
    Args hostSysUsageFreq = {
        "host-sys-usage-freq", "The sampling frequency in hertz. the default value is 50 Hz the range is 1 to 50 Hz.",
        "50"};
    argsList_.push_back(hostSys);
    argsList_.push_back(hostSysPid);
    argsList_.push_back(hostSysUsage);
    argsList_.push_back(hostSysUsageFreq);
}

void ArgsManager::AddDynProfArgs()
{
    if (!Platform::instance()->CheckIfSupport(PLATFORM_TASK_DYNAMIC)) {
        return;
    }
    Args dynamic = {"dynamic", "Dynamic profiling switch, the default value is off.", OFF};
    Args pid = {"pid", "Dynamic profiling pids of the target processes"};
    argsList_.push_back(dynamic);
    argsList_.push_back(pid);
}

void ArgsManager::AddDelayDurationArgs()
{
    if (!Platform::instance()->CheckIfSupport(PLATFORM_TASK_DELAY_DURATION)) {
        return;
    }
    Args delay = {"delay", "Collect start delay time in seconds, range 1 ~ 4294967295s."};
    Args duration = {"duration", "Collection duration in seconds, range 1 ~ 4294967295s."};
    argsList_.push_back(delay);
    argsList_.push_back(duration);
}

void ArgsManager::AddScaleArgs()
{
    if (!Platform::instance()->CheckIfSupport(PLATFORM_TASK_SCALE)) {
        return;
    }
    Args opType = {
        "optype", "Customized operator type with the following format: "
                  "\"*,*\"."};
    argsList_.push_back(opType);
}

void ArgsManager::AddLowPowerArgs()
{
    if (!Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_LOW_POWER)) {
        return;
    }
    Args sysLpArgs = {"sys-lp", "Open low power profiling data config, the default value is on.", ON};
    Args sysLpFreqArgs = {
        "sys-lp-freq", "Config low power frequency, the default value is 100Hz, "
                       "the range is 1 to 100Hz."};
    argsList_.push_back(sysLpArgs);
    argsList_.push_back(sysLpFreqArgs);
}

void ArgsManager::AddArgs()
{
    AddStorageLimitArgs();
    AddHCCLArgs();
    AddModelExecutionArgs();
    AddAicMetricsArgs();
    AddAnalysisArgs();
    AddAicpuArgs();
    AddAivArgs();
    AddNtsMetricsArgs();
    AddHardWareMemArgs();
    AddCpuArgs();
    AddSysArgs();
    AddIoArgs();
    AddInstrArgs();
    AddInterArgs();
    AddDvvpArgs();
    AddL2Args();
    AddHostArgs();
    AddStarsArgs();
    AddLowPowerArgs();
    AddDynProfArgs();
    AddDelayDurationArgs();
    AddScaleArgs();
}

void ArgsManager::AddHardWareMemArgs()
{
    auto hardwareMem = Args("sys-hardware-mem", "", OFF);
    auto hardwareMemFreq = Args("sys-hardware-mem-freq", "", "50");
    if (Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_US)) {
        hardwareMem.SetDetail("QOS, HBM, LLC, SOC and mem acquisition switch, optional on / off, "
                              "the default value is off.");
        hardwareMemFreq.SetDetail(
            "QOS, HBM, LLC, SOC and mem acquisition frequency, "
            "range 1 ~ 10000 for QOS and SOC, 1 ~ 100 for HBM, LLC and mem, the default value is 50, unit Hz.");
    } else {
        hardwareMem.SetDetail("LLC, DDR, HBM acquisition switch, optional on / off, the default value is off.");
        hardwareMemFreq.SetDetail("LLC, DDR, HBM acquisition frequency, range 1 ~ 100, "
                                  "the default value is 50, unit Hz.");
    }
    auto llcProfiling = Args("llc-profiling", "", "capacity");
    llcProfiling.SetDetail("The llc profiling groups, include read, write. the default value is read.");
    argsList_.push_back(hardwareMem);
    argsList_.push_back(hardwareMemFreq);
    if (Platform::instance()->CheckIfSupport(PLATFORM_SYS_MEM_SERVICEFLOW)) {
        argsList_.push_back({"sys-mem-serviceflow", "The qos serviceflow group, based on user customized.", ""});
    }
    argsList_.push_back(llcProfiling);
}

ArgsManager::ArgsManager()
{
    std::string task_trace_ranges = Platform::instance()->CheckIfSupport(PLATFORM_TASK_TRACE_L3) ?
                                        "'l0', 'l1', 'l2', 'l3', 'on' or 'off'." :
                                        "'l0', 'l1', 'l2', 'on' or 'off'.";
    argsList_ = {
        {"output", "Specify the directory that is used for storing data results."},
        {"application",
         "Specify application path, considering the risk of privilege escalation, please pay attention to\n"
         "\t\t\t\t\t\t   the group of the application and confirm whether it is the same as the user currently.\n"
         "\t\t\t\t\t\t   [Note] This option will be discarded in later versions.\n"
         "\t\t\t\t\t\t   you can try to use: msprof [msprof arguments] <app> [app arguments].\n"
         "\t\t\t\t\t\t   [Note] Do not run an application that configures Profiling by calling aclprofInit or\n"
         "\t\t\t\t\t\t   aclprofStart in tool-based profiling. Only one Profiling configuration can exist at\n"
         "\t\t\t\t\t\t   a time; otherwise the application may fail with error 100042."},
        {"ascendcl", "Show acl profiling data, the default value is on.", ON},
        {"ge-api",
         "Specify if report GE event, the default value is off. "
         "The possible parameters are 'l0', 'l1' or 'off'.",
         OFF},
        {"runtime-api", "Show runtime api profiling data, the default value is off.", OFF},
        {"task-time",
         "Show task profiling data, the default value is on. "
         "The possible parameters are " +
             task_trace_ranges,
         ON},
        {"aicore-shape",
         "Collect AI Core operator shape data. This option takes effect only when task-time is l0. "
         "The possible values are 'on' and 'off', and the default value is off.",
         OFF},
        {"task-tsfw", "Specify the start of collection of ts management data, the default value is off.", OFF},
        {"task-memory",
         "Show the memory usage of the operator, the default value is off. "
         "The possible parameters are 'on' or 'off'.",
         ON},
        {"ai-core", "Turn on / off the ai core profiling, the default value is on when collecting app Profiling.", ON},
        {"aic-mode",
         "Set the aic profiling mode to task-based or sample-based.\n"
         "\t\t\t\t\t\t   In task-based mode, profiling data will be collected by tasks.\n"
         "\t\t\t\t\t\t   In sample-based mode, profiling data will be collected in a specific interval.\n"
         "\t\t\t\t\t\t   The default value is task-based in AI task mode, sample-based in system mode.",
         TASK_BASED},
        {"aic-freq",
         "The aic sampling frequency in hertz, "
         "the default value is 100 Hz, the range is 1 to 100 Hz.",
         "100"},
        {"environment", "User app custom environment variable configuration."},
        {"sys-period", "Set total sampling period of system profiling in seconds."},
        {"sys-devices", "Specify the profiling scope by device ID when collect sys profiling."
                        "The value is all or ID list (split with ',')."},
        {"msproftx", "Show msproftx and mstx data, the default value is off.", OFF},
        {"mstx-domain-include", "Choose to only include mstx events from a comma separated list of domains;\n"
                                "\t\t\t\t\t\t   `default` filters the mstx default domain;\n"
                                "\t\t\t\t\t\t   The switch is only applicable when parameter msproftx is set to on;\n"
                                "\t\t\t\t\t\t   The switch cannot be set with mstx-domain-exclude at the same time."},
        {"mstx-domain-exclude", "Choose to exclude mstx events from a comma separated list of domains;\n"
                                "\t\t\t\t\t\t   `default` excludes the mstx default domain;\n"
                                "\t\t\t\t\t\t   The switch is only applicable when parameter msproftx is set to on;\n"
                                "\t\t\t\t\t\t   The switch cannot be set with mstx-domain-include at the same time."}};
    AddArgs();
    Args help = {"help", "help message."};
    argsList_.push_back(help);
}

void ArgsManager::AddStarsArgs()
{
    if (!Platform::instance()->CheckIfSupport(PLATFORM_TASK_BLOCK)) {
        return;
    }
    std::string task_block_ranges;
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_CLOUD_V3 ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_CLOUD_V3_LITE ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_CLOUD_V4 ||
        Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_TASK_BLOCK_ON)) {
        task_block_ranges = "'all', 'on', 'off'.";
    } else {
        task_block_ranges = "'all', 'off'.";
    }
    Args fftsBlockArgs = {
        "task-block", "Show task block profiling data, the default value is off."
                      "The possible parameters are " +
                          task_block_ranges};
    argsList_.push_back(fftsBlockArgs);
}

void ArgsManager::AddStorageLimitArgs()
{
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_TYPE) {
        return;
    }
    Args storageLimitArgs = {"storage-limit", "Specify the output directory volume. range 200MB ~ 4294967295MB."};
    argsList_.push_back(storageLimitArgs);
}

void ArgsManager::AddHCCLArgs()
{
    constexpr char hcclArgName[] = "hccl";
    if (IsHiddenCliArg(hcclArgName)) {
        return;
    }
    Args hcclArgs = {
        hcclArgName,
        "Show hccl profiling data, the default value is off. "
        "[Note] This option will be discarded in later versions.",
        OFF};
    argsList_.push_back(hcclArgs);
}

void ArgsManager::AddModelExecutionArgs()
{
    constexpr char modelExecutionArgName[] = "model-execution";
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_TINY_V1 ||
        IsHiddenCliArg(modelExecutionArgName)) {
        return;
    }
    Args modelExecutionArgs = {
        modelExecutionArgName,
        "Show ge model execution profiling data, the default value is off. "
        "[Note] This option will be discarded in later versions.",
        OFF};
    argsList_.push_back(modelExecutionArgs);
}

void ArgsManager::AddAicpuArgs()
{
    constexpr char aicpuArgName[] = "aicpu";
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_TINY_V1 || IsHiddenCliArg(aicpuArgName)) {
        return;
    }
    Args aicpu = {aicpuArgName, "Show aicpu profiling data, the default value is off.", OFF};
    argsList_.push_back(aicpu);
}

void ArgsManager::AddAivArgs()
{
    if (!Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_AIV_INDEPENDENT_CONFIG)) {
        return;
    }
    Args aiv = {"ai-vector-core", "Turn on / off the ai vector core profiling, the default value is on.", ON};
    Args aivMode = {
        "aiv-mode",
        "Set the aiv profiling mode to task-based or sample-based.\n"
        "\t\t\t\t\t\t   In task-based mode, profiling data will be collected by tasks.\n"
        "\t\t\t\t\t\t   In sample-based mode, profiling data will be collected in a specific interval.\n"
        "\t\t\t\t\t\t   The default value is task-based in AI task mode, sample-based in system mode.",
        TASK_BASED};
    Args aivFreq = {
        "aiv-freq",
        "The aiv sampling frequency in hertz, "
        "the default value is 100 Hz, the range is 1 to 100 Hz.",
        "100"};
    Args aivMetrics = {
        "aiv-metrics",
        "The aiv metrics groups, "
        "include ArithmeticUtilization, PipeUtilization, "
        "Memory, MemoryL0, ResourceConflictRatio, MemoryUB.\n"
        "\t\t\t\t\t\t   the default value is PipeUtilization.",
        "PipeUtilization"};
    argsList_.push_back(aiv);
    argsList_.push_back(aivMode);
    argsList_.push_back(aivFreq);
    argsList_.push_back(aivMetrics);
}

void ArgsManager::AddNtsMetricsArgs()
{
    if (!Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_TASK_NTS)) {
        return;
    }
    Args ntsMetrics = {
        "nts-metrics", "The NTS metrics groups, include PipeUtilization or "
                       "Custom:<event-list>.\n"
                       "\t\t\t\t\t\t   Custom event list supports hexadecimal or decimal integers in the range "
                       "[0x0, 0x71b], separated by comma, up to 10 events."};
    argsList_.push_back(ntsMetrics);
}

void ArgsManager::AddIoArgs()
{
    constexpr char ioArgName[] = "sys-io-profiling";
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::DC_TYPE ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_TINY_V1 || IsHiddenCliArg(ioArgName)) {
        return;
    }
    Args ioArgs = {ioArgName, "NIC acquisition switch, the default value is off.", OFF};
    Args ioFreqArgs = {
        "sys-io-sampling-freq",
        "NIC acquisition frequency, range 1 ~ 100, "
        "the default value is 100, unit Hz.",
        "100"};

    if (ConfigManager::instance()->GetPlatformType() == PlatformType::CLOUD_TYPE ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_V4_1_0 ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_V3_TYPE) {
        ioArgs.SetDetail("NIC, ROCE acquisition switch, the default value is off.");
        ioFreqArgs.SetDetail("NIC, ROCE acquisition frequency, range 1 ~ 100, "
                             "the default value is 100, unit Hz.");
    }
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_CLOUD_V3 ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_CLOUD_V3_LITE) {
        ioArgs.SetDetail("UB acquisition switch, the default value is off.");
        ioFreqArgs.SetDetail("UB acquisition frequency, range 1 ~ 100, "
                             "the default value is 100, unit Hz.");
    }
    argsList_.push_back(ioArgs);
    argsList_.push_back(ioFreqArgs);
}

void ArgsManager::AddInterArgs()
{
    if (!Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_SYS_DEVICE_INTERCONNECTION)) {
        return;
    }
    Args interArgs = {"sys-interconnection-profiling", "PCIE, HCCS acquisition switch, the default value is off.", OFF};
    Args interFreq = {
        "sys-interconnection-freq",
        "PCIE, HCCS acquisition frequency, range 1 ~ 50, "
        "the default value is 50, unit Hz.",
        "50"};
    if (ConfigManager::instance()->GetPlatformType() != PlatformType::CLOUD_TYPE &&
        ConfigManager::instance()->GetPlatformType() != PlatformType::CHIP_V4_1_0) {
        interArgs = {"sys-interconnection-profiling", "PCIE acquisition switch, the default value is off.", OFF};
        interFreq = {
            "sys-interconnection-freq",
            "PCIE acquisition frequency, range 1 ~ 50, "
            "the default value is 50, unit Hz.",
            "50"};
    }
    if (Platform::instance()->CheckIfSupport(::Dvvp::Collect::Platform::PLATFORM_SYS_DEVICE_SIO_PA)) {
        interArgs.SetDetail("SIO and PA acquisition switch, the default value is off.");
        interFreq.SetDetail("SIO and PA acquisition frequency, range 1 ~ 50, "
                            "the default value is 50, unit Hz.");
    }
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_CLOUD_V3 ||
        ConfigManager::instance()->GetPlatformType() == PlatformType::CHIP_CLOUD_V3_LITE) {
        interArgs.SetDetail("PCIE, CCU, SIO and UB acquisition switch, the default value is off.");
        interFreq.SetDetail("PCIE, CCU, SIO and UB acquisition frequency, range 1 ~ 50, "
                            "the default value is 50, unit Hz.");
    }
    argsList_.push_back(interArgs);
    argsList_.push_back(interFreq);
}

void ArgsManager::AddL2Args()
{
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_TYPE) {
        return;
    }
    std::string noc = "";
    std::string smmu = "";
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_SOC_PMU_NOC)) {
        noc = " 4 parameters for NOC.";
    }
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_SOC_PMU)) {
        smmu = " and SMMU";
    }
    Args l2 = {"l2", "L2 Cache" + smmu + " acquisition switch. The default value is off.", OFF};
    Args npuEvents = {
        "npu-events",
        "Customize soc pmu parameters for collection. "
        "The input is hexadecimal number starting with 0x. Maximum of 8 parameters can be received for MATA and SMMU." +
            noc};
    argsList_.push_back(l2);
    argsList_.push_back(npuEvents);
}
} // namespace Msprof
} // namespace Dvvp
} // namespace Analysis
