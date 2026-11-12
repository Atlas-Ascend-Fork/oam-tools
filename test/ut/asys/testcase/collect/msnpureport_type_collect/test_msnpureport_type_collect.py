#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# ----------------------------------------------------------------------------
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain a
# copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
# ----------------------------------------------------------------------------

import os
import shutil

from collect.msnpureport_type_collect import (
    collect_msnpureport_type_info,
    merge_dir,
)
from params import ParamDict


class TestMsnpureportTypeCollect:
    def setup_method(self):
        ParamDict().set_env_type("EP")
        self.output = os.path.join(os.path.dirname(__file__), "type_collect_tmp")
        if os.path.exists(self.output):
            shutil.rmtree(self.output)
        os.makedirs(self.output)

    def teardown_method(self):
        ParamDict.clear()
        if os.path.exists(self.output):
            shutil.rmtree(self.output)

    def test_commands_are_selected_by_chip_and_archived(self, mocker, caplog):
        commands = []
        output_dirs = {}

        def fake_run_cmd_output(command, timeout=None):  # noqa: ARG001  # timeout kwarg since #399
            commands.append(command)
            type_dir = os.path.join(self.output, "export_type_tmp", "type_5")
            output_dir = os.path.join(type_dir, "20261107110000")
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(os.path.join(output_dir, "system_info"), exist_ok=True)
            with open(
                os.path.join(output_dir, "system_info", "data.log"),
                "w",
                encoding="utf-8",
            ) as fw:
                fw.write("module data")
            output_dirs[command] = output_dir
            return True, ""

        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            side_effect=fake_run_cmd_output,
        )
        mocker.patch("common.DeviceInfo.get_chip_info", return_value="Ascend910B1")
        mocker.patch("common.DeviceInfo.get_device_count", return_value=1)
        mocker.patch(
            "collect.msnpureport_type_collect.parse_ub_in_place", return_value=True
        )

        result = collect_msnpureport_type_info(self.output)

        assert result is True
        assert len(commands) == 1
        assert "msnpureport report -t 5" in commands[0]
        assert os.path.isfile(
            os.path.join(self.output, "dfx", "system_info", "data.log")
        )
        assert not os.path.exists(os.path.join(self.output, "export_type_tmp"))
        assert "No device supports msnpureport typed export, skip." not in caplog.text

    def test_950_runs_all_commands_and_merges_ao_dirs(self, mocker):
        commands = []

        def fake_run_cmd_output(command, timeout=None):  # noqa: ARG001  # timeout kwarg since #399
            commands.append(command)
            type_id = int(command.rsplit("-t ", 1)[1].split()[0])
            type_dir = os.path.join(self.output, "export_type_tmp", f"type_{type_id}")
            output_dir = os.path.join(type_dir, "20261107110000")
            dir_name = {
                5: "system_info",
                6: "ub_info",
                7: "ao_info",
                8: "ao_info",
                9: "ao_info",
                10: "ccu_info",
                11: "network_info",
            }[type_id]
            leaf_name = {7: "ao_self", 8: "ao_cnt", 9: "ao_uart"}.get(type_id, "data")
            os.makedirs(
                os.path.join(output_dir, dir_name, "dev-os-0", leaf_name), exist_ok=True
            )
            with open(
                os.path.join(output_dir, dir_name, "dev-os-0", leaf_name, "data.log"),
                "w",
                encoding="utf-8",
            ) as fw:
                fw.write(f"type {type_id}")
            return True, ""

        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            side_effect=fake_run_cmd_output,
        )
        mocker.patch("common.DeviceInfo.get_chip_info", return_value="Ascend950")
        mocker.patch("common.DeviceInfo.get_device_count", return_value=1)
        mocker.patch(
            "collect.msnpureport_type_collect.parse_ub_in_place", return_value=True
        )

        result = collect_msnpureport_type_info(self.output)

        assert result is True
        assert [command.rsplit("-t ", 1)[1].split()[0] for command in commands] == [
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
        ]
        assert os.path.isfile(
            os.path.join(
                self.output, "dfx", "ao_info", "dev-os-0", "ao_self", "data.log"
            )
        )
        assert os.path.isfile(
            os.path.join(
                self.output, "dfx", "ao_info", "dev-os-0", "ao_cnt", "data.log"
            )
        )
        assert os.path.isfile(
            os.path.join(
                self.output, "dfx", "ao_info", "dev-os-0", "ao_uart", "data.log"
            )
        )

    def test_960_environment_runs_all_type_commands(self, mocker):
        commands = []

        def fake_run_cmd_output(command, timeout=None):  # noqa: ARG001  # timeout kwarg since #399
            commands.append(command)
            type_id = int(command.rsplit("-t ", 1)[1].split()[0])
            type_dir = os.path.join(self.output, "export_type_tmp", f"type_{type_id}")
            output_dir = os.path.join(type_dir, "20261107110000")
            dir_name = {
                5: "system_info",
                6: "ub_info",
                7: "ao_info",
                8: "ao_info",
                9: "ao_info",
                10: "ccu_info",
                11: "network_info",
            }[type_id]
            output_tree = os.path.join(output_dir, dir_name)
            os.makedirs(output_tree, exist_ok=True)
            with open(
                os.path.join(output_tree, "data.log"), "w", encoding="utf-8"
            ) as fw:
                fw.write(f"type {type_id}")
            return True, ""

        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            side_effect=fake_run_cmd_output,
        )
        mocker.patch("common.DeviceInfo.get_chip_info", return_value="Ascend960")
        mocker.patch("common.DeviceInfo.get_device_count", return_value=1)
        mocker.patch(
            "collect.msnpureport_type_collect.parse_ub_in_place", return_value=True
        )

        assert collect_msnpureport_type_info(self.output) is True
        assert [command.rsplit("-t ", 1)[1].split()[0] for command in commands] == [
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
        ]

    def test_partial_failure_returns_true_and_warns_once(self, mocker, caplog):
        commands = []

        def fake_run_cmd_output(command, timeout=None):  # noqa: ARG001  # timeout kwarg since #399
            commands.append(command)
            type_id = int(command.rsplit("-t ", 1)[1].split()[0])
            if type_id != 5:
                return False, "typed export failed"

            type_dir = os.path.join(self.output, "export_type_tmp", "type_5")
            output_dir = os.path.join(type_dir, "20261107110000")
            os.makedirs(os.path.join(output_dir, "system_info"), exist_ok=True)
            with open(
                os.path.join(output_dir, "system_info", "data.log"),
                "w",
                encoding="utf-8",
            ) as fw:
                fw.write("module data")
            return True, ""

        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            side_effect=fake_run_cmd_output,
        )
        mocker.patch("common.DeviceInfo.get_chip_info", return_value="Ascend950")
        mocker.patch("common.DeviceInfo.get_device_count", return_value=1)
        mocker.patch(
            "collect.msnpureport_type_collect.parse_ub_in_place", return_value=True
        )

        assert collect_msnpureport_type_info(self.output) is True
        assert len(commands) == 7
        assert (
            caplog.text.count(
                "execute failed, which may be caused by a low driver package version"
            )
            == 1
        )

    def test_failed_commands_are_merged_into_one_warning(self, mocker, caplog):
        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            return_value=(False, "typed export failed"),
        )
        mocker.patch("common.DeviceInfo.get_chip_info", return_value="Ascend950")
        mocker.patch("common.DeviceInfo.get_device_count", return_value=1)
        mocker.patch(
            "collect.msnpureport_type_collect.parse_ub_in_place", return_value=True
        )

        result = collect_msnpureport_type_info(self.output)

        assert result is False
        assert (
            caplog.text.count(
                "execute failed, which may be caused by a low driver package version"
            )
            == 1
        )
        assert (
            "msnpureport report -t 5/-t 6/-t 7/-t 8/-t 9/-t 10/-t 11 execute failed"
            in caplog.text
        )

    def test_merge_dir_keeps_existing_content(self, tmp_path):
        source = tmp_path / "source"
        target = tmp_path / "target"
        (source / "dev-os-0" / "ao_self").mkdir(parents=True)
        (target / "dev-os-0" / "ao_cnt").mkdir(parents=True)
        (source / "dev-os-0" / "ao_self" / "new.log").write_text(
            "new", encoding="utf-8"
        )
        (target / "dev-os-0" / "ao_cnt" / "old.log").write_text("old", encoding="utf-8")

        assert merge_dir(str(source), str(target)) is True
        assert (target / "dev-os-0" / "ao_self" / "new.log").is_file()
        assert (target / "dev-os-0" / "ao_cnt" / "old.log").is_file()
        assert not source.exists()

    def test_empty_output_and_unexpected_dir_are_failures(self, mocker, caplog):
        output_dir = os.path.join(self.output, "empty_timestamp")
        os.makedirs(output_dir)

        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            return_value=(True, ""),
        )
        mocker.patch(
            "common.FileOperate.list_dir", return_value=[os.path.basename(output_dir)]
        )
        mocker.patch("common.DeviceInfo.get_chip_info", return_value="Ascend910B1")
        mocker.patch("common.DeviceInfo.get_device_count", return_value=1)
        mocker.patch(
            "collect.msnpureport_type_collect.parse_ub_in_place", return_value=True
        )

        assert collect_msnpureport_type_info(self.output) is False
        assert "msnpureport report -t 5 execute failed" in caplog.text

    def test_unexpected_output_dir_logs_warning(self, tmp_path, caplog):
        source = tmp_path / "source" / "unexpected"
        source.mkdir(parents=True)
        (source / "keep.log").write_text("keep", encoding="utf-8")
        target = tmp_path / "target"

        from collect.msnpureport_type_collect import _archive_type_output

        assert (
            _archive_type_output(str(source.parent), str(target), ["system_info"])
            is False
        )
        assert "No expected msnpureport output directories" in caplog.text

    def test_merge_dir_reports_target_file_conflict_without_overwrite(
        self, tmp_path, caplog
    ):
        source = tmp_path / "source"
        target = tmp_path / "target"
        (source / "dev-os-0").mkdir(parents=True)
        (target / "dev-os-0").mkdir(parents=True)
        (source / "dev-os-0" / "ao_self.log").write_text("new", encoding="utf-8")
        (target / "dev-os-0" / "ao_self.log").write_text("old", encoding="utf-8")

        assert merge_dir(str(source), str(target)) is False
        assert (target / "dev-os-0" / "ao_self.log").read_text(
            encoding="utf-8"
        ) == "old"
        assert "The merge target file already exists" in caplog.text

    def test_merge_dir_moves_empty_source_dir(self, tmp_path):
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()

        assert merge_dir(str(source), str(target)) is True
        assert target.is_dir()
        assert not source.exists()

    def test_merge_dir_returns_false_when_listing_fails(self, tmp_path, mocker):
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        mocker.patch("os.listdir", side_effect=OSError("permission denied"))

        assert merge_dir(str(source), str(target)) is False
