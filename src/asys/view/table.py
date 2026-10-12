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

from common.const import MAX_CHAR_LINE

__all__ = ["generate_report"]

VERTICAL = " | "
ADD_SUB = " +-"
SUB_ADD = "-+ "


def format_cell(cell, width, fillchar=" "):
    return str(cell).ljust(width, fillchar)


def _split_cell(cell, width):
    cell = str(cell)
    if not cell:
        return [""]
    return [cell[i : i + width] for i in range(0, len(cell), width)]


def _iter_row_lines(row, column_widths):
    cell_lines = [
        _split_cell(row[index] if index < len(row) else "", width)
        for index, width in enumerate(column_widths)
    ]
    if not cell_lines:
        yield []
        return
    line_count = max(len(lines) for lines in cell_lines)
    for line_index in range(line_count):
        yield [
            lines[line_index] if line_index < len(lines) else "" for lines in cell_lines
        ]


def write_header(table_string, table_header, column_widths):
    # Table header data
    for header in table_header:
        for row in _iter_row_lines(header, column_widths):
            # Align the cells in each column print header
            table_string += VERTICAL
            for i, cell in enumerate(row):
                # Align the cells in each column
                table_string += format_cell(cell, column_widths[i]) + VERTICAL
            table_string += "\n"
    return table_string


def write_data(table_string, data_value, column_widths, split_line):
    # Align the each column print data
    for row in data_value:
        for wrapped_row in _iter_row_lines(row, column_widths):
            table_string += VERTICAL
            for i, cell in enumerate(wrapped_row):
                # Align the cells in each column print data
                table_string += format_cell(cell, column_widths[i]) + VERTICAL
            table_string += "\n"
        if split_line:
            table_string += ADD_SUB
            for i, _ in enumerate(column_widths):
                # Align the cells in each column
                table_string += format_cell("", column_widths[i], "-") + SUB_ADD
            table_string += "\n"
    return table_string


def generate_report(table_header, table_data, split_line=False):
    """
    Generate a formatted table string.

    Args:
        table_header (list): The header of the table [[1, 2, 3]].
        table_data (dict): The data of the table
            {
                'none': [
                    [1, 2, 3],
                    [4, 5, 6]
                ],
                'test': [
                    [1, 2, 3],
                    [4, 5, 6]
                ]
            }.
        split_line (bool):  Indicates whether to display the data split line.
    Returns:
        str: The formatted table string.
    """
    # Calculate the width of each column
    table_row = list()
    table_row += table_header
    for data_key, data_value in table_data.items():
        key_list = ["0" for _ in range(len(table_row[0]))]
        key_list[0] = data_key
        table_row.append(key_list)
        table_row += data_value
    column_count = max(len(row) for row in table_row)
    column_widths = [
        max(len(str(row[i])) if i < len(row) else 0 for row in table_row)
        for i in range(column_count)
    ]
    # Create the formatted table string
    table_string = "\n"
    table_string += ADD_SUB
    for i, _ in enumerate(column_widths):
        if column_widths[i] > MAX_CHAR_LINE:
            column_widths[i] = MAX_CHAR_LINE
        column_widths[i] += 5
        # Align the cells in each column
        table_string += str().ljust(column_widths[i], "-") + SUB_ADD
    table_string += "\n"

    table_string = write_header(table_string, table_header, column_widths)

    # Splitting line between header and data
    table_string += " +="
    for i, _ in enumerate(column_widths):
        # Align the cells in each column
        table_string += str().ljust(column_widths[i], "=") + "=+ "
    table_string += "\n"
    # Table content data
    for data_key, data_value in table_data.items():
        if data_key != "none":
            group_row = ["--" + data_key] + [""] * (len(column_widths) - 1)
            for wrapped_row in _iter_row_lines(group_row, column_widths):
                table_string += ADD_SUB
                for i, cell in enumerate(wrapped_row):
                    # Align the cells in each column
                    table_string += format_cell(cell, column_widths[i], "-") + SUB_ADD
                table_string += "\n"
        table_string = write_data(table_string, data_value, column_widths, split_line)

    if not split_line:
        table_string += ADD_SUB
        for i, _ in enumerate(column_widths):
            # Align the cells in each column
            table_string += format_cell("", column_widths[i], "-") + SUB_ADD
        table_string += "\n"
    table_string = table_string.replace("-+ -", "-+--").replace("=+ =", "=+==")
    return "\n".join(line.rstrip() for line in table_string.split("\n"))
