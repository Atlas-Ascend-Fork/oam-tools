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
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "docs/benchmark/2026-10-18/derive_selection_v3.py"


@unittest.skipUnless(SCRIPT.is_file(), "Missing independently reviewed cohort builder")
class BenchmarkSelectionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing independently reviewed cohort builder")
        spec = importlib.util.spec_from_file_location("derive_selection_v3", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.parent = {
            "version": 2, "benchmark_revision": "frozen-revision", "original_count": 4,
            "cases": [
                {"source": "benchmark-DTS", "case_id": "old", "decision": "exclude",
                 "reason": "Previously confirmed"},
                {"source": "benchmark-DTS", "case_id": "confirmed", "decision": "retain"},
                {"source": "benchmark-DTS", "case_id": "disputed", "decision": "retain"},
                {"source": "benchmark-ISSUE", "case_id": "untouched", "decision": "retain"},
            ],
        }
        self.proposals = {"proposal.json": {"cases": [
            {"case_id": "confirmed", "decision": "exclude"},
            {"case_id": "disputed", "decision": "confirm-exclude"},
        ]}}
        self.reviews = {"review.json": {"cases": [
            {"case_id": "confirmed", "independent_decision": "confirm-exclude",
             "independent_rationale": "The supplied evidence cannot distinguish different repairs."},
            {"case_id": "disputed", "independent_decision": "review",
             "independent_rationale": "An equivalent diagnosis remains possible."},
        ]}}

    def test_only_jointly_confirmed_cases_are_removed_without_mutating_parent(self):
        before = copy.deepcopy(self.parent)
        result = self.builder.derive_selection(self.parent, self.proposals, self.reviews)
        self.assertEqual(self.parent, before)
        self.assertEqual([row["case_id"] for row in result["cases"]],
                         [row["case_id"] for row in before["cases"]])
        self.assertEqual([row["decision"] for row in result["cases"]],
                         ["exclude", "exclude", "retain", "retain"])
        self.assertEqual(result["added_excluded_count"], 1)
        self.assertEqual(result["retained_count"], 2)
        self.assertEqual(result["cases"][1]["review_ref"], "review.json#/cases/0")

    def test_unreviewed_candidate_and_duplicate_review_are_rejected(self):
        self.reviews["review.json"]["cases"].pop()
        with self.assertRaisesRegex(ValueError, "review"):
            self.builder.derive_selection(self.parent, self.proposals, self.reviews)
        self.reviews["review.json"]["cases"].append(
            copy.deepcopy(self.reviews["review.json"]["cases"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.builder.derive_selection(self.parent, self.proposals, self.reviews)

    def test_unknown_or_overlapping_case_cannot_change_denominator(self):
        for case_id in ("unknown", "old", "untouched"):
            with self.subTest(case_id=case_id):
                proposals = copy.deepcopy(self.proposals)
                reviews = copy.deepcopy(self.reviews)
                proposals["proposal.json"]["cases"][0]["case_id"] = case_id
                reviews["review.json"]["cases"][0]["case_id"] = case_id
                with self.assertRaises(ValueError):
                    self.builder.derive_selection(self.parent, proposals, reviews)

    def test_withdrawn_proposal_is_retained_despite_earlier_confirmation(self):
        self.proposals["proposal.json"]["cases"][0]["decision"] = "review"
        result = self.builder.derive_selection(self.parent, self.proposals, self.reviews)
        self.assertEqual(result["cases"][1]["decision"], "retain")
        self.assertEqual(result["added_excluded_count"], 0)

    def test_frozen_source_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "proposal.json"
            source.write_text('{"cases": []}')
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(self.builder.load_frozen(source, checksum), {"cases": []})
            source.write_text('{"cases": [{"case_id": "changed"}]}')
            with self.assertRaisesRegex(ValueError, "Frozen"):
                self.builder.load_frozen(source, checksum)

    def test_existing_cohort_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "selection.json"
            self.builder.write_selection(output, self.parent)
            before = output.read_bytes()
            self.builder.write_selection(output, self.parent)
            with self.assertRaises(ValueError):
                self.builder.write_selection(output, {"cases": []})
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
