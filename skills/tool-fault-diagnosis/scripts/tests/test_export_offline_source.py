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
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "export_offline_source.py"


class ExportSourceTests(unittest.TestCase):
    def test_exports_source_bytes_and_license_without_docs_or_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            files = {
                "LICENSE": b"Example license\r\n",
                "op_host/api.cpp": b"int example() { return 1; }\r\n",
                "tests/test_api.py": b"assert True\n",
                "docs/api.md": b"Documentation stored separately\n",
                "docs/source.cpp": b"int documentation_example;\n",
                ".gitcode/job.yml": b"command: irrelevant\n",
                "op_kernel/data.bin": b"\x00binary",
                "op_kernel/binary.cpp": b"\x00not source",
                "op_kernel/non_utf8.py": b"\xff\xfe",
            }
            for name, raw in files.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run([
                "git", "-C", str(repo), "-c", "user.name=Test", "-c",
                "user.email=test@example.invalid", "commit", "-qm", "fixture",
            ], check=True)
            revision = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            output = root / "out" / "source.json.gz"
            manifest = root / "manifest.json"
            command = [
                "python3", str(SCRIPT), "--git", str(repo / ".git"),
                "--revision", revision, "--version", "fixture",
                "--repository", "https://gitcode.com/cann/example", "--name", "example",
                "--output", str(output), "--manifest", str(manifest),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            spec = importlib.util.spec_from_file_location(
                "reader", SCRIPT.parents[1] / "eval-skill/scripts/lookup_api_docs.py")
            reader = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(reader)
            corpus = reader.load_corpus(output)
            documents = {item["path"]: item for item in corpus["documents"]}
            self.assertEqual(set(documents), {"LICENSE", "op_host/api.cpp", "tests/test_api.py"})
            for name, document in documents.items():
                self.assertEqual(document["content"].encode(), files[name])
                blob = subprocess.check_output([
                    "git", "-C", str(repo), "rev-parse", revision + ":" + name,
                ], text=True).strip()
                self.assertEqual(document["git_blob"], blob)
            self.assertEqual((output.parent / "LICENSE.example").read_bytes(), files["LICENSE"])
            self.assertEqual(json.loads(gzip.decompress(output.read_bytes())), corpus)
            docs_output = root / "docs-out" / "docs.json.gz"
            docs_manifest = root / "docs-manifest.json"
            docs_command = command.copy()
            docs_command[docs_command.index("--output") + 1] = str(docs_output)
            docs_command[docs_command.index("--manifest") + 1] = str(docs_manifest)
            docs_result = subprocess.run(
                docs_command + ["--scope", "docs"], capture_output=True, text=True)
            self.assertEqual(docs_result.returncode, 0, docs_result.stderr)
            docs_corpus = reader.load_corpus(docs_output)
            self.assertEqual({item["path"] for item in docs_corpus["documents"]},
                             {"LICENSE", "docs/api.md"})
            for item in docs_corpus["documents"]:
                self.assertEqual(item["content"].encode(), files[item["path"]])
            self.assertEqual(json.loads(docs_manifest.read_text())["document_count"], 2)
            prior = output.read_bytes()
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(output.read_bytes(), prior)
            for index, (output_name, manifest_name) in enumerate([
                    ("same.json.gz", "same.json.gz"),
                    ("LICENSE.example", "manifest.json"),
                    ("source.json.gz", "LICENSE.example")]):
                with self.subTest(output_name=output_name, manifest_name=manifest_name):
                    target = root / ("collision-" + str(index))
                    colliding = command.copy()
                    colliding[colliding.index("--output") + 1] = str(target / output_name)
                    colliding[colliding.index("--manifest") + 1] = str(target / manifest_name)
                    rejected = subprocess.run(colliding, capture_output=True, text=True)
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
                    self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
