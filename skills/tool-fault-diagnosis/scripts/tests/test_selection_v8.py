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
SCRIPT = DIRECTORY / "derive_selection_v8.py"


@unittest.skipUnless(SCRIPT.is_file(), "Missing v8 cohort builder")
class SelectionV8Tests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing v8 cohort builder")
        spec = importlib.util.spec_from_file_location("selection_v8", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.documents = self.builder.load_inputs(DIRECTORY)
        self.parent = self.documents[self.builder.PARENT]
        self.decisions = self.documents[self.builder.DECISIONS]

    def test_only_confirmed_pair_changes_and_parent_is_unchanged(self):
        before = copy.deepcopy(self.parent)
        result = self.builder.derive(self.parent, self.decisions)
        self.assertEqual(self.parent, before)
        self.assertEqual([row["case_id"] for row in result["cases"]],
                         [row["case_id"] for row in before["cases"]])
        changed = [old["case_id"] for old, new in zip(before["cases"], result["cases"])
                   if old != new]
        self.assertEqual(changed, ["CASE-DTS-DTS2026071013226"])
        self.assertEqual(result["retained_count"], 934)
        self.assertEqual(result["excluded_count"], 209)
        self.assertEqual(result["added_excluded_case_ids"], changed)
        self.assertEqual(sum(row["decision"] == "exclude" for row in result["cases"]), 209)

    def test_unconfirmed_or_changed_decisions_and_parent_counts_are_rejected(self):
        for mutation in ("unconfirmed", "extra_exclusion", "unknown_case", "wrong_count"):
            with self.subTest(mutation=mutation):
                parent, decisions = copy.deepcopy(self.parent), copy.deepcopy(self.decisions)
                rows = {row["case_id"]: row for row in decisions["cases"]}
                if mutation == "unconfirmed":
                    rows[self.builder.CASE]["independent_decision"] = "review"
                elif mutation == "extra_exclusion":
                    rows[self.builder.RETAINED_CASE]["final_decision"] = "exclude"
                elif mutation == "unknown_case":
                    decisions["cases"][0]["case_id"] = "unknown"
                else:
                    parent["retained_count"] -= 1
                with self.assertRaises(ValueError):
                    self.builder.derive(parent, decisions)

    def test_changed_frozen_report_or_decisions_are_rejected(self):
        for name in self.builder.ARTIFACTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for filename in self.builder.ARTIFACTS:
                    (root / filename).write_bytes((DIRECTORY / filename).read_bytes())
                target = root / name
                target.write_bytes(target.read_bytes() + b" ")
                with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                    self.builder.load_inputs(root)


if __name__ == "__main__":
    unittest.main()
