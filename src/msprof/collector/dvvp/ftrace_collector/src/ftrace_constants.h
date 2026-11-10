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
#ifndef MSPROF_FTRACE_COLLECTOR_FTRACE_CONSTANTS_H
#define MSPROF_FTRACE_COLLECTOR_FTRACE_CONSTANTS_H

#include <cstddef>
#include <cstdint>
#include <sys/types.h>

namespace Ftrace {
// Numeric literals that carry meaning get a name here instead of appearing inline, which keeps
// the arithmetic readable and gives codecheck a single place to look.
constexpr int32_t kMaxCpuCount = 4096;      // hard ceiling for -c / -M input
constexpr int32_t kDefaultBufsizeKb = 4096; // ring buffer per CPU when -b is absent
constexpr int32_t kMaxSubbufSizeKb = 1024 * 1024;
constexpr int32_t kBitsPerByte = 8;
constexpr int32_t kBitsPerHexDigit = 4;
constexpr int32_t kBitsPerWord = 32;
constexpr uint32_t kHexMaskMaxLen = 32; // 32 hex chars describe one 32 bit word
constexpr int32_t kDecimalBase = 10;
constexpr int32_t kHexBase = 16;
constexpr unsigned long kMaxUint32 = 0xFFFFFFFFUL;
constexpr size_t kMaxMaskTextLen = 128; // comma separated 8 digit words
constexpr size_t kPidFieldLen = 4;      // strlen("pid=")
constexpr size_t kRbTypeLenUnit = 4;    // one type_len unit is 4 bytes
constexpr size_t kEventHdrWithLen = 8;  // header word + payload length word
constexpr size_t kJsonEscapeSlack = 8;  // reserve slack for escaped chars
constexpr size_t kHashHexBufLen = 32;   // 16 hex digits + NUL, with slack
constexpr size_t kKbToBytes = 1024;
constexpr size_t kByteBucket = 1024;
constexpr size_t kBytesPerMb = kByteBucket * kByteBucket;
constexpr size_t kMaxLineLen = 256;
constexpr size_t kHolderRecordLen = 512;
constexpr size_t kSummaryLen = 512;

constexpr uint64_t kNanosPerSecond = 1000000000ULL;
constexpr uint64_t kNanosPerMilliSec = 1000000ULL;
constexpr uint64_t kHeartbeatIntervalNs = kNanosPerSecond;
constexpr int64_t kMonitorSleepNs = 100LL * 1000 * 1000;
constexpr int64_t kDrainPollNs = 20LL * 1000 * 1000;
constexpr int64_t kTakeoverWaitNs = 200LL * 1000 * 1000;

constexpr double kDiskEstimateFactor = 1.5;
constexpr mode_t kDirMode = 0755;
constexpr mode_t kDataFileMode = 0644;
constexpr mode_t kLockFileMode = 0666;
constexpr mode_t kWriterFileMode = 0600;
} // namespace Ftrace

#endif // MSPROF_FTRACE_COLLECTOR_FTRACE_CONSTANTS_H
