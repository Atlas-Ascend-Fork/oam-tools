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
"""Export pinned public source or docs as a corpus for lookup_api_docs.py."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".cce",
            ".py", ".cmake", ".sh", ".json", ".yaml", ".yml", ".proto", ".def", ".in"}
ROOT_FILES = {"LICENSE", "README.md", "CMakeLists.txt", "requirements.txt"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--scope", choices=("source", "docs"), default="source")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise ValueError("Use a full immutable Git revision")
    if not re.fullmatch(r"[a-z0-9-]+", args.name):
        raise ValueError("Invalid corpus name")
    license_path = args.output.parent / ("LICENSE." + args.name)
    destinations = (args.output, args.manifest, license_path)
    if len({path.resolve() for path in destinations}) != len(destinations):
        raise ValueError("Corpus, manifest and license paths must be distinct")
    if any(path.exists() for path in destinations):
        raise ValueError("Refusing to overwrite an existing export")

    def git(*command, **options):
        return subprocess.check_output(
            ["git", "--git-dir=" + str(args.git), *command], timeout=240, **options)

    if git("rev-parse", args.revision + "^{commit}").decode().strip() != args.revision:
        raise ValueError("Unexpected commit revision")
    selected = []
    for row in git("ls-tree", "-r", "-z", args.revision).split(b"\0"):
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        parts = PurePosixPath(path).parts
        if any(part.startswith(".") for part in parts):
            continue
        if args.scope == "docs":
            if path != "LICENSE" and not ("docs" in parts and path.endswith(".md")):
                continue
        else:
            if "docs" in parts:
                continue
            if (path not in ROOT_FILES and PurePosixPath(path).suffix not in SUFFIXES
                    and PurePosixPath(path).name != "CMakeLists.txt"):
                continue
        mode, kind, blob = metadata.split()
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            continue
        selected.append({"path": path, "git_blob": blob.decode()})
    payload = git("cat-file", "--batch", input="".join(
        item["git_blob"] + "\n" for item in selected).encode("ascii"))
    cursor, documents, omitted = 0, [], []
    for item in selected:
        end = payload.index(b"\n", cursor)
        header = payload[cursor:end].split()
        if len(header) != 3 or header[:2] != [item["git_blob"].encode(), b"blob"]:
            raise ValueError("Unexpected Git object: " + item["path"])
        size = int(header[2])
        if size < 0:
            raise ValueError("Negative object size")
        cursor = end + 1
        raw = payload[cursor:cursor + size]
        cursor += size
        if payload[cursor:cursor + 1] != b"\n":
            raise ValueError("Invalid object delimiter")
        cursor += 1
        blob = hashlib.sha1(b"blob " + str(size).encode() + b"\0" + raw).hexdigest()
        if len(raw) != size or blob != item["git_blob"]:
            raise ValueError("Git blob mismatch: " + item["path"])
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            omitted.append(item | {"reason": "non-UTF-8"})
            continue
        if "\0" in content:
            omitted.append(item | {"reason": "NUL bytes"})
            continue
        if content.encode("utf-8") != raw:
            raise ValueError("UTF-8 round trip mismatch")
        documents.append(item | {"bytes": size, "sha256": hashlib.sha256(raw).hexdigest(),
                                 "content": content})
    if cursor != len(payload) or not any(item["path"] == "LICENSE" for item in documents):
        raise ValueError("Trailing objects or missing root license")
    scope = ("All Markdown under any docs/ directory plus root LICENSE; "
             "no source, images or other revisions" if args.scope == "docs" else
             "Tracked UTF-8 source/build/test files by suffix plus root LICENSE/README; "
             "no docs directories, dot paths, binary files, history or other revisions")
    corpus = {"schema_version": 1, "repository": args.repository,
              "revision": args.revision, "version": args.version,
              "scope": scope,
              "license_path": "LICENSE", "documents": sorted(documents, key=lambda item: item["path"])}
    compressed = gzip.compress(json.dumps(corpus, ensure_ascii=False, separators=(",", ":")).encode(),
                               compresslevel=9, mtime=0)
    manifest = {key: value for key, value in corpus.items() if key != "documents"} | {
        "source_bytes": sum(item["bytes"] for item in documents), "document_count": len(documents),
        "corpus_sha256": hashlib.sha256(compressed).hexdigest(),
        "export_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "suffixes": [".md"] if args.scope == "docs" else sorted(SUFFIXES),
        "root_files": ["LICENSE"] if args.scope == "docs" else sorted(ROOT_FILES), "omitted": omitted,
        "files": [{key: value for key, value in item.items() if key != "content"}
                  for item in corpus["documents"]]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(compressed)
    license_path.write_bytes(next(item["content"].encode() for item in documents if item["path"] == "LICENSE"))
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key not in ("files", "omitted")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
