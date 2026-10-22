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

#ifndef _HCCL_CHECK_BUF_INIT_H_
#define _HCCL_CHECK_BUF_INIT_H_
#include <stdio.h>
#include <math.h>
#include <unistd.h>
#include <chrono>
#include <vector>
#include <string>
#include <cmath>
#include <cstdint>
#include <limits>
#include <hccl/hccl_types.h>
#include "hccl_test_common.h"
#include <map>

static inline float fp32_from_bits(uint32_t w)
{
    union {
        uint32_t as_bits;
        float as_value;
    } fp32 = {w};
    return fp32.as_value;
}

static inline uint32_t fp32_to_bits(float f)
{
    union {
        float as_value;
        uint32_t as_bits;
    } fp32 = {f};
    return fp32.as_bits;
}

static inline uint16_t fp16_ieee_from_fp32_value(float f)
{
#if defined(__STDC_VERSION__) && (__STDC_VERSION__ >= 199901L) || defined(__GNUC__) && !defined(__STRICT_ANSI__)
    const float scale_to_inf = 0x1.0p+112f;
    const float scale_to_zero = 0x1.0p-110f;
#else
    const float scale_to_inf = fp32_from_bits(UINT32_C(0x77800000));
    const float scale_to_zero = fp32_from_bits(UINT32_C(0x08800000));
#endif
    float base = (fabsf(f) * scale_to_inf) * scale_to_zero;

    const uint32_t w = fp32_to_bits(f);
    const uint32_t shl1_w = w + w;
    const uint32_t sign = w & UINT32_C(0x80000000);
    uint32_t bias = shl1_w & UINT32_C(0xFF000000);
    if (bias < UINT32_C(0x71000000)) {
        bias = UINT32_C(0x71000000);
    }

    base = fp32_from_bits((bias >> 1) + UINT32_C(0x07800000)) + base;
    const uint32_t bits = fp32_to_bits(base);
    const uint32_t exp_bits = (bits >> 13) & UINT32_C(0x00007C00);
    const uint32_t mantissa_bits = bits & UINT32_C(0x00000FFF);
    const uint32_t nonsign = exp_bits + mantissa_bits;
    return (sign >> 16) | (shl1_w > UINT32_C(0xFF000000) ? UINT16_C(0x7E00) : nonsign);
}

static inline uint16_t fp32tobf16(float x)
{
    uint32_t bits = fp32_to_bits(x);
    uint32_t sign = bits & 0x80000000u;
    uint32_t exp = bits & 0x7F800000u;
    if ((bits & 0x7FFFFFFFu) == 0) {
        // zero
        return (uint16_t)(sign >> 16);
    }

    // sign    exp        man
    // 0/1     11111111   don't care
    if (exp == 0x7F800000u) {
        // infinity or Nans
        return (uint16_t)(bits >> 16);
    }
    // Normalized number
    // round to nearest
    // r 与 x 同符号、同指数，r/256 即半个 bf16 ULP
    float r = fp32_from_bits(sign | exp) / 256;
    return (uint16_t)(fp32_to_bits(x + r) >> 16);
}

constexpr u8 HIF8_SIGN_MASK = 0x80;
constexpr u8 HIF8_DATA_MASK = 0x7F;
constexpr u8 HIF8_POSITIVE_INFINITY = 0x6F;
constexpr u8 HIF8_NAN = 0x80;
constexpr float HIF8_INFINITY_THRESHOLD = 40960.0F;

// 昇腾 HiFloat8：符号位 + 7 位数据（高位至低位：前缀|指数|尾数，三者位宽恒为 7）。
// 前缀标记小数点位置：0001/001/01/10/11 依次为 dot0..dot4，0000（0x00-0x07）为非规格化数。
static inline float decode_positive_hif8(u8 encoded)
{
    if (encoded == HIF8_POSITIVE_INFINITY) {
        return std::numeric_limits<float>::infinity();
    }

    if ((encoded & 0x78U) == 0) {
        // 0000eee：eee 为 0 时表示 0，否则表示 2^(eee-23)。
        const int denormalExponent = encoded & 0x07U;
        return denormalExponent == 0 ? 0.0F : std::ldexp(1.0F, denormalExponent - 23);
    }

    int exponentWidth = 0; // 点位前缀确定的指数位宽
    int mantissaWidth = 0; // 点位前缀确定的尾数位宽
    switch (encoded >> 3) {
        case 0x1: // 前缀 0001：0 位指数，3 位尾数
            exponentWidth = 0;
            mantissaWidth = 3;
            break;
        case 0x2:
        case 0x3: // 前缀 001：1 位指数，3 位尾数
            exponentWidth = 1;
            mantissaWidth = 3;
            break;
        case 0x4:
        case 0x5:
        case 0x6:
        case 0x7: // 前缀 01：2 位指数，3 位尾数
            exponentWidth = 2;
            mantissaWidth = 3;
            break;
        case 0x8:
        case 0x9:
        case 0xA:
        case 0xB: // 前缀 10：3 位指数，2 位尾数
            exponentWidth = 3;
            mantissaWidth = 2;
            break;
        default: // 前缀 11：4 位指数，1 位尾数
            exponentWidth = 4;
            mantissaWidth = 1;
            break;
    }

    // 规格化数的尾数有一个不存储的前导 1。
    const u8 mantissaMask = static_cast<u8>((1U << mantissaWidth) - 1U);
    const float significand
        = 1.0F + static_cast<float>(encoded & mantissaMask) / static_cast<float>(1U << mantissaWidth);
    if (exponentWidth == 0) {
        return significand;
    }

    const u8 exponentMask = static_cast<u8>((1U << exponentWidth) - 1U);
    const u8 encodedExponent = static_cast<u8>((encoded >> mantissaWidth) & exponentMask);
    const u8 exponentSign = static_cast<u8>(encodedExponent >> (exponentWidth - 1));
    // 指数采用符号-幅值编码：存储域为 1 位符号 + 幅值低位，幅值的最高位 1 隐含不存储。
    const int exponentMagnitude = (1U << (exponentWidth - 1)) | (encodedExponent & ((1U << (exponentWidth - 1)) - 1U));
    const int exponent = exponentSign == 0 ? exponentMagnitude : -exponentMagnitude;
    return std::ldexp(significand, exponent);
}

static inline u8 fp32tohif8(float value)
{
    if (std::isnan(value)) {
        return HIF8_NAN;
    }

    const bool isNegative = std::signbit(value);
    const float absValue = std::fabs(value);
    if (absValue == 0.0F) {
        return 0;
    }
    if (std::isinf(absValue) || absValue >= HIF8_INFINITY_THRESHOLD) {
        return static_cast<u8>(HIF8_POSITIVE_INFINITY | (isNegative ? HIF8_SIGN_MASK : 0));
    }

    // Select the nearest finite encoding. On a tie, the larger magnitude implements round half away from zero.
    u8 nearest = 0;
    float nearestValue = 0.0F;
    float nearestError = std::numeric_limits<float>::infinity();
    for (u16 encoded = 0; encoded <= HIF8_DATA_MASK; ++encoded) {
        if (encoded == HIF8_POSITIVE_INFINITY) {
            continue;
        }
        const float candidate = decode_positive_hif8(static_cast<u8>(encoded));
        const float error = std::fabs(absValue - candidate);
        if (error < nearestError || (error == nearestError && candidate > nearestValue)) {
            nearest = static_cast<u8>(encoded);
            nearestValue = candidate;
            nearestError = error;
        }
    }
    return static_cast<u8>(nearest | (isNegative ? HIF8_SIGN_MASK : 0));
}

typedef void (*HostBufInitFunc)(void*, u64, int);
extern std::map<int, HostBufInitFunc> functionMap;

typedef void (*ReduceCheckBufInitFunc)(void*, u64, int, int, int);
extern std::map<int, ReduceCheckBufInitFunc> functionReduceMap;

typedef int (*AllToAllCheckResult)(const void*, u64*, u64*, int, int, int, int);
extern std::map<int, AllToAllCheckResult> functionAllToAllMap;

extern void hccl_host_buf_init(void* dst_buf, unsigned long long count, int dtype, int val);
extern void
hccl_reduce_check_buf_init(void* dst_buf, unsigned long long count, int dtype, int op, int val, int rank_size);
extern int hccl_alltoallv_check_result(
    void* check_buf, unsigned long long* recv_counts, unsigned long long* recv_disp, int rank_id, int rank_size,
    int dtype, int check_level);
extern bool hccl_alltoall_check_result(
    const void* recv_buff, const std::size_t count, const int nRanks, const int rank,
    const std::vector<std::uint8_t>& pattern);

#endif
