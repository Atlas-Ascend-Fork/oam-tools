# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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

"""Bounded, non-extracting reader for one directory or archive boundary."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import tarfile
import zipfile


@dataclass(frozen=True)
class ReaderLimits:
    max_entry_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 512 * 1024 * 1024
    max_archive_depth: int = 2


@dataclass(frozen=True)
class PackageEntry:
    source_path: str
    data: bytes
    content_sha256: str


class PackageReadError(ValueError):
    """Raised when the top-level input cannot be read as a package."""


class _Budget:
    def __init__(self, limits: ReaderLimits) -> None:
        self.limits = limits
        self.total_bytes = 0

    def rejection(self, size: int) -> str | None:
        if size > self.limits.max_entry_bytes:
            return "entry_size_limit"
        if self.total_bytes + size > self.limits.max_total_bytes:
            return "cumulative_size_limit"
        return None

    def consume(self, size: int) -> None:
        self.total_bytes += size


def read_package(
    input_path: Path, limits: ReaderLimits | None = None
) -> tuple[list[PackageEntry], list[dict[str, object]], str]:
    active_limits = limits or ReaderLimits()
    if min(
        active_limits.max_entry_bytes,
        active_limits.max_total_bytes,
        active_limits.max_archive_depth + 1,
    ) <= 0:
        raise PackageReadError("package limits must be positive")

    entries: list[PackageEntry] = []
    inventory: list[dict[str, object]] = []
    budget = _Budget(active_limits)

    if input_path.is_symlink():
        raise PackageReadError("top-level input cannot be a symbolic link")
    if input_path.is_dir():
        _read_directory(input_path, entries, inventory, budget)
    elif input_path.is_file():
        kind = _archive_kind_path(input_path)
        if kind is None:
            raise PackageReadError("input file is not a supported archive")
        _read_archive_path(input_path, kind, entries, inventory, budget)
    else:
        raise PackageReadError("input path does not exist")

    return entries, inventory, secrets.token_hex(8)


def _read_directory(
    root: Path,
    entries: list[PackageEntry],
    inventory: list[dict[str, object]],
    budget: _Budget,
) -> None:
    for source in sorted(root.rglob("*")):
        relative_path = source.relative_to(root).as_posix()
        try:
            metadata = source.lstat()
            if source.is_symlink() or stat.S_ISLNK(metadata.st_mode):
                inventory.append(_rejected(relative_path, "symbolic_link"))
                continue
            is_junction = getattr(source, "is_junction", None)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if (callable(is_junction) and is_junction()) or (
                reparse_flag
                and getattr(metadata, "st_file_attributes", 0) & reparse_flag
            ):
                inventory.append(_rejected(relative_path, "reparse_point"))
                continue
            if stat.S_ISDIR(metadata.st_mode):
                continue
            if not stat.S_ISREG(metadata.st_mode):
                inventory.append(_rejected(relative_path, "unsupported_entry_type"))
                continue
            if metadata.st_nlink > 1:
                inventory.append(_rejected(relative_path, "hard_link"))
                continue
            with source.open("rb") as stream:
                data, reason = _read_bounded(stream, metadata.st_size, budget)
        except OSError:
            inventory.append(_rejected(relative_path, "unreadable"))
            continue
        if reason:
            inventory.append(_rejected(relative_path, reason))
            continue
        budget.consume(len(data))
        _accept_or_descend(relative_path, data, 0, entries, inventory, budget)


def _read_archive_path(
    path: Path,
    kind: str,
    entries: list[PackageEntry],
    inventory: list[dict[str, object]],
    budget: _Budget,
) -> None:
    try:
        if kind == "zip":
            with zipfile.ZipFile(path) as archive:
                _read_zip_members(archive, "", 0, entries, inventory, budget)
        else:
            with tarfile.open(path, mode="r:*") as archive:
                _read_tar_members(archive, "", 0, entries, inventory, budget)
    except (OSError, tarfile.TarError, zipfile.BadZipFile, RuntimeError) as error:
        raise PackageReadError(f"cannot read input archive: {error}") from error


def _read_archive(
    data: bytes,
    prefix: str,
    depth: int,
    entries: list[PackageEntry],
    inventory: list[dict[str, object]],
    budget: _Budget,
) -> None:
    kind = _archive_kind(prefix, data)
    try:
        if kind == "zip":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                _read_zip_members(archive, prefix, depth, entries, inventory, budget)
        elif kind == "tar":
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                _read_tar_members(archive, prefix, depth, entries, inventory, budget)
        else:
            inventory.append(_rejected(prefix or "<input>", "unsupported_archive"))
    except (OSError, tarfile.TarError, zipfile.BadZipFile, RuntimeError):
        inventory.append(_rejected(prefix or "<input>", "unreadable_archive"))


def _read_zip_members(
    archive: zipfile.ZipFile,
    prefix: str,
    depth: int,
    entries: list[PackageEntry],
    inventory: list[dict[str, object]],
    budget: _Budget,
) -> None:
    for member in archive.infolist():
        if member.is_dir():
            continue
        source_path = _joined_path(prefix, member.filename)
        path_reason = _unsafe_path_reason(member.filename)
        if path_reason:
            inventory.append(_rejected(source_path, path_reason))
            continue
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            inventory.append(_rejected(source_path, "symbolic_link"))
            continue
        mode_type = stat.S_IFMT(mode)
        if member.create_system == 3 and mode_type not in {0, stat.S_IFREG}:
            inventory.append(_rejected(source_path, "unsupported_entry_type"))
            continue
        try:
            with archive.open(member) as stream:
                member_data, reason = _read_bounded(stream, member.file_size, budget)
        except (OSError, EOFError, RuntimeError, NotImplementedError, zipfile.BadZipFile):
            inventory.append(_rejected(source_path, "unreadable"))
            continue
        if reason:
            inventory.append(_rejected(source_path, reason))
            continue
        budget.consume(len(member_data))
        _accept_or_descend(source_path, member_data, depth, entries, inventory, budget)


def _read_tar_members(
    archive: tarfile.TarFile,
    prefix: str,
    depth: int,
    entries: list[PackageEntry],
    inventory: list[dict[str, object]],
    budget: _Budget,
) -> None:
    for member in archive:
        if member.isdir():
            continue
        source_path = _joined_path(prefix, member.name)
        path_reason = _unsafe_path_reason(member.name)
        if path_reason:
            inventory.append(_rejected(source_path, path_reason))
            continue
        if member.issym():
            inventory.append(_rejected(source_path, "symbolic_link"))
            continue
        if member.islnk():
            inventory.append(_rejected(source_path, "hard_link"))
            continue
        if not member.isfile():
            inventory.append(_rejected(source_path, "unsupported_entry_type"))
            continue
        try:
            extracted = archive.extractfile(member)
            if extracted is None:
                inventory.append(_rejected(source_path, "unreadable"))
                continue
            with extracted:
                member_data, reason = _read_bounded(extracted, member.size, budget)
        except (OSError, EOFError, tarfile.TarError):
            inventory.append(_rejected(source_path, "unreadable"))
            continue
        if reason:
            inventory.append(_rejected(source_path, reason))
            continue
        budget.consume(len(member_data))
        _accept_or_descend(source_path, member_data, depth, entries, inventory, budget)


def _read_bounded(stream: object, declared_size: int, budget: _Budget) -> tuple[bytes, str | None]:
    reason = budget.rejection(declared_size)
    if reason:
        return b"", reason
    remaining_total = budget.limits.max_total_bytes - budget.total_bytes
    read_limit = min(budget.limits.max_entry_bytes, remaining_total) + 1
    data = stream.read(read_limit)  # type: ignore[attr-defined]
    if len(data) > budget.limits.max_entry_bytes:
        return b"", "entry_size_limit"
    if len(data) > remaining_total:
        return b"", "cumulative_size_limit"
    return data, None


def _accept_or_descend(
    source_path: str,
    data: bytes,
    depth: int,
    entries: list[PackageEntry],
    inventory: list[dict[str, object]],
    budget: _Budget,
) -> None:
    kind = _archive_kind(source_path, data)
    if kind:
        inventory.append(_archive_record(source_path, data))
        if depth >= budget.limits.max_archive_depth:
            inventory.append(_rejected(source_path, "archive_depth_limit"))
            return
        _read_archive(data, source_path, depth + 1, entries, inventory, budget)
    elif _archive_candidate_kind(source_path, data):
        inventory.append(
            _rejected(
                source_path,
                "unreadable_archive",
                content_sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    else:
        entries.append(
            PackageEntry(source_path, data, hashlib.sha256(data).hexdigest())
        )


def _archive_kind(name: str, data: bytes) -> str | None:
    lower_name = name.lower()
    if zipfile.is_zipfile(io.BytesIO(data)):
        return "zip"
    if not name or lower_name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*"):
                return "tar"
        except tarfile.TarError:
            return None
    return None


def _archive_candidate_kind(name: str, data: bytes) -> str | None:
    lower_name = name.lower()
    if lower_name.endswith(".zip") or data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    if lower_name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        return "tar"
    return None


def _archive_kind_path(path: Path) -> str | None:
    try:
        if zipfile.is_zipfile(path):
            return "zip"
        if path.name.lower().endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
            with tarfile.open(path, mode="r:*"):
                return "tar"
    except (OSError, tarfile.TarError):
        return None
    return None


def _unsafe_path_reason(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return "absolute_path"
    if ".." in PurePosixPath(normalized).parts:
        return "parent_traversal"
    return None


def _joined_path(prefix: str, member_name: str) -> str:
    normalized = member_name.replace("\\", "/")
    return f"{prefix}!/{normalized}" if prefix else normalized


def _rejected(
    source_path: str,
    reason: str,
    *,
    content_sha256: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "source_path": source_path,
        "status": "rejected",
        "reason": reason,
        "parsed_records": 0,
        "unparsed_records": 0,
    }
    if content_sha256:
        record["content_sha256"] = content_sha256
    return record


def _archive_record(source_path: str, data: bytes) -> dict[str, object]:
    return {
        "source_path": source_path,
        "status": "archive",
        "size_bytes": len(data),
        "content_sha256": hashlib.sha256(data).hexdigest(),
        "parsed_records": 0,
        "unparsed_records": 0,
    }
