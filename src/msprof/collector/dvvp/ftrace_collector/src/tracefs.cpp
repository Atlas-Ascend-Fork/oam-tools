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
#include "tracefs.h"

#include "ftrace_path.h"

#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>

#include "securec.h"

#include "ftrace_constants.h"
#include "ftrace_log.h"

namespace Ftrace {
namespace {
constexpr char TRACE_ROOT_PRIMARY[] = "/sys/kernel/tracing";
constexpr char TRACE_ROOT_FALLBACK[] = "/sys/kernel/debug/tracing";
constexpr char CLOCK_NAME[] = "mono_raw";

std::string Trim(const std::string& input)
{
    const size_t begin = input.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
        return "";
    }
    const size_t end = input.find_last_not_of(" \t\r\n");
    return input.substr(begin, end - begin + 1);
}

bool ParseUint64Text(const std::string& text, uint64_t& value)
{
    if (text.empty()) {
        return false;
    }
    try {
        size_t consumed = 0;
        const unsigned long long parsed = std::stoull(text, &consumed, kDecimalBase);
        if (consumed != text.size()) {
            return false;
        }
        value = static_cast<uint64_t>(parsed);
    } catch (const std::exception&) {
        return false;
    }
    return true;
}

std::string JsonEscape(const std::string& value)
{
    std::string out;
    out.reserve(value.size() + kJsonEscapeSlack);
    for (char chr : value) {
        switch (chr) {
            case '"':
                out += "\\\"";
                break;
            case '\\':
                out += "\\\\";
                break;
            case '\n':
                out += "\\n";
                break;
            case '\r':
                out += "\\r";
                break;
            case '\t':
                out += "\\t";
                break;
            default:
                out += chr;
                break;
        }
    }
    return out;
}

bool IsDir(const std::string& path)
{
    struct stat st {};
    return (stat(path.c_str(), &st) == 0) && S_ISDIR(st.st_mode);
}

bool IsFile(const std::string& path)
{
    struct stat st {};
    return (stat(path.c_str(), &st) == 0) && S_ISREG(st.st_mode);
}
} // namespace

bool TraceFs::DetectRoot(std::string& root)
{
    if (IsDir(TRACE_ROOT_PRIMARY)) {
        root = TRACE_ROOT_PRIMARY;
        return true;
    }
    if (IsDir(TRACE_ROOT_FALLBACK)) {
        root = TRACE_ROOT_FALLBACK;
        return true;
    }
    return false;
}

bool TraceFs::ReadText(const std::string& root, const std::string& relativePath, std::string& content)
{
    std::ifstream stream(CanonicalizeFilePath(root + "/" + relativePath));
    if (!stream.is_open()) {
        return false;
    }
    std::ostringstream buffer;
    buffer << stream.rdbuf();
    content = buffer.str();
    return true;
}

bool TraceFs::WriteText(const std::string& root, const std::string& relativePath, const std::string& value)
{
    std::ofstream stream(CanonicalizeFilePath(root + "/" + relativePath), std::ios::out | std::ios::trunc);
    if (!stream.is_open()) {
        return false;
    }
    stream << value;
    stream.flush();
    return stream.good();
}

bool TraceFs::CheckEvent(const std::string& root, const EventSpec& spec)
{
    const std::string dir = root + "/events/" + spec.system + "/" + spec.event;
    return IsDir(dir) && IsFile(dir + "/id") && IsFile(dir + "/format");
}

namespace {
// "field:unsigned short common_type; offset:0; size:2; signed:0;" -> one TraceEventField.
bool ParseFieldLine(const std::string& line, TraceEventField& field)
{
    const size_t nameBegin = strlen("field:");
    const size_t nameEnd = line.find(';', nameBegin);
    if (nameEnd == std::string::npos) {
        return false;
    }
    std::string decl = Trim(line.substr(nameBegin, nameEnd - nameBegin));
    const size_t lastSpace = decl.find_last_of(' ');
    if (lastSpace == std::string::npos) {
        field.cType = decl;
        field.name = decl;
    } else {
        field.cType = Trim(decl.substr(0, lastSpace));
        field.name = Trim(decl.substr(lastSpace + 1));
    }
    // "char prev_comm[16]" must become name=prev_comm, cType=char[16]: the bracket belongs
    // to the type, and the reference msprof.db stores the bare field name.
    const size_t bracket = field.name.find('[');
    if (bracket != std::string::npos) {
        field.cType += field.name.substr(bracket);
        field.name = field.name.substr(0, bracket);
    }
    const std::string rest = line.substr(nameEnd + 1);
    const size_t offsetPos = rest.find("offset:");
    const size_t sizePos = rest.find("size:");
    const size_t signedPos = rest.find("signed:");
    if (offsetPos == std::string::npos || sizePos == std::string::npos) {
        return false;
    }
    field.offset = atoi(rest.c_str() + offsetPos + strlen("offset:"));
    field.size = atoi(rest.c_str() + sizePos + strlen("size:"));
    field.isSigned =
        (signedPos == std::string::npos) ? true : (atoi(rest.c_str() + signedPos + strlen("signed:")) != 0);
    return true;
}
} // namespace

bool TraceFs::ParseFormat(const std::string& root, const EventSpec& spec, TraceEvent& event)
{
    std::string content;
    if (!ReadText(root, "events/" + spec.system + "/" + spec.event + "/format", content)) {
        return false;
    }
    event.system = spec.system;
    event.name = spec.event;
    event.formatHash = HashOf(content);
    event.fields.clear();

    std::istringstream lines(content);
    std::string line;
    while (std::getline(lines, line)) {
        const std::string trimmed = Trim(line);
        if (trimmed.rfind("field:", 0) != 0) {
            continue;
        }
        TraceEventField field;
        if (ParseFieldLine(trimmed, field)) {
            event.fields.emplace_back(field);
        }
    }
    std::string kernelId;
    if (ReadText(root, "events/" + spec.system + "/" + spec.event + "/id", kernelId)) {
        event.kernelId = atoi(Trim(kernelId).c_str());
    }
    return !event.fields.empty();
}

bool TraceFs::ReadCpuDrops(const std::string& root, int32_t cpu, uint64_t& drops)
{
    drops = 0;
    std::string content;
    if (!ReadText(root, "per_cpu/cpu" + std::to_string(cpu) + "/stats", content)) {
        return false;
    }
    static const char* lossKeys[] = {"overrun:", "commit overrun:", "dropped events:"};
    std::istringstream lines(content);
    std::string line;
    while (std::getline(lines, line)) {
        for (const char* key : lossKeys) {
            if (line.rfind(key, 0) == 0) {
                uint64_t value = 0;
                if (ParseUint64Text(Trim(line.substr(strlen(key))), value)) {
                    drops += value;
                }
            }
        }
    }
    return true;
}

bool TraceFs::SetClock(const std::string& root, const std::string& clock)
{
    return WriteText(root, "trace_clock", clock);
}

bool TraceFs::SetBufferSizeKb(const std::string& root, int32_t sizeKb)
{
    return WriteText(root, "buffer_size_kb", std::to_string(sizeKb));
}

namespace {
// tracing_cpumask only accepts the shape it prints itself: 32 bit words, eight hex digits
// each, highest word first, comma separated. A single 64 hex digit token (what a plain bitmap
// would look like on a 256 CPU machine) is rejected with EINVAL, and a rejected mask silently
// leaves the previous session's mask in place, which used to drop 248 of 256 CPUs.
std::string BuildTracingCpuMask(const std::vector<int32_t>& cpus)
{
    if (cpus.empty()) {
        return "";
    }
    int32_t maxCpu = 0;
    for (const auto cpu : cpus) {
        if (cpu > maxCpu) {
            maxCpu = cpu;
        }
    }
    const int32_t words = maxCpu / kBitsPerWord + 1;
    std::vector<uint32_t> values(static_cast<size_t>(words), 0U);
    for (const auto cpu : cpus) {
        if (cpu < 0) {
            continue;
        }
        const size_t word = static_cast<size_t>(cpu / kBitsPerWord);
        values[word] |= (1U << (static_cast<uint32_t>(cpu) % kBitsPerWord));
    }
    std::string mask;
    for (int32_t idx = words - 1; idx >= 0; --idx) {
        char group[kHashHexBufLen] = {0};
        if (snprintf_s(group, sizeof(group), sizeof(group) - 1, "%08x", values[static_cast<size_t>(idx)]) < 0) {
            return "";
        }
        if (!mask.empty()) {
            mask += ",";
        }
        mask += group;
    }
    return mask;
}
} // namespace

bool TraceFs::SetCpuMask(const std::string& root, const std::string& mask)
{
    if (mask.empty()) {
        return true;
    }
    return WriteText(root, "tracing_cpumask", mask);
}

bool TraceFs::EnableEvents(const std::string& root, const std::vector<EventSpec>& specs)
{
    // clear previous selection, then enable one by one so that a single bad event is visible
    (void)WriteText(root, "events/enable", "0");
    (void)WriteText(root, "set_event", "");
    for (const auto& spec : specs) {
        const std::string enablePath = "events/" + spec.system + "/" + spec.event + "/enable";
        if (!WriteText(root, enablePath, "1")) {
            return false;
        }
    }
    return true;
}

bool TraceFs::Prepare(
    const std::string& root, const Options& options, const std::vector<EventSpec>& specs,
    const std::vector<int32_t>& cpus)
{
    (void)WriteText(root, "tracing_on", "0");
    // a previous run may have died before Clear(), normalise the global switch
    (void)WriteText(root, "events/enable", "0");
    (void)WriteText(root, "current_tracer", "nop");
    if (!SetClock(root, CLOCK_NAME)) {
        FtraceLog::Instance().Write("error", "write trace_clock failed");
        return false;
    }
    if (!SetBufferSizeKb(root, options.bufferSizeKb)) {
        FtraceLog::Instance().Write("error", "write buffer_size_kb failed");
        return false;
    }
    // Always normalize tracing_cpumask: -M wins when given, otherwise the mask follows the
    // selected CPUs. A mask left over from a previous run would silently collect nothing.
    const std::string cpuMask = options.cpuMask.empty() ? BuildTracingCpuMask(cpus) : options.cpuMask;
    if (!SetCpuMask(root, cpuMask)) {
        // Without a working mask the kernel keeps an older one, which silently drops CPUs.
        FtraceLog::Instance().Write("error", "write tracing_cpumask failed: " + cpuMask);
        return false;
    }
    if (!EnableEvents(root, specs)) {
        FtraceLog::Instance().Write("error", "enable events failed");
        return false;
    }
    (void)Clear(root);
    return true;
}

bool TraceFs::Start(const std::string& root) { return WriteText(root, "tracing_on", "1"); }

bool TraceFs::Stop(const std::string& root) { return WriteText(root, "tracing_on", "0"); }

bool TraceFs::Clear(const std::string& root) { return WriteText(root, "trace", ""); }

std::string TraceFs::HashOf(const std::string& content)
{
    // FNV-1a 64bit, enough for format drift detection
    uint64_t hash = 1469598103934665603ULL;
    for (unsigned char chr : content) {
        hash ^= static_cast<uint64_t>(chr);
        hash *= 1099511628211ULL;
    }
    char buf[kHashHexBufLen] = {0};
    if (snprintf_s(buf, sizeof(buf), sizeof(buf) - 1, "%016llx", static_cast<unsigned long long>(hash)) < 0) {
        return "";
    }
    return std::string(buf);
}

namespace {
// "sources" lists the distinct subsystems once; "types" carries one entry per event.
void WriteSourceList(std::ofstream& out, const std::vector<EventSpec>& specs)
{
    out << "  \"sources\": [\n";
    std::vector<std::string> systems;
    for (const auto& spec : specs) {
        bool seen = false;
        for (const auto& item : systems) {
            seen = seen || (item == spec.system);
        }
        if (!seen) {
            systems.emplace_back(spec.system);
        }
    }
    for (size_t idx = 0; idx < systems.size(); ++idx) {
        out << "    {\"system\": \"" << JsonEscape(systems[idx]) << "\", \"group\": 1}"
            << (idx + 1 == systems.size() ? "\n" : ",\n");
    }
    out << "  ],\n  \"types\": [\n";
}

void WriteTypeList(std::ofstream& out, const std::string& root, const std::vector<EventSpec>& specs)
{
    bool firstType = true;
    for (const auto& spec : specs) {
        TraceEvent event;
        if (!TraceFs::ParseFormat(root, spec, event)) {
            FtraceLog::Instance().Write("warn", "parse format failed: " + spec.FullName());
            continue;
        }
        if (!firstType) {
            out << ",\n";
        }
        firstType = false;
        std::string formatText;
        (void)TraceFs::ReadText(root, "events/" + event.system + "/" + event.name + "/format", formatText);
        out << "    {\"system\": \"" << JsonEscape(event.system) << "\", \"name\": \"" << JsonEscape(event.name)
            << "\", \"kernelId\": " << event.kernelId << ", \"formatHash\": \"" << event.formatHash
            << "\", \"format\": \"" << JsonEscape(formatText) << "\", \"fields\": [";
        for (size_t fidx = 0; fidx < event.fields.size(); ++fidx) {
            const auto& field = event.fields[fidx];
            out << "{\"name\": \"" << JsonEscape(field.name) << "\", \"cType\": \"" << JsonEscape(field.cType)
                << "\", \"offset\": " << field.offset << ", \"size\": " << field.size
                << ", \"signed\": " << (field.isSigned ? 1 : 0) << "}";
            out << (fidx + 1 == event.fields.size() ? "" : ", ");
        }
        out << "]}\n";
    }
}

// One /proc/<pid>/task/<tid>/status snapshot.
struct ThreadStatus {
    std::string tgid;
    std::string comm;
    std::string nspid;
};

bool ReadThreadStatus(const std::string& statusPath, ThreadStatus& status)
{
    std::ifstream in(CanonicalizeFilePath(statusPath));
    if (!in.is_open()) {
        return false;
    }
    std::string line;
    while (std::getline(in, line)) {
        if (line.rfind("Name:", 0) == 0) {
            status.comm = Trim(line.substr(strlen("Name:")));
        } else if (line.rfind("Tgid:", 0) == 0) {
            status.tgid = Trim(line.substr(strlen("Tgid:")));
        } else if (line.rfind("NSpid:", 0) == 0) {
            status.nspid = Trim(line.substr(strlen("NSpid:")));
        }
    }
    return !status.tgid.empty();
}

// Writes every thread of one process. ftrace's common_pid is a TID, so worker threads have to be
// listed as well; writing them here keeps the caller a plain directory walk.
void WriteProcessThreads(std::ofstream& out, const std::string& procDir, bool& first)
{
    const std::string taskDir = procDir + "/task";
    DIR* tasks = opendir(taskDir.c_str());
    if (tasks == nullptr) {
        return;
    }
    struct dirent* entry = nullptr;
    while ((entry = readdir(tasks)) != nullptr) {
        if (entry->d_name[0] < '0' || entry->d_name[0] > '9') {
            continue;
        }
        ThreadStatus status;
        if (!ReadThreadStatus(taskDir + "/" + entry->d_name + "/status", status)) {
            continue;
        }
        if (!first) {
            out << ",\n";
        }
        first = false;
        out << "    {\"tid\": " << entry->d_name << ", \"tgid\": " << status.tgid << ", \"comm\": \""
            << JsonEscape(status.comm) << "\", \"nspid\": \"" << JsonEscape(status.nspid) << "\"}";
    }
    closedir(tasks);
}

} // namespace

bool TraceFs::WriteEventMetaJson(
    const std::string& root, const std::vector<EventSpec>& specs, size_t pageSize, size_t pageDataOffset,
    const std::string& path)
{
    std::string kernel;
    (void)ReadText(root, "..", kernel); // not used, keep empty
    std::string clock;
    (void)ReadText(root, "trace_clock", clock);

    std::ofstream out(CanonicalizeFilePath(path));
    if (!out.is_open()) {
        return false;
    }
    out << "{\n";
    out << "  \"clock\": \"" << JsonEscape(CLOCK_NAME) << "\",\n";
    out << "  \"pageSize\": " << pageSize << ",\n";
    out << "  \"pageDataOffset\": " << pageDataOffset << ",\n";
    // Ring buffer event lengths are kernel dependent. The collector runs on the same kernel
    // as the trace it produces, so the values it counted with are recorded here and the
    // parser reads them back instead of hard coding one kernel version.
    out << "  \"ringbuf\": {\"timeExtendLen\": " << kTimeExtendLen << ", \"timeStampLen\": " << kTimeStampLen << "},\n";
    WriteSourceList(out, specs);
    WriteTypeList(out, root, specs);
    out << "  ]\n}\n";
    return out.good();
}

bool TraceFs::WriteThreadMapJson(const std::string& path, uint64_t snapshotStartNs, uint64_t snapshotEndNs)
{
    std::ofstream out(CanonicalizeFilePath(path));
    if (!out.is_open()) {
        return false;
    }
    out << "{\n  \"snapshotStart\": " << snapshotStartNs << ",\n  \"snapshotEnd\": " << snapshotEndNs
        << ",\n  \"threads\": [\n";
    DIR* proc = opendir("/proc");
    if (proc == nullptr) {
        return false;
    }
    bool first = true;
    struct dirent* entry = nullptr;
    while ((entry = readdir(proc)) != nullptr) {
        if (entry->d_name[0] < '0' || entry->d_name[0] > '9') {
            continue;
        }
        WriteProcessThreads(out, std::string("/proc/") + entry->d_name, first);
    }
    closedir(proc);
    out << "\n  ]\n}\n";
    return out.good();
}
} // namespace Ftrace
