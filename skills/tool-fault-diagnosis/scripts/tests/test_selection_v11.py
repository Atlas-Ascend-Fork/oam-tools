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
import importlib.util
from pathlib import Path
import tempfile
import unittest


DIRECTORY = Path(__file__).resolve().parents[2] / "docs/benchmark/2026-10-18"
SCRIPT = DIRECTORY / "derive_selection_v11.py"
CASES = ["CASE-ISSUE-pypto-1514", "CASE-ISSUE-pypto-154", "CASE-ISSUE-pypto-1938"]


@unittest.skipUnless(SCRIPT.is_file(), "Missing v11 cohort builder")
class SelectionV11Tests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing v11 cohort builder")
        spec = importlib.util.spec_from_file_location("selection_v11", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.documents = self.builder.load_inputs(DIRECTORY)
        self.parent = self.documents[self.builder.PARENT]
        self.decisions = self.documents[self.builder.DECISIONS]

    def test_only_confirmed_three_change_and_1649_and_old_exclusions_stay(self):
        before = copy.deepcopy(self.parent)
        result = self.builder.derive(self.parent, self.decisions)
        self.assertEqual(self.parent, before)
        changed = [a["case_id"] for a, b in zip(before["cases"], result["cases"]) if a != b]
        self.assertEqual(changed, CASES)
        self.assertEqual([r["case_id"] for r in before["cases"]],
                         [r["case_id"] for r in result["cases"]])
        self.assertEqual((result["original_count"], result["excluded_count"],
                          result["retained_count"]), (1143, 217, 926))
        self.assertEqual(result["historical_cohorts"],
                         [1143, 1054, 1027, 954, 941, 937, 936, 935, 934, 931, 929])
        self.assertEqual(result["base92_denominator"], 92)
        rows = {r["case_id"]: r for r in result["cases"]}
        preserved = [r for r in before["cases"] if r["case_id"] not in CASES]
        self.assertEqual(len(preserved), 1140)
        self.assertTrue(all(rows[r["case_id"]] == r for r in preserved))

    def test_confirmation_parent_and_history_tampering_are_rejected(self):
        for mutation in ("confirmation", "reason", "case", "missing", "parent", "history", "binding"):
            with self.subTest(mutation=mutation):
                d = copy.deepcopy(self.decisions)
                if mutation == "confirmation":
                    d["cases"][0]["independent_decision"] = "review"
                elif mutation == "reason":
                    d["cases"][0]["reason"] = " "
                elif mutation == "case":
                    d["cases"][0]["case_id"] = "CASE-ISSUE-pypto-1649"
                elif mutation == "missing":
                    d["cases"].pop()
                elif mutation == "parent":
                    d["parent_selection_sha256"] = "0" * 64
                elif mutation == "history":
                    d["historical_cohorts"].pop()
                else:
                    d["report_bindings"][self.builder.REVIEW] = "0" * 64
                with self.assertRaises(ValueError):
                    self.builder.derive(self.parent, d)

    def test_changed_frozen_artifact_is_rejected(self):
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

    def test_fixed_git_source_inventory_and_hash_are_checked(self):
        self.builder.validate_sources(self.decisions)
        for mutation in ("hash", "missing", "traversal"):
            with self.subTest(mutation=mutation):
                d = copy.deepcopy(self.decisions)
                files = d["cases"][0]["source_files"]
                if mutation == "hash":
                    files["input.json"] = "0" * 64
                elif mutation == "missing":
                    files.pop("gold.json")
                else:
                    files["../input.json"] = files.pop("input.json")
                with self.assertRaises(ValueError):
                    self.builder.validate_sources(d)


if __name__ == "__main__":
    unittest.main()
