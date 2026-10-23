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
import json
from pathlib import Path
import tempfile
import unittest


DIRECTORY = Path(__file__).resolve().parents[2] / "docs/benchmark/2026-10-18"
SCRIPT = DIRECTORY / "derive_selection_v5.py"
INPUT_NAMES = (
    "selection-v4a.json",
    "issue-nonhixl-answerability-audit.json",
    "issue-nonhixl-answerability-independent-review.json",
    "wiki-answerability-audit.json",
    "wiki-two-proposals-independent-review-v1.json",
)
EXPECTED_ADDED = {
    "CASE-ISSUE-asc-comm-3", "CASE-ISSUE-asc-devkit-12",
    "CASE-ISSUE-asc-devkit-1470", "CASE-WIKI-202406173788571",
}
DISPUTED = "CASE-WIKI-202406173785130"


@unittest.skipUnless(SCRIPT.is_file(), "Missing v5 cohort builder")
class SelectionV5Tests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing v5 cohort builder")
        spec = importlib.util.spec_from_file_location("derive_selection_v5", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.documents = [json.loads((DIRECTORY / name).read_bytes()) for name in INPUT_NAMES]

    def derive(self, documents=None):
        return self.builder.derive_selection(*(documents or self.documents))

    def test_exact_four_joint_confirmations_preserve_all_other_rows(self):
        before = copy.deepcopy(self.documents)
        result = self.derive()
        self.assertEqual(self.documents, before)
        parent_rows = before[0]["cases"]
        self.assertEqual([r["case_id"] for r in result["cases"]],
                         [r["case_id"] for r in parent_rows])
        changed = {old["case_id"] for old, new in zip(parent_rows, result["cases"]) if old != new}
        self.assertEqual(changed, EXPECTED_ADDED)
        self.assertEqual((len(result["cases"]), result["excluded_count"],
                          result["retained_count"], result["added_excluded_count"]),
                         (1143, 206, 937, 4))
        for old, row in zip(parent_rows, result["cases"]):
            if row["case_id"] in EXPECTED_ADDED:
                self.assertEqual(row["decision"], "exclude")
                self.assertEqual(set(row), set(old) | {"reason", "proposal_ref", "review_ref"})
                self.assertTrue(row["reason"].strip())
                self.assertIn("#/", row["proposal_ref"])
                self.assertIn("#/", row["review_ref"])
            else:
                self.assertEqual(row, old)
        disputed = next(r for r in result["cases"] if r["case_id"] == DISPUTED)
        self.assertEqual(disputed["decision"], "retain")
        self.assertEqual(result["version"], 5)
        self.assertEqual(result["parent_selection"], "selection-v4a.json")
        self.assertIn("Post-evaluation", result["audit_timing"])
        self.assertIn("not pre-registered", result["audit_timing"])
        self.assertIn("not blind", result["audit_timing"])

    def test_unconfirmed_or_unproposed_exclusion_cannot_be_applied(self):
        for mutation in ("issue_unconfirmed", "issue_unproposed", "wiki_unconfirmed",
                         "wiki_unproposed", "disputed_confirmed", "empty_reason"):
            with self.subTest(mutation=mutation):
                docs = copy.deepcopy(self.documents)
                if mutation == "issue_unconfirmed":
                    docs[2]["cases"][0]["decision"] = "retain"
                elif mutation == "issue_unproposed":
                    docs[1]["cases"][4]["proposal"] = "review"
                elif mutation == "wiki_unconfirmed":
                    docs[4]["case_results"][1]["exclusion_supported"] = False
                elif mutation == "wiki_unproposed":
                    docs[3]["cases"][5]["decision"] = "review"
                elif mutation == "disputed_confirmed":
                    docs[4]["case_results"][0]["exclusion_supported"] = True
                else:
                    docs[2]["cases"][0]["independent_reason"] = "  "
                with self.assertRaises(ValueError):
                    self.derive(docs)

    def test_missing_duplicate_unknown_or_wrong_source_ids_are_rejected(self):
        for mutation in ("missing_review", "duplicate_review", "unknown_review", "fixed_scope",
                         "missing_issue", "missing_wiki", "duplicate_parent", "wrong_source",
                         "already_excluded"):
            with self.subTest(mutation=mutation):
                docs = copy.deepcopy(self.documents)
                if mutation == "missing_review":
                    docs[2]["cases"].pop()
                elif mutation == "duplicate_review":
                    docs[2]["cases"].append(copy.deepcopy(docs[2]["cases"][0]))
                elif mutation == "unknown_review":
                    docs[2]["cases"][0]["case_id"] = "CASE-ISSUE-unknown"
                elif mutation == "fixed_scope":
                    docs[2]["fixed_scope"].append(docs[2]["fixed_scope"][0])
                elif mutation == "missing_issue":
                    docs[1]["cases"].pop()
                elif mutation == "missing_wiki":
                    docs[3]["cases"].pop()
                elif mutation == "duplicate_parent":
                    docs[0]["cases"].append(copy.deepcopy(docs[0]["cases"][0]))
                else:
                    row = next(r for r in docs[0]["cases"] if r["case_id"] in EXPECTED_ADDED)
                    row["source" if mutation == "wrong_source" else "decision"] = (
                        "benchmark-wiki" if mutation == "wrong_source" else "exclude")
                with self.assertRaises(ValueError):
                    self.derive(docs)

    def test_revision_report_reference_and_fingerprint_drift_are_rejected(self):
        for mutation in ("issue_revision", "wiki_revision", "review_revision", "issue_reference",
                         "wiki_reference", "issue_cohort", "wiki_cohort", "case_input", "gold",
                         "issue_inventory", "wiki_inventory", "wiki_pointer"):
            with self.subTest(mutation=mutation):
                docs = copy.deepcopy(self.documents)
                if mutation == "issue_revision":
                    docs[1]["upstream"]["revision"] = "changed"
                elif mutation == "wiki_revision":
                    docs[3]["frozen_source"]["upstream_revision"] = "changed"
                elif mutation == "review_revision":
                    docs[4]["frozen_manifest"]["value"]["source_revision"] = "changed"
                elif mutation == "issue_reference":
                    docs[2]["first_audit_frozen_artifacts"]["json_sha256"] = "changed"
                elif mutation == "wiki_reference":
                    docs[4]["frozen_manifest"]["value"]["prior_audits"][0]["sha256"] = "changed"
                elif mutation == "issue_cohort":
                    docs[2]["source"]["input_and_log_cohort_manifest_sha256"] = "changed"
                elif mutation == "wiki_cohort":
                    docs[3]["frozen_source"]["input_log_manifest_sha256"] = "changed"
                elif mutation == "case_input":
                    docs[2]["cases"][0]["independently_verified_input_and_log_manifest_sha256"] = "changed"
                elif mutation == "gold":
                    docs[2]["cases"][0]["first_audit_gold_sha256"] = "changed"
                elif mutation == "issue_inventory":
                    docs[2]["cases"][0]["source_file_inventory"][0]["sha256"] = "0" * 64
                elif mutation == "wiki_inventory":
                    docs[4]["frozen_manifest"]["value"]["cases"][1]["source_files"][0]["sha256"] = "0" * 64
                else:
                    docs[4]["case_results"][1]["prior_audit_pointer"] = "/cases/3"
                if mutation in {"review_revision", "wiki_reference", "wiki_inventory"}:
                    value = docs[4]["frozen_manifest"]["value"]
                    content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                    docs[4]["frozen_manifest"]["sha256"] = hashlib.sha256(content).hexdigest()
                with self.assertRaises(ValueError):
                    self.derive(docs)

    def test_every_frozen_parent_and_report_byte_change_is_rejected(self):
        for name in self.builder.ARTIFACTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                for filename in self.builder.ARTIFACTS:
                    (directory / filename).write_bytes((DIRECTORY / filename).read_bytes())
                target = directory / name
                target.write_bytes(target.read_bytes() + b" ")
                with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                    self.builder.load_inputs(directory)

    def test_source_bytes_missing_extra_and_unsafe_inventory_are_rejected(self):
        for mutation in ("changed", "missing", "extra", "unsafe"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "log").mkdir()
                for relative in ("input.json", "gold.json", "log/test.txt"):
                    (root / relative).write_bytes(b"frozen\n")
                inventory = {relative: {"size_bytes": 7,
                             "sha256": hashlib.sha256(b"frozen\n").hexdigest()}
                             for relative in ("input.json", "gold.json", "log/test.txt")}
                self.builder.verify_case_files(root, inventory)
                if mutation == "changed":
                    (root / "input.json").write_bytes(b"changed")
                elif mutation == "missing":
                    (root / "log/test.txt").unlink()
                elif mutation == "extra":
                    (root / "log/extra.txt").write_bytes(b"extra")
                else:
                    inventory["../outside"] = inventory.pop("input.json")
                with self.assertRaises(ValueError):
                    self.builder.verify_case_files(root, inventory)

    def test_selection_writer_is_idempotent_and_never_overwrites(self):
        result = self.derive()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "selection.json"
            checksum = self.builder.write_selection(output, result)
            original = output.read_bytes()
            self.assertEqual(checksum, self.builder.write_selection(output, result))
            self.assertEqual(output.read_bytes(), original)
            changed = copy.deepcopy(result)
            changed["retained_count"] -= 1
            with self.assertRaisesRegex(ValueError, "existing cohort"):
                self.builder.write_selection(output, changed)
            self.assertEqual(output.read_bytes(), original)
            symlink = output.with_name("symlink.json")
            symlink.symlink_to(output)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.builder.write_selection(symlink, result)


if __name__ == "__main__":
    unittest.main()
