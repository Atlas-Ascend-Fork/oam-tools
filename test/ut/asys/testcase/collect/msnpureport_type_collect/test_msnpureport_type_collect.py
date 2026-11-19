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

    def test_350_environment_runs_all_type_commands(self, mocker):
        # Ascend350 supports every typed export (-t 5 through -t 11) just
        # like 950/960: the chip gate must not skip the typed collection.
        commands = []

        def fake_run_cmd_output(command, timeout=None, **_kwargs):  # noqa: ARG001
            commands.append(command)
            type_id = int(command.rsplit("-t ", 1)[1].split()[0])
            type_dir = os.path.join(self.output, "export_type_tmp", f"type_{type_id}")
            output_dir = os.path.join(type_dir, "20261118000000")
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
        mocker.patch(
            "common.DeviceInfo.get_chip_info", return_value="Ascend Ascend350 v1"
        )
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

    def test_merge_dir_identical_file_is_idempotent(self, tmp_path):
        # -f and -t 5 both export system_info; the same relative file is
        # merged twice per collect run. Identical content must be a no-op
        # success (so the typed export is not misreported as failed), while
        # the duplicate source copy is removed.
        source = tmp_path / "source"
        target = tmp_path / "target"
        (source / "dev-os-0" / "tee").mkdir(parents=True)
        (target / "dev-os-0" / "tee").mkdir(parents=True)
        (source / "dev-os-0" / "tee" / "tee.log").write_text("same", encoding="utf-8")
        (target / "dev-os-0" / "tee" / "tee.log").write_text("same", encoding="utf-8")

        assert merge_dir(str(source), str(target)) is True
        assert (target / "dev-os-0" / "tee" / "tee.log").read_text(
            encoding="utf-8"
        ) == "same"
        assert not (source / "dev-os-0" / "tee" / "tee.log").exists()

    def test_merge_dir_conflicting_content_keeps_both_copies(self, tmp_path):
        # Genuinely different content under the same relative path stays a
        # conflict: the target copy keeps its name, the source copy is kept
        # under a suffixed name tagged with its origin (the temporary export
        # directory is deleted afterwards, so dropping the source would lose
        # the data). No data is lost, so the merge succeeds with a warning.
        source = tmp_path / "source"
        target = tmp_path / "target"
        (source / "dev-os-0" / "tee").mkdir(parents=True)
        (target / "dev-os-0" / "tee").mkdir(parents=True)
        (source / "dev-os-0" / "tee" / "tee.log").write_text("new", encoding="utf-8")
        (target / "dev-os-0" / "tee" / "tee.log").write_text("old", encoding="utf-8")

        assert merge_dir(str(source), str(target), "typed_export") is True
        assert (target / "dev-os-0" / "tee" / "tee.log").read_text(
            encoding="utf-8"
        ) == "old"
        assert (target / "dev-os-0" / "tee" / "tee__typed_export.log").read_text(
            encoding="utf-8"
        ) == "new"
        assert not (source / "dev-os-0" / "tee" / "tee.log").exists()

    def test_merge_dir_conflict_without_tag_uses_default_suffix(self, tmp_path):
        # Without an explicit tag the suffixed copy still lands next to the
        # target, so the data survives regardless of the caller.
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        target.mkdir()
        (source / "a.log").write_text("new", encoding="utf-8")
        (target / "a.log").write_text("old", encoding="utf-8")

        assert merge_dir(str(source), str(target)) is True
        assert (target / "a.log").read_text(encoding="utf-8") == "old"
        assert (target / "a__conflict.log").read_text(encoding="utf-8") == "new"

    def test_merge_dir_repeated_conflicts_keep_every_copy(self, tmp_path):
        # fujun19 复现：同一目标目录连续多次同名不同内容冲突（-t 7/-t 8/-t 9
        # 都归档到 ao_info 时可能发生），后缀名不能重复，否则 os.replace 覆盖
        # 上一次保留的副本。已占用的后缀名追加 __2、__3 序号，每份都保留。
        target = tmp_path / "target"
        target.mkdir()
        (target / "a.log").write_text("full", encoding="utf-8")

        for round_no, content in enumerate(["typed-1st", "typed-2nd", "typed-3rd"], 1):
            source = tmp_path / f"round_{round_no}"
            source.mkdir()
            (source / "a.log").write_text(content, encoding="utf-8")
            assert merge_dir(str(source), str(target), "typed_export") is True
            assert not source.exists()

        contents = {
            path.name: path.read_text(encoding="utf-8") for path in target.iterdir()
        }
        assert contents == {
            "a.log": "full",
            "a__typed_export.log": "typed-1st",
            "a__typed_export__2.log": "typed-2nd",
            "a__typed_export__3.log": "typed-3rd",
        }

    def test_merge_dir_long_name_conflict_truncates_to_name_max(self, tmp_path):
        # fujun19 复现：主名接近 NAME_MAX 的同名冲突文件，加 __typed_export
        # 后缀会超出文件系统单名上限（ext4/xfs 255 字节），os.replace 报
        # Errno 36，源副本滞留临时目录随后被清理删除。基名必须截断到后缀名
        # 仍合法，数据才能保住；截断后的后缀名也绝不能塌回目标名本身。
        from collect.msnpureport_type_collect import _CONFLICT_NAME_MAX

        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        target.mkdir()
        # base + ext 刚好顶满 NAME_MAX，再加 __typed_export 必然超限
        long_name = "x" * (_CONFLICT_NAME_MAX - len(".log")) + ".log"
        (source / long_name).write_text("typed", encoding="utf-8")
        (target / long_name).write_text("full", encoding="utf-8")

        assert merge_dir(str(source), str(target), "typed_export") is True
        assert not source.exists()
        target_names = os.listdir(target)
        assert len(target_names) == 2
        assert long_name in target_names
        for name in target_names:
            content = (target / name).read_text(encoding="utf-8")
            if name == long_name:
                assert content == "full"
            else:
                assert name.endswith("__typed_export.log")
                assert len(name.encode("utf-8")) <= _CONFLICT_NAME_MAX
                assert content == "typed"

    def test_merge_dir_long_name_repeated_conflict_stays_within_name_max(
        self, tmp_path
    ):
        # 组合场景：接近 NAME_MAX 的文件名连续冲突两次——既要每份都保留
        # （序号后缀），又要每个后缀名都截断到 NAME_MAX 以内。
        from collect.msnpureport_type_collect import _CONFLICT_NAME_MAX

        target = tmp_path / "target"
        target.mkdir()
        long_name = "x" * (_CONFLICT_NAME_MAX - len(".log")) + ".log"
        (target / long_name).write_text("full", encoding="utf-8")

        for round_no, content in enumerate(["typed-1st", "typed-2nd"], 1):
            source = tmp_path / f"round_{round_no}"
            source.mkdir()
            (source / long_name).write_text(content, encoding="utf-8")
            assert merge_dir(str(source), str(target), "typed_export") is True
            assert not source.exists()

        target_names = os.listdir(target)
        assert len(target_names) == 3
        contents = {
            name: (target / name).read_text(encoding="utf-8") for name in target_names
        }
        assert contents[long_name] == "full"
        for name in target_names:
            assert len(name.encode("utf-8")) <= _CONFLICT_NAME_MAX
        assert sorted(contents[name] for name in target_names if name != long_name) == [
            "typed-1st",
            "typed-2nd",
        ]

    def test_merge_dir_overlong_extension_conflict_keeps_both(self, tmp_path):
        # fujun19 复现：主名 a + 250 字符扩展名（原名 251 字节，磁盘合法），
        # 加 __typed_export 后缀后超 NAME_MAX。基名截空仍超限时，截扩展名会让
        # 同一冲突序列的候选名互相撞名（区分字符被切掉）甚至死循环，因此超长
        # 扩展名整体替换为 .conf，再按预算截基名：两份数据都保留、名字合法
        # 且可区分。
        from collect.msnpureport_type_collect import _CONFLICT_NAME_MAX

        source = tmp_path / "source"
        target = tmp_path / "target"
        source.mkdir()
        target.mkdir()
        overlong_ext = "." + "e" * 249
        name = "a" + overlong_ext
        (source / name).write_text("typed", encoding="utf-8")
        (target / name).write_text("full", encoding="utf-8")

        assert merge_dir(str(source), str(target), "typed_export") is True
        assert not source.exists()
        target_names = os.listdir(target)
        assert len(target_names) == 2
        assert name in target_names
        assert (target / name).read_text(encoding="utf-8") == "full"
        for kept in target_names:
            assert len(kept.encode("utf-8")) <= _CONFLICT_NAME_MAX
        suffixed = [n for n in target_names if n != name][0]
        assert suffixed == "a__typed_export.conf"
        assert (target / suffixed).read_text(encoding="utf-8") == "typed"

    def test_merge_dir_overlong_extension_repeated_conflict_keeps_all(self, tmp_path):
        # 超长扩展名 + 连续两次冲突：序号候选必须仍可区分，不能撞名死循环。
        from collect.msnpureport_type_collect import _CONFLICT_NAME_MAX

        target = tmp_path / "target"
        target.mkdir()
        overlong_ext = "." + "e" * 249
        name = "a" + overlong_ext
        (target / name).write_text("full", encoding="utf-8")

        for round_no, content in enumerate(["typed-1st", "typed-2nd"], 1):
            source = tmp_path / f"round_{round_no}"
            source.mkdir()
            (source / name).write_text(content, encoding="utf-8")
            assert merge_dir(str(source), str(target), "typed_export") is True
            assert not source.exists()

        target_names = os.listdir(target)
        assert len(target_names) == 3
        contents = {n: (target / n).read_text(encoding="utf-8") for n in target_names}
        assert contents[name] == "full"
        for n in target_names:
            assert len(n.encode("utf-8")) <= _CONFLICT_NAME_MAX
        assert sorted(c for n, c in contents.items() if n != name) == [
            "typed-1st",
            "typed-2nd",
        ]
        assert len({n for n in target_names if n != name}) == 2

    def test_merge_dir_reports_target_file_conflict_without_overwrite(
        self, tmp_path, caplog
    ):
        # Different content under the same name: the target is never
        # overwritten, both copies survive, and the divergence is a warning.
        source = tmp_path / "source"
        target = tmp_path / "target"
        (source / "dev-os-0").mkdir(parents=True)
        (target / "dev-os-0").mkdir(parents=True)
        (source / "dev-os-0" / "ao_self.log").write_text("new", encoding="utf-8")
        (target / "dev-os-0" / "ao_self.log").write_text("old", encoding="utf-8")

        assert merge_dir(str(source), str(target)) is True
        assert (target / "dev-os-0" / "ao_self.log").read_text(
            encoding="utf-8"
        ) == "old"
        assert (target / "dev-os-0" / "ao_self__conflict.log").read_text(
            encoding="utf-8"
        ) == "new"
        assert (
            "The merge target file already exists with different content" in caplog.text
        )

    def test_full_chain_conflicting_system_info_keeps_both(self, mocker, tmp_path):
        # fujun19 复现的整链场景：-f 与 -t 5 都导出 system_info/dev-os-0/tee/tee.log
        # 且内容不同。collect_msnpureport_type_info 必须返回 True（不再把冲突
        # 误报为类型化采集失败），且 dfx/system_info 下两份数据都在：
        # 先归档的 full_export 版本保留原名，typed_export 版本改名为
        # <名称>__typed_export.<扩展名> 保留。
        from collect.msnpureport_type_collect import collect_msnpureport_type_info

        mocker.patch("params.ParamDict.get_env_type", return_value="EP")
        mocker.patch("common.DeviceInfo.get_device_count", return_value=1)
        mocker.patch("common.DeviceInfo.get_chip_info", return_value="Ascend950")
        mocker.patch(
            "collect.msnpureport_type_collect.parse_ub_in_place", return_value=True
        )

        # -f 先归档的 system_info（collect_device_logs 阶段已进入 dfx）
        dfx_system_info = tmp_path / "dfx" / "system_info" / "dev-os-0" / "tee"
        dfx_system_info.mkdir(parents=True)
        (dfx_system_info / "tee.log").write_text("full-export", encoding="utf-8")

        # typed -t 5 导出目录里的同名不同内容文件
        def fake_run_cmd_output(command, timeout=None, **_kwargs):  # noqa: ARG001
            if "report -t 5" in command:
                type_dir = command.split(";")[0].split("cd ")[-1].strip("'")
                out = os.path.join(type_dir, "20261117000000")
                tee = os.path.join(out, "system_info", "dev-os-0", "tee")
                os.makedirs(tee, exist_ok=True)
                with open(os.path.join(tee, "tee.log"), "w", encoding="utf-8") as fw:
                    fw.write("typed-export")
            return True, ""

        mocker.patch(
            "collect.msnpureport_type_collect.run_cmd_output",
            side_effect=fake_run_cmd_output,
        )

        assert collect_msnpureport_type_info(str(tmp_path)) is True
        merged = tmp_path / "dfx" / "system_info" / "dev-os-0" / "tee"
        assert (merged / "tee.log").read_text(encoding="utf-8") == "full-export"
        assert (merged / "tee__typed_export.log").read_text(
            encoding="utf-8"
        ) == "typed-export"
        assert not os.path.exists(tmp_path / "export_type_tmp")

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
