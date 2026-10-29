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

"""Static package permission declarations stay explicit-safe on master files.

Unlike the ST baseline comparisons, these checks read only repository files
(no build required) and assert what is *declared*, not what a build produces:
declared install_mod values are valid octal without group/world write or
special bits, CMake permission-declaring commands (install(DIRECTORY/TARGETS/
FILES/PROGRAMS) and file(COPY)) never grant unsafe bits, and the scanner
itself sees every block.
"""

import json
from pathlib import Path
import pytest
import re
import sys
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from package_permission_guard import _normalize_declared_path  # noqa: E402


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_DIR = ROOT / "scripts/package"
XML_PATHS = sorted(PACKAGE_DIR.rglob("*.xml"))
CMAKE_PATHS = [
    ROOT / "CMakeLists.txt",
    *(ROOT).glob("*.cmake"),
    *(ROOT / "cmake").glob("**/*"),
    *(path for path in (ROOT / "src").rglob("CMakeLists.txt")),
    *(ROOT / "src").rglob("*.cmake"),
]
DATA_DIR = ROOT / "test/st/install/data"
BASELINE_META = DATA_DIR / "baseline_meta.json"


def test_xml_modes_are_safe_numeric_modes():
    modes = []
    for path in XML_PATHS:
        root = ET.parse(path).getroot()  # nosec B314 - repository-owned test input
        modes.extend(node.get("install_mod") for node in root.iter() if node.get("install_mod"))
    assert modes
    for mode in modes:
        assert re.fullmatch(r"[0-7]{3,4}", mode), f"invalid install_mod: {mode}"
        numeric = int(mode, 8)
        assert numeric & 0o022 == 0, f"mode {mode} grants group/world write"
        assert numeric & 0o7000 == 0, f"mode {mode} contains special bits"


def test_baseline_meta_matches_tsv_entries():
    meta = json.loads(BASELINE_META.read_text(encoding="utf-8"))
    package_count = _baseline_entry_count(DATA_DIR / "package_payload.tsv")
    installed_count = _baseline_entry_count(DATA_DIR / "installed_tree.tsv")
    assert meta["package_payload_entries"] == package_count
    assert meta["installed_tree_entries"] == installed_count


def test_xml_declared_paths_present_in_installed_tree():
    # Review 2026-10-27: a baseline regenerated on a branch behind master
    # silently lost a directory master's oam_tools.xml had declared
    # (<path value="tools/aml/lib64/aicore_stl/ascend960dt_aicore_stl"/>),
    # and only the full packaging pipeline caught it as an "extra entry".
    # Cross-check the declarations statically instead: every <path value=.../>
    # in the package XMLs (normalized the way the guard normalizes them) must
    # already be a row in installed_tree.tsv. Only the installed tree is
    # checked -- toolkit, var and {{ARCH}}-linux/{bin,conf,pkg_inc} exist only
    # after install, never inside the .run payload.
    declared = set()
    for path in XML_PATHS:
        root = ET.parse(path).getroot()  # nosec B314 - repository-owned test input
        for node in root.iter("path"):
            value = node.get("value")
            if value:
                declared.add(_normalize_declared_path(value))
    installed = {row["path"] for row in _tsv_data_rows(DATA_DIR / "installed_tree.tsv")}
    missing = sorted(declared - installed)
    assert not missing, (
        f"XML-declared install paths absent from installed_tree.tsv "
        f"(sync master and regenerate the baseline): {missing}"
    )


def test_baseline_tsv_modes_are_safe():
    # Review 2026-10-23: the drift-zone safety check in package_permission_guard
    # only guards entries that actually exist at compare time, and 905 zone rows
    # in these TSVs come from an upstream daily-built whl. If upstream ever
    # ships a group/world-writable or setuid file and the baseline is
    # regenerated, that mode would be baked in as the expected value and every
    # later compare would pass. Assert the stored modes directly so an unsafe
    # regeneration fails here instead.
    for path, mode_columns in (
        (DATA_DIR / "package_payload.tsv", ("mode",)),
        (DATA_DIR / "installed_tree.tsv", ("mode_private", "mode_shared")),
    ):
        rows = _tsv_data_rows(path)
        assert rows, f"baseline {path} has no data rows"
        offenders = []
        for row in rows:
            if row["type"] == "l":
                continue  # symlink lstat mode is always 0777, no meaning
            for column in mode_columns:
                mode = int(row[column], 8)
                location = f"{path.name}:{row['path']}:{column}={row[column]}"
                if mode & 0o022:
                    offenders.append(f"{location} grants group/world write")
                elif mode & 0o7000:
                    offenders.append(f"{location} has special bits")
        assert not offenders, f"unsafe modes in baseline TSVs: {offenders}"


def _strip_cmake_comments(text):
    """Drop '#' comments but keep '#' inside double-quoted CMake strings.

    A plain ``re.sub(r"#.*", ...)`` also eats a '#' inside a quoted path
    (``DESTINATION "dir#name"``) and deletes the rest of that line, so the
    closing paren and trailing permission keywords would silently escape
    the block scanner below. Scan character by character instead: '#'
    starts a comment only outside a string, and '\\"' inside a string is an
    escaped quote, not the string terminator.
    """
    stripped = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            stripped.append(char)
            if char == "\\" and index + 1 < len(text):
                stripped.append(text[index + 1])
                index += 1
            elif char == '"':
                in_string = False
        elif char == '"':
            stripped.append(char)
            in_string = True
        elif char == "#":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        else:
            stripped.append(char)
        index += 1
    return "".join(stripped)


def _install_command_blocks(text):
    """Extract install()/file(COPY) command blocks with quote-aware depth scan.

    Blocks start at install(DIRECTORY|TARGETS|FILES|PROGRAMS) or file(COPY) --
    every command form that can carry a PERMISSIONS family keyword -- and end
    at the matching close paren. Brackets inside a quoted argument
    (``PATTERN "x)y(w"``) must not affect the nesting count: a quote-internal
    ')' would truncate the block so trailing permission keywords escape the
    permission checks, while a quote-internal '(' would inflate the depth and
    swallow the next block. Parens inside comments are already gone because
    comment stripping runs before this scan.
    """
    text = _strip_cmake_comments(text)
    blocks = []
    starts = list(
        re.finditer(
            r"\b(?:install|file)\s*\(\s*(?:DIRECTORY|TARGETS|FILES|PROGRAMS|COPY)\b",
            text,
            re.IGNORECASE,
        )
    )
    for match in starts:
        depth = 1
        position = match.end()
        in_string = False
        while depth and position < len(text):
            char = text[position]
            if in_string:
                if char == "\\":
                    position += 2  # skip the escaped char, e.g. '\\"'
                    continue
                if char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            position += 1
        if depth:
            raise AssertionError("unbalanced install()/file(COPY) command block")
        blocks.append(text[match.start() : position])
    return blocks


def test_cmake_command_blocks_are_fully_scanned():
    for path in _cmake_paths():
        text = _strip_cmake_comments(path.read_text(encoding="utf-8"))
        primary = len(_install_command_blocks(text))
        # Deliberately different recount: a word-bounded "install(" or
        # "file(" keyword matched in two stages (keyword, then the leading
        # command argument) instead of the single combined regex driving the
        # block scanner. "reinstall(", "configure_file(" or
        # "install(FILES_MATCHING" match only one side, so equal counts here
        # mean the scanner neither swallowed nor split blocks -- sharing one
        # regex would make the assertion vacuous.
        independent = sum(
            1
            for match in re.finditer(r"\b(?:install|file)\s*\(", text, re.IGNORECASE)
            if re.match(
                r"\s*(?:DIRECTORY|TARGETS|FILES|PROGRAMS|COPY)\b",
                text[match.end():],
                re.IGNORECASE,
            )
        )
        assert primary == independent, (
            f"{path.relative_to(ROOT)}: block scanner extracted {primary} "
            f"permission-relevant command blocks, keyword recount found "
            f"{independent}"
        )


# Synthetic parser fixtures, one case per blind spot raised in review. Each
# entry is (case name, cmake text, expected block count, fragments that must
# be found inside the extracted blocks). Fragments deliberately pin the tail
# of a block (trailing keyword plus closing paren) so a block truncated at a
# quote-internal ')' fails the fragment assertions, not just the count.
_INSTALL_COMMAND_FIXTURES = [
    (
        "single-block",
        "install(DIRECTORY scripts/ DESTINATION share/scripts"
        " FILE_PERMISSIONS OWNER_READ)\n",
        1,
        ["DESTINATION share/scripts FILE_PERMISSIONS OWNER_READ)"],
    ),
    (
        "two-blocks",
        "install(DIRECTORY a DESTINATION x)\n"
        "install(DIRECTORY b DESTINATION y)\n",
        2,
        ["DESTINATION x)", "DESTINATION y)"],
    ),
    (
        "quote-internal-parens",
        'install(DIRECTORY a DESTINATION b PATTERN "x)y(w"'
        " FILE_PERMISSIONS OWNER_READ GROUP_READ)\n",
        1,
        ['PATTERN "x)y(w"', "GROUP_READ)"],
    ),
    (
        "quote-internal-hash",
        'install(DIRECTORY a DESTINATION "dir#name" FILE_PERMISSIONS'
        " OWNER_READ)\n",
        1,
        ['DESTINATION "dir#name" FILE_PERMISSIONS OWNER_READ)'],
    ),
    (
        "commented-out-declaration-ignored",
        "# install(DIRECTORY commented DESTINATION out) not real\n"
        "install(DIRECTORY real DESTINATION target)\n",
        1,
        ["DESTINATION target)"],
    ),
    (
        "in-block-comment-paren",
        "install(DIRECTORY a\n"
        "    # trailing ) must not close the block\n"
        "    DESTINATION target)\n",
        1,
        ["DESTINATION target)"],
    ),
    (
        "generator-expression-nested-parens",
        "install(DIRECTORY conf\n"
        "    DESTINATION $<JOIN:${CMAKE_INSTALL_SYSCONFDIR},/>\n"
        "    FILES_MATCHING PATTERN (a|b).conf\n"
        "    )\n",
        1,
        [
            "DESTINATION $<JOIN:${CMAKE_INSTALL_SYSCONFDIR},/>",
            "PATTERN (a|b).conf\n    )",
        ],
    ),
    (
        "escaped-quote-in-string",
        'install(DIRECTORY a DESTINATION "we\\"ird" FILE_PERMISSIONS'
        " OWNER_READ)\n",
        1,
        ['DESTINATION "we\\"ird" FILE_PERMISSIONS OWNER_READ)'],
    ),
    (
        "paren-inside-escaped-quote",
        'install(DIRECTORY a DESTINATION "we\\"ird)" FILE_PERMISSIONS'
        " OWNER_READ)\n",
        1,
        ['DESTINATION "we\\"ird)"', "FILE_PERMISSIONS OWNER_READ)"],
    ),
    (
        "targets-block-permissions",
        "install(TARGETS mytool RUNTIME DESTINATION bin"
        " PERMISSIONS OWNER_READ OWNER_EXECUTE)\n",
        1,
        ["PERMISSIONS OWNER_READ OWNER_EXECUTE)"],
    ),
    (
        "programs-block-permissions",
        "install(PROGRAMS scripts/tool.py DESTINATION bin"
        " PERMISSIONS OWNER_EXECUTE)\n",
        1,
        ["PERMISSIONS OWNER_EXECUTE)"],
    ),
    (
        "files-block-permissions",
        "install(FILES a.conf b.conf DESTINATION etc"
        " PERMISSIONS OWNER_READ)\n",
        1,
        ["PERMISSIONS OWNER_READ)"],
    ),
    (
        "file-copy-block-permissions",
        "file(COPY tools DESTINATION ${CMAKE_BINARY_DIR}/out"
        " FILE_PERMISSIONS OWNER_READ DIRECTORY_PERMISSIONS"
        " OWNER_READ OWNER_EXECUTE)\n",
        1,
        [
            "FILE_PERMISSIONS OWNER_READ DIRECTORY_PERMISSIONS",
            "OWNER_READ OWNER_EXECUTE)",
        ],
    ),
    (
        "files-matching-is-not-a-files-block",
        "install(DIRECTORY a DESTINATION b\n"
        "    FILES_MATCHING PATTERN \"*.conf\"\n"
        "    )\n",
        1,
        ['FILES_MATCHING PATTERN "*.conf"'],
    ),
]


@pytest.mark.parametrize(
    ("text", "expected_count", "expected_fragments"),
    [fixture[1:] for fixture in _INSTALL_COMMAND_FIXTURES],
    ids=[fixture[0] for fixture in _INSTALL_COMMAND_FIXTURES],
)
def test_install_command_parser_fixtures(text, expected_count, expected_fragments):
    blocks = _install_command_blocks(text)
    assert len(blocks) == expected_count, (
        f"expected {expected_count} block(s), parsed {len(blocks)}: {blocks!r}"
    )
    for fragment in expected_fragments:
        assert any(fragment in block for block in blocks), (
            f"fragment {fragment!r} not found in parsed blocks: {blocks!r}"
        )


def test_cmake_declared_permissions_do_not_grant_unsafe_bits():
    # Review 2026-10-23: install(DIRECTORY)-only scanning missed the other
    # permission-declaring command forms -- install(TARGETS/PROGRAMS) in
    # acp/msprofbin CMakeLists and file(COPY) in build_submodules.cmake.
    # The keyword check uses the "PERMISSIONS" substring so FILE_PERMISSIONS,
    # DIRECTORY_PERMISSIONS and the bare install(TARGETS) PERMISSIONS form
    # are all covered.
    permission_bits = ("GROUP_WRITE", "WORLD_WRITE", "SETUID", "SETGID")
    offenders = []
    for path in _cmake_paths():
        for block in _install_command_blocks(path.read_text(encoding="utf-8")):
            if "PERMISSIONS" not in block:
                continue
            if any(bit in block for bit in permission_bits):
                offenders.append(
                    f"{path.relative_to(ROOT)}:{block.splitlines()[0].strip()}"
                )
    assert not offenders, f"unsafe permission declarations: {offenders}"


def test_cmake_scan_set_covers_included_files():
    # Review 2026-10-23: the static permission checks only guard files listed
    # by _cmake_paths(), which used to miss .cmake files pulled in via
    # include() -- version.cmake from the root CMakeLists.txt, plus component
    # files like asys/asys.cmake and msprof_find_target.cmake. Pin one file
    # per include origin so future scan-set edits cannot silently drop
    # include()d files and let unsafe FILE_PERMISSIONS slip past the gate.
    scanned = set(_cmake_paths())
    for included in (
        ROOT / "version.cmake",
        ROOT / "src" / "asys" / "asys.cmake",
        ROOT / "src" / "msprof" / "collector" / "dvvp" / "msprof_find_target.cmake",
    ):
        assert included in scanned, (
            f"{included.relative_to(ROOT)} is include()d by a CMakeLists.txt "
            "but missing from the static permission scan set"
        )


def _cmake_paths():
    return sorted(
        set(
            path
            for path in CMAKE_PATHS
            if path.is_file() and path.suffix in {".cmake", ".txt"}
        )
    )


def _tsv_data_rows(path):
    """Baseline data rows as dicts: skip the '#' license header and blank lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header_line = next(line for line in lines if not line.startswith("#"))
    header = header_line.split("\t")
    rows = []
    for line in lines[lines.index(header_line) + 1 :]:
        if not line or line.startswith("#"):
            continue
        rows.append(dict(zip(header, line.split("\t"))))
    return rows


def _baseline_entry_count(path):
    return len(_tsv_data_rows(path))
