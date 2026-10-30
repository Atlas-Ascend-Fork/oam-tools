#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import config.config_parser as config_parser
from config import AsysConfigParser
from params import ParamDict
from testcase.conftest import AssertTest

SHIPPED_ROWS = "g++,g++ --version | grep g++\ngcc,gcc --version | grep gcc\n"


class TestConfigParserDepRows(AssertTest):
    """main() reaches dependent_package.csv through AsysConfigParser.parse().

    The other cases in this area stub the CSV reader out, so they never touch
    the entry main() actually uses. These cases drive parse() with a real file
    to keep that path covered.
    """

    def _conf_dir(self, tmp_path, csv_text):
        conf_dir = tmp_path / "conf"
        conf_dir.mkdir(exist_ok=True)
        (conf_dir / "dependent_package.csv").write_text(csv_text, encoding="utf-8")
        (conf_dir / "asys.ini").write_text(
            "[launch]\ngraph=TRUE\nops=TRUE\n", encoding="utf-8"
        )
        return conf_dir

    def _parse(self, mocker, tmp_path, csv_text):
        conf_dir = self._conf_dir(tmp_path, csv_text)
        mocker.patch.object(
            config_parser, "get_project_conf", return_value=str(conf_dir)
        )
        mocker.patch("params.ParamDict.get_command", return_value="launch")
        # ParamDict is a singleton, so the deps collected here would leak into
        # the next case; start every case from an empty registry.
        ParamDict()._ParamDict__deps.clear()

        parser = AsysConfigParser()
        assert parser.parse() is True
        return list(ParamDict().get_deps())

    def test_parse_keeps_the_usable_rows(self, mocker, tmp_path):
        assert self._parse(mocker, tmp_path, SHIPPED_ROWS) == ["g++", "gcc"]

    def test_parse_accepts_a_csv_with_a_trailing_blank_line(self, mocker, tmp_path):
        # csv.reader turns the trailing newline of the shipped file into an
        # empty row, and set_deps() used to index row[1] on it.
        assert self._parse(mocker, tmp_path, SHIPPED_ROWS + "\n") == ["g++", "gcc"]

    def test_parse_accepts_a_csv_with_a_middle_blank_line(self, mocker, tmp_path):
        assert self._parse(
            mocker, tmp_path, "g++,g++ --version\n\ngcc,gcc --version\n"
        ) == ["g++", "gcc"]

    def test_parse_accepts_a_csv_with_a_comment_row(self, mocker, tmp_path):
        assert self._parse(mocker, tmp_path, "# note\n" + SHIPPED_ROWS) == [
            "g++",
            "gcc",
        ]

    def test_parse_accepts_a_csv_with_a_single_column_row(self, mocker, tmp_path):
        # A package written without its command column used to raise
        # IndexError here, before any command could run.
        assert self._parse(mocker, tmp_path, SHIPPED_ROWS + "only-a-name\n") == [
            "g++",
            "gcc",
        ]
