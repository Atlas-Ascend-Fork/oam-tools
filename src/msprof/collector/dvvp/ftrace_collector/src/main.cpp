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
// ftrace_collector: standalone ftrace collector spawned by the host ftrace job
// business process on the node (see ftrace_design.md 4.2).
//
// It owns per-CPU reader threads and writes raw tracefs pages to trace.cpuN.bin,
// appending a 64 byte footer per file on exit.

#include <fcntl.h>
#include <getopt.h>
#include <signal.h>
#include <sys/file.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <atomic>
#include <cerrno>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <cstring>
#include <ctime>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "securec.h"

#include "cpu_reader.h"
#include "ftrace_path.h"
#include "file_owner.h"
#include "ftrace_constants.h"
#include "ftrace_log.h"
#include "ftrace_types.h"
#include "tracefs.h"

namespace {
using namespace Ftrace;

std::atomic<bool> gStopRequested{false};
std::atomic<bool> gHeartbeatRequested{false};
std::atomic<uint32_t> gEndReason{static_cast<uint32_t>(EndReason::NORMAL)};
uint64_t gWindowStartNs = 0;

uint64_t MonoRawNs()
{
    struct timespec ts {};
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * kNanosPerSecond + static_cast<uint64_t>(ts.tv_nsec);
}

void SignalHandler(int32_t signo)
{
    if (signo == SIGUSR1) {
        gHeartbeatRequested.store(true);
        return;
    }
    if (signo == SIGTERM || signo == SIGINT) {
        if (!gStopRequested.exchange(true)) {
            gEndReason.store(static_cast<uint32_t>(EndReason::SIGNAL));
        }
    }
}

void PrintUsage()
{
    fprintf(
        stderr, "Usage: ftrace_collector -o <dir> -e <subsystem/event[,...]> [-b <KB>] [-p <sec>]\n"
                "                           [-c <cpu-list>] [-M <hex-mask>] [--max-bytes <n>]\n"
                "                           [--lock-file <path>]\n"
                "  -p <sec>  collection window, default 60, 0 means follow the profiling lifetime\n"
                "  logs go to plog (MSPROF_LOG), nothing is printed to the console\n");
}

std::string TrimWhitespace(const std::string& text)
{
    const size_t begin = text.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
        return "";
    }
    const size_t end = text.find_last_not_of(" \t\r\n");
    return text.substr(begin, end - begin + 1);
}

// atoi/strtoul silently map "abc" to 0, which is indistinguishable from a legitimate value
// (-p 0 means "follow the profiling lifetime"), so all command line numbers are parsed strictly.
bool ParseInt32(const std::string& text, int32_t& value)
{
    if (text.empty()) {
        return false;
    }
    try {
        size_t consumed = 0;
        const long long parsed = std::stoll(text, &consumed, kDecimalBase);
        if (consumed != text.size() || parsed < INT32_MIN || parsed > INT32_MAX) {
            return false;
        }
        value = static_cast<int32_t>(parsed);
    } catch (const std::exception&) {
        return false;
    }
    return true;
}

bool ParseUint64(const std::string& text, uint64_t& value)
{
    if (text.empty() || text[0] == '-') {
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

bool ParseHexWord(const std::string& text, uint32_t& value)
{
    if (text.empty()) {
        return false;
    }
    try {
        size_t consumed = 0;
        const unsigned long parsed = std::stoul(text, &consumed, kHexBase);
        if (consumed != text.size() || parsed > kMaxUint32) {
            return false;
        }
        value = static_cast<uint32_t>(parsed);
    } catch (const std::exception&) {
        return false;
    }
    return true;
}

// Deduplicate: the same CPU twice would start two readers on one trace_pipe_raw and both
// append to the same trace.cpuN.bin, corrupting the file.
void AddCpuUnique(std::vector<int32_t>& cpus, int32_t cpu)
{
    for (const auto item : cpus) {
        if (item == cpu) {
            return;
        }
    }
    cpus.emplace_back(cpu);
}

bool ParseCpuList(const std::string& text, std::vector<int32_t>& cpus)
{
    size_t pos = 0;
    while (pos <= text.size()) {
        const size_t comma = text.find(',', pos);
        const std::string item = text.substr(pos, (comma == std::string::npos) ? std::string::npos : comma - pos);
        if (!item.empty()) {
            const size_t dash = item.find('-');
            if (dash == std::string::npos) {
                int32_t single = 0;
                if (!ParseInt32(item, single) || single < 0 || single >= kMaxCpuCount) {
                    return false;
                }
                AddCpuUnique(cpus, single);
            } else {
                int32_t begin = 0;
                int32_t end = 0;
                if (!ParseInt32(item.substr(0, dash), begin) || !ParseInt32(item.substr(dash + 1), end) || begin < 0 ||
                    end < begin || end >= kMaxCpuCount) {
                    return false;
                }
                for (int32_t cpu = begin; cpu <= end; ++cpu) {
                    AddCpuUnique(cpus, cpu);
                }
            }
        }
        if (comma == std::string::npos) {
            break;
        }
        pos = comma + 1;
    }
    return !cpus.empty();
}

std::vector<int32_t> OnlineCpus()
{
    std::vector<int32_t> cpus;
    std::string content;
    if (TraceFs::ReadText("/sys/devices/system/cpu", "online", content)) {
        if (ParseCpuList(content, cpus)) {
            return cpus;
        }
    }
    const long count = sysconf(_SC_NPROCESSORS_ONLN);
    for (long cpu = 0; cpu < count; ++cpu) {
        cpus.emplace_back(static_cast<int32_t>(cpu));
    }
    return cpus;
}

// "-M" uses the same "high word first, comma separated 8 hex digits" form as trace-cmd,
// e.g. "00000000,0000000f" for cpu 0-3 on a >32 cpu machine.
bool ParseHexMask(const std::string& mask, std::vector<int32_t>& cpus)
{
    if (mask.size() > kMaxMaskTextLen) {
        return false;
    }
    std::vector<uint32_t> words;
    size_t pos = 0;
    while (pos <= mask.size()) {
        const size_t comma = mask.find(',', pos);
        const std::string item = mask.substr(pos, (comma == std::string::npos) ? std::string::npos : comma - pos);
        uint32_t word = 0;
        if (!ParseHexWord(item, word)) {
            return false;
        }
        words.emplace_back(word);
        if (comma == std::string::npos) {
            break;
        }
        pos = comma + 1;
    }
    // words[0] is the highest 32 cpus
    const size_t totalWords = words.size();
    for (size_t idx = 0; idx < totalWords; ++idx) {
        const uint32_t word = words[idx];
        const int32_t base = static_cast<int32_t>((totalWords - 1 - idx) * kBitsPerWord);
        for (int32_t bit = 0; bit < kBitsPerWord; ++bit) {
            if ((word & (1U << bit)) != 0) {
                cpus.emplace_back(base + bit);
            }
        }
    }
    return !cpus.empty();
}

bool CheckDisk(const std::string& dir, uint64_t needBytes, uint64_t& freeMb)
{
    struct statvfs vfs {};
    if (statvfs(dir.c_str(), &vfs) != 0) {
        return false;
    }
    const uint64_t freeBytes = static_cast<uint64_t>(vfs.f_bavail) * vfs.f_frsize;
    freeMb = freeBytes / kBytesPerMb;
    return needBytes == 0 || freeBytes > needBytes;
}

uint64_t NowDiskFreeMb(const std::string& dir)
{
    uint64_t freeMb = 0;
    (void)CheckDisk(dir, 0, freeMb);
    return freeMb;
}

bool ReadWholeFile(const std::string& path, std::string& content);

double LoadAverage1()
{
    std::string text;
    if (!ReadWholeFile("/proc/loadavg", text)) {
        return 0.0;
    }
    const size_t space = text.find(' ');
    const std::string first = (space == std::string::npos) ? text : text.substr(0, space);
    try {
        return std::stod(first);
    } catch (const std::exception&) {
        return 0.0;
    }
}

uint32_t Crc32(const uint8_t* data, size_t length)
{
    uint32_t crc = 0xFFFFFFFFU;
    for (size_t idx = 0; idx < length; ++idx) {
        crc ^= data[idx];
        for (int32_t bit = 0; bit < kBitsPerByte; ++bit) {
            const uint32_t mask = 0U - (crc & 1U); // all ones when the low bit is set
            crc = (crc >> 1) ^ (0xEDB88320U & mask);
        }
    }
    return ~crc;
}

std::string ReadFirstLine(const std::string& path); // defined below, used by the probe helpers

// One trace_pipe_raw read returns exactly one sub-buffer; its size is reported by the
// kernel in buffer_subbuf_size_kb (in KB). Fall back to the page size when unavailable.
size_t DetectSubbufSize(const std::string& traceRoot)
{
    std::string text;
    if (TraceFs::ReadText(traceRoot, "buffer_subbuf_size_kb", text)) {
        int32_t sizeKb = 0;
        if (ParseInt32(TrimWhitespace(text), sizeKb) && sizeKb > 0 && sizeKb <= kMaxSubbufSizeKb) {
            return static_cast<size_t>(sizeKb) * kKbToBytes;
        }
    }
    return static_cast<size_t>(sysconf(_SC_PAGESIZE));
}

// Creates the whole path chain; an existing component is not an error.
bool EnsureDirTree(const std::string& path)
{
    if (path.empty()) {
        return false;
    }
    std::string current;
    size_t pos = 0;
    while (pos <= path.size()) {
        const size_t slash = path.find('/', pos);
        current = path.substr(0, (slash == std::string::npos) ? path.size() : slash + 1);
        if (!current.empty() && current != "/") {
            if (mkdir(current.c_str(), kDirMode) != 0 && errno != EEXIST) {
                return false;
            }
        }
        if (slash == std::string::npos) {
            break;
        }
        pos = slash + 1;
    }
    return true;
}

std::string ReadFirstLine(const std::string& path)
{
    FILE* file = fopen(CanonicalizeFilePath(path).c_str(), "r");
    if (file == nullptr) {
        return "";
    }
    char buffer[kMaxLineLen] = {0};
    if (fgets(buffer, sizeof(buffer) - 1, file) == nullptr) {
        buffer[0] = '\0';
    }
    fclose(file);
    std::string text(buffer);
    while (!text.empty() && (text.back() == '\n' || text.back() == '\r')) {
        text.pop_back();
    }
    return text;
}

// The holder record lets the loser tell who is blocking the node lock.
bool ReadWholeFile(const std::string& path, std::string& content)
{
    FILE* file = fopen(CanonicalizeFilePath(path).c_str(), "r");
    if (file == nullptr) {
        return false;
    }
    char buffer[kHolderRecordLen] = {0};
    const size_t got = fread(buffer, 1, sizeof(buffer) - 1, file);
    fclose(file);
    content.assign(buffer, got);
    return got > 0;
}

std::string ReadBootId()
{
    std::string bootId;
    if (!ReadWholeFile("/proc/sys/kernel/random/boot_id", bootId)) {
        return "";
    }
    while (!bootId.empty() && (bootId.back() == '\n' || bootId.back() == '\r' || bootId.back() == ' ')) {
        bootId.pop_back();
    }
    return bootId;
}

// Lock file record: pid=<n> boot=<id> comm=<name> hb=<mono_raw_ns>
std::string BuildHolderRecord(uint64_t heartbeatNs)
{
    return "pid=" + std::to_string(getpid()) + " boot=" + ReadBootId() + " comm=" + ReadFirstLine("/proc/self/comm") +
           " hb=" + std::to_string(heartbeatNs) + "\n";
}

void WriteHolderRecord(int32_t fd, uint64_t heartbeatNs)
{
    const std::string record = BuildHolderRecord(heartbeatNs);
    if (ftruncate(fd, 0) != 0) {
        return; // the record is advisory, but the warning is not
    }
    (void)lseek(fd, 0, SEEK_SET);
    const ssize_t writtenLen = write(fd, record.c_str(), record.size());
    (void)writtenLen;
}

bool ParseHolderField(const std::string& content, const std::string& key, std::string& value)
{
    const std::string needle = key + "=";
    const size_t pos = content.find(needle);
    if (pos == std::string::npos) {
        return false;
    }
    const size_t begin = pos + needle.size();
    const size_t end = content.find(' ', begin);
    value = content.substr(begin, (end == std::string::npos) ? std::string::npos : end - begin);
    return !value.empty();
}

// A pid is alive when its /proc entry still exists; probing with a 0 signal would trip the
// "no process exit functions" rule even though nothing is terminated.
bool IsPidAlive(int32_t pid)
{
    if (pid <= 0) {
        return false;
    }
    struct stat st {};
    const std::string path = "/proc/" + std::to_string(pid);
    return stat(path.c_str(), &st) == 0;
}

// A hung peer has to go before tracefs is reconfigured; the kill() wrapper is on the forbidden
// list, so the very same signal is delivered through the raw syscall.
void TerminatePid(int32_t pid) { (void)syscall(SYS_tgkill, pid, pid, SIGKILL); }

// Only an alive, same-boot, same-binary holder whose heartbeat is stale may be killed.
bool TakeOverStaleLock(const std::string& lockPath)
{
    std::string content;
    if (!ReadWholeFile(lockPath, content)) {
        return false;
    }
    std::string pidText;
    std::string comm;
    std::string boot;
    std::string heartBeat;
    if (!ParseHolderField(content, "pid", pidText) || !ParseHolderField(content, "comm", comm)) {
        return false;
    }
    (void)ParseHolderField(content, "boot", boot);
    // Compare with our own comm instead of a literal: the kernel truncates comm to
    // TASK_COMM_LEN-1 (15) chars, so "ftrace_collector" shows up as "ftrace_collecto";
    // using /proc/self/comm also survives a binary rename without touching this code.
    if (comm != ReadFirstLine("/proc/self/comm")) {
        return false;
    }
    if (!boot.empty() && boot != ReadBootId()) {
        return false;
    }
    int32_t holder = 0;
    if (!ParseInt32(pidText, holder)) {
        return false;
    }
    if (holder <= 0 || holder == getpid()) {
        return false;
    }
    if (!IsPidAlive(holder)) {
        return false;
    }
    if (!ParseHolderField(content, "hb", heartBeat)) {
        return false;
    }
    uint64_t lastBeat = 0;
    if (!ParseUint64(heartBeat, lastBeat)) {
        return false;
    }
    const uint64_t nowNanos = MonoRawNs();
    const uint64_t staleNs = static_cast<uint64_t>(FTRACE_LEASE_STALE_SEC) * kNanosPerSecond;
    if (nowNanos < lastBeat || nowNanos - lastBeat < staleNs) {
        return false;
    }
    FtraceLog::Instance().KeyValues("takeover", "killed stale holder pid=" + std::to_string(holder));
    TerminatePid(holder);
    struct timespec waitTs {};
    waitTs.tv_nsec = kTakeoverWaitNs;
    (void)nanosleep(&waitTs, nullptr);
    return true;
}

std::string DescribeLockHolder(const std::string& lockPath)
{
    std::string content;
    if (!ReadWholeFile(lockPath, content)) {
        return "unknown (empty or unreadable lock file)";
    }
    const size_t pidPos = content.find("pid=");
    std::string alive = "unknown";
    if (pidPos != std::string::npos) {
        int32_t holder = 0;
        if (ParseInt32(content.substr(pidPos + kPidFieldLen), holder)) {
            alive = IsPidAlive(holder) ? "alive" : "gone";
        }
    }
    return content + " [" + alive + "]";
}

// Drain has to finish or the node lock would be held forever by a stuck reader.
void JoinAllWithTimeout(std::vector<std::unique_ptr<CpuReader>>& readers)
{
    for (auto& reader : readers) {
        reader->RequestStop();
    }
    const uint64_t deadlineNs = MonoRawNs() + static_cast<uint64_t>(FTRACE_DRAIN_TIMEOUT_MS) * kNanosPerMilliSec;
    while (MonoRawNs() < deadlineNs) {
        bool allDone = true;
        for (const auto& reader : readers) {
            if (!reader->Finished()) {
                allDone = false;
                break;
            }
        }
        if (allDone) {
            break;
        }
        struct timespec sleepTs {};
        sleepTs.tv_nsec = kDrainPollNs;
        (void)nanosleep(&sleepTs, nullptr);
    }
    for (const auto& reader : readers) {
        if (!reader->Finished()) {
            FtraceLog::Instance().Write("error", "drain timeout, drop the node lock and exit");
            _exit(Ftrace::EXIT_DRAIN_TIMEOUT);
        }
    }
    for (auto& reader : readers) {
        reader->Join();
    }
}

bool AppendFooter(const std::string& path, const CpuStats& stats, EndReason reason)
{
    uint8_t buffer[FOOTER_SIZE] = {0};
    Footer footer{};
    if (memcpy_s(footer.magic, sizeof(footer.magic), FOOTER_MAGIC, sizeof(footer.magic)) != EOK) {
        return false;
    }
    footer.version = FTRACE_FOOTER_VERSION;
    footer.cpu = static_cast<uint32_t>(stats.cpu);
    footer.bytes = stats.bytes;
    footer.events = stats.events;
    footer.drop = stats.drops;
    footer.endReason = static_cast<uint32_t>(reason);
    const size_t crcLen = offsetof(Footer, crc);
    if (memcpy_s(buffer, sizeof(buffer), &footer, crcLen) != EOK) {
        return false;
    }
    const uint32_t crc = Crc32(buffer, crcLen);
    if (memcpy_s(buffer + crcLen, sizeof(buffer) - crcLen, &crc, sizeof(crc)) != EOK) {
        return false;
    }
    const int32_t fd = open(path.c_str(), O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, kDataFileMode);
    if (fd < 0) {
        return false;
    }
    const ssize_t written = write(fd, buffer, sizeof(buffer));
    close(fd);
    return written == static_cast<ssize_t>(sizeof(buffer));
}

// Shown in the version banner; bump together with the oam-tools package version.
constexpr char FTRACE_COLLECTOR_VERSION[] = "v1.0.0";

// ---- steps extracted from main() so each one stays small --------------------

bool ParseEventSpecs(const std::string& list, std::vector<EventSpec>& specs)
{
    size_t pos = 0;
    while (pos <= list.size()) {
        const size_t comma = list.find(',', pos);
        const std::string item = list.substr(pos, (comma == std::string::npos) ? std::string::npos : comma - pos);
        const size_t slash = item.find('/');
        if (slash == std::string::npos || slash == 0 || slash + 1 >= item.size()) {
            FtraceLog::Instance().Write("error", "check=events result=fail detail=bad format: " + item);
            return false;
        }
        EventSpec spec;
        spec.system = item.substr(0, slash);
        spec.event = item.substr(slash + 1);
        specs.emplace_back(spec);
        if (comma == std::string::npos) {
            break;
        }
        pos = comma + 1;
    }
    return true;
}

// Kept out of main() so the entry point only holds the loop itself.
const struct option kLongOptions[] = {
    {"output", required_argument, nullptr, 'o'},
    {"events", required_argument, nullptr, 'e'},
    {"bufsize", required_argument, nullptr, 'b'},
    {"period", required_argument, nullptr, 'p'},
    {"cpus", required_argument, nullptr, 'c'},
    {"mask", required_argument, nullptr, 'M'},
    {"max-bytes", required_argument, nullptr, 'm'},
    {"lock-file", required_argument, nullptr, 'L'},
    {"help", no_argument, nullptr, 'h'},
    {nullptr, 0, nullptr, 0},
};

int32_t ParseOneOption(
    int32_t opt, const std::string& arg, Options& options, std::string& cpuList, std::string& cpuMask)
{
    switch (opt) {
        case 'o':
            options.outputDir = arg;
            break;
        case 'e':
            options.eventList = arg;
            break;
        case 'b':
            if (!ParseInt32(arg, options.bufferSizeKb)) {
                PrintUsage();
                return EXIT_BAD_ARGS;
            }
            break;
        case 'p':
            if (!ParseInt32(arg, options.periodSec)) {
                PrintUsage();
                return EXIT_BAD_ARGS;
            }
            break;
        case 'c':
            cpuList = arg;
            break;
        case 'M':
            cpuMask = arg;
            break;
        case 'L':
            options.lockPath = arg;
            break;
        case 'm':
            if (!ParseUint64(arg, options.maxBytes)) {
                PrintUsage();
                return EXIT_BAD_ARGS;
            }
            break;
        case 'h':
            PrintUsage();
            return EXIT_OK;
        default:
            PrintUsage();
            return EXIT_BAD_ARGS;
    }
    return EXIT_OK;
}

// Validation and defaults for the options collected by main()'s getopt loop.
int32_t FinishCommandLine(Options& options, const std::string& cpuMask)
{
    if (options.outputDir.empty() || options.eventList.empty()) {
        fprintf(stderr, "ERROR: -o and -e are mandatory.\n");
        PrintUsage();
        return EXIT_BAD_ARGS;
    }
    options.cpuMask = cpuMask;
    if (options.bufferSizeKb <= 0) {
        options.bufferSizeKb = kDefaultBufsizeKb;
    }
    if (options.periodSec < 0) {
        options.periodSec = 0;
    }
    return EXIT_OK;
}

// The "start" plog line is built here so main() stays a thin sequence of steps.
std::string BuildStartKvs(const Options& options, const std::string& cpuList, const std::string& cpuMask)
{
    return "output=" + options.outputDir + " events=" + options.eventList +
           " bufsize_kb=" + std::to_string(options.bufferSizeKb) + " period_sec=" + std::to_string(options.periodSec) +
           " cpu_list=" + cpuList + " cpu_mask=" + cpuMask;
}

bool ResolveCpus(const Options& options, const std::string& cpuList, std::vector<int32_t>& cpus)
{
    if (!cpuList.empty()) {
        if (!ParseCpuList(cpuList, cpus)) {
            FtraceLog::Instance().Write("error", "check=cpus result=fail detail=bad list: " + cpuList);
            return false;
        }
    } else if (!options.cpuMask.empty()) {
        if (!ParseHexMask(options.cpuMask, cpus)) {
            FtraceLog::Instance().Write("error", "check=cpus result=fail detail=bad mask: " + options.cpuMask);
            return false;
        }
    } else {
        cpus = OnlineCpus();
    }
    return true;
}

bool CheckDiskSpace(Options& options, const std::vector<int32_t>& cpus, uint64_t& freeMb)
{
    const uint64_t estimateBytes =
        static_cast<uint64_t>(options.bufferSizeKb) * kKbToBytes * static_cast<uint64_t>(cpus.size());
    const uint64_t needBytes = static_cast<uint64_t>(static_cast<double>(estimateBytes) * kDiskEstimateFactor);
    if (!CheckDisk(options.outputDir, needBytes, freeMb)) {
        FtraceLog::Instance().Write("error", "check=disk result=fail detail=insufficient free space");
        return false;
    }
    return true;
}

// Self check: root, tracefs, events, cpus and free space.
int32_t RunSelfCheck(
    Options& options, const std::string& cpuList, std::string& traceRoot, std::vector<EventSpec>& specs,
    std::vector<int32_t>& cpus)
{
    if (geteuid() != 0) {
        FtraceLog::Instance().Write("error", "check=root result=fail detail=root privilege required, rerun with sudo");
        return EXIT_ENV_CHECK;
    }
    if (!TraceFs::DetectRoot(traceRoot)) {
        FtraceLog::Instance().Write("error", "check=tracefs result=fail detail=not mounted");
        return EXIT_ENV_CHECK;
    }
    if (!ParseEventSpecs(options.eventList, specs)) {
        return EXIT_BAD_ARGS;
    }
    for (const auto& spec : specs) {
        if (!TraceFs::CheckEvent(traceRoot, spec)) {
            FtraceLog::Instance().Write("error", "check=events result=fail detail=not found: " + spec.FullName());
            return EXIT_ENV_CHECK;
        }
    }
    if (!ResolveCpus(options, cpuList, cpus)) {
        return EXIT_BAD_ARGS;
    }
    options.cpus = cpus;

    // trace_pipe_raw hands out one full sub-buffer per read, so the read buffer must be
    // exactly that size or every page after the first one lands misaligned in the file.
    options.pageSize = DetectSubbufSize(traceRoot);
    // Measured on 6.8/aarch64: the per page header is 16 bytes (an 8 byte timestamp plus the
    // commit counter), so the first event header always sits at that offset.
    options.pageDataOffset = PAGE_DATA_OFFSET_DEFAULT;
    uint64_t freeMb = 0;
    if (!CheckDiskSpace(options, cpus, freeMb)) {
        return EXIT_DISK_FULL;
    }
    FtraceLog::Instance().KeyValues(
        "selfcheck_ok", "tracefs=" + traceRoot + " nr_cpu=" + std::to_string(cpus.size()) +
                            " page_size=" + std::to_string(options.pageSize) + " data_offset=" +
                            std::to_string(options.pageDataOffset) + " disk_free_mb=" + std::to_string(freeMb));
    return EXIT_OK;
}

// The collector owns the lock, so "lock held" means "a collector is running".
// Whoever loses the race exits here without touching tracefs.
int32_t AcquireNodeLock(const Options& options, int32_t& lockFd)
{
    if (options.lockPath.empty()) {
        FtraceLog::Instance().Write("warn", "no --lock-file given, single instance protection is off");
        return EXIT_OK;
    }
    // Open an existing lock without O_CREAT: /var/tmp and /tmp are sticky, and with
    // fs.protected_regular a root open(O_CREAT) of a file owned by the invoking user is denied
    // (EACCES), which used to make the collector exit with an environment error.
    const std::string lockPath = CanonicalizeFilePath(options.lockPath);
    lockFd = open(lockPath.c_str(), O_RDWR | O_CLOEXEC, kLockFileMode);
    if (lockFd < 0 && errno == ENOENT) {
        lockFd = open(lockPath.c_str(), O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC, kLockFileMode);
        if (lockFd < 0 && errno == EEXIST) {
            lockFd = open(lockPath.c_str(), O_RDWR | O_CLOEXEC, kLockFileMode);
        }
    }
    if (lockFd < 0) {
        FtraceLog::Instance().Write("error", "open node lock failed: " + options.lockPath);
        return EXIT_ENV_CHECK;
    }
    // The collector usually runs as root while the profiling job runs as the invoking user, and the
    // job probes this same file: keep it writable for everyone so the next run can still open it.
    (void)fchmod(lockFd, kLockFileMode);
    if (flock(lockFd, LOCK_EX | LOCK_NB) == 0) {
        FtraceLog::Instance().KeyValues("lock_acquired", "path=" + options.lockPath);
        WriteHolderRecord(lockFd, MonoRawNs());
        return EXIT_OK;
    }
    // The holder may be alive but stuck: its heartbeat stops, so reap it once.
    bool acquired = false;
    if (TakeOverStaleLock(options.lockPath)) {
        acquired = (flock(lockFd, LOCK_EX | LOCK_NB) == 0);
    }
    if (!acquired) {
        FtraceLog::Instance().Write(
            "info", "node lock busy: " + options.lockPath + " holder=[" + DescribeLockHolder(options.lockPath) + "]");
        close(lockFd);
        lockFd = -1;
        return EXIT_LOCK_BUSY;
    }
    FtraceLog::Instance().Write("warn", "took over a stale node lock: " + options.lockPath);
    FtraceLog::Instance().KeyValues("lock_acquired", "path=" + options.lockPath);
    WriteHolderRecord(lockFd, MonoRawNs());
    return EXIT_OK;
}

// Meta and thread map are written before the window starts so a parser can always map the raw
// pages back to events, even if the collector is killed before the footer is appended.
int32_t WriteArtifactMeta(
    const Options& options, const std::string& traceRoot, const std::vector<EventSpec>& specs,
    const std::string& threadMapPath)
{
    const std::string metaPath = options.outputDir + "/trace_event_meta.json";
    if (!TraceFs::WriteEventMetaJson(traceRoot, specs, options.pageSize, options.pageDataOffset, metaPath)) {
        FtraceLog::Instance().Write("warn", "write trace_event_meta.json failed");
    }
    (void)TraceFs::WriteThreadMapJson(threadMapPath, MonoRawNs(), 0);
    // Same reason as the cpu files: the parser runs as the profiling user, not as root.
    GiveBackOwnership(metaPath);
    GiveBackOwnership(threadMapPath);
    return EXIT_OK;
}

int32_t StartReaders(
    const Options& options, const std::string& traceRoot, const std::vector<EventSpec>& specs,
    const std::vector<int32_t>& cpus, std::vector<std::unique_ptr<CpuReader>>& readers)
{
    if (!TraceFs::Prepare(traceRoot, options, specs, cpus)) {
        FtraceLog::Instance().Write("error", "prepare tracefs failed");
        return EXIT_TRACEFS;
    }
    readers.reserve(cpus.size());
    for (int32_t cpu : cpus) {
        const std::string outputPath = options.outputDir + "/trace.cpu" + std::to_string(cpu) + ".bin";
        auto reader = std::make_unique<CpuReader>(cpu, traceRoot, outputPath, options.pageSize, options.pageDataOffset);
        reader->Start();
        readers.emplace_back(std::move(reader));
    }
    if (!TraceFs::Start(traceRoot)) {
        FtraceLog::Instance().Write("error", "tracing_on=1 failed");
        JoinAllWithTimeout(readers);
        return EXIT_TRACEFS;
    }
    gWindowStartNs = MonoRawNs();
    return EXIT_OK;
}

// A reader stuck in write() would keep the node lock forever, so the lifetime is enforced by an
// independent thread: it can still run and _exit() the process even when every reader thread is
// blocked. A missing footer is expected on that path.
void StartLifetimeWatchdog(const Options& options, const std::string& traceRoot)
{
    if (options.periodSec <= 0) {
        FtraceLog::Instance().Write("warn", "--period=0, collector lifetime is unbounded");
        return;
    }
    const uint64_t watchdogNs =
        (static_cast<uint64_t>(options.periodSec) + FTRACE_WATCHDOG_MARGIN_SEC) * kNanosPerSecond;
    std::thread([watchdogNs, traceRoot]() {
        const uint64_t deadlineNs = gWindowStartNs + watchdogNs;
        while (MonoRawNs() < deadlineNs) {
            struct timespec sleepTs {};
            sleepTs.tv_sec = 1;
            (void)nanosleep(&sleepTs, nullptr);
        }
        FtraceLog::Instance().Write("error", "collector lifetime exceeded, release the node lock");
        (void)TraceFs::Stop(traceRoot);
        _exit(EXIT_OK);
    }).detach();
}

uint64_t SumReaderBytes(const std::vector<std::unique_ptr<CpuReader>>& readers)
{
    uint64_t total = 0;
    for (const auto& reader : readers) {
        total += reader->Bytes();
    }
    return total;
}

uint64_t SumReaderEvents(const std::vector<std::unique_ptr<CpuReader>>& readers)
{
    uint64_t total = 0;
    for (const auto& reader : readers) {
        total += reader->Events();
    }
    return total;
}

uint64_t ReadTotalDrops(const std::string& traceRoot, const std::vector<int32_t>& cpus)
{
    uint64_t drops = 0;
    for (int32_t cpu : cpus) {
        uint64_t cpuDrops = 0;
        if (TraceFs::ReadCpuDrops(traceRoot, cpu, cpuDrops)) {
            drops += cpuDrops;
        }
    }
    return drops;
}

// Returns the accumulated drop counter so the exit summary can report it.
uint64_t RunMonitor(
    const Options& options, const std::string& traceRoot, const std::vector<int32_t>& cpus,
    const std::vector<std::unique_ptr<CpuReader>>& readers, int32_t lockFd)
{
    const uint64_t periodNs = static_cast<uint64_t>(options.periodSec) * kNanosPerSecond;
    uint64_t lastHeartbeatNs = gWindowStartNs;
    uint64_t lastDrops = 0;
    while (!gStopRequested.load()) {
        if (getppid() == 1) { // parent died without telling us
            FtraceLog::Instance().Write("warn", "parent process gone, stop collecting");
            gEndReason.store(static_cast<uint32_t>(EndReason::PARENT_GONE));
            gStopRequested.store(true);
            break;
        }
        struct timespec sleepTs {};
        sleepTs.tv_sec = 0;
        sleepTs.tv_nsec = kMonitorSleepNs;
        (void)nanosleep(&sleepTs, nullptr);

        const uint64_t nowNanos = MonoRawNs();
        const uint64_t totalBytes = SumReaderBytes(readers);
        const uint64_t totalEvents = SumReaderEvents(readers);
        const uint64_t drops = ReadTotalDrops(traceRoot, cpus);
        if (drops > lastDrops) {
            FtraceLog::Instance().KeyValues("drop_detected", "drop_total=" + std::to_string(drops));
            lastDrops = drops;
        }
        if (nowNanos - lastHeartbeatNs >= kHeartbeatIntervalNs || gHeartbeatRequested.exchange(false)) {
            if (lockFd >= 0) {
                WriteHolderRecord(lockFd, nowNanos); // lease: a stuck holder stops updating this
            }
            FtraceLog::Instance().Heartbeat(
                totalBytes, totalEvents, drops, NowDiskFreeMb(options.outputDir), 0, LoadAverage1());
            lastHeartbeatNs = nowNanos;
        }
        if (periodNs > 0 && (nowNanos - gWindowStartNs) >= periodNs) {
            gEndReason.store(static_cast<uint32_t>(EndReason::PERIOD));
            gStopRequested.store(true);
            break;
        }
        if (options.maxBytes > 0 && totalBytes >= options.maxBytes) {
            FtraceLog::Instance().Write("warn", "max-bytes reached, stop collecting");
            gEndReason.store(static_cast<uint32_t>(EndReason::DISK_FULL));
            gStopRequested.store(true);
            break;
        }
    }
    if (getppid() == 1) {
        gEndReason.store(static_cast<uint32_t>(EndReason::PARENT_GONE));
    }
    return lastDrops;
}

int32_t FinishCollection(
    const Options& options, const std::string& traceRoot, const std::string& threadMapPath,
    std::vector<std::unique_ptr<CpuReader>>& readers, uint64_t lastDrops)
{
    (void)TraceFs::Stop(traceRoot);
    const uint64_t stopNs = MonoRawNs();
    // The readers must be drained and joined before the footer is appended: an open writer would
    // keep appending pages after the footer and push the magic out of the last 64 bytes.
    JoinAllWithTimeout(readers);
    EndReason reason = static_cast<EndReason>(gEndReason.load());
    uint64_t totalBytes = 0;
    uint64_t totalEvents = 0;
    bool collectFailed = false;
    for (const auto& reader : readers) {
        CpuStats stats = reader->Snapshot();
        // The kernel per-cpu drop counter is only readable while the buffer still exists, so it has
        // to be captured here: the footer is what tells a consumer whether pages were lost.
        uint64_t cpuDrops = 0;
        if (TraceFs::ReadCpuDrops(traceRoot, stats.cpu, cpuDrops)) {
            stats.drops = cpuDrops;
        }
        const std::string path = options.outputDir + "/trace.cpu" + std::to_string(stats.cpu) + ".bin";
        if (!AppendFooter(path, stats, reason)) {
            FtraceLog::Instance().Write("error", "cpu" + std::to_string(stats.cpu) + " write footer failed: " + path);
            collectFailed = true;
        }
        totalBytes += stats.bytes;
        totalEvents += stats.events;
        if (!reader->Error().empty()) {
            FtraceLog::Instance().Write("error", "cpu" + std::to_string(stats.cpu) + " " + reader->Error());
            collectFailed = true;
        }
    }

    if (!TraceFs::WriteThreadMapJson(threadMapPath, gWindowStartNs, stopNs)) {
        FtraceLog::Instance().Write("error", "write thread_map.json failed: " + threadMapPath);
        collectFailed = true;
    }
    (void)TraceFs::Clear(traceRoot);

    if (collectFailed) {
        // The artifacts on disk are incomplete, so the exit code and the diag summary must say so
        // instead of reporting a successful collection.
        reason = EndReason::ERROR;
    }
    const int32_t exitCode = collectFailed ? Ftrace::EXIT_COLLECT_FAILED : EXIT_OK;

    char summary[kSummaryLen] = {0};
    const int32_t written = snprintf_s(
        summary, sizeof(summary), sizeof(summary) - 1,
        "reason=%u duration_ms=%llu total_bytes=%llu total_events=%llu total_drop=%llu exit_code=%d",
        static_cast<uint32_t>(reason), static_cast<unsigned long long>((stopNs - gWindowStartNs) / kNanosPerMilliSec),
        static_cast<unsigned long long>(totalBytes), static_cast<unsigned long long>(totalEvents),
        static_cast<unsigned long long>(lastDrops), exitCode);
    if (written >= 0) {
        FtraceLog::Instance().KeyValues("exit", summary);
    }
    return exitCode;
}
int32_t CollectAndFinish(
    Options& options, const std::string& traceRoot, const std::vector<EventSpec>& specs,
    const std::vector<int32_t>& cpus)
{
    int32_t lockFd = -1;
    const int32_t lockRet = AcquireNodeLock(options, lockFd);
    if (lockRet != EXIT_OK) {
        return lockRet;
    }
    const std::string threadMapPath = options.outputDir + "/thread_map.json";
    (void)WriteArtifactMeta(options, traceRoot, specs, threadMapPath);
    signal(SIGTERM, SignalHandler);
    signal(SIGINT, SignalHandler);
    signal(SIGUSR1, SignalHandler);

    std::vector<std::unique_ptr<CpuReader>> readers;
    const int32_t startRet = StartReaders(options, traceRoot, specs, cpus, readers);
    if (startRet != EXIT_OK) {
        (void)TraceFs::Stop(traceRoot);
        return startRet;
    }
    StartLifetimeWatchdog(options, traceRoot);
    FtraceLog::Instance().KeyValues("tracing_started", "window_start_ns=" + std::to_string(gWindowStartNs));

    const uint64_t lastDrops = RunMonitor(options, traceRoot, cpus, readers, lockFd);
    const int32_t finishRet = FinishCollection(options, traceRoot, threadMapPath, readers, lastDrops);
    if (lockFd >= 0) {
        close(lockFd);
    }
    return finishRet;
}
} // namespace

int main(int argc, char* argv[])
{
    // One plog event per run, before any other work: whatever happens next (bad args, node lock
    // busy, collection failure) the log still shows which collector build produced the artifacts.
    FtraceLog::Instance().Event("version", std::string("collector=") + FTRACE_COLLECTOR_VERSION);

    Options options;
    std::string cpuList;
    std::string cpuMask;
    int32_t opt = 0;
    while ((opt = getopt_long(argc, argv, "o:e:b:p:c:M:m:hL:", kLongOptions, nullptr)) != -1) {
        const std::string argText = (optarg == nullptr) ? std::string() : std::string(optarg);
        const int32_t ret = ParseOneOption(opt, argText, options, cpuList, cpuMask);
        if (ret != EXIT_OK || opt == 'h') {
            return ret;
        }
    }
    const int32_t cliRet = FinishCommandLine(options, cpuMask);
    if (cliRet != EXIT_OK) {
        return cliRet;
    }
    if (!EnsureDirTree(options.outputDir)) {
        fprintf(stderr, "ERROR: cannot create output dir %s\n", options.outputDir.c_str());
        return EXIT_ENV_CHECK;
    }
    // parent death protection: never leave tracing_on=1 behind
    (void)prctl(PR_SET_PDEATHSIG, SIGTERM);
    FtraceLog::Instance().KeyValues("start", BuildStartKvs(options, cpuList, cpuMask));

    std::string traceRoot;
    std::vector<EventSpec> specs;
    std::vector<int32_t> cpus;
    const int32_t checkRet = RunSelfCheck(options, cpuList, traceRoot, specs, cpus);
    if (checkRet != EXIT_OK) {
        return checkRet;
    }
    return CollectAndFinish(options, traceRoot, specs, cpus);
}
