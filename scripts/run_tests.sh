#!/bin/bash
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASEPATH="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_OUTPUT_DIR="${BASEPATH}/build"
# build.sh moves generated cann-oam-tools_*.run packages to build_out/.
BUILD_OUT_DIR="${BASEPATH}/build_out"

declare -A TEST_CASES=(
    ["host_ut"]="pytest"
    ["asys_st"]="pytest"
    ["asys_ut"]="pytest"
    ["msaicerr_st"]="pytest"
    ["msaicerr_ut"]="pytest"
    ["msprof_ut"]="gtest"
    ["install_st"]="pytest"
    ["upgrade_st"]="pytest"
    ["uninstall_st"]="pytest"
)

VALID_COMPONENTS=("host" "asys" "msaicerr" "msprof" "install" "upgrade" "uninstall" "all")

# 代码覆盖率基线：低于该值判失败。固定值，不提供命令行开关——门禁阈值可调
# 等于可被绕过，失去门禁意义。要调整基线请改此处并走评审。
COV_BASELINE=80

# validate_*_result 只往这些数组里填结果，不直接打印；由 print_summary 统一呈现。
# 计数不可用（崩溃/统计缺失）时填 "-"。
declare -A R_PASSED R_FAILED R_SKIPPED R_COV R_STATUS R_FAILLIST R_NOTES

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --component <name>  Specify component to test:"
    echo "                        host, asys, msaicerr, msprof, install, upgrade, uninstall, all (default: all)"
    echo "  --ut               Run UT tests only"
    echo "  --st               Run ST tests only"
    echo "  --cov              Enable gcov coverage collection for gtest cases"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Coverage baseline is fixed at ${COV_BASELINE}%; a suite below it is reported as FAIL."
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests (UT + ST)"
    echo "  $0 --component host --ut              # Run pure Python host UT"
    echo "  $0 --component asys                  # Run asys UT + ST"
    echo "  $0 --component msaicerr --ut         # Run msaicerr UT only"
    echo "  $0 --st                              # Run all ST tests"
    echo "  $0 --component msprof --ut           # Run msprof UT only"
    echo "  $0 --component install               # Run install ST"
    echo "  $0 --component upgrade               # Run upgrade ST"
    echo "  $0 --component uninstall             # Run uninstall ST"
}

parse_args() {
    COMPONENT="all"
    RUN_UT=false
    RUN_ST=false
    RUN_COV=false

    if [[ $# -eq 0 ]]; then
        RUN_UT=true
        RUN_ST=true
        return 0
    fi

    local parsed_args
    parsed_args=$(getopt -a -o h -l help,component:,ut,st,cov -- "$@") || {
        print_usage
        exit 1
    }

    eval set -- "$parsed_args"

    while true; do
        case "$1" in
            -h|--help)
                print_usage
                exit 0
                ;;
            --component)
                COMPONENT="$2"
                shift 2
                ;;
            --ut)
                RUN_UT=true
                shift
                ;;
            --st)
                RUN_ST=true
                shift
                ;;
            --cov)
                RUN_COV=true
                shift
                ;;
            --)
                shift
                break
                ;;
            *)
                echo "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    if [[ "$COMPONENT" != "all" ]] && [[ ! " ${VALID_COMPONENTS[*]} " =~ " ${COMPONENT} " ]]; then
        echo "ERROR: Invalid component '$COMPONENT'. Valid options: ${VALID_COMPONENTS[*]}"
        exit 1
    fi

    if [[ "$RUN_UT" == "false" ]] && [[ "$RUN_ST" == "false" ]]; then
        RUN_UT=true
        RUN_ST=true
    fi

}

get_test_cases() {
    local result=()

    local components=()
    if [[ "$COMPONENT" == "all" ]]; then
        components=("host" "asys" "msaicerr" "msprof" "install" "upgrade" "uninstall")
    else
        components=("$COMPONENT")
    fi

    for comp in "${components[@]}"; do
        if [[ "$RUN_UT" == "true" ]]; then
            case "$comp" in
                host)
                    result+=("host_ut")
                    ;;
                asys)
                    result+=("asys_ut")
                    ;;
                msaicerr)
                    result+=("msaicerr_ut")
                    ;;
                msprof)
                    result+=("msprof_ut")
                    ;;
                # install/upgrade/uninstall have no UT counterpart
            esac
        fi

        if [[ "$RUN_ST" == "true" ]]; then
            case "$comp" in
                asys)
                    result+=("asys_st")
                    ;;
                msaicerr)
                    result+=("msaicerr_st")
                    ;;
                msprof)
                    ;;
                install)
                    result+=("install_st")
                    ;;
                upgrade)
                    result+=("upgrade_st")
                    ;;
                uninstall)
                    result+=("uninstall_st")
                    ;;
            esac
        fi
    done

    echo "${result[@]}"
}

is_package_st_case() {
    case "$1" in
        install_st|upgrade_st|uninstall_st)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

find_run_package() {
    local pkg
    pkg=$(find "${BUILD_OUT_DIR}" -maxdepth 1 -type f -name "cann-oam-tools_*.run" 2>/dev/null \
        | sort -V | tail -n 1)
    if [[ -n "${pkg}" ]]; then
        echo "${pkg}"
        return 0
    fi
    return 1
}

ensure_run_package_for_st_cases() {
    local test_cases=("$@")
    local case_name
    local need_package=false

    for case_name in "${test_cases[@]}"; do
        if is_package_st_case "${case_name}"; then
            need_package=true
            break
        fi
    done

    if [[ "${need_package}" != "true" ]]; then
        return 0
    fi

    local run_pkg
    run_pkg=$(find_run_package || true)
    if [[ -n "${run_pkg}" ]]; then
        echo "INFO: Using run package: ${run_pkg}"
        return 0
    fi

    echo "INFO: install/upgrade/uninstall ST requires a cann-oam-tools .run package."
    echo "INFO: No cann-oam-tools_*.run found in ${BUILD_OUT_DIR}; building package first."
    if ! bash "${BASEPATH}/build.sh" --noexec; then
        echo "ERROR: Failed to build run package with bash build.sh --noexec"
        return 1
    fi

    run_pkg=$(find_run_package || true)
    if [[ -z "${run_pkg}" ]]; then
        echo "ERROR: build.sh finished but no cann-oam-tools_*.run was found in ${BUILD_OUT_DIR}"
        return 1
    fi

    echo "INFO: Prepared run package: ${run_pkg}"
}

# 记录一个用例集的结果。计数不可用时传 "-"。
# $1 case_name  $2 passed  $3 failed  $4 skipped  $5 cov  $6 status  $7 notes(多行)
record_result() {
    R_PASSED["$1"]="$2"
    R_FAILED["$1"]="$3"
    R_SKIPPED["$1"]="$4"
    R_COV["$1"]="$5"
    R_STATUS["$1"]="$6"
    R_NOTES["$1"]="$7"
}

# 统计 gtest 日志里"启动的 target 数"与"跑完的 target 数"。
# 跑完的判据是 gtest 的收尾汇总行 "[  PASSED  ] N test(s)."——它在
# OnTestIterationEnd 里无条件打印（不论用例通过与否，见 gtest.cc
# PrettyUnitTestResultPrinter::OnTestIterationEnd），是"框架正常跑完
# 一个 target"的权威信号。
#
# 为何不再逐用例配对 [ RUN ] 与 [ OK ]：多线程用例里，被测代码在别的线程
# printf 未换行时会把 gtest 标记从中间劈开（已实测到标记被拼接的情形），
# 此时任何字符串匹配都配不上，通过的用例会被误判为"未完成"，整个套件被
# 误报 CRASH。逐用例配对对输出交错天生不鲁棒，故改为按 target 粒度判断：
# 少一个收尾汇总行才说明真的有 target 中途死了。
count_gtest_targets() {
    local output_file="$1"
    local started finished
    # run_test_case 为每个 target 打一行 "----- running <bin> -----"
    started=$(LC_ALL=C grep -ac "^----- running " "$output_file")
    finished=$(LC_ALL=C grep -aoE "\[  PASSED  \] [0-9]+ test" "$output_file" | wc -l)
    echo "${started:-0} ${finished:-0}"
}

validate_gtest_result() {
    local output_file="$1"
    local case_name="$2"

    if [[ ! -f "$output_file" ]]; then
        record_result "$case_name" "-" "-" "-" "-" "CRASH" "output file not found: $output_file"
        return 1
    fi

    local exit_code=0
    if [[ -f "${BUILD_OUTPUT_DIR}/${case_name}.exitcode" ]]; then
        exit_code=$(cat "${BUILD_OUTPUT_DIR}/${case_name}.exitcode")
    fi
    exit_code=${exit_code:-0}

    local cov_ratio="${R_COV[$case_name]:--}"

    # 异常退出检测：信号杀死(exit_code >= 128)、输出含崩溃标记，或有 target
    # 启动了却没打出收尾汇总行。任一命中都说明框架未正常跑完，统计不可靠。
    local crashed=false
    if [[ "$exit_code" =~ ^[0-9]+$ ]] && [[ $exit_code -ge 128 ]]; then
        crashed=true
    fi
    if LC_ALL=C grep -qaE "Segmentation fault|core dumped|==ERROR:.*Sanitizer|Aborted|SIGABRT|signal 6" "$output_file"; then
        crashed=true
    fi

    local tgt_started tgt_finished
    read -r tgt_started tgt_finished <<< "$(count_gtest_targets "$output_file")"
    # 只在退出码非零时才把"少收尾汇总行"当作崩溃依据。
    # 依据：run_test_case 里任一 target 返回非零即置 msprof_ut_rc=1，故
    # ExitCode=0 表示所有 gtest 二进制都正常退出——而正常退出的 gtest 必然
    # 打印了收尾汇总行。此时若 grep 数不到，只可能是标记被其它线程的输出从
    # 中间劈开（"[  PAS==noise==SED  ]"）这类解析假象，不是真崩溃。
    # 退出码是"进程是否跑完"的权威信号，日志解析只用于提取计数。
    if [[ "$exit_code" =~ ^[0-9]+$ ]] && [[ $exit_code -ne 0 ]] \
        && [[ ${tgt_started:-0} -gt 0 ]] && [[ ${tgt_finished:-0} -lt ${tgt_started:-0} ]]; then
        crashed=true
    fi

    if [[ "$crashed" == "true" ]]; then
        local notes="CRASHED (ExitCode=${exit_code}), statistics unavailable"
        local markers
        # -a 必需：崩溃日志往往正是含非 UTF-8 字节的那一类，grep 判为 binary 时
        # -o 不输出任何内容，crash marker 摘要会为空，丢掉关键诊断信息。
        markers=$(LC_ALL=C grep -haoE "Segmentation fault|core dumped|Aborted|SIGABRT|==ERROR:.*Sanitizer|AddressSanitizer|runtime error:" \
            "$output_file" 2>/dev/null | sort -u | head -5)
        if [[ -n "$markers" ]]; then
            notes+=$'\n'"crash marker: $(echo "$markers" | paste -sd', ' -)"
        fi
        if [[ ${tgt_finished:-0} -lt ${tgt_started:-0} ]]; then
            notes+=$'\n'"only ${tgt_finished}/${tgt_started} gtest target(s) reached the summary line"
            # 指出最后一个没跑完的 target，便于直接定位到二进制
            local last_target
            last_target=$(LC_ALL=C grep -a "^----- running " "$output_file" | tail -1 | sed 's/^----- running //; s/ -----$//')
            [[ -n "$last_target" ]] && notes+=$'\n'"last target started: ${last_target}"
        fi
        record_result "$case_name" "-" "-" "-" "$cov_ratio" "CRASH" "$notes"
        return 1
    fi

    # 正常退出：解析用例统计
    local passed_count=0
    local failed_count=0
    local skipped_count=0

    # 标记可能被拼到行中间（被测代码 printf 未换行），不能按行首锚定。
    # 用 grep -o 抽取标记本身再取数字，位置无关。
    # -a 必需：设备侧输出含非 UTF-8 字节，grep 会把日志判为 binary，
    # 此时 -o 不输出任何内容，计数会全部变成 0。LC_ALL=C 同理规避 locale 影响。
    # 一个 case 可能运行多个 gtest target，输出含多段汇总，需累加求和。
    passed_count=$(LC_ALL=C grep -aoE "\[  PASSED  \] [0-9]+ test" "$output_file" \
        | awk '{s+=$4} END{print s+0}')
    passed_count=${passed_count:-0}

    failed_count=$(LC_ALL=C grep -aoE "\[  FAILED  \] [0-9]+ test" "$output_file" \
        | awk '{s+=$4} END{print s+0}')
    failed_count=${failed_count:-0}

    # SKIPPED 有两个来源，都要计入：
    # 1. GTEST_SKIP() 运行时跳过 → 汇总行 "[  SKIPPED ] N test(s), listed below:"
    #    （注意 gtest 并无 "YOU HAVE n SKIPPED TEST" 这种句式，那是 DISABLED 专用）
    # 2. DISABLED_ 前缀的用例 → "  YOU HAVE n DISABLED TESTS"
    local gtest_skipped=0
    local gtest_disabled=0
    gtest_skipped=$(LC_ALL=C grep -aoE "\[  SKIPPED \] [0-9]+ test" "$output_file" \
        | awk '{s+=$4} END{print s+0}')
    gtest_disabled=$(LC_ALL=C grep -aoE "YOU HAVE [0-9]+ DISABLED TEST" "$output_file" \
        | awk '{s+=$3} END{print s+0}')
    skipped_count=$(( ${gtest_skipped:-0} + ${gtest_disabled:-0} ))

    local notes=""
    local status="PASS"

    if [[ $exit_code -ne 0 ]]; then
        notes+="exited with code ${exit_code} (expected 0)"$'\n'
        status="FAIL"
    fi

    if LC_ALL=C grep -qaE "runtime error:" "$output_file"; then
        notes+="has runtime errors"$'\n'
        status="FAIL"
    fi

    if LC_ALL=C grep -qaE "AddressSanitizer|memory leak" "$output_file"; then
        notes+="has memory issues"$'\n'
        status="FAIL"
    fi

    if [[ $failed_count -gt 0 ]]; then
        status="FAIL"
        # 逐条失败行形如 "[  FAILED  ] Suite.Case (0 ms)"。与计数解析同口径：
        # 不按行首锚定（标记可能被拼在行中间），并加 -a（binary 日志下裸 grep
        # 会输出 "Binary file ... matches" 这种假条目）。用例名首字符为字母/
        # 下划线，可与汇总行 "[  FAILED  ] 2 tests," 区分。
        # gtest 在结尾清单里会重复列出，故去重。
        local names
        names=$(LC_ALL=C grep -aoE "\[  FAILED  \] [A-Za-z_][A-Za-z0-9_/.]*" "$output_file" \
            | sed -E 's/^\[  FAILED  \] //' | sort -u)
        R_FAILLIST["$case_name"]="$names"
    fi

    if [[ $passed_count -eq 0 ]] && [[ $failed_count -eq 0 ]]; then
        notes+="ran but produced no test results"$'\n'
        status="FAIL"
    fi

    record_result "$case_name" "$passed_count" "$failed_count" "$skipped_count" \
        "$cov_ratio" "$status" "${notes%$'\n'}"

    [[ "$status" == "PASS" ]]
}

validate_pytest_result() {
    local output_file="$1"
    local case_name="$2"

    if [[ ! -f "$output_file" ]]; then
        record_result "$case_name" "-" "-" "-" "-" "CRASH" "output file not found: $output_file"
        return 1
    fi

    local exit_code=0
    if [[ -f "${BUILD_OUTPUT_DIR}/${case_name}.exitcode" ]]; then
        exit_code=$(cat "${BUILD_OUTPUT_DIR}/${case_name}.exitcode")
    fi
    exit_code=${exit_code:-0}

    # 覆盖率先解析出来，崩溃分支也要带上（coverage report 可能已经落盘）。
    local cov_ratio="-"
    local coverage_line
    coverage_line=$(LC_ALL=C grep -aE "^TOTAL" "$output_file" | tail -1)
    if [[ -n "$coverage_line" ]]; then
        cov_ratio=$(echo "$coverage_line" | awk '{print $4}' | sed 's/%//')
        [[ -n "$cov_ratio" ]] || cov_ratio="-"
    fi

    # 异常退出检测：信号杀死(exit_code >= 128) 或输出含崩溃标记。
    # 此时框架未正常完成，通过/失败统计不可靠。
    local crashed=false
    if [[ "$exit_code" =~ ^[0-9]+$ ]] && [[ $exit_code -ge 128 ]]; then
        crashed=true
    fi
    if LC_ALL=C grep -qaE "Segmentation fault|core dumped|Fatal Python error|==ERROR:.*Sanitizer|Aborted|SIGABRT|signal 6" \
        "$output_file"; then
        crashed=true
    fi

    if [[ "$crashed" == "true" ]]; then
        local notes="CRASHED (ExitCode=${exit_code}), statistics unavailable"
        local markers
        # -a 同 gtest 分支：崩溃日志常含非 UTF-8 字节，grep 判为 binary 时
        # -o 不输出内容，crash marker 摘要会为空。
        markers=$(LC_ALL=C grep -haoE "Segmentation fault|core dumped|Fatal Python error|==ERROR:.*Sanitizer|AddressSanitizer|Aborted|SIGABRT" \
            "$output_file" 2>/dev/null | sort -u | head -5)
        if [[ -n "$markers" ]]; then
            notes+=$'\n'"crash marker: $(echo "$markers" | paste -sd', ' -)"
        fi
        record_result "$case_name" "-" "-" "-" "$cov_ratio" "CRASH" "$notes"
        return 1
    fi

    # 正常退出：解析用例统计
    local summary_line
    # pytest appends "(HH:MM:SS)" after the seconds when total time exceeds 1 minute.
    summary_line=$(LC_ALL=C grep -aE "^=+ .* in [0-9.]+s( \([0-9:]+\))? =+$" "$output_file")

    local failed_count passed_count error_count skipped_count
    failed_count=$(echo "$summary_line" | grep -oE '[0-9]+ failed' | awk '{print $1}')
    passed_count=$(echo "$summary_line" | grep -oE '[0-9]+ passed' | awk '{print $1}')
    error_count=$(echo "$summary_line" | grep -oE '[0-9]+ error' | awk '{print $1}')
    skipped_count=$(echo "$summary_line" | grep -oE '[0-9]+ skipped' | awk '{print $1}')

    passed_count=${passed_count:-0}
    failed_count=${failed_count:-0}
    error_count=${error_count:-0}
    skipped_count=${skipped_count:-0}

    local notes=""
    local status="PASS"

    if [[ $exit_code -ne 0 ]]; then
        notes+="exited with code ${exit_code} (expected 0)"$'\n'
        status="FAIL"
    fi

    if [[ $error_count -gt 0 ]]; then
        notes+="${error_count} collection/runner error(s)"$'\n'
        status="FAIL"
    fi

    # 不再扫日志正文里的 Traceback / ImportError 字样来判定失败。
    # 这两个字样在"用例正常通过"的日志里也会大量出现：
    #   - 用例故意验证异常路径（如 test_get_compile_from_tik_import_error），
    #     被测代码打印的回溯就是预期输出；
    #   - 环境缺可选依赖时，被测代码自己 catch 后打 WARNING，形如
    #     "failed to import te or tbe ... error: ImportError: No module named 'te'"。
    # 实测：704 passed / 0 failed 的日志因含一行 ImportError 字样即被判 FAIL，
    # 且失败清单为空——报了个查不下去的错。
    # pytest 的 failed/error 计数才是权威信号：真正的导入失败会被计为
    # collection error 并进 error_count，无需再扫正文。

    if [[ $failed_count -gt 0 ]] || [[ $error_count -gt 0 ]]; then
        status="FAIL"
        # short test summary info 里的 "FAILED <nodeid>" / "ERROR <nodeid>" 行即失败用例清单。
        # 去掉 FAILED 前缀（区块标题已说明），collection error 保留 (error) 后缀以区分。
        # -a 必需：pytest 用例可能把二进制内容打进 stdout，一旦日志被判为
        # binary，裸 grep 只输出 "Binary file ... matches" 这种假条目。
        # 这两个前缀由 pytest 输出在行首，故保留行首锚定。
        local names
        names=$(LC_ALL=C grep -aE "^(FAILED|ERROR) " "$output_file" \
            | sed -E 's/ - .*$//; s/^FAILED //; s/^ERROR (.*)$/\1 (error)/' | sort -u)
        R_FAILLIST["$case_name"]="$names"
    fi

    if [[ $passed_count -eq 0 ]] && [[ $failed_count -eq 0 ]] && [[ $error_count -eq 0 ]]; then
        notes+="ran but produced no test results (possible collection failure)"$'\n'
        status="FAIL"
    fi

    record_result "$case_name" "$passed_count" "$failed_count" "$skipped_count" \
        "$cov_ratio" "$status" "${notes%$'\n'}"

    [[ "$status" == "PASS" ]]
}

run_pytest_with_coverage() {
    local case_name="$1"
    local source_dir="$2"
    local test_dir="$3"
    local output_file="$4"
    local cov_dir="${BUILD_OUTPUT_DIR}/${case_name}_cov"

    # 先清理再重建：只 mkdir -p 会留下上一次的 .coverage，本次采集若失败，
    # 后面的 coverage report 会照旧读到旧数据并给出一个"看起来达标"的百分比，
    # 把"应产出覆盖率却缺失"的门禁一并绕过（实测复跑可复现）。
    rm -rf "${cov_dir}" "${BUILD_OUTPUT_DIR}/${case_name}_html"
    mkdir -p "${cov_dir}"
    # Each case gets its own COVERAGE_FILE so concurrent or sequential runs of
    # different components do not overwrite one another's .coverage data file.
    export COVERAGE_FILE="${cov_dir}/.coverage"

    python3 -m coverage run --source="${source_dir}" -m pytest "${test_dir}" 2>&1 | tee "${output_file}"
    local pytest_rc=${PIPESTATUS[0]}
    echo "${pytest_rc}" > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"

    # 返回码要先存再判：写成 `if ! cmd; then ... $? ...` 时 $? 是 ! 取反后的值
    # （恒为 0），打出来的 rc 是错的。
    # --precision=2：默认整数百分比会四舍五入（79.75% 显示成 80%），
    # 基线判定读的就是这一行，取整会让未达标的覆盖率蒙混过关。
    python3 -m coverage report --precision=2 2>&1 | tee -a "${output_file}"
    local report_rc=${PIPESTATUS[0]}
    if [[ ${report_rc} -ne 0 ]]; then
        # 报错要落进日志：覆盖率解析不到时 apply_cov_baseline 会判 FAIL，
        # 排障需要知道是采集/报告哪一步失败。
        echo "WARNING: coverage report failed (rc=${report_rc})" | tee -a "${output_file}"
    fi

    python3 -m coverage html -d "${BUILD_OUTPUT_DIR}/${case_name}_html" 2>&1 | tee -a "${output_file}"
    local html_rc=${PIPESTATUS[0]}
    if [[ ${html_rc} -ne 0 ]]; then
        echo "WARNING: coverage html failed (rc=${html_rc})" | tee -a "${output_file}"
    fi

    unset COVERAGE_FILE
    return "${pytest_rc}"
}

run_pytest_plain() {
    local case_name="$1"
    local test_dir="$2"
    local output_file="$3"
    shift 3
    python3 -m pytest "${test_dir}" "$@" 2>&1 | tee "${output_file}"
    local pytest_rc=${PIPESTATUS[0]}
    echo "${pytest_rc}" > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
    return "${pytest_rc}"
}

# Collect C++ gcov coverage for a gtest case (e.g. msprof_ut).
# $1 case_name (used for *_cov / *_html dir naming, aligned with pytest cases)
# $2 capture_dir: build subdir holding .gcno/.gcda (the UT build tree)
# $3 extract_arg: 覆盖率统计口径。可为：
#      - lcov path glob（如 '*/src/msprof/*'），按通配符保留；
#      - 一个已存在的白名单文件路径，按其中逐行列出的源文件精确保留。
# $4 output_file: test log to append the coverage summary to
collect_gcov_coverage() {
    local case_name="$1"
    local capture_dir="$2"
    local extract_arg="$3"
    local output_file="$4"
    local cov_dir="${BUILD_OUTPUT_DIR}/${case_name}_cov"
    local html_dir="${BUILD_OUTPUT_DIR}/${case_name}_html"
    # lcov/geninfo and genhtml accept different --ignore-errors categories
    # (e.g. gcov/mismatch are capture-only), so keep two separate lists.
    local ign="--ignore-errors=mismatch,gcov,source,negative,unused,empty,inconsistent"
    local html_ign="--ignore-errors=source,inconsistent,unmapped,category,corrupt"

    # 同 pytest 分支：先清理，避免 lcov 本次失败时 --summary 读到上一轮遗留的
    # coverage.info，用历史数据把基线顶上去。
    rm -rf "${cov_dir}" "${html_dir}"
    mkdir -p "${cov_dir}"

    # baseline (zero counts for every instrumented file) so files that no test
    # exercised still count toward the denominator, like coverage.py --source.
    lcov -c -i -d "${capture_dir}" -o "${cov_dir}/base.info" ${ign} >> "${output_file}" 2>&1
    lcov -c -d "${capture_dir}" -o "${cov_dir}/run.info" ${ign} >> "${output_file}" 2>&1
    lcov -a "${cov_dir}/base.info" -a "${cov_dir}/run.info" \
        -o "${cov_dir}/total.info" ${ign} >> "${output_file}" 2>&1
    # 口径：白名单文件 → 按文件列表精确 extract；否则按通配符 extract。
    if [[ -f "${extract_arg}" ]]; then
        local extract_files=()
        local _f
        while IFS= read -r _f; do
            [[ -n "${_f}" ]] && extract_files+=("${_f}")
        done < "${extract_arg}"
        lcov --extract "${cov_dir}/total.info" "${extract_files[@]}" \
            -o "${cov_dir}/coverage.info" ${ign} >> "${output_file}" 2>&1
    else
        lcov --extract "${cov_dir}/total.info" "${extract_arg}" \
            -o "${cov_dir}/coverage.info" ${ign} >> "${output_file}" 2>&1
    fi

    genhtml "${cov_dir}/coverage.info" -o "${html_dir}" ${html_ign} >> "${output_file}" 2>&1

    local cov_ratio
    cov_ratio=$(lcov --summary "${cov_dir}/coverage.info" ${ign} 2>&1 \
        | grep -E "lines\.+:" | head -1 | grep -oE "[0-9]+\.[0-9]+%" | head -1 | sed 's/%//')
    # validate_gtest_result 从 R_COV 取值填表，此处只记录不打印。
    R_COV["${case_name}"]="${cov_ratio:--}"
}

# 动态生成 msprof 覆盖率统计白名单：
# oam-tools 本仓只编译/安装 acp 与 msprofbin 两个模块，其余 lib(profapi/profimpl/
# msprofiler 等)在 runtime 仓编译。覆盖率只应统计这两个模块实际编译的源文件，
# 因此从二者的生产 CMakeLists 动态解析源文件清单，避免分母混入本仓不编译的代码。
# $1 输出白名单文件路径
gen_msprof_cov_whitelist() {
    local out_file="$1"
    local collector_dir="${BASEPATH}/src/msprof/collector"
    python3 - "$collector_dir" "$out_file" <<'PYEOF'
import os, re, sys
collector = sys.argv[1]
out_file = sys.argv[2]
dvvp = os.path.join(collector, "dvvp")
varmap = {
    "PROF_BASIC_DIR": os.path.join(collector, "basic"),
    "MSPROF_SOURCE_DIR": collector,
    "MSPROF_DIR": os.path.join(collector, "..", ".."),
}
def resolve(token, cmdir):
    m = re.match(r'\$\{([A-Z_]+)\}/(.*)', token)
    if m:
        var, rest = m.group(1), m.group(2)
        if var in varmap:
            return os.path.normpath(os.path.join(varmap[var], rest))
        return None
    if token.startswith("$"):
        return None
    return os.path.normpath(os.path.join(cmdir, token))
srcs = set()
for cm in [os.path.join(dvvp, "acp", "CMakeLists.txt"),
           os.path.join(dvvp, "msprofbin", "CMakeLists.txt")]:
    if not os.path.isfile(cm):
        continue
    cmdir = os.path.dirname(cm)
    txt = open(cm).read()
    for tok in re.findall(r'[^\s"()]+\.(?:cpp|c)\b', txt):
        p = resolve(tok, cmdir)
        if p and os.path.isfile(p):
            srcs.add(os.path.abspath(p))
with open(out_file, "w") as f:
    for s in sorted(srcs):
        f.write(s + "\n")
print("msprof cov whitelist: %d source files" % len(srcs))
PYEOF
}

run_test_case() {
    local case_name="$1"
    local framework="${TEST_CASES[$case_name]}"
    local output_file="${BUILD_OUTPUT_DIR}/${case_name}_output.log"
    local return_code=0

    echo "---"
    echo "STARTING TEST: **$case_name** (Framework: $framework)"

    cd "${BASEPATH}"

    case "$case_name" in
        host_ut)
            # Host tests exercise standalone Python tools without device conftests.
            run_pytest_plain "${case_name}" "./test/host" "${output_file}" \
                "--confcutdir=${BASEPATH}/test/host"
            ;;
        asys_st)
            run_pytest_with_coverage "${case_name}" "./src/asys" "./test/st/asys/testcase" "${output_file}"
            ;;
        asys_ut)
            run_pytest_with_coverage "${case_name}" "./src/asys" "./test/ut/asys/testcase" "${output_file}"
            ;;
        msaicerr_st)
            run_pytest_with_coverage "${case_name}" "./src/msaicerr" "./test/st/msaicerr/testcase" "${output_file}"
            ;;
        msaicerr_ut)
            run_pytest_with_coverage "${case_name}" "./src/msaicerr" "./test/ut/msaicerr/testcase" "${output_file}"
            ;;
        msprof_ut)
            local msprof_ut_manifest="${BUILD_OUTPUT_DIR}/msprof_ut_targets.txt"
            local msprof_ut_capture_dir="${BUILD_OUTPUT_DIR}/test/ut/msprof"
            local msprof_ut_rc=0
            : > "${output_file}"
            # 必须在跑二进制之前清 .gcda：.gcda 由本次运行产出，而 gcov 的
            # 计数是累加的——同一个 build tree 复跑时，上一轮的执行痕迹会被
            # 本轮带进来，本次没覆盖到的代码也算作已覆盖，80% 门禁被顶上去。
            # 不能挪进 collect_gcov_coverage（在运行之后）：那时删掉的就是本轮
            # 自己的数据，lcov 采集到空结果。.gcno 是编译产物，不能删。
            if [[ "${RUN_COV}" == "true" && -d "${msprof_ut_capture_dir}" ]]; then
                find "${msprof_ut_capture_dir}" -name '*.gcda' -type f -delete 2>/dev/null
            fi
            if [[ ! -f "${msprof_ut_manifest}" ]]; then
                echo "ERROR: msprof ut target manifest not found at ${msprof_ut_manifest}" | tee -a "${output_file}"
                echo "1" > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
                return 1
            fi
            while IFS= read -r ut_bin; do
                [[ -z "${ut_bin}" ]] && continue
                if [[ -f "${ut_bin}" ]]; then
                    # 前置 \n 是必需的：该标记紧接在上一个二进制的输出之后写入，
                    # 若上一个二进制崩溃在 printf 中途（末行无换行），标记会被拼到
                    # 那半行中间，count_gtest_targets 的行首匹配就数不到它——
                    # started 少一个，恰好与 finished 相等，真截断反而判不出 CRASH。
                    printf '\n----- running %s -----\n' "${ut_bin}" >> "${output_file}"
                    "${ut_bin}" 2>&1 | tee -a "${output_file}"
                    [[ ${PIPESTATUS[0]} -eq 0 ]] || msprof_ut_rc=1
                else
                    echo "ERROR: msprof_utest binary not found at ${ut_bin}" | tee -a "${output_file}"
                    msprof_ut_rc=1
                fi
            done < "${msprof_ut_manifest}"
            echo ${msprof_ut_rc} > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
            if [[ "${RUN_COV}" == "true" ]]; then
                local msprof_cov_whitelist="${BUILD_OUTPUT_DIR}/msprof_cov_files.txt"
                gen_msprof_cov_whitelist "${msprof_cov_whitelist}" >> "${output_file}" 2>&1
                collect_gcov_coverage "${case_name}" \
                    "${msprof_ut_capture_dir}" \
                    "${msprof_cov_whitelist}" "${output_file}"
            fi
            ;;
        install_st)
            run_pytest_plain "${case_name}" "./test/st/install/testcase" "${output_file}"
            ;;
        upgrade_st)
            run_pytest_plain "${case_name}" "./test/st/upgrade/testcase" "${output_file}"
            ;;
        uninstall_st)
            run_pytest_plain "${case_name}" "./test/st/uninstall/testcase" "${output_file}"
            ;;
        *)
            echo "ERROR: Unknown test case: $case_name"
            return 1
            ;;
    esac

    echo "END TEST: **$case_name**"

    if [[ "$framework" == "gtest" ]]; then
        validate_gtest_result "$output_file" "$case_name" || return_code=1
    elif [[ "$framework" == "pytest" ]]; then
        validate_pytest_result "$output_file" "$case_name" || return_code=1
    fi

    # 逐用例集不再打印统计和原始日志；结果汇总到 print_summary 统一呈现。
    echo "log saved to: **$output_file**"

    return $return_code
}

# 判断某用例集是否"应当产出覆盖率"。
# asys/msaicerr 走 run_pytest_with_coverage，无条件采集 coverage.py；
# msprof 仅在 --cov 时采集 gcov；install/upgrade/uninstall 走 run_pytest_plain，
# 本就没有覆盖率口径。
# 这个区分是必要的：不能靠"R_COV 是 -"反推无口径——采集链路故障（coverage
# report 失败、无 TOTAL 行、lcov 解析失败）同样会留下 "-"，若一并跳过校验，
# 覆盖率门禁在最该拦的时候失效。
case_expects_coverage() {
    case "$1" in
        asys_ut|asys_st|msaicerr_ut|msaicerr_st)
            return 0
            ;;
        msprof_ut)
            [[ "${RUN_COV}" == "true" ]]
            ;;
        *)
            return 1
            ;;
    esac
}

# 覆盖率基线校验：低于基线、或应产出却缺失/非数字，均改判为 FAIL。
apply_cov_baseline() {
    local case_name
    for case_name in "$@"; do
        local cov="${R_COV[$case_name]:--}"

        if ! case_expects_coverage "$case_name"; then
            continue
        fi

        # 应产出覆盖率却拿不到有效数字：采集链路出了问题，不能放行。
        if [[ "$cov" == "-" ]] || [[ ! "$cov" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
            COV_MISSING+=("$case_name")
            R_NOTES["$case_name"]="${R_NOTES[$case_name]:+${R_NOTES[$case_name]}$'\n'}coverage expected but not collected (got '${cov}'); check coverage report / lcov output in the log"
            if [[ "${R_STATUS[$case_name]}" == "PASS" ]]; then
                R_STATUS["$case_name"]="FAIL"
            fi
            continue
        fi

        # 整数比较即可，覆盖率取整后与基线比（79.9% 视为 79，低于 80）。
        if [[ ${cov%%.*} -lt $COV_BASELINE ]]; then
            COV_BELOW_BASELINE+=("$case_name")
            if [[ "${R_STATUS[$case_name]}" == "PASS" ]]; then
                R_STATUS["$case_name"]="FAIL"
            fi
        fi
    done
}

print_summary() {
    local test_cases=("$@")
    local case_name
    local total_passed=0 total_failed=0 total_skipped=0
    local overall="PASS"

    echo ""
    echo "========================================================================"
    printf " TEST SUMMARY   (coverage baseline: %s%%)\n" "$COV_BASELINE"
    echo "========================================================================"
    printf " %-14s %-10s %7s %7s %8s %5s   %s\n" \
        "SUITE" "FRAMEWORK" "PASSED" "FAILED" "SKIPPED" "COV" "RESULT"
    echo "------------------------------------------------------------------------"

    for case_name in "${test_cases[@]}"; do
        local status="${R_STATUS[$case_name]:-CRASH}"
        local passed="${R_PASSED[$case_name]:--}"
        local failed="${R_FAILED[$case_name]:--}"
        local skipped="${R_SKIPPED[$case_name]:--}"
        local cov="${R_COV[$case_name]:--}"
        # 显示取整，与基线判定口径一致（79.9% 判为 79）；原始值在下方明细里给出。
        [[ "$cov" != "-" ]] && cov="${cov%%.*}%"

        # 崩溃用例集的计数不可信，不计入 TOTAL，避免把崩溃摊薄成"没失败"。
        if [[ "$passed" =~ ^[0-9]+$ ]]; then
            total_passed=$((total_passed + passed))
            total_failed=$((total_failed + failed))
            total_skipped=$((total_skipped + skipped))
        fi

        [[ "$status" == "PASS" ]] || overall="FAIL"

        printf " %-14s %-10s %7s %7s %8s %5s   %s\n" \
            "$case_name" "${TEST_CASES[$case_name]}" "$passed" "$failed" "$skipped" "$cov" "$status"
    done

    echo "------------------------------------------------------------------------"
    printf " %-14s %-10s %7s %7s %8s %5s   %s\n" \
        "TOTAL" "" "$total_passed" "$total_failed" "$total_skipped" "" "$overall"
    echo "========================================================================"

    if [[ "$overall" == "PASS" ]]; then
        return 0
    fi

    echo ""
    echo "FAILED CASES"
    echo "------------------------------------------------------------------------"
    for case_name in "${test_cases[@]}"; do
        local status="${R_STATUS[$case_name]:-CRASH}"
        [[ "$status" == "PASS" ]] && continue

        local faillist="${R_FAILLIST[$case_name]:-}"
        if [[ -n "$faillist" ]]; then
            printf "[%s] (%s)\n" "$case_name" "$(echo "$faillist" | grep -c .)"
            while IFS= read -r name; do
                [[ -n "$name" ]] && echo "  ${name}"
            done <<< "$faillist"
        else
            printf "[%s]\n" "$case_name"
        fi

        local notes="${R_NOTES[$case_name]:-}"
        if [[ -n "$notes" ]]; then
            while IFS= read -r line; do
                [[ -n "$line" ]] && echo "  ${line}"
            done <<< "$notes"
        fi
    done
    echo "------------------------------------------------------------------------"

    if [[ ${#COV_BELOW_BASELINE[@]} -gt 0 ]]; then
        printf "COVERAGE BELOW BASELINE (%s%%)\n" "$COV_BASELINE"
        for case_name in "${COV_BELOW_BASELINE[@]}"; do
            printf "  %-14s %s%%   -> FAIL\n" "$case_name" "${R_COV[$case_name]}"
        done
        echo "------------------------------------------------------------------------"
    fi

    if [[ ${#COV_MISSING[@]} -gt 0 ]]; then
        echo "COVERAGE EXPECTED BUT NOT COLLECTED"
        for case_name in "${COV_MISSING[@]}"; do
            printf "  %-14s -> FAIL (coverage pipeline failed; see log)\n" "$case_name"
        done
        echo "------------------------------------------------------------------------"
    fi

    echo "full logs: ${BUILD_OUTPUT_DIR}/<suite>_output.log"
    echo "========================================================================"
    return 1
}

main() {
    parse_args "$@"

    mkdir -p "${BUILD_OUTPUT_DIR}"

    # Check if chip_handler.py exists when asys component is involved
    # (chip_handler.py is generated by cmake configure from chip_handler.py.in)
    if [[ "$COMPONENT" == "asys" || "$COMPONENT" == "all" ]]; then
        if [[ ! -f "${BASEPATH}/src/asys/common/chip_handler.py" ]]; then
            echo "ERROR: chip_handler.py not found at ${BASEPATH}/src/asys/common/chip_handler.py"
            echo "This file is generated by cmake configure from chip_handler.py.in."
            echo "Please run cmake configure first:"
            echo "  mkdir -p build && cd build && cmake .. && cd .."
            exit 1
        fi
    fi

    echo "========================================"
    echo "Test Configuration:"
    echo "  Component: $COMPONENT"
    echo "  Run UT: $RUN_UT"
    echo "  Run ST: $RUN_ST"
    echo "  Coverage baseline: ${COV_BASELINE}%"
    echo "  Output Dir: $BUILD_OUTPUT_DIR"
    echo "========================================"

    local test_cases=($(get_test_cases))

    if [[ ${#test_cases[@]} -eq 0 ]]; then
        echo "ERROR: No test cases to run"
        exit 1
    fi

    echo "INFO: Running test cases: ${test_cases[*]}"
    ensure_run_package_for_st_cases "${test_cases[@]}" || exit 1

    COV_BELOW_BASELINE=()
    COV_MISSING=()

    for case_name in "${test_cases[@]}"; do
        run_test_case "$case_name" || true
    done

    apply_cov_baseline "${test_cases[@]}"

    local overall_return_code=0
    print_summary "${test_cases[@]}" || overall_return_code=1

    if [[ $overall_return_code -eq 0 ]]; then
        echo "RESULT: All test cases passed"
    else
        echo "RESULT: One or more test cases failed"
    fi

    exit $overall_return_code
}

main "$@"
