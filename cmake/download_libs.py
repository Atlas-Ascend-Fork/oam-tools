#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import os
import re
import sys
import argparse
import logging
import subprocess
import shutil

logging.basicConfig(level=logging.INFO)

# 闭源包(bundle) OBS 基址与分支配置，须与 cmake/install_bundle.cmake 保持一致：
# 离线预置在此按分支拼出 bundle 下载地址，联编时 install_bundle.cmake 按同样规则解析分支。
OAM_BUNDLE_BASE_URL = (
    "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cann/oam-tools-diag"
)
# OBS 上实际提供包的分支白名单（与 install_bundle.cmake 的 OAM_BUNDLE_KNOWN_BRANCHES 同步）。
OAM_BUNDLE_KNOWN_BRANCHES = ("master", "9.1.0")
# 发布线分支的识别模式（与 install_bundle.cmake 的 OAM_BUNDLE_RELEASE_REF_REGEX 同步）：
# 形如 9.1.0 或 9.1.0-beta.3 的远端分支都算发布线。不硬编码具体 ref——同一条发布线上
# 并存 9.1.0、9.1.0-beta.1/2/3 等多个分支，硬编码任一个都会让其余分支探测不到而回退 master。
OAM_BUNDLE_RELEASE_REF_REGEX = re.compile(r"^\d+\.\d+\.\d+(-beta\.\d+)?$")
# 需预置的目标架构；离线机器无法预知目标架构，两种都下以覆盖 x86_64 / aarch64 构建。
OAM_BUNDLE_ARCHES = ("x86_64", "aarch64")


def map_ref_to_obs_branch(ref):
    """把远端 ref 归一化为 OBS 路径名；非发布线返回 None。

    去掉 remote 前缀后：master 原样；发布线去掉 -beta.N 后缀（9.1.0-beta.3 -> 9.1.0）。
    """
    name = ref.split("/", 1)[-1]
    if name == "master":
        return "master"
    if OAM_BUNDLE_RELEASE_REF_REGEX.match(name):
        return re.sub(r"-beta\.\d+$", "", name)
    return None


def detect_bundle_branch():
    """git 探测所属发布分支：枚举远端分支，取领先提交数最小者（血缘最近）。

    与 cmake/install_bundle.cmake 的 oam_resolve_bundle_branch 探测逻辑一致；
    git 不可用或无候选命中时返回 None，由调用方兜底 master。
    """
    git_path = shutil.which("git")
    if not git_path:
        return None
    listed = subprocess.run(
        [git_path, "for-each-ref", "--format=%(refname:short)", "refs/remotes"],
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0:
        logging.warning(
            "git for-each-ref refs/remotes failed: %s", listed.stderr.strip()
        )
        return None
    best_branch = None
    best_ahead = None
    for ref in listed.stdout.split():
        mapped = map_ref_to_obs_branch(ref)
        # 只比较 OBS 上确有包的分支，避免探测出必然触发白名单报错的发布线。
        if mapped is None or mapped not in OAM_BUNDLE_KNOWN_BRANCHES:
            continue
        count = subprocess.run(
            [git_path, "rev-list", "--count", f"{ref}..HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if count.returncode != 0:
            logging.warning(
                "git rev-list --count %s..HEAD failed: %s", ref, count.stderr.strip()
            )
            continue
        ahead = int(count.stdout.strip() or "0")
        if best_ahead is None or ahead < best_ahead:
            best_ahead = ahead
            best_branch = mapped
    return best_branch


def resolve_bundle_branch(explicit=None):
    """解析要预置的 bundle 分支：显式指定 > git 探测 > master 兜底。

    与 install_bundle.cmake 一致，并对结果做白名单硬校验，避免拼出无对应包的地址。
    """
    branch = explicit if explicit else (detect_bundle_branch() or "master")
    if branch not in OAM_BUNDLE_KNOWN_BRANCHES:
        known = ", ".join(OAM_BUNDLE_KNOWN_BRANCHES)
        raise ValueError(
            f"bundle branch '{branch}' has no published package on OBS; known branches: {known}"
        )
    return branch


def bundle_urls(branch):
    """按分支拼各架构的 bundle 下载地址（下载路径恒为 release 包）。"""
    return [
        (f"{OAM_BUNDLE_BASE_URL}/{branch}/cann-oam-tools-release-{arch}.tar.gz",)
        for arch in OAM_BUNDLE_ARCHES
    ]


def write_bundle_branch_metadata(branch, tar_paths):
    """在预置包旁写 <tar>.branch 元数据，记录该包来自哪个分支。

    预置包文件名不含分支信息（各分支同名），联编时无从分辨。install_bundle.cmake
    命中本地预置包后会读此文件校验分支，不匹配则在配置阶段报错，
    避免离线/缓存构建静默混入其它分支的闭源包。

    tar_paths 只应传本轮确实下载成功的包：仅按文件是否存在来写，会把目录里
    残留的旧分支 tar 误标成本轮分支，联编时反而错误通过校验。
    """
    for tar_path in tar_paths:
        meta_path = f"{tar_path}.branch"
        with open(meta_path, "w", encoding="utf-8") as meta_file:
            meta_file.write(f"{branch}\n")
        logging.info("Wrote bundle branch metadata %s -> %s", meta_path, branch)


def download_single_file(url, current_dir):
    """下载单个文件"""
    actual_url = url
    custom_name = None

    if isinstance(url, tuple):
        if len(url) == 1:
            actual_url = url[0]
        elif len(url) == 2:
            actual_url = url[0]
            custom_name = url[1]
        else:
            raise ValueError(f"URL tuple length must be 1 or 2, got {len(url)}")

    if actual_url.endswith(".git"):
        repo_name = actual_url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(current_dir, custom_name if custom_name else repo_name)
        logging.info("Start git clone %s", actual_url)

        git_path = shutil.which("git")
        result = subprocess.run(
            [git_path, "clone", actual_url, repo_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr}")
        logging.info("Successfully cloned to %s", repo_path)
        return repo_path

    file_name = custom_name if custom_name else actual_url.split("/")[-1]
    if not file_name:
        file_name = "downloaded_file"

    # 仅允许 https，杜绝 file:/ 等本地/自定义 scheme。
    if not actual_url.startswith("https://"):
        raise ValueError(f"only https url is allowed, got: {actual_url}")

    file_path = os.path.join(current_dir, file_name)
    # custom_name 可带相对子目录（如 patch/xxx.patch，对齐 cann-cmake 的补丁缓存查找路径）；
    # wget -O 不会自建目录，须先确保父目录存在。
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    logging.info("Start download %s", actual_url)

    wget_path = shutil.which("wget")
    if not wget_path:
        raise RuntimeError("wget not found in PATH")
    result = subprocess.run(
        [wget_path, "--no-check-certificate", "-O", file_path, actual_url],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # wget -O 会先建目标文件，失败时残留半截内容；留着会被后续误当作可用预置包。
        if os.path.exists(file_path):
            os.remove(file_path)
        raise RuntimeError(f"wget download failed: {result.stderr}")
    logging.info("Successfully saved to %s", file_path)
    return file_path


def download_files_native(url_list):
    """下载多个文件，返回本轮成功落盘的路径集合。

    单个失败不中断其余下载（保持原有行为），但失败者不进返回集合——
    调用方据此只给本轮确实取到的包写元数据，避免把目录里的旧包误标成新分支。
    """
    current_dir = os.getcwd()
    downloaded = set()
    for url in url_list:
        try:
            downloaded.add(download_single_file(url, current_dir))
        except (ValueError, RuntimeError, OSError) as e:
            logging.info("Download file from %s failed: %s", url, e)
    return downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="离线预置 oam-tools 编译依赖（第三方库 + 闭源 bundle 包 + 子仓）"
    )
    parser.add_argument(
        "--bundle_branch",
        default=None,
        help="预置哪个分支的闭源 bundle 包（可选 master / 9.1.0）。"
        "不指定则按当前 git 提交自动探测所属发布分支，探测不出时回退 master。"
        "须与联编时 build.sh --bundle_branch / install_bundle.cmake 的解析结果一致。",
    )
    args = parser.parse_args()

    # bundle 分支解析与 install_bundle.cmake 同规则：显式 > git 探测 > master 兜底 + 白名单校验。
    bundle_branch = resolve_bundle_branch(args.bundle_branch)
    logging.info("prefetch bundle for branch: %s", bundle_branch)

    # 三方件下载清单，须与本地构建引用（cann-cmake 各 tag 的 third_party/*.cmake）保持一致：
    # - 源码包优先 gitcode 镜像，其内容须与 cann-cmake 按 sha256 校验的 OBS 包一致；
    # - makeself 的源码包与补丁 cann-cmake 直接引用 OBS 地址，gitcode 无对应镜像；
    # - 补丁落盘位置须与 cann-cmake 的本地缓存查找路径一致：makeself-2.5.0.patch 与
    #   backport-CVE-2025-0838.patch 与 mockcpp-2.7-h5.patch 在 patch/ 子目录；
    # - 升级 cmake/fetch_cann_cmake.cmake 的 CANN_CMAKE_TAG 时，须同步核对 cann-cmake
    #   third_party/ 下各三方件的版本、地址与补丁路径。
    my_urls = [
        (
            "https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1"
            "/protobuf-25.1.tar.gz",
        ),
        (
            "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself"
            "/makeself-release-2.5.0.tar.gz",
        ),
        (
            "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself/fix"
            "/makeself-2.5.0.patch",
            "patch/makeself-2.5.0.patch",
        ),
        (
            "https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download"
            "/20230802.1/abseil-cpp-20230802.1.tar.gz",
        ),
        (
            "https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download"
            "/20230802.1-h0/backport-CVE-2025-0838.patch",
            "patch/backport-CVE-2025-0838.patch",
        ),
        (
            "https://gitcode.com/cann-src-third-party/boost/releases/download"
            "/v1.87.0/boost_1_87_0.tar.gz",
        ),
        (
            "https://gitcode.com/cann-src-third-party/googletest/releases/download"
            "/v1.14.0/googletest-1.14.0.tar.gz",
        ),
        (
            "https://gitcode.com/cann-src-third-party/mockcpp/releases/download"
            "/v2.7-h5/mockcpp-2.7-h5.patch",
            "patch/mockcpp-2.7-h5.patch",
        ),
        (
            "https://gitcode.com/cann-src-third-party/mockcpp/releases/download"
            "/v2.7-h2/mockcpp-2.7.tar.gz",
        ),
        # cann-cmake 工程仓 tar 包：版本须与 cmake/fetch_cann_cmake.cmake 的
        # CANN_CMAKE_TAG 保持一致，离线联编时供其 FetchContent 本地缓存分支使用。
        (
            "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cmake"
            "/cmake-master-059.tar.gz",
        ),
    ]
    # 闭源 bundle 包按解析出的分支拼地址（各架构一份），不再硬编码 master。
    bundle_url_list = bundle_urls(bundle_branch)
    my_urls.extend(bundle_url_list)
    my_urls.extend(
        [
            ("https://gitcode.com/Ascend/msprobe.git",),
            ("https://gitcode.com/Ascend/msprof.git",),
        ]
    )

    downloaded = download_files_native(my_urls)
    # 预置包名不含分支，旁写元数据供联编时校验，避免混用其它分支的闭源包。
    # 只给本轮确实下载成功的 bundle tar 写：否则目录里的旧分支包会被误标成本轮分支，
    # 联编时反而错误通过校验。
    bundle_tars = [
        os.path.join(os.getcwd(), url[0].split("/")[-1]) for url in bundle_url_list
    ]
    fetched_bundle_tars = [tar for tar in bundle_tars if tar in downloaded]
    if not fetched_bundle_tars:
        logging.error(
            "no bundle tarball downloaded for branch %s; "
            "offline build cannot use prestaged bundle",
            bundle_branch,
        )
        sys.exit(1)
    write_bundle_branch_metadata(bundle_branch, fetched_bundle_tars)
    # 本轮没取到的包若还留着上一轮的元数据，会被联编时当成"已核对"而错误放行；
    # 删掉元数据让 install_bundle.cmake 走"无元数据"告警分支，而非错误通过校验。
    for tar in bundle_tars:
        if tar in downloaded:
            continue
        logging.warning("bundle tarball not fetched this run: %s", tar)
        stale_meta = f"{tar}.branch"
        if os.path.exists(stale_meta):
            os.remove(stale_meta)
            logging.warning("removed stale branch metadata %s", stale_meta)
