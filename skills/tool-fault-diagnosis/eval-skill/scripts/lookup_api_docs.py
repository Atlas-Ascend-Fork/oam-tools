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
"""Read a pinned, offline API documentation corpus without extracting it."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sys
from urllib.parse import quote
import zlib


DEFAULT_CORPUS = (Path(__file__).resolve().parents[1] / "references" /
                  "api-docs" / "asc-devkit-v9.0.0-beta.2.json.gz")


def _read_corpus_bytes(path):
    if path.exists():
        return path.read_bytes()
    parts = sorted(path.parent.glob(path.name + ".part[0-9][0-9]"))
    if not parts:
        raise FileNotFoundError(path)
    return b"".join(part.read_bytes() for part in parts)


def load_corpus(path):
    raw = _read_corpus_bytes(path)
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as handle:
        content = handle.read().decode("utf-8")
    with io.StringIO(content) as handle:
        corpus = json.load(handle)
    if corpus.get("schema_version") != 1 or not corpus.get("documents"):
        raise ValueError("Unsupported or empty documentation corpus")
    for key in ("repository", "revision", "version", "scope", "license_path"):
        if not isinstance(corpus.get(key), str) or not corpus[key]:
            raise ValueError("Missing corpus metadata: " + key)
    paths = set()
    for document in corpus["documents"]:
        path = document["path"]
        if path in paths:
            raise ValueError("Duplicate document: " + path)
        paths.add(path)
        raw = document["content"].encode("utf-8")
        if (len(raw) != document["bytes"] or
                hashlib.sha256(raw).hexdigest() != document["sha256"]):
            raise ValueError("Document integrity mismatch: " + path)
    return corpus


def identity(corpus):
    return {key: corpus[key] for key in
            ("repository", "revision", "version", "scope", "license_path")}


def document_identity(corpus, document):
    return {key: document[key] for key in ("path", "bytes", "sha256")} | {
        "source_url": (corpus["repository"].rstrip("/") + "/blob/" +
                       corpus["revision"] + "/" + quote(document["path"], safe="/"))}


def numbered(lines, start, count):
    return [{"line": index + 1, "text": lines[index]}
            for index in range(start - 1, min(len(lines), start - 1 + count))]


def search_docs(corpus, query, limit=5):
    if not query.strip() or not 1 <= limit <= 20:
        raise ValueError("Use a nonempty literal query and limit between 1 and 20")
    query = query.casefold()
    hits = []
    for document in corpus["documents"]:
        path = document["path"]
        lines = document["content"].splitlines()
        matched = [index + 1 for index, line in enumerate(lines)
                   if query in line.casefold()]
        stem = PurePosixPath(path).stem.casefold()
        if query not in path.casefold() and not matched:
            continue
        rank = 0 if query == stem else 1 if query in path.casefold() else 2
        first = matched[0] if matched else 1
        hits.append((rank, path, document_identity(corpus, document) | {
            "matched_lines": matched[:20], "matching_line_count": len(matched),
            "matched_lines_truncated": len(matched) > 20,
            "total_lines": len(lines),
            "lines": numbered(lines, max(1, first - 3), 7),
        }))
    hits.sort(key=lambda item: (item[0], item[1]))
    return identity(corpus) | {
        "status": "ok", "searched_documents": len(corpus["documents"]),
        "matching_documents": len(hits), "truncated": len(hits) > limit,
        "window_policy": "First matching window per document; use --document for context",
        "results": [item[2] for item in hits[:limit]],
    }


def read_document(corpus, path, start_line=1, count=100):
    document = next((item for item in corpus["documents"]
                     if item["path"] == path), None)
    if document is None:
        raise ValueError("Unknown document: " + path)
    lines = document["content"].splitlines()
    if not 1 <= count <= 400 or start_line < 1 or start_line > max(1, len(lines)):
        raise ValueError("Invalid line range; count must be between 1 and 400")
    end = min(len(lines), start_line - 1 + count)
    return identity(corpus) | document_identity(corpus, document) | {
        "status": "ok", "total_lines": len(lines),
        "lines": numbered(lines, start_line, count),
        "has_more": end < len(lines),
        "next_start_line": end + 1 if end < len(lines) else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--query", help="Literal API name or phrase; case insensitive")
    action.add_argument("--document", help="Exact repository-relative path from search")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--start-line", type=int, default=1)
    parser.add_argument("--lines", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        corpus = load_corpus(args.corpus)
        if args.query is not None:
            result = search_docs(corpus, args.query, args.limit)
        else:
            result = read_document(corpus, args.document, args.start_line, args.lines)
    except (OSError, EOFError, ValueError, KeyError, TypeError, AttributeError, zlib.error) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
