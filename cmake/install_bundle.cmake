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

# 闭源包(bundle)拉取与解压：原 install_bundle.sh 的 CMake 版本。
# 按 架构 + 分支 拼出 OBS 地址，下载后解压到 ${OAM_TOOLS_DIR}/bundle。
set(OAM_BUNDLE_BASE_URL
    "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cann/oam-tools-diag")

# master 分支每日集成包（weekly）优先来源：ascend-cann bucket 按最近周三日期命名的
# {YYYYMMDD}_newest/ 目录。该 bucket 不开放列举（AccessDenied），无法自动发现，
# 故按"当天或已过周三用本周三，否则用上周三"推算日期拼地址。
set(OAM_BUNDLE_WEEKLY_BASE_URL
    "https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN")
# weekly 包取不到时的固定回退版本目录（cann-3rd bucket 同样不开放列举，
# 无法自动发现最新 weekly.NN，发布新版本时须人工同步此值）。
set(OAM_BUNDLE_WEEKLY_FALLBACK_VER "weekly.20260909.01")

# OBS 上实际存在包的分支白名单。新增 release 线时须在此同步，
# 并先确认 OBS bucket 下已上传对应的 <branch>/cann-oam-tools-release-<arch>.tar.gz。
# （已核实：截至当前仅 master、9.1.0 两条路径可下载，其余返回 403。）
set(OAM_BUNDLE_KNOWN_BRANCHES "master" "9.1.0")

# 记录 bundle/ 内容来自哪个分支。解压产物本身不含分支信息，切分支后复用旧 bundle
# 无从分辨，故取包成功后在此落一份元数据，下次命中已有 bundle 时据它校验。
set(OAM_BUNDLE_META_NAME ".bundle_branch")

# 发布线分支的识别模式：形如 9.1.0 或 9.1.0-beta.3 的远端分支都算发布线。
# 不硬编码具体 ref——同一条发布线上并存 9.1.0、9.1.0-beta.1/2/3 等多个分支，
# 硬编码任一个都会让其余分支探测不到而静默回退 master。
set(OAM_BUNDLE_RELEASE_REF_REGEX "^[0-9]+\\.[0-9]+\\.[0-9]+(-beta\\.[0-9]+)?$")

# 解析要拉取的 bundle 分支：显式指定 > git 探测(领先提交数最小) > master 兜底。
# 结果写入 RESULT_VAR（PARENT_SCOPE）。仅在确需从 OBS 下载时调用，
# 避免"bundle 已就绪 / 命中本地预置包"时做无谓的 git 探测或误触白名单校验。
function(oam_resolve_bundle_branch RESULT_VAR)
    # 1) 显式 -DOAM_BUNDLE_BRANCH 优先。
    if(DEFINED OAM_BUNDLE_BRANCH AND NOT OAM_BUNDLE_BRANCH STREQUAL "")
        message(STATUS "bundle branch (explicit): ${OAM_BUNDLE_BRANCH}")
        set(${RESULT_VAR} "${OAM_BUNDLE_BRANCH}" PARENT_SCOPE)
        return()
    endif()

    # 2) git 探测：对每个存在的候选 ref 算 HEAD 相对其分家点的领先提交数，
    #    取最小者（血缘最近）。git 不可用或无候选命中则回退。
    set(_best_branch "")
    set(_best_ahead "")
    # 自行确保 GIT_EXECUTABLE 可用，不依赖其他 cmake 文件的 include 顺序副作用
    # （当前 build_submodules.cmake 恰在本文件之前 include 并已 find_package(Git)，
    #  但那属实现细节，顺序一变本函数就会静默跳过探测）。找不到 git 时走 master 兜底。
    if(NOT GIT_EXECUTABLE)
        find_package(Git QUIET)
    endif()
    if(NOT GIT_EXECUTABLE)
        find_program(GIT_EXECUTABLE git)
    endif()
    if(GIT_EXECUTABLE)
        # 枚举已有的远端分支（各 remote 都算，fork 场景下 release 线常在 upstream），
        # 再按模式筛出发布线。这样同一条线上的 9.1.0 / 9.1.0-beta.N 都能命中，
        # 不必逐个硬编码 ref。
        execute_process(
            # --format 必须加引号：括号在 CMake 非引号实参里会被当作参数分隔，
            # 未加引号时该实参会被截成 "%"，git 只输出 "%" 而非分支名。
            COMMAND ${GIT_EXECUTABLE} for-each-ref "--format=%(refname:short)" refs/remotes
            WORKING_DIRECTORY "${OAM_TOOLS_DIR}"
            RESULT_VARIABLE _ls_result
            OUTPUT_VARIABLE _ls_out
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_VARIABLE _ls_err)
        if(NOT _ls_result EQUAL 0)
            message(WARNING
                "bundle branch detect: 'git for-each-ref refs/remotes' failed "
                "(code ${_ls_result}): ${_ls_err}; fall back to master")
            set(_ls_out "")
        endif()
        string(REPLACE "\n" ";" _remote_refs "${_ls_out}")
        foreach(_ref IN LISTS _remote_refs)
            # 去掉 remote 名前缀（origin/ 或 upstream/ 等），只看分支名本身。
            string(REGEX REPLACE "^[^/]+/" "" _name "${_ref}")
            # 归一化成 OBS 路径名：master 原样；发布线去掉 -beta.N 后缀（9.1.0-beta.3 -> 9.1.0）。
            if(_name STREQUAL "master")
                set(_mapped "master")
            elseif(_name MATCHES "${OAM_BUNDLE_RELEASE_REF_REGEX}")
                string(REGEX REPLACE "-beta\\.[0-9]+$" "" _mapped "${_name}")
            else()
                continue()
            endif()
            # 只保留 OBS 上确有包的分支作为候选：其余发布线（如尚未上传包的 9.2.0）
            # 直接忽略而非纳入比较，避免探测出一个必然触发白名单报错的分支。
            if(NOT _mapped IN_LIST OAM_BUNDLE_KNOWN_BRANCHES)
                continue()
            endif()
            # 领先提交数 = merge-base(HEAD, ref)..HEAD 的提交数。
            execute_process(
                COMMAND ${GIT_EXECUTABLE} rev-list --count "${_ref}..HEAD"
                WORKING_DIRECTORY "${OAM_TOOLS_DIR}"
                RESULT_VARIABLE _cnt_result
                OUTPUT_VARIABLE _ahead
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_VARIABLE _cnt_err)
            if(NOT _cnt_result EQUAL 0)
                # ref 已存在却仍数不出提交数，属异常（仓库损坏 / ref 格式异常等）。
                # 输出 WARNING 区分"正常回退"与"git 异常误回退"，便于排查。
                message(WARNING
                    "bundle branch detect: 'git rev-list --count ${_ref}..HEAD' failed "
                    "(code ${_cnt_result}): ${_cnt_err}; skip this candidate")
                continue()
            endif()
            if(_best_ahead STREQUAL "" OR _ahead LESS _best_ahead)
                set(_best_ahead "${_ahead}")
                set(_best_branch "${_mapped}")
            endif()
        endforeach()
    endif()

    if(NOT _best_branch STREQUAL "")
        message(STATUS "bundle branch (git-detected): ${_best_branch} (ahead ${_best_ahead})")
        set(${RESULT_VAR} "${_best_branch}" PARENT_SCOPE)
        return()
    endif()

    # 3) 兜底 master，保持无 git 环境 / CI 上的原有行为。
    message(STATUS "bundle branch (fallback): master")
    set(${RESULT_VAR} "master" PARENT_SCOPE)
endfunction()

# 推算最近的周三日期（YYYYMMDD）：当天是周三或已过周三用本周三，否则用上周三。
# 结果写入 RESULT_VAR（PARENT_SCOPE）。注意 CMake 的 string(TIMESTAMP) 不提供星期，
# 旧版（如 3.18）也不支持带自定义时间戳参数的四参 TIMESTAMP，故借当前 UNIX
# 时间戳对 1970-01-01（周四）取模换算：days%7 == 0 周四、1 周五、2 周六、
# 3 周日、4 周一、5 周二、6 周三。将日期转换为儒略日后减去天数差，再转回 YYYYMMDD。
# 日期和 days 均使用 UTC，避免非 UTC 时区的本地日期与 UTC 星期跨日错位。
function(oam_recent_wednesday RESULT_VAR)
    string(TIMESTAMP _today "%Y%m%d" UTC)
    string(TIMESTAMP _epoch "%s")
    math(EXPR _days "${_epoch} / 86400")
    math(EXPR _weekday "${_days} % 7")
    if(_weekday EQUAL 6)
        # 周三：本周三即今天。
        set(_back 0)
    else()
        # 周四~周二：最近一个已到来的周三在 w+1 天前（周四回 1 天，周二回 6 天）。
        # 周三当天已过（周四起）落在"本周三"，尚未到（周一/二）落在"上周三"。
        math(EXPR _back "${_weekday} + 1")
    endif()
    if(_back EQUAL 0)
        set(${RESULT_VAR} "${_today}" PARENT_SCOPE)
        return()
    endif()
    # 把 YYYYMMDD 拆成 y/m/d 数值，换算成儒略日做天级回退后再转回日期，
    # 避免手写跨月/跨年日历。儒略日公式取自 Fliegel & Van Flandern 算法。
    # 注意 math(EXPR) 不识别裸变量名（产生 dev 警告并按 0 参与运算），全部展开。
    string(SUBSTRING "${_today}" 0 4 _y)
    string(SUBSTRING "${_today}" 4 2 _m)
    string(SUBSTRING "${_today}" 6 2 _d)
    math(EXPR _jd "${_d} - 32075 + 1461 * (${_y} + 4800 + (${_m} - 14) / 12) / 4
        + 367 * (${_m} - 2 - (${_m} - 14) / 12 * 12) / 12
        - 3 * ((${_y} + 4900 + (${_m} - 14) / 12) / 100) / 4")
    math(EXPR _jd "${_jd} - ${_back}")
    # 儒略日转回公历日期（Fliegel & Van Flandern 逆变换）。
    math(EXPR _l "${_jd} + 68569")
    math(EXPR _n "4 * ${_l} / 146097")
    math(EXPR _l "${_l} - (146097 * ${_n} + 3) / 4")
    math(EXPR _i "4000 * (${_l} + 1) / 1461001")
    math(EXPR _l "${_l} - 1461 * ${_i} / 4 + 31")
    math(EXPR _j "80 * ${_l} / 2447")
    set(_d "${_l} - 2447 * ${_j} / 80")
    math(EXPR _d "${_d}")
    math(EXPR _l "${_j} / 11")
    math(EXPR _m "${_j} + 2 - 12 * ${_l}")
    math(EXPR _y "100 * (${_n} - 49) + ${_i} + ${_l}")
    # 补零拼回 YYYYMMDD。
    string(LENGTH "${_m}" _m_len)
    if(_m_len LESS 2)
        set(_m "0${_m}")
    endif()
    string(LENGTH "${_d}" _d_len)
    if(_d_len LESS 2)
        set(_d "0${_d}")
    endif()
    set(${RESULT_VAR} "${_y}${_m}${_d}" PARENT_SCOPE)
endfunction()

function(oam_install_bundle)
    set(_bundle_dir "${OAM_TOOLS_DIR}/bundle")
    set(_bundle_meta "${_bundle_dir}/${OAM_BUNDLE_META_NAME}")

    # bundle 已存在且非空即视为就绪，跳过下载（--make_clean 会先删掉它以强制刷新）。
    # 空目录（上一轮下载失败留下的残壳）需重新拉取，否则会带空 bundle 继续、
    # 把"取包失败"推迟成后续 install() 阶段更难定位的报错。
    if(EXISTS "${_bundle_dir}" AND IS_DIRECTORY "${_bundle_dir}")
        file(GLOB _bundle_entries "${_bundle_dir}/*")
        if(_bundle_entries)
            # 复用已有 bundle 前必须核对它来自哪个分支：从 master 构建后切到 9.1.0
            # 直接 build.sh 会命中这里，若不校验就会继续混用 master 的闭源包，
            # 这正是本改动要修的场景（连显式 --bundle_branch 也会被静默忽略）。
            oam_resolve_bundle_branch(_bundle_branch)
            if(EXISTS "${_bundle_meta}")
                file(READ "${_bundle_meta}" _present_branch)
                string(STRIP "${_present_branch}" _present_branch)
                if(NOT _present_branch STREQUAL _bundle_branch)
                    message(FATAL_ERROR
                        "existing bundle at ${_bundle_dir} is from branch "
                        "'${_present_branch}' but this build targets '${_bundle_branch}'.\n"
                        "re-run build.sh --make_clean to refetch, "
                        "or pass --bundle_branch=${_present_branch} to keep using it.")
                endif()
                message(STATUS
                    "bundle already present at ${_bundle_dir} (branch ${_present_branch}), "
                    "skip download")
            else()
                # 本改动之前拉下的 bundle 没有元数据，无从核对；告警而非报错，
                # 避免让既有工作目录必须先 --make_clean 才能继续构建。
                message(WARNING
                    "existing bundle at ${_bundle_dir} has no ${OAM_BUNDLE_META_NAME} "
                    "metadata; cannot verify it matches target branch "
                    "'${_bundle_branch}'. run build.sh --make_clean to refetch if unsure.")
            endif()
            return()
        endif()
        message(STATUS "bundle dir empty, re-downloading")
    endif()

    # 架构直接用 CMAKE_SYSTEM_PROCESSOR（= uname -m），与原 install_bundle.sh 的 ARCH 一致：
    # x86_64 / aarch64 均原样进包名。
    if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|aarch64)$")
        message(FATAL_ERROR "unsupported arch for bundle download: ${CMAKE_SYSTEM_PROCESSOR}")
    endif()

    # 编译类型决定本地包名：release/debug（CMAKE_BUILD_TYPE 小写，空或未定义则默认 release），
    # 与原 install_bundle.sh 的 OUTPUT_FILE=${BASE_NAME}-${BUILD_TYPE}-${ARCH} 一致。
    # 注意 CMAKE_BUILD_TYPE 未定义时 `if(CMAKE_BUILD_TYPE STREQUAL "")` 判 false
    # （未定义变量在非引号比较里按 undefined 处理），须用 NOT DEFINED 一并兜底，
    # 否则 _build_type 为空、本地包名拼成 cann-oam-tools--<arch>.tar.gz（双横线）。
    if(NOT DEFINED CMAKE_BUILD_TYPE OR CMAKE_BUILD_TYPE STREQUAL "")
        set(_build_type "release")
    else()
        string(TOLOWER "${CMAKE_BUILD_TYPE}" _build_type)
    endif()

    # 本地预置包按编译类型查找；下载则始终取 release 包（debug 包只能本地提供，不下载）,
    # 与原脚本 URL 恒为 cann-oam-tools-release-${ARCH} 的行为一致。
    set(_local_tar_name "cann-oam-tools-${_build_type}-${CMAKE_SYSTEM_PROCESSOR}.tar.gz")
    set(_release_tar_name "cann-oam-tools-release-${CMAKE_SYSTEM_PROCESSOR}.tar.gz")

    file(MAKE_DIRECTORY "${_bundle_dir}")

    # 离线构建：优先用预置的本地包（含编译类型），命中则免下载。检测顺序与原脚本一致：
    # 先 build/（本地编译产物），再 CANN_3RD_LIB_PATH（原脚本的 ./third_party）。
    set(_local_tar "")
    foreach(_cand
        "${OAM_TOOLS_DIR}/build/${_local_tar_name}"
        "${CANN_3RD_LIB_PATH}/${_local_tar_name}")
        if(_local_tar STREQUAL "" AND EXISTS "${_cand}")
            set(_local_tar "${_cand}")
        endif()
    endforeach()

    # 取包来源的分支；仅在确知时才落 bundle/ 元数据，避免把"来源不明"记成目标分支。
    set(_bundle_branch "")

    if(NOT _local_tar STREQUAL "")
        # 预置包文件名不含分支信息（各分支同名），直接复用会静默混入其它分支的闭源包。
        # download_libs.py 会在包旁写 <tar>.branch 元数据，此处校验其与本次目标分支一致。
        # 无元数据者按旧约定放行（兼容手工预置的既有包），仅告警提示无法核对。
        if(EXISTS "${_local_tar}.branch")
            file(READ "${_local_tar}.branch" _local_tar_branch)
            string(STRIP "${_local_tar_branch}" _local_tar_branch)
            oam_resolve_bundle_branch(_bundle_branch)
            if(NOT _local_tar_branch STREQUAL _bundle_branch)
                message(FATAL_ERROR
                    "local bundle tarball branch mismatch: ${_local_tar} is from "
                    "'${_local_tar_branch}' but this build targets '${_bundle_branch}'.\n"
                    "re-run cmake/download_libs.py --bundle_branch=${_bundle_branch}, "
                    "or pass --bundle_branch=${_local_tar_branch} to match the prestaged package.")
            endif()
            message(STATUS "bundle local tarball branch verified: ${_local_tar_branch}")
        else()
            message(WARNING
                "local bundle tarball ${_local_tar} has no .branch metadata; "
                "cannot verify it matches the target branch. "
                "re-run cmake/download_libs.py to generate it.")
        endif()
        message(STATUS "bundle using local tarball: ${_local_tar}")
        file(COPY "${_local_tar}" DESTINATION "${_bundle_dir}")
        set(_tar_path "${_bundle_dir}/${_local_tar_name}")
    else()
        # 仅在确需下载时才解析分支：bundle 已就绪或命中本地预置包时不会走到这里，
        # 从而避免无谓的 git 探测，以及"有缓存却因分支校验失败"的误报。
        oam_resolve_bundle_branch(_bundle_branch)
        # 白名单硬校验：拼出的分支若 OBS 上没有对应包，立即报错，
        # 避免下载到 403 空包后把失败推迟到后续 install() 阶段更难定位。
        if(NOT _bundle_branch IN_LIST OAM_BUNDLE_KNOWN_BRANCHES)
            string(REPLACE ";" ", " _known "${OAM_BUNDLE_KNOWN_BRANCHES}")
            # 提示里逐个列出 --bundle_branch=<name>，不用 <...> 包裹取值列表：
            # 尖括号是 shell 重定向元字符，用户整行复制到终端会被解析为重定向而报错。
            set(_hint "")
            foreach(_b IN LISTS OAM_BUNDLE_KNOWN_BRANCHES)
                string(APPEND _hint " --bundle_branch=${_b}")
            endforeach()
            message(FATAL_ERROR
                "bundle branch '${_bundle_branch}' has no published package on OBS.\n"
                "known branches: ${_known}\n"
                "specify one explicitly, e.g.${_hint}")
        endif()
        set(_url "${OAM_BUNDLE_BASE_URL}/${_bundle_branch}/${_release_tar_name}")

        # master 分支优先取 ascend-cann bucket 按最近周三日期命名的集成包，
        # 取不到再回退 cann-3rd 的固定 weekly 版本目录；发布线分支仍走原地址。
        set(_urls "")
        if(_bundle_branch STREQUAL "master")
            oam_recent_wednesday(_wed)
            list(APPEND _urls
                "${OAM_BUNDLE_WEEKLY_BASE_URL}/${_wed}_newest/${_release_tar_name}|weekly ${_wed}"
                "${OAM_BUNDLE_BASE_URL}/master/${OAM_BUNDLE_WEEKLY_FALLBACK_VER}/${_release_tar_name}|fallback ${OAM_BUNDLE_WEEKLY_FALLBACK_VER}")
        else()
            list(APPEND _urls "${_url}|branch ${_bundle_branch}")
        endif()

        # 下载路径只提供 release 包；debug 构建若未预置本地 debug 包，将回退到 release bundle。
        set(_tar_path "${_bundle_dir}/${_release_tar_name}")
        set(_dl_ok FALSE)
        set(_last_url "")
        set(_first TRUE)
        foreach(_pair IN LISTS _urls)
            string(REGEX REPLACE "\\|.*$" "" _try_url "${_pair}")
            string(REGEX REPLACE "^.*\\|" "" _try_desc "${_pair}")
            if(NOT _first)
                # 首选源失败，正式切到备用源前告知用户：WARNING 级别 + 即将下载的完整地址。
                message(WARNING
                    "bundle download failed at ${_last_url} (${_dl_code}: ${_dl_msg}); "
                    "falling back to ${_try_url}")
            endif()
            set(_first FALSE)
            set(_last_url "${_try_url}")
            message(STATUS "bundle download (release only): ${_try_url} (${_try_desc})")
            file(DOWNLOAD "${_try_url}" "${_tar_path}"
                TLS_VERIFY OFF
                STATUS _dl_status
                LOG _dl_log)
            list(GET _dl_status 0 _dl_code)
            list(GET _dl_status 1 _dl_msg)
            if(_dl_code EQUAL 0)
                set(_dl_ok TRUE)
                break()
            endif()
            # 该源取不到（403/404/网络异常等）时清理残留。
            file(REMOVE "${_tar_path}")
        endforeach()
        if(NOT _dl_ok)
            message(FATAL_ERROR "bundle download failed from all sources\n"
                "last url: ${_last_url} (${_dl_code}: ${_dl_msg})\n${_dl_log}")
        endif()
    endif()

    # 解压到 bundle 目录，失败即报错（避免带残缺 bundle 继续构建）。
    file(ARCHIVE_EXTRACT
        INPUT "${_tar_path}"
        DESTINATION "${_bundle_dir}")

    # 解压后删除 tar 包，保持 bundle 目录只含解压产物。
    file(REMOVE "${_tar_path}")

    # 落分支元数据供下次复用时校验。仅在确知来源分支时写：命中本地预置包但其无
    # .branch 元数据时 _bundle_branch 为空，此时来源不明，不能记成目标分支。
    if(NOT _bundle_branch STREQUAL "")
        file(WRITE "${_bundle_meta}" "${_bundle_branch}\n")
    endif()
    message(STATUS "bundle ready at ${_bundle_dir}")
endfunction()

oam_install_bundle()
