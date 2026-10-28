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

#ifndef ARGPARSER_H
#define ARGPARSER_H
#include <functional>
#include <set>
#include <iomanip>
#include <string>
#include <map>
#include <unordered_map>
#include <vector>
#include "utils/utils_tool.h"

namespace analysis {
namespace dvvp {
namespace common {
namespace argparse {

const int32_t ARGPARSE_ERROR = -1;
const int32_t ARGPARSE_OK = 0;
const std::string LONG_PRE = "--";

struct Option {
    Option(
        std::string lname, std::string hp, std::string val, std::function<int32_t(std::string&)> checkFunc,
        std::vector<std::string> valRange)
        : longName(lname), help(hp), value(val), checkValidFunc(checkFunc), valueRange(valRange)
    {}
    std::string longName;
    std::string help;
    std::string value;
    std::function<int32_t(std::string&)> checkValidFunc;
    std::vector<std::string> valueRange;
};

class Argparser {
public:
    explicit Argparser(const std::string& description);
    ~Argparser() = default;

public:
    Argparser& SetProgramName(const std::string& name);
    Argparser& SetUsage(const std::string& usage);
    Argparser& AddOption(std::string lname, std::string help, std::string defaultValue);
    Argparser& AddOption(
        std::string lname, std::string help, std::string defaultValue,
        std::function<int32_t(std::string&)> checkValidFunc);
    Argparser& AddOption(
        std::string lname, std::string help, std::string defaultValue, std::vector<std::string> valueRange);
    Argparser& AddOption(
        std::string lname, std::string help, std::string defaultValue,
        std::function<int32_t(std::string&)> checkValidFunc, std::vector<std::string> valueRange);
    Argparser& AddRearAppSupport();
    std::string GetOption(const std::string& longName);
    Argparser& AddSubCommand(std::string commandName, Argparser& subcommand);
    Argparser& GetSubCommand(std::string commandName);
    Argparser& BindPreCheck(std::function<int32_t(void)> preCheckFunc);
    Argparser& BindExecute(std::function<int32_t(Argparser&)> executeFunc);
    Argparser& Parse(int32_t argc, const CHAR* argv[]);
    bool ParsedSuccess() const;
    std::string GetDescription();
    void PrintHelp();
    int32_t Execute();

public:
    std::vector<std::string> appArgs;
    std::string enabledSubCmd;

private:
    int32_t ProcessOptLong(int32_t argc, const CHAR* argv[]);
    void ProcessAppArgs(std::vector<std::string>& tokens);
    int32_t CheckOptionValue(Option& option) const;
    bool StartWith(const std::string& str, const std::string& prefix) const;
    std::string StringJoin(std::vector<std::string>& stringList, std::string sep) const;

private:
    std::string description_;
    std::string programName_;
    std::string usage_;
    std::vector<Option> options_;
    bool appSupported_{false};
    std::unordered_map<std::string, std::size_t> longNameIndex_;
    std::unordered_map<std::string, SHARED_PTR_ALIA<Argparser>> subcommands_;
    int32_t status_{ARGPARSE_ERROR};
    std::function<int32_t(void)> preCheckFunc_{nullptr};
    std::function<int32_t(Argparser&)> executeFunc_{nullptr};
};
} // namespace argparse
} // namespace common
} // namespace dvvp
} // namespace analysis
#endif
