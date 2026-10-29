# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helpers for comparing package payload and installed-tree permissions."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
import os
from pathlib import Path
import platform
import stat
import xml.etree.ElementTree as ET


ARCH = "x86_64" if platform.machine() in ("x86_64", "AMD64") else platform.machine()

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGE_XML_PATHS = sorted((REPO_ROOT / "scripts/package").rglob("*.xml"))

# oam_tools.xml 声明 copy_all=true：安装器 do_copy_files 走 `cp -af` 整树
# 拷贝，filter_install_type 不参与，所有 install_type 条目在任意模式下均
# 落地。下述过滤语义是对将来 copy_all=false 场景的前瞻建模：届时安装器按
# filelist 第 8 列过滤（cann-cmake scripts/install/common_func_v2.inc 的
# filter_install_type：full/debug 匹配全部条目，其余模式只匹配
# (all)|(<自身类型>)），期望集合需按同样规则裁剪。
FULL_INSTALL_TYPES = frozenset({"full", "debug"})

# 打包过程生成的元数据（cann-cmake scripts/package/filelist.py 的
# generate_filelist/generate_record_file 生成并显式 chmod）。载荷权限随构建
# 环境引入的 cann-cmake 版本漂移（master-058 chmod 0440、master-059 chmod 0640，
# 与 root/非 root 无关）；安装阶段由安装器按 filelist install_mod 强制，
# 安装树不受影响。CI 证据：PR #799 install ST 的
# test_package_payload_matches_baseline 中仅这两个条目出现 owner-write 位差异
# （基线 0440 / CI 实际 0640），其余 1400+ 条目一致。
PACKAGE_GENERATED_METADATA = frozenset(
    {
        "share/info/oam_tools/RECORD",
        "share/info/oam_tools/script/filelist.csv",
    }
)
# 比较上述集合内文件的 mode 时，两侧屏蔽 owner-write 位后比较；
# kind/target 与 group/world/特殊位仍严格断言。
_METADATA_MODE_DRIFT_MASK = ~stat.S_IWUSR

# msprof 分析 whl 由构建时从上游 OBS 日构建地址下载（内容与本仓无关，
# 独立演进，曾一夜之间新增 3 个 analysis/msinterface 文件——CI run#1448），
# 其文件集合无法用静态基线追踪：区内不做 missing/extra 集合断言，
# 但每个实际存在的条目仍强制安全断言（见 _entry_safe）。
UPSTREAM_DAILY_WHL_SUBTREES = ("tools/profiler/profiler_tool/",)

# 区内锚点（评审 2026-10-23）：漂移区对 missing 的容忍是双向的，若无
# 下限，基线 905 条区内条目会整体失去存在性看护——整棵 profiler 工具
# 消失也能静默通过。锚点是该子树的功能性入口（whl 本体、dist-info、
# analysis/lib64/msprof_analysis.so）：写进基线就必须实际存在；基线一旦
# 建模漂移区，锚点就必须在基线中——上游改名后重生成基线若丢失锚点，
# 会显式报错而非静默重开缺口（届时需同步更新本元组）。
UPSTREAM_DAILY_WHL_ZONE_ANCHORS = (
    "tools/profiler/profiler_tool/msprof-{{VERSION}}-py3-none-any.whl",
    "tools/profiler/profiler_tool/msprof-{{VERSION}}.dist-info",
    "tools/profiler/profiler_tool/analysis/lib64/msprof_analysis.so",
)


def _in_daily_whl_zone(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in UPSTREAM_DAILY_WHL_SUBTREES)

_XML_VAR_SUBSTITUTIONS = (
    ("$(TARGET_ENV)", "{{ARCH}}-linux"),
    ("$(ARCH)", "{{ARCH}}"),
)


@dataclass(frozen=True)
class Entry:
    kind: str
    mode: int
    path: str
    target: str = ""


def normalize_path(path: str, version: str | None = None) -> str:
    normalized = path.replace(f"{ARCH}-linux", "{{ARCH}}-linux")
    normalized = normalized.replace("x86-linux", "{{ARCH}}-linux")
    normalized = normalized.replace(f"lib/linux/{ARCH}", "lib/linux/{{ARCH}}")
    normalized = normalized.replace("lib/linux/aarch64", "lib/linux/{{ARCH}}")
    normalized = normalized.replace("lib/linux/x86_64", "lib/linux/{{ARCH}}")
    if version:
        normalized = normalized.replace(f"msprof-{version}", "msprof-{{VERSION}}")
    return normalized


def _actual_version(root: Path) -> str:
    for path in root.rglob("msprof-*.whl"):
        name = path.name
        if name.startswith("msprof-") and name.endswith("-py3-none-any.whl"):
            return name[len("msprof-") : -len("-py3-none-any.whl")]
    return ""


def collect_tree(root: Path) -> dict[str, Entry]:
    if not root.exists():
        raise AssertionError(f"tree root does not exist: {root}")

    version = _actual_version(root)
    entries: dict[str, Entry] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            kind = "l"
            mode = stat.S_IMODE(path.lstat().st_mode)
            target = str(path.readlink())
        elif path.is_dir():
            kind = "d"
            mode = stat.S_IMODE(path.stat().st_mode)
            target = ""
        else:
            kind = "f"
            mode = stat.S_IMODE(path.stat().st_mode)
            target = ""
        normalized = normalize_path(relative, version)
        entries[normalized] = Entry(
            kind, mode, normalized, normalize_path(target, version)
        )
    return entries


def load_baseline(path: Path, mode_column: str = "mode") -> dict[str, Entry]:
    entries: dict[str, Entry] = {}
    with path.open(encoding="utf-8", newline="") as source:
        lines = source.read().splitlines()
        try:
            header_line = next(line for line in lines if not line.startswith("#"))
        except StopIteration as error:
            raise AssertionError(f"baseline has no header: {path}") from error
        header = header_line.split("\t")
        data_lines = lines[lines.index(header_line) + 1 :]
    mode_index = header.index(mode_column)
    type_index = header.index("type")
    target_index = header.index("target")
    path_index = header.index("path")
    for line in data_lines:
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        entries[fields[path_index]] = Entry(
            fields[type_index],
            int(fields[mode_index], 8),
            fields[path_index],
            fields[target_index],
        )
    return entries


def _entry_matches(actual: Entry, expected: Entry, path: str) -> bool:
    if actual.kind != expected.kind or actual.target != expected.target:
        return False
    if path in PACKAGE_GENERATED_METADATA:
        return (actual.mode & _METADATA_MODE_DRIFT_MASK) == (
            expected.mode & _METADATA_MODE_DRIFT_MASK
        )
    return actual.mode == expected.mode


def _entry_safe(entry: Entry) -> bool:
    # 符号链接的 lstat mode 恒 0777（见 collect_tree），无权限语义，
    # 跳过 mode 检查；其余条目要求无 group/world 写位且无特殊位
    # （setuid/setgid/sticky），任一出现即视为上游投放危险权限。
    if entry.kind == "l":
        return True
    return entry.mode & 0o022 == 0 and entry.mode & 0o7000 == 0


def assert_tree_matches(
    root: Path, baseline: Path, mode_column: str = "mode", install_type: str | None = None
) -> None:
    actual = collect_tree(root)
    expected = load_baseline(baseline, mode_column)
    # 基线完整性：基线只要建模了漂移区，锚点就必须在基线中。锚点缺失
    # 说明上游改名后基线重生成未同步（或锚点元组过期），此时区内
    # missing 容忍会静默重开整棵工具消失的缺口，必须显式报错。
    if any(_in_daily_whl_zone(path) for path in expected):
        absent_anchors = sorted(
            path
            for path in UPSTREAM_DAILY_WHL_ZONE_ANCHORS
            if path not in expected
        )
        if absent_anchors:
            raise AssertionError(
                f"baseline {baseline} models the daily whl drift zone but is "
                f"missing anchor entries (upstream renamed or anchors stale): "
                f"{absent_anchors}"
            )
    if install_type is not None:
        excluded = install_type_exclusions(install_type)
        unmatched = sorted(excluded - set(expected))
        if unmatched:
            raise AssertionError(
                f"install_type '{install_type}' exclusions absent from baseline "
                f"{baseline} (stale baseline or broken XML mapping): {unmatched}"
            )
        expected = {
            path: entry for path, entry in expected.items() if path not in excluded
        }

    # 上游漂移区（msprof 日构建 whl 子树）内的 missing/extra 属上游独立
    # 演进（CI run#1448：本地构建 10-22 与 CI 构建 10-23 之间，上游 whl
    # 新增 3 个 analysis/msinterface 文件），静态基线无法追踪，不做集合
    # 断言；区外维持严格语义。两条例外仍强制：区内实际存在的 extra 条目
    # 逐条 _entry_safe 断言（上游投放 group/world 可写或带特殊位的文件
    # 照样拦截）；区内锚点条目不做 missing 容忍（见
    # UPSTREAM_DAILY_WHL_ZONE_ANCHORS——锚点写进基线就必须实际存在，
    # 整棵 profiler 工具消失会被拦下）。changed（两侧共有条目）区内区外
    # 均维持 _entry_matches 精确比对不变。
    missing = sorted(
        path
        for path in set(expected) - set(actual)
        if not _in_daily_whl_zone(path) or path in UPSTREAM_DAILY_WHL_ZONE_ANCHORS
    )
    extra = sorted(
        path
        for path in set(actual) - set(expected)
        if not _in_daily_whl_zone(path)
    )
    zone_extra = sorted(
        path for path in set(actual) - set(expected) if _in_daily_whl_zone(path)
    )
    unsafe_extra = [path for path in zone_extra if not _entry_safe(actual[path])]
    changed = sorted(
        path
        for path in set(actual) & set(expected)
        if not _entry_matches(actual[path], expected[path], path)
    )
    if missing or extra or unsafe_extra or changed:
        details = []
        if missing:
            details.append("missing entries:\n" + "\n".join(missing[:50]))
        if extra:
            details.append("extra entries:\n" + "\n".join(extra[:50]))
        if unsafe_extra:
            details.extend(
                "unsafe extra entry (upstream daily whl zone): "
                f"{path}: {actual[path]}"
                for path in unsafe_extra[:50]
            )
        if changed:
            details.extend(
                f"{path}: expected {expected[path]}, got {actual[path]}"
                for path in changed[:50]
            )
        raise AssertionError(
            f"permission baseline mismatch for {root}:\n" + "\n".join(details)
        )


def assert_run_package_mode(package: Path) -> None:
    mode = stat.S_IMODE(Path(package).stat().st_mode)
    assert mode == 0o755, f"run package must be 0755, got {mode:04o}"


def install_type_exclusions(install_type: str) -> set[str]:
    # <copy_all>true</copy_all> makes the installer copy the whole payload
    # (do_copy_files: `cp -af *`), bypassing filter_install_type entirely, so
    # every install type lands the full tree and the baseline applies as-is.
    if install_type in FULL_INSTALL_TYPES or _package_declares_copy_all():
        return set()
    excluded: set[str] = set()
    for declared_type, paths in _xml_install_type_paths().items():
        for part in declared_type.split(";"):
            if part == "all" or part == install_type:
                break
        else:
            excluded |= paths
    return excluded


def _package_declares_copy_all() -> bool:
    for xml_path in PACKAGE_XML_PATHS:
        root = ET.parse(xml_path).getroot()  # nosec B314 - repository-owned input
        for node in root.iter("copy_all"):
            if (node.text or "").strip().lower() == "true":
                return True
    return False


def _xml_install_type_paths() -> dict[str, set[str]]:
    paths_by_type: dict[str, set[str]] = {}
    for xml_path in PACKAGE_XML_PATHS:
        root = ET.parse(xml_path).getroot()  # nosec B314 - repository-owned input
        _collect_xml_install_paths(root, "all", paths_by_type)
    return paths_by_type


def _collect_xml_install_paths(node, inherited_type, paths_by_type):
    install_type = node.get("install_type") or inherited_type
    for declared_type, path in _xml_node_paths(node, install_type):
        normalized = _normalize_declared_path(path)
        if normalized:
            paths_by_type.setdefault(declared_type, set()).add(normalized)
    for child in node:
        if child.tag == "file":
            continue
        _collect_xml_install_paths(child, install_type, paths_by_type)


def _xml_node_paths(node, install_type):
    tag = node.tag
    if tag == "path":
        value = node.get("value")
        return [(install_type, value)] if value else []
    if tag == "generate_info":
        value, dst_path = node.get("value"), node.get("dst_path")
        if value and dst_path:
            return [(install_type, f"{dst_path}/{value}")]
        return []
    if tag == "file_info":
        dst_path = node.get("dst_path") or ""
        entries = []
        for child in node.findall("file"):
            value = child.get("value")
            if not value:
                continue
            file_dst = child.get("dst_path") or dst_path
            path = f"{file_dst}/{value}" if file_dst else value
            entries.append((child.get("install_type") or install_type, path))
        return entries
    return []


def _normalize_declared_path(path):
    normalized = path.strip().strip("/")
    for var, replacement in _XML_VAR_SUBSTITUTIONS:
        normalized = normalized.replace(var, replacement)
    return normalized


def current_installation_is_private() -> bool:
    """Default installations are private for non-root and shared for root."""

    return os.geteuid() != 0


def write_package_baseline(root: Path, output: Path) -> None:
    entries = collect_tree(root)
    with output.open("w", encoding="utf-8", newline="\n") as target:
        _write_license_header(target)
        target.write("type\tmode\ttarget\tpath\n")
        for path, entry in sorted(entries.items()):
            target.write(
                f"{entry.kind}\t{entry.mode:04o}\t{entry.target}\t{path}\n".rstrip()
                + "\n"
            )
    _write_meta(output, len(entries))


def write_installed_baseline(
    private_root: Path, shared_root: Path, output: Path
) -> None:
    private = collect_tree(private_root)
    shared = collect_tree(shared_root)
    if set(private) != set(shared):
        only_private = sorted(set(private) - set(shared))
        only_shared = sorted(set(shared) - set(private))
        raise AssertionError(
            "private/shared trees differ:\n"
            f"only private: {only_private[:30]}\nonly shared: {only_shared[:30]}"
        )

    with output.open("w", encoding="utf-8", newline="\n") as target:
        _write_license_header(target)
        target.write("type\tmode_private\tmode_shared\ttarget\tpath\n")
        for path in sorted(private):
            left = private[path]
            right = shared[path]
            if left.kind != right.kind or left.target != right.target:
                raise AssertionError(f"private/shared type or link mismatch: {path}")
            target.write(
                f"{left.kind}\t{left.mode:04o}\t{right.mode:04o}\t{left.target}\t{path}\n".rstrip()
                + "\n"
            )
    _write_meta(output, len(private))


def _write_meta(baseline: Path, entry_count: int) -> None:
    meta = baseline.with_name("baseline_meta.json")
    data = {}
    if meta.exists():
        data = json.loads(meta.read_text(encoding="utf-8"))
    data["arch"] = ARCH
    key = (
        "package_payload_entries"
        if baseline.stem == "package_payload"
        else "installed_tree_entries"
    )
    data[key] = entry_count
    data["normalization"] = ["{{ARCH}}-linux", "msprof-{{VERSION}}"]
    meta.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_license_header(target) -> None:
    target.write("# Copyright (c) 2026 Huawei Technologies Co., Ltd.\n")
    target.write('# Licensed under the Apache License, Version 2.0 (the "License");\n')
    target.write("# you may not use this file except in compliance with the License.\n")
    target.write("# You may obtain a copy of the License at\n")
    target.write("# http://www.apache.org/licenses/LICENSE-2.0\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    package = sub.add_parser("package")
    package.add_argument("root", type=Path)
    package.add_argument("output", type=Path)
    installed = sub.add_parser("installed")
    installed.add_argument("private_root", type=Path)
    installed.add_argument("shared_root", type=Path)
    installed.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.command == "package":
        write_package_baseline(args.root, args.output)
    else:
        write_installed_baseline(args.private_root, args.shared_root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
