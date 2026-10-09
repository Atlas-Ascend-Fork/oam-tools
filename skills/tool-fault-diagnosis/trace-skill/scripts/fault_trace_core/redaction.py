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

"""Deterministic package-local pseudonymization for displayable trace text."""

from __future__ import annotations

import re


_LABELED_PATH = re.compile(
    r"(?i)\b((?:path|data|file|dir|directory|cwd)\s*[=:]\s*)"
    r"(\"[^\"]+\"|'[^']+'|[A-Z]:\\.*?(?=\s+\w+\s*[=:]|$)|/.*?(?=\s+\w+\s*[=:]|$))"
)
_QUOTED_PATH = re.compile(
    r"(?i)([\"'])(?:[A-Z]:\\|/(?:home|Users|data|workspace|mnt|opt|var|tmp|srv)/).*?\1"
)
_WINDOWS_OR_BUSINESS_PATH = re.compile(
    r"(?i)(?<![\w])(?:[A-Z]:\\(?:[^\\\s,:\)\]]+\\)*[^\\\s,:\)\]]+|"
    r"/(?:home|Users|data|workspace|mnt|opt|var|tmp|srv)(?:/[^\s,:\)\]]+)+)"
)
_IP_ADDRESS = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6_CANDIDATE = re.compile(
    r"(?<![0-9A-Za-z:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Za-z:])"
)
_HOST_VALUE = re.compile(r"(?i)\b(host(?:name)?(?:\s*[=:]\s*|\s+))([A-Za-z0-9_.-]+)")
_USER_VALUE = re.compile(r"(?i)\b(user(?:name)?(?:\s*[=:]\s*|\s+))([A-Za-z0-9_.-]+)")
_PATTERN_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,31}")
_BUILTIN_KINDS = {"PATH", "IP", "HOST", "USER"}


def compile_additional_patterns(
    patterns: dict[str, str] | None,
) -> tuple[tuple[str, re.Pattern[str]], ...]:
    if patterns is None:
        return ()
    if not isinstance(patterns, dict):
        raise ValueError("additional_patterns must be an object")
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for name, expression in sorted(patterns.items()):
        if (
            not isinstance(name, str)
            or _PATTERN_NAME.fullmatch(name) is None
            or name in _BUILTIN_KINDS
        ):
            raise ValueError(
                "additional pattern names must be unique uppercase identifiers and not builtin names"
            )
        if not isinstance(expression, str) or not expression:
            raise ValueError(f"additional pattern {name} must be a non-empty regex string")
        try:
            pattern = re.compile(expression)
        except re.error as error:
            raise ValueError(f"additional pattern {name} is not a valid regex: {error}") from error
        if pattern.search("") is not None:
            raise ValueError(f"additional pattern {name} must not match empty text")
        compiled.append((name, pattern))
    return tuple(compiled)


class Pseudonymizer:
    """Assign stable aliases in deterministic first-seen order within one package."""

    def __init__(self, additional_patterns: dict[str, str] | None = None) -> None:
        self._aliases: dict[str, dict[str, str]] = {
            "PATH": {},
            "IP": {},
            "HOST": {},
            "USER": {},
        }
        self._additional_patterns = compile_additional_patterns(additional_patterns)
        self._aliases.update({name: {} for name, _ in self._additional_patterns})

    def _alias(self, kind: str, value: str) -> str:
        aliases = self._aliases[kind]
        if value not in aliases:
            aliases[value] = f"{kind}-{len(aliases) + 1:03d}"
        return aliases[value]

    def redact(self, text: str) -> str:
        result = text
        for name, pattern in self._additional_patterns:
            result = pattern.sub(
                lambda match, kind=name: self._alias(kind, match.group(0)), result
            )
        result = _LABELED_PATH.sub(
            lambda match: match.group(1) + self._alias("PATH", match.group(2).strip("\"'")),
            result,
        )
        result = _QUOTED_PATH.sub(
            lambda match: self._alias("PATH", match.group(0).strip("\"'")), result
        )
        result = _WINDOWS_OR_BUSINESS_PATH.sub(
            lambda match: self._alias("PATH", match.group(0)), result
        )
        result = _IPV6_CANDIDATE.sub(self._redact_ipv6_candidate, result)
        result = _IP_ADDRESS.sub(lambda match: self._alias("IP", match.group(0)), result)
        result = _HOST_VALUE.sub(
            lambda match: match.group(1) + self._alias("HOST", match.group(2)), result
        )
        return _USER_VALUE.sub(
            lambda match: match.group(1) + self._alias("USER", match.group(2)), result
        )

    def _redact_ipv6_candidate(self, match: re.Match[str]) -> str:
        candidate = match.group(0)
        if "::" not in candidate and candidate.count(":") < 4:
            return candidate
        return self._alias("IP", candidate)
