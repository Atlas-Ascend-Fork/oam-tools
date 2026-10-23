#!/usr/bin/env python3
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
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


DIRECTORY = Path(__file__).resolve().parents[2] / "docs/benchmark/2026-10-18"
SCRIPT = DIRECTORY / "derive_selection_v9.py"
CASES = ["CASE-ISSUE-asc-devkit-1368", "CASE-ISSUE-asc-devkit-68",
         "CASE-ISSUE-asc-tools-1"]
HISTORICAL = [1143, 1054, 1027, 954, 941, 937, 936, 935, 934]


@unittest.skipUnless(SCRIPT.is_file(), "Missing v9 cohort builder")
class SelectionV9Tests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing v9 cohort builder")
        spec = importlib.util.spec_from_file_location("selection_v9", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.documents = self.builder.load_inputs(DIRECTORY)
        self.parent = self.documents[self.builder.PARENT]
        self.decisions = self.documents[self.builder.DECISIONS]

    def test_only_three_confirmed_rows_change_and_parent_is_unchanged(self):
        before = copy.deepcopy(self.parent)
        result = self.builder.derive(self.parent, self.decisions)
        self.assertEqual(self.parent, before)
        self.assertEqual([row["case_id"] for row in result["cases"]],
                         [row["case_id"] for row in before["cases"]])
        changed = [old["case_id"] for old, new in zip(before["cases"], result["cases"])
                   if old != new]
        self.assertEqual(changed, CASES)
        self.assertEqual((result["original_count"], result["excluded_count"],
                          result["retained_count"]), (1143, 212, 931))
        self.assertEqual(result["added_excluded_count"], 3)
        self.assertEqual(result["added_excluded_case_ids"], CASES)
        self.assertEqual(result["historical_cohorts"], HISTORICAL)
        self.assertEqual(result["base92_denominator"], 92)
        old_excludes = [row for row in before["cases"] if row["decision"] == "exclude"]
        new_by_id = {row["case_id"]: row for row in result["cases"]}
        self.assertEqual(len(old_excludes), 209)
        self.assertTrue(all(new_by_id[row["case_id"]] == row for row in old_excludes))
        self.assertEqual(sum(row["decision"] == "exclude" for row in result["cases"]), 212)
        for case_id in CASES:
            self.assertEqual(new_by_id[case_id]["decision"], "exclude")

    def test_unconfirmed_wrong_bindings_and_incomplete_cases_are_rejected(self):
        for mutation in ("unconfirmed", "retained", "proposal", "unknown_case", "duplicate",
                         "missing_case", "rationale", "parent_hash", "report_hash", "revision"):
            with self.subTest(mutation=mutation):
                decisions = copy.deepcopy(self.decisions)
                row = decisions["cases"][0]
                if mutation == "unconfirmed":
                    row["independent_decision"] = "review"
                elif mutation == "retained":
                    row["final_decision"] = "retain"
                elif mutation == "proposal":
                    row["proposal_decision"] = "retain"
                elif mutation == "unknown_case":
                    row["case_id"] = "unknown"
                elif mutation == "duplicate":
                    decisions["cases"][1] = copy.deepcopy(row)
                elif mutation == "missing_case":
                    decisions["cases"].pop()
                elif mutation == "rationale":
                    row["reason"] = " "
                elif mutation == "parent_hash":
                    decisions["parent_selection_sha256"] = "0" * 64
                elif mutation == "report_hash":
                    decisions["report_bindings"][self.builder.REVIEW] = "0" * 64
                else:
                    decisions["benchmark_revision"] = "wrong"
                with self.assertRaises(ValueError):
                    self.builder.derive(self.parent, decisions)

    def test_wrong_parent_counts_inventory_or_target_are_rejected(self):
        for mutation in ("retained_count", "row_count", "duplicate", "source", "overlap"):
            with self.subTest(mutation=mutation):
                parent = copy.deepcopy(self.parent)
                target = next(row for row in parent["cases"] if row["case_id"] == CASES[0])
                if mutation == "retained_count":
                    parent["retained_count"] -= 1
                elif mutation == "row_count":
                    parent["cases"].pop()
                elif mutation == "duplicate":
                    parent["cases"][-1] = copy.deepcopy(parent["cases"][-2])
                elif mutation == "source":
                    target["source"] = "benchmark-DTS"
                else:
                    target["decision"] = "exclude"
                    other = next(row for row in parent["cases"]
                                 if row["decision"] == "exclude" and row is not target)
                    other["decision"] = "retain"
                with self.assertRaises(ValueError):
                    self.builder.derive(parent, self.decisions)

    def test_all_frozen_inputs_reject_byte_changes_and_evidence_is_opaque(self):
        self.assertEqual(set(self.documents), {self.builder.PARENT, self.builder.DECISIONS})
        for name in self.builder.ARTIFACTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for filename in self.builder.ARTIFACTS:
                    (root / filename).write_bytes((DIRECTORY / filename).read_bytes())
                target = root / name
                target.write_bytes(target.read_bytes() + b" ")
                with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                    self.builder.load_inputs(root)

    def test_source_hash_git_bytes_and_complete_inventory_are_checked(self):
        self.builder.validate_sources(self.decisions)
        git_dir = subprocess.check_output(
            ["git", "-C", str(self.builder.BENCHMARK), "rev-parse", "--absolute-git-dir"],
            text=True).strip()
        for mutation in ("bytes", "bytes_and_hash", "extra_file", "missing_entry", "traversal"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / ".git").write_text("gitdir: " + git_dir + "\n", encoding="utf-8")
                decisions = copy.deepcopy(self.decisions)
                for row in decisions["cases"]:
                    for name in row["source_files"]:
                        relative = Path("benchmark-ISSUE/cases") / row["case_id"] / name
                        path = root / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes((self.builder.BENCHMARK / relative).read_bytes())
                row = decisions["cases"][0]
                case_root = root / "benchmark-ISSUE/cases" / row["case_id"]
                target = case_root / "input.json"
                if mutation in {"bytes", "bytes_and_hash"}:
                    target.write_bytes(target.read_bytes() + b" ")
                    if mutation == "bytes_and_hash":
                        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
                        row["source_files"]["input.json"] = checksum
                    expected = ("Source differs from frozen Git blob"
                                if mutation == "bytes_and_hash" else "Frozen input changed")
                elif mutation == "extra_file":
                    (case_root / "log/extra.txt").write_text("extra", encoding="utf-8")
                    expected = "Incomplete source inventory"
                elif mutation == "missing_entry":
                    row["source_files"].pop("gold.json")
                    expected = "Incomplete source inventory"
                else:
                    row["source_files"]["../input.json"] = row["source_files"].pop("input.json")
                    expected = "Unsafe source path"
                with patch.object(self.builder, "BENCHMARK", root):
                    with self.assertRaisesRegex(ValueError, expected):
                        self.builder.validate_sources(decisions)


if __name__ == "__main__":
    unittest.main()
