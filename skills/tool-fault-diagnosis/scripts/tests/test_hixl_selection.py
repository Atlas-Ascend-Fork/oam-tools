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
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "docs/benchmark/2026-10-18/derive_selection_v4.py"


@unittest.skipUnless(SCRIPT.is_file(), "Missing HIXL cohort builder")
class HixlSelectionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing HIXL cohort builder")
        spec = importlib.util.spec_from_file_location("derive_selection_v4", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.parent = {"benchmark_revision": "revision", "cases": [
            {"source": "benchmark-DTS", "case_id": "old", "decision": "exclude"},
            {"source": "benchmark-ISSUE", "case_id": "CASE-ISSUE-hixl-1", "decision": "retain"},
            {"source": "benchmark-ISSUE", "case_id": "CASE-ISSUE-hixl-2", "decision": "retain"},
            {"source": "benchmark-wiki", "case_id": "other", "decision": "retain"},
        ]}
        upstream = {"revision": "revision", "fixed_case_ids": [
            "CASE-ISSUE-hixl-1", "CASE-ISSUE-hixl-2"],
            "input_and_log_cohort_manifest_sha256": "inputs"}
        self.proposal = {"upstream": copy.deepcopy(upstream), "cases": [
            {"case_id": "CASE-ISSUE-hixl-1", "proposal": "exclude",
             "input_and_log_manifest_sha256": "input1", "gold_sha256": "gold1"},
            {"case_id": "CASE-ISSUE-hixl-2", "proposal": "exclude",
             "input_and_log_manifest_sha256": "input2", "gold_sha256": "gold2"},
        ]}
        self.review = {"upstream": copy.deepcopy(upstream), "cases": [
            {"case_id": "CASE-ISSUE-hixl-1", "decision": "confirm_exclude",
             "reason": "Scoring requires an absent cause with different repairs.",
             "input_and_log_manifest_sha256": "input1", "gold_sha256": "gold1"},
            {"case_id": "CASE-ISSUE-hixl-2", "decision": "retain",
             "reason": "Equivalent diagnosis is answerable.",
             "input_and_log_manifest_sha256": "input2", "gold_sha256": "gold2"},
        ]}

    def test_only_joint_confirmation_changes_cohort_and_parent_is_unchanged(self):
        before = copy.deepcopy(self.parent)
        result = self.builder.derive_selection(self.parent, self.proposal, self.review)
        self.assertEqual(self.parent, before)
        self.assertEqual([r["case_id"] for r in result["cases"]],
                         [r["case_id"] for r in before["cases"]])
        self.assertEqual([r["decision"] for r in result["cases"]],
                         ["exclude", "exclude", "retain", "retain"])
        self.assertEqual(result["added_excluded_count"], 1)
        self.assertEqual(result["retained_count"], 2)
        self.assertTrue(result["cases"][1]["review_ref"].endswith("#/cases/0"))

    def test_missing_unknown_and_duplicate_review_cases_are_rejected(self):
        for mutation in ("missing", "unknown", "duplicate"):
            with self.subTest(mutation=mutation):
                review = copy.deepcopy(self.review)
                if mutation == "missing":
                    review["cases"].pop()
                elif mutation == "unknown":
                    review["cases"][1]["case_id"] = "CASE-ISSUE-hixl-999"
                else:
                    review["cases"].append(copy.deepcopy(review["cases"][0]))
                with self.assertRaises(ValueError):
                    self.builder.derive_selection(self.parent, self.proposal, review)

    def test_unproposed_confirmation_and_empty_rationale_are_rejected(self):
        for mutation in ("unproposed", "empty_reason"):
            with self.subTest(mutation=mutation):
                proposal, review = copy.deepcopy(self.proposal), copy.deepcopy(self.review)
                if mutation == "unproposed":
                    proposal["cases"][0]["proposal"] = "review"
                else:
                    review["cases"][0]["reason"] = "  "
                with self.assertRaises(ValueError):
                    self.builder.derive_selection(self.parent, proposal, review)

    def test_changed_revision_or_input_fingerprint_is_rejected(self):
        for mutation in ("revision", "cohort", "case_input", "gold"):
            with self.subTest(mutation=mutation):
                review = copy.deepcopy(self.review)
                if mutation == "revision":
                    review["upstream"]["revision"] = "changed"
                elif mutation == "cohort":
                    review["upstream"]["input_and_log_cohort_manifest_sha256"] = "changed"
                elif mutation == "case_input":
                    review["cases"][0]["input_and_log_manifest_sha256"] = "changed"
                else:
                    review["cases"][0]["gold_sha256"] = "changed"
                with self.assertRaises(ValueError):
                    self.builder.derive_selection(self.parent, self.proposal, review)

    def test_existing_exclusion_cannot_be_counted_twice(self):
        self.parent["cases"][1]["decision"] = "exclude"
        with self.assertRaises(ValueError):
            self.builder.derive_selection(self.parent, self.proposal, self.review)


if __name__ == "__main__":
    unittest.main()
