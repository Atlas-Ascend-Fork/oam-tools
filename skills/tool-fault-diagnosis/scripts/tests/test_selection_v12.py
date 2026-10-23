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
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


DIRECTORY = Path(__file__).resolve().parents[2] / "docs/benchmark/2026-10-18"
SCRIPT = DIRECTORY / "derive_selection_v12.py"
CASE = "CASE-WIKI-202501035620611"
RETAINED = "CASE-ISSUE-ops-blas-290"
HISTORICAL = [1143, 1054, 1027, 954, 941, 937, 936, 935, 934, 931, 929, 926]


@unittest.skipUnless(SCRIPT.is_file(), "Missing v12 cohort builder")
class SelectionV12Tests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Missing v12 cohort builder")
        spec = importlib.util.spec_from_file_location("selection_v12", SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.documents = self.builder.load_inputs(DIRECTORY)
        self.parent = self.documents[self.builder.PARENT]
        self.decisions = self.documents[self.builder.DECISIONS]

    def test_only_wiki_changes_with_all_old_rows_order_and_cohorts_preserved(self):
        before = copy.deepcopy(self.parent)
        result = self.builder.derive(self.parent, self.decisions)
        self.assertEqual(self.parent, before)
        self.assertEqual([row["case_id"] for row in before["cases"]],
                         [row["case_id"] for row in result["cases"]])
        self.assertEqual([old["case_id"] for old, new in zip(before["cases"], result["cases"])
                          if old != new], [CASE])
        rows = {row["case_id"]: row for row in result["cases"]}
        unchanged = [row for row in before["cases"] if row["case_id"] != CASE]
        self.assertEqual(len(unchanged), 1142)
        self.assertTrue(all(rows[row["case_id"]] == row for row in unchanged))
        old_excluded = [row for row in before["cases"] if row["decision"] == "exclude"]
        self.assertEqual(len(old_excluded), 217)
        self.assertTrue(all(rows[row["case_id"]] == row for row in old_excluded))
        self.assertEqual(rows[RETAINED], next(row for row in before["cases"]
                                            if row["case_id"] == RETAINED))
        self.assertEqual((result["version"], result["original_count"], result["excluded_count"],
                          result["retained_count"], result["added_excluded_count"]),
                         (12, 1143, 218, 925, 1))
        self.assertEqual(result["added_excluded_case_ids"], [CASE])
        self.assertEqual(result["historical_cohorts"], HISTORICAL)
        self.assertEqual(result["base92_denominator"], 92)
        self.assertEqual(result["additional_source_reports"][:len(before["additional_source_reports"])],
                         before["additional_source_reports"])

    def test_implementation_extract_is_exactly_bound_to_root_rationale(self):
        root = (DIRECTORY / self.builder.ROOT_REVIEW).read_text()
        self.assertIn(self.decisions["cases"][0]["reason"], root)
        self.assertIn(self.decisions["reviewed_retained_cases"][0]["reason"], root)
        self.assertEqual(self.decisions["authorship"], self.builder.AUTHORSHIP)
        self.assertIn("not an independent", self.decisions["authorship"])

    def test_missing_joint_confirmation_or_changed_adjudication_is_rejected(self):
        for mutation in ("proposal", "independent", "final", "reason", "case", "source", "missing",
                         "extra", "retained", "authorship", "parent", "history", "base92", "binding",
                         "timing", "scope"):
            with self.subTest(mutation=mutation):
                decision = copy.deepcopy(self.decisions)
                row = decision["cases"][0]
                if mutation in ("proposal", "independent", "final"):
                    row[{"proposal": "proposal_decision", "independent": "independent_decision",
                         "final": "final_decision"}[mutation]] = "retain"
                elif mutation == "reason":
                    row["reason"] = " "
                elif mutation == "case":
                    row["case_id"] = RETAINED
                elif mutation == "source":
                    row["source"] = "benchmark-ISSUE"
                elif mutation == "missing":
                    decision["cases"].clear()
                elif mutation == "extra":
                    decision["cases"].append(copy.deepcopy(row))
                elif mutation == "retained":
                    decision["reviewed_retained_cases"][0]["final_decision"] = "exclude"
                elif mutation == "authorship":
                    decision["authorship"] = "Independent mechanical review"
                elif mutation == "parent":
                    decision["parent_selection_sha256"] = "0" * 64
                elif mutation == "history":
                    decision["historical_cohorts"].pop()
                elif mutation == "base92":
                    decision["base92_denominator"] = 925
                elif mutation == "binding":
                    decision["report_bindings"][self.builder.REVIEW] = "0" * 64
                elif mutation == "timing":
                    decision["audit_timing"] = "Blind preregistered random holdout"
                else:
                    decision["decision_scope"] = "All future versions of this customer issue"
                with self.assertRaises(ValueError):
                    self.builder.derive(self.parent, decision)

    def test_wrong_parent_counts_identity_or_review_target_state_are_rejected(self):
        for mutation in ("revision", "version", "counts", "duplicate", "target_source", "target_state",
                         "retained_source", "retained_state", "history", "base92"):
            with self.subTest(mutation=mutation):
                parent = copy.deepcopy(self.parent)
                rows = {row["case_id"]: row for row in parent["cases"]}
                if mutation == "revision":
                    parent["benchmark_revision"] = "0" * 40
                elif mutation == "version":
                    parent["version"] = 10
                elif mutation == "counts":
                    parent["excluded_count"] -= 1
                elif mutation == "duplicate":
                    parent["cases"][0] = copy.deepcopy(parent["cases"][1])
                elif mutation.endswith("source"):
                    rows[CASE if mutation == "target_source" else RETAINED]["source"] = "benchmark-DTS"
                elif mutation.endswith("state"):
                    rows[CASE if mutation == "target_state" else RETAINED]["decision"] = "exclude"
                elif mutation == "history":
                    parent["historical_cohorts"].pop()
                else:
                    parent["base92_denominator"] = 925
                with self.assertRaises(ValueError):
                    self.builder.derive(parent, self.decisions)

    def test_every_frozen_artifact_hash_is_enforced(self):
        self.assertEqual(set(self.documents), {self.builder.PARENT, self.builder.DECISIONS})
        for name in self.builder.ARTIFACTS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.copy_artifacts(root)
                target = root / name
                target.write_bytes(target.read_bytes() + b" ")
                with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                    self.builder.load_inputs(root)

    def test_complete_current_git_sources_include_both_gold_files(self):
        self.assertEqual(self.builder.validate_sources(self.decisions), 9)
        for mutation in ("hash", "gold", "log", "traversal", "absolute", "alias", "retained_gold"):
            with self.subTest(mutation=mutation):
                decision = copy.deepcopy(self.decisions)
                files = decision["cases"][0]["source_files"]
                if mutation == "hash":
                    files["input.json"] = "0" * 64
                elif mutation == "gold":
                    files.pop("gold.json")
                elif mutation == "log":
                    files.pop(next(name for name in files if name.startswith("log/")))
                elif mutation in ("traversal", "absolute", "alias"):
                    name = {"traversal": "../input.json", "absolute": "/input.json",
                            "alias": "log/../input.json"}[mutation]
                    files[name] = files.pop("input.json")
                else:
                    decision["reviewed_retained_cases"][0]["source_files"].pop("gold.json")
                with self.assertRaises(ValueError):
                    self.builder.validate_sources(decision)

    def copy_artifacts(self, root):
        for name in self.builder.ARTIFACTS:
            (root / name).write_bytes((DIRECTORY / name).read_bytes())

    def make_git_fixture(self, root):
        for row in self.decisions["cases"] + self.decisions["reviewed_retained_cases"]:
            base = Path(row["source"]) / "cases" / row["case_id"]
            for name in row["source_files"]:
                target = root / base / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((self.builder.BENCHMARK / base / name).read_bytes())
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Selection Test",
                        "-c", "user.email=selection-test@example.invalid", "-c", "commit.gpgsign=false",
                        "commit", "-qm", "Fixed reviewed source fixture"], check=True)
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

    def test_real_git_fixture_rejects_extra_archive_and_hash_laundered_worktree(self):
        for mutation in ("extra_archive", "changed_with_updated_hash", "symlink"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "benchmark"
                root.mkdir()
                revision = self.make_git_fixture(root)
                decision = copy.deepcopy(self.decisions)
                decision["benchmark_revision"] = revision
                target_row = decision["cases"][0]
                base = root / target_row["source"] / "cases" / target_row["case_id"]
                with mock.patch.object(self.builder, "BENCHMARK", root), \
                        mock.patch.object(self.builder, "REVISION", revision):
                    self.assertEqual(self.builder.validate_sources(decision), 9)
                    name = next(name for name in target_row["source_files"] if name.startswith("log/"))
                    target = base / name
                    if mutation == "extra_archive":
                        (base / "log.tar.gz").write_bytes(b"untracked archive")
                        message = "Incomplete source inventory"
                    elif mutation == "changed_with_updated_hash":
                        target.write_bytes(target.read_bytes() + b"changed")
                        target_row["source_files"][name] = hashlib.sha256(target.read_bytes()).hexdigest()
                        message = "Source differs from frozen Git blob"
                    else:
                        other = Path(temporary) / "outside.txt"
                        other.write_bytes(target.read_bytes())
                        target.unlink()
                        target.symlink_to(other)
                        message = "Unsafe source"
                    with self.assertRaisesRegex(ValueError, message):
                        self.builder.validate_sources(decision)

    def test_main_is_idempotent_and_refuses_existing_different_or_symlink_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.copy_artifacts(root)
            output = root / "selection-v12.json"
            with mock.patch.object(self.builder, "DIRECTORY", root), contextlib.redirect_stdout(io.StringIO()):
                self.builder.main()
                original = output.read_bytes()
                self.builder.main()
                self.assertEqual(output.read_bytes(), original)
                self.assertEqual(json.loads(original)["retained_count"], 925)
                output.write_bytes(b"preexisting frozen cohort")
                with self.assertRaisesRegex(ValueError, "Refusing to change an existing cohort"):
                    self.builder.main()
                self.assertEqual(output.read_bytes(), b"preexisting frozen cohort")
                output.unlink()
                target = root / "other.json"
                target.write_bytes(b"unchanged")
                output.symlink_to(target)
                with self.assertRaisesRegex(ValueError, "Refusing a symlinked selection output"):
                    self.builder.main()
                self.assertEqual(target.read_bytes(), b"unchanged")


if __name__ == "__main__":
    unittest.main()
