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
SCRIPT = DIRECTORY / "derive_selection_v10.py"
CASES = ["CASE-ISSUE-ops-nn-4999", "CASE-ISSUE-ops-nn-5035"]


@unittest.skipUnless(SCRIPT.is_file(), "Missing v10 cohort builder")
class SelectionV10Tests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing v10 cohort builder")
        spec = importlib.util.spec_from_file_location("selection_v10", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.documents = self.builder.load_inputs(DIRECTORY)
        self.parent = self.documents[self.builder.PARENT]
        self.decisions = self.documents[self.builder.DECISIONS]

    def test_only_two_confirmed_rows_change_and_4262_is_preserved(self):
        before = copy.deepcopy(self.parent)
        result = self.builder.derive(self.parent, self.decisions)
        self.assertEqual(before, self.parent)
        changed = [a["case_id"] for a, b in zip(before["cases"], result["cases"]) if a != b]
        self.assertEqual(changed, CASES)
        self.assertEqual([r["case_id"] for r in before["cases"]],
                         [r["case_id"] for r in result["cases"]])
        self.assertEqual((result["original_count"], result["excluded_count"],
                          result["retained_count"]), (1143, 214, 929))
        self.assertEqual(result["historical_cohorts"],
                         [1143, 1054, 1027, 954, 941, 937, 936, 935, 934, 931])
        self.assertEqual(result["base92_denominator"], 92)
        old_excluded = [r for r in before["cases"] if r["decision"] == "exclude"]
        new_by_id = {r["case_id"]: r for r in result["cases"]}
        self.assertEqual(len(old_excluded), 212)
        self.assertTrue(all(new_by_id[r["case_id"]] == r for r in old_excluded))
        target = "CASE-ISSUE-ops-nn-4262"
        self.assertEqual(new_by_id[target], next(r for r in before["cases"] if r["case_id"] == target))

    def test_missing_confirmation_binding_or_case_is_rejected(self):
        for mutation in ("confirmation", "rationale", "case", "duplicate", "missing",
                         "parent", "review", "revision", "history"):
            with self.subTest(mutation=mutation):
                d = copy.deepcopy(self.decisions)
                if mutation == "confirmation":
                    d["cases"][0]["independent_decision"] = "review"
                elif mutation == "rationale":
                    d["cases"][0]["reason"] = " "
                elif mutation == "case":
                    d["cases"][0]["case_id"] = "CASE-ISSUE-ops-nn-4262"
                elif mutation == "duplicate":
                    d["cases"][1] = copy.deepcopy(d["cases"][0])
                elif mutation == "missing":
                    d["cases"].pop()
                elif mutation == "parent":
                    d["parent_selection_sha256"] = "0" * 64
                elif mutation == "review":
                    d["report_bindings"][self.builder.REVIEW] = "0" * 64
                elif mutation == "revision":
                    d["benchmark_revision"] = "wrong"
                else:
                    d["historical_cohorts"].pop()
                with self.assertRaises(ValueError):
                    self.builder.derive(self.parent, d)

    def test_wrong_parent_counts_duplicate_source_and_overlap_are_rejected(self):
        for mutation in ("count", "duplicate", "source", "overlap"):
            with self.subTest(mutation=mutation):
                p = copy.deepcopy(self.parent)
                target = next(r for r in p["cases"] if r["case_id"] == CASES[0])
                if mutation == "count":
                    p["retained_count"] -= 1
                elif mutation == "duplicate":
                    p["cases"][-1] = copy.deepcopy(p["cases"][-2])
                elif mutation == "source":
                    target["source"] = "benchmark-DTS"
                else:
                    target["decision"] = "exclude"
                    next(r for r in p["cases"] if r["decision"] == "exclude" and r is not target)["decision"] = "retain"
                with self.assertRaises(ValueError):
                    self.builder.derive(p, self.decisions)

    def test_frozen_artifacts_reject_byte_changes_and_evidence_is_opaque(self):
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

    def test_fixed_git_source_inventory_is_checked(self):
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
