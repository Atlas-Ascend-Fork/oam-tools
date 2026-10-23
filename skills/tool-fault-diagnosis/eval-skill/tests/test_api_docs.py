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
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lookup_api_docs.py"


class ApiDocsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "Offline API lookup is missing")
        spec = importlib.util.spec_from_file_location("api_docs", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "docs.json.gz"
        contents = {
            "docs/Notes.md": "# Notes\nSetSingleShape( is mentioned here.\n",
            "docs/SetSingleShape.md": "# SetSingleShape\n尺寸约束\nthird line\nfourth line\n",
            "docs/Other.md": "# Other\nSetSingleShape( appears here.\n",
        }
        self.document = {
            "schema_version": 1,
            "repository": "https://example.invalid/vendor/api",
            "revision": "a" * 40,
            "version": "fixture",
            "scope": "Markdown only; images are not included",
            "license_path": "LICENSE",
            "documents": [
                {"path": name, "content": text,
                 "bytes": len(text.encode("utf-8")),
                 "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
                for name, text in contents.items()
            ],
        }
        self.write_corpus()

    def write_corpus(self):
        with gzip.open(self.path, "wt", encoding="utf-8") as handle:
            json.dump(self.document, handle, ensure_ascii=False)

    def test_api_filename_ranks_before_mentions_and_limit_is_explicit(self):
        corpus = self.module.load_corpus(self.path)
        result = self.module.search_docs(corpus, "setsingleshape", limit=1)
        self.assertEqual(result["results"][0]["path"], "docs/SetSingleShape.md")
        self.assertEqual(result["matching_documents"], 3)
        self.assertEqual(result["searched_documents"], 3)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["revision"], "a" * 40)

    def test_unicode_literal_search_returns_original_line_number_and_text(self):
        result = self.module.search_docs(
            self.module.load_corpus(self.path), "尺寸约束")
        hit = result["results"][0]
        self.assertEqual(hit["matched_lines"], [2])
        self.assertIn({"line": 2, "text": "尺寸约束"}, hit["lines"])

    def test_search_treats_regex_metacharacters_as_literal(self):
        result = self.module.search_docs(
            self.module.load_corpus(self.path), ".*")
        self.assertEqual(result["matching_documents"], 0)
        self.assertFalse(result["truncated"])

    def test_later_window_keeps_line_numbers_and_remaining_range(self):
        result = self.module.read_document(
            self.module.load_corpus(self.path), "docs/SetSingleShape.md", 3, 1)
        self.assertEqual(result["lines"], [{"line": 3, "text": "third line"}])
        self.assertEqual(result["total_lines"], 4)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_start_line"], 4)

    def test_unknown_path_cannot_return_a_different_api(self):
        with self.assertRaisesRegex(ValueError, "Unknown document"):
            self.module.read_document(
                self.module.load_corpus(self.path), "../SetSingleShape.md")

    def test_content_corruption_fails_before_search(self):
        self.document["documents"][0]["content"] += "modified"
        self.write_corpus()
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.module.load_corpus(self.path)

    def test_multipart_corpus_is_joined_when_base_file_is_absent(self):
        raw = self.path.read_bytes()
        self.path.unlink()
        midpoint = len(raw) // 2
        self.path.with_name(self.path.name + ".part00").write_bytes(raw[:midpoint])
        self.path.with_name(self.path.name + ".part01").write_bytes(raw[midpoint:])
        corpus = self.module.load_corpus(self.path)
        self.assertEqual(len(corpus["documents"]), 3)
        self.assertEqual(self.module.search_docs(corpus, "SetSingleShape")["status"], "ok")

    def test_duplicate_paths_fail_instead_of_overwriting_a_variant(self):
        self.document["documents"].append(self.document["documents"][0].copy())
        self.write_corpus()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.module.load_corpus(self.path)

    def test_cli_corrupt_deflate_is_a_json_error_without_success_output(self):
        self.path.write_bytes(bytes.fromhex("1f8b0800000000000003070000000000000000"))
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--corpus", str(self.path), "--query", "needle"],
            capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(process.stdout, "")
        self.assertTrue(process.stderr.startswith('{"status": "error"'), process.stderr)
        self.assertEqual(json.loads(process.stderr)["status"], "error")

    def test_empty_query_and_invalid_ranges_fail(self):
        corpus = self.module.load_corpus(self.path)
        for query in ("", " "):
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.module.search_docs(corpus, query)
        for start, count in ((0, 1), (1, 0), (1, 401), (6, 1)):
            with self.subTest(start=start, count=count), self.assertRaises(ValueError):
                self.module.read_document(corpus, "docs/Other.md", start, count)


if __name__ == "__main__":
    unittest.main()
