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

import io
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLI = SKILL_ROOT / "scripts" / "build_fault_trace.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fault_trace_core import build_trace, validate_trace  # noqa: E402
from fault_trace_core import pipeline as trace_pipeline  # noqa: E402
from fault_trace_core.package_reader import read_package  # noqa: E402
from fault_trace_core.pipeline import TraceValidationError  # noqa: E402


def cann_record(message: str, timestamp: str = "2026-09-08-10:11:12.000001") -> str:
    return f"[FATAL] RUNTIME(7,app):{timestamp} [runtime.cc:3]{message}\n"


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return stream.getvalue()


class PackageIngestionTest(unittest.TestCase):
    def run_cli(self, input_path: Path, output_path: Path, *options: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(CLI),
                str(input_path),
                "--output-dir",
                str(output_path),
                *options,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_zip_and_depth_two_nested_archives_are_one_collection_boundary(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            level_two = zip_bytes({"device/device.log": cann_record("Device panic").encode()})
            level_one = zip_bytes({"asys-level-two.zip": level_two})
            outer = root / "collection.zip"
            with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("host/host.log", cann_record("Host abort").encode())
                archive.writestr("asys-level-one.zip", level_one)

            completed = self.run_cli(outer, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(len(trace["events"]), 2)
            source_paths = {item["source_path"] for item in trace["input"]["inventory"]}
            self.assertIn("host/host.log", source_paths)
            device_item = next(
                item for item in trace["input"]["inventory"]
                if item["source_path"]
                == "asys-level-one.zip!/asys-level-two.zip!/device/device.log"
            )
            self.assertEqual(device_item["status"], "parsed")
            self.assertEqual(device_item["parser"], "device-common-slog-v1")
            self.assertEqual(trace["metadata"]["redaction_scope"]["kind"], "package-local")
            self.assertNotIn("incomplete_parse_coverage", trace["diagnostics"]["gaps"])

    def test_unsafe_archive_members_are_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("safe/fault.log", cann_record("Process abort").encode())
                archive.writestr("../escape.log", cann_record("escaped").encode())
                archive.writestr("/absolute.log", cann_record("absolute").encode())
                symlink = zipfile.ZipInfo("linked.log")
                symlink.create_system = 3
                symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(symlink, "safe/fault.log")
                special = zipfile.ZipInfo("special-entry")
                special.create_system = 3
                special.external_attr = (stat.S_IFIFO | 0o644) << 16
                archive.writestr(special, b"special")

            completed = self.run_cli(archive_path, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text(encoding="utf-8"))
            rejected = {
                item["source_path"]: item["reason"]
                for item in trace["input"]["inventory"]
                if item["status"] == "rejected"
            }
            self.assertEqual(rejected["../escape.log"], "parent_traversal")
            self.assertEqual(rejected["/absolute.log"], "absolute_path")
            self.assertEqual(rejected["linked.log"], "symbolic_link")
            self.assertEqual(rejected["special-entry"], "unsupported_entry_type")
            self.assertIn("uninspected_evidence", trace["diagnostics"]["gaps"])
            self.assertFalse((root / "escape.log").exists())

    def test_depth_and_expanded_size_limits_are_reported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            level_three = zip_bytes({"deep.log": cann_record("deep panic").encode()})
            level_two = zip_bytes({"level-three.zip": level_three})
            level_one = zip_bytes({"level-two.zip": level_two})
            depth_archive = root / "depth.zip"
            with zipfile.ZipFile(depth_archive, "w") as archive:
                archive.writestr("safe.log", cann_record("safe abort").encode())
                archive.writestr("level-one.zip", level_one)

            depth_result = self.run_cli(depth_archive, root / "depth-output")
            self.assertEqual(depth_result.returncode, 0, depth_result.stderr)
            depth_trace = json.loads((root / "depth-output" / "fault-trace.json").read_text())
            self.assertIn(
                "archive_depth_limit",
                {item.get("reason") for item in depth_trace["input"]["inventory"]},
            )

            size_archive = root / "size.zip"
            with zipfile.ZipFile(size_archive, "w") as archive:
                archive.writestr("safe.log", cann_record("safe abort").encode())
                archive.writestr("too-large.bin", b"x" * 5000)
                archive.writestr("cumulative.bin", b"y" * 500)

            entry_result = self.run_cli(
                size_archive,
                root / "entry-output",
                "--max-entry-bytes",
                "1024",
                "--max-total-bytes",
                "10000",
            )
            self.assertEqual(entry_result.returncode, 0, entry_result.stderr)
            entry_trace = json.loads((root / "entry-output" / "fault-trace.json").read_text())
            self.assertIn(
                "entry_size_limit",
                {item.get("reason") for item in entry_trace["input"]["inventory"]},
            )

            total_result = self.run_cli(
                size_archive,
                root / "total-output",
                "--max-entry-bytes",
                "10000",
                "--max-total-bytes",
                "400",
            )
            self.assertEqual(total_result.returncode, 0, total_result.stderr)
            total_trace = json.loads((root / "total-output" / "fault-trace.json").read_text())
            self.assertIn(
                "cumulative_size_limit",
                {item.get("reason") for item in total_trace["input"]["inventory"]},
            )

    def test_orphan_and_unsupported_text_remain_auditable_but_off_timeline(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "evidence.tar.gz"
            fault_text = cann_record("Abort user alice") + "stack fragment user alice\n"
            with tarfile.open(archive_path, "w:gz") as archive:
                for name, data in {
                    "run/fault.log": fault_text.encode(),
                    "notes/readme.txt": b"unsupported material\n",
                }.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))

            completed = self.run_cli(archive_path, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text(encoding="utf-8"))
            self.assertEqual(len(trace["events"]), 1)
            self.assertEqual(len(trace["orphan_evidence"]), 1)
            orphan = trace["orphan_evidence"][0]
            self.assertEqual(orphan["source_path"], "run/fault.log")
            self.assertEqual(orphan["line"], 2)
            self.assertIn("USER-001", orphan["excerpt"])
            self.assertNotIn("alice", json.dumps(trace))
            unsupported = [
                item for item in trace["input"]["inventory"] if item["status"] == "unsupported"
            ]
            self.assertEqual(unsupported[0]["source_path"], "notes/readme.txt")
            self.assertEqual(trace["diagnostics"]["parse_coverage"], {
                "parsed_records": 1,
                "unparsed_records": 2,
            })

    def test_top_level_archive_is_streamed_without_path_read_bytes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "collection.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("fault.log", cann_record("Process abort").encode())

            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("unbounded read")):
                entries, inventory, _ = read_package(archive_path)

            self.assertEqual([entry.source_path for entry in entries], ["fault.log"])
            self.assertEqual(inventory, [])

    def test_directory_hardlink_is_rejected_as_out_of_boundary_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            input_dir.mkdir()
            input_dir.joinpath("safe.log").write_text(cann_record("safe abort"), encoding="utf-8")
            outside = root / "outside.log"
            outside.write_text(cann_record("outside abort"), encoding="utf-8")
            os.link(outside, input_dir / "linked.log")

            completed = self.run_cli(input_dir, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text())
            self.assertEqual(len(trace["events"]), 1)
            linked = next(
                item for item in trace["input"]["inventory"] if item["source_path"] == "linked.log"
            )
            self.assertEqual(linked["status"], "rejected")
            self.assertEqual(linked["reason"], "hard_link")

    def test_corrupt_zip_member_does_not_hide_later_safe_members(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "partially-corrupt.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("broken.txt", b"broken payload")
                archive.writestr("safe.log", cann_record("safe abort").encode())
            with zipfile.ZipFile(archive_path) as archive:
                broken = archive.getinfo("broken.txt")
                with archive_path.open("r+b") as stream:
                    stream.seek(broken.header_offset)
                    header = stream.read(30)
                    name_length = int.from_bytes(header[26:28], "little")
                    extra_length = int.from_bytes(header[28:30], "little")
                    payload_offset = broken.header_offset + 30 + name_length + extra_length
                    stream.seek(payload_offset)
                    original = stream.read(1)
                    stream.seek(payload_offset)
                    stream.write(bytes([original[0] ^ 0xFF]))

            completed = self.run_cli(archive_path, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text())
            self.assertEqual(len(trace["events"]), 1)
            broken_item = next(
                item for item in trace["input"]["inventory"] if item["source_path"] == "broken.txt"
            )
            self.assertEqual(broken_item["status"], "rejected")
            self.assertEqual(broken_item["reason"], "unreadable")

    def test_v1_validator_accepts_artifacts_without_new_optional_ingestion_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(cann_record("Process abort"), encoding="utf-8")
            trace = build_trace(root)
            del trace["metadata"]["redaction_scope"]
            del trace["orphan_evidence"]
            del trace["diagnostics"]["parse_coverage"]

            validate_trace(trace)

    def test_runtime_validator_rejects_invalid_optional_ingestion_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(cann_record("Process abort"), encoding="utf-8")
            valid_trace = build_trace(root)

            invalid_scope = json.loads(json.dumps(valid_trace))
            invalid_scope["metadata"]["redaction_scope"]["scope_id"] = 1234567890123456
            invalid_coverage = json.loads(json.dumps(valid_trace))
            invalid_coverage["diagnostics"]["parse_coverage"]["parsed_records"] = -1
            invalid_parser = json.loads(json.dumps(valid_trace))
            invalid_parser["input"]["inventory"][0]["parser"] = 1
            invalid_orphan_hash = json.loads(json.dumps(valid_trace))
            invalid_orphan_hash["orphan_evidence"] = [{
                "id": "orphan-000001",
                "source_path": "fault.log",
                "line": 2,
                "record_sha256": int("1" * 64),
                "excerpt": "fragment",
            }]

            for invalid_trace in (
                invalid_scope,
                invalid_coverage,
                invalid_parser,
                invalid_orphan_hash,
            ):
                with self.subTest(trace=invalid_trace):
                    with self.assertRaises(TraceValidationError):
                        validate_trace(invalid_trace)

    def test_corrupt_nested_archive_is_rejected_instead_of_parsed_as_text(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            outer = root / "collection.zip"
            with zipfile.ZipFile(outer, "w") as archive:
                archive.writestr("fault.log", cann_record("safe abort").encode())
                archive.writestr("nested/broken.zip", b"PK\x03\x04not-a-valid-zip")

            completed = self.run_cli(outer, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text())
            broken = next(
                item for item in trace["input"]["inventory"]
                if item["source_path"] == "nested/broken.zip"
            )
            self.assertEqual(broken["status"], "rejected")
            self.assertEqual(broken["reason"], "unreadable_archive")
            self.assertIn("uninspected_evidence", trace["diagnostics"]["gaps"])

    def test_directory_special_entry_is_rejected_and_inventoried(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            input_dir.mkdir()
            input_dir.joinpath("safe.log").write_text(cann_record("safe abort"), encoding="utf-8")
            if hasattr(os, "mkfifo"):
                special_name = "events.pipe"
                expected_reason = "unsupported_entry_type"
                os.mkfifo(input_dir / special_name)
            elif os.name == "nt":
                special_name = "outside-junction"
                expected_reason = "reparse_point"
                outside = root / "outside"
                outside.mkdir()
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(input_dir / special_name), str(outside)],
                    capture_output=True,
                    text=True,
                )
                if created.returncode:
                    self.skipTest("directory junction creation is unavailable")
            else:
                self.skipTest("no supported special entry fixture on this platform")

            completed = self.run_cli(input_dir, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text())
            special = next(
                item for item in trace["input"]["inventory"]
                if item["source_path"] == special_name
            )
            self.assertEqual(special["status"], "rejected")
            self.assertEqual(special["reason"], expected_reason)

    def test_no_usable_records_still_write_an_auditable_inventory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            input_dir.mkdir()
            input_dir.joinpath("broken.zip").write_bytes(b"PK\x03\x04broken")
            output_dir = root / "output"

            completed = self.run_cli(input_dir, output_dir)

            self.assertEqual(completed.returncode, 3, completed.stderr)
            audit = json.loads(
                output_dir.joinpath("fault-trace-inventory.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit["artifact_kind"], "fault-trace-inventory")
            self.assertEqual(audit["inventory_schema_version"], "1.0.0")
            self.assertNotIn("schema_version", audit)
            self.assertEqual(audit["status"], "no_trace")
            self.assertEqual(audit["input"]["inventory"][0]["reason"], "unreadable_archive")
            self.assertFalse(output_dir.joinpath("fault-trace.json").exists())

            validator = getattr(trace_pipeline, "validate_inventory_audit", None)
            self.assertTrue(callable(validator))
            invalid_audits = []
            invalid_scope = json.loads(json.dumps(audit))
            invalid_scope["metadata"]["redaction_scope"]["scope_id"] = 7
            invalid_audits.append(invalid_scope)
            for field, value in (("parser", 1), ("reason", 2), ("size_bytes", -1)):
                invalid_entry = json.loads(json.dumps(audit))
                invalid_entry["input"]["inventory"][0][field] = value
                invalid_audits.append(invalid_entry)
            for invalid in invalid_audits:
                with self.subTest(audit=invalid):
                    with self.assertRaises(TraceValidationError):
                        validator(invalid)

    def test_generated_file_inventory_has_content_hash(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(cann_record("safe abort"), encoding="utf-8")
            unsupported = b"unsupported material\n"
            root.joinpath("notes.txt").write_bytes(unsupported)

            trace = build_trace(root)

            notes = next(
                item for item in trace["input"]["inventory"]
                if item["source_path"] == "notes.txt"
            )
            self.assertEqual(notes["content_sha256"], hashlib.sha256(unsupported).hexdigest())

    def test_redaction_scope_is_unique_for_separate_ingestions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            for package in (first, second):
                package.joinpath("fault.log").write_text(
                    cann_record("safe abort"), encoding="utf-8"
                )

            first_scope = read_package(first)[2]
            second_scope = read_package(second)[2]

            self.assertNotEqual(first_scope, second_scope)

    def test_reader_does_not_persist_raw_os_error_details(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root.joinpath("fault.log").write_text(cann_record("safe abort"), encoding="utf-8")
            with mock.patch.object(
                Path,
                "open",
                side_effect=OSError(r"cannot read C:\Users\alice\secret\fault.log"),
            ):
                entries, inventory, _ = read_package(root)

            self.assertEqual(entries, [])
            serialized = json.dumps(inventory)
            self.assertNotIn("alice", serialized)
            self.assertNotIn("C:\\Users", serialized)
            self.assertNotIn("detail", inventory[0])

    def test_tar_hardlink_is_reported_distinctly(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "links.tar"
            with tarfile.open(archive_path, "w") as archive:
                safe = cann_record("safe abort").encode()
                info = tarfile.TarInfo("safe.log")
                info.size = len(safe)
                archive.addfile(info, io.BytesIO(safe))
                linked = tarfile.TarInfo("linked.log")
                linked.type = tarfile.LNKTYPE
                linked.linkname = "safe.log"
                archive.addfile(linked)

            completed = self.run_cli(archive_path, root / "output")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text())
            linked_item = next(
                item for item in trace["input"]["inventory"]
                if item["source_path"] == "linked.log"
            )
            self.assertEqual(linked_item["reason"], "hard_link")

    def test_zero_archive_depth_disables_nested_archive_reading(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            outer = root / "collection.zip"
            with zipfile.ZipFile(outer, "w") as archive:
                archive.writestr("fault.log", cann_record("safe abort").encode())
                archive.writestr("nested.zip", zip_bytes({"hidden.log": cann_record("hidden panic").encode()}))

            completed = self.run_cli(
                outer,
                root / "output",
                "--max-archive-depth",
                "0",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            trace = json.loads((root / "output" / "fault-trace.json").read_text())
            self.assertEqual(len(trace["events"]), 1)
            nested = next(
                item for item in trace["input"]["inventory"]
                if item["source_path"] == "nested.zip" and item["status"] == "rejected"
            )
            self.assertEqual(nested["reason"], "archive_depth_limit")


if __name__ == "__main__":
    unittest.main()
