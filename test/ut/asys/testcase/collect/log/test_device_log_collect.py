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


import os

from testcase.conftest import AssertTest

from collect.log import collect_device_logs


def setup_module():
    print("TestDeviceLogCollect ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestDeviceLogCollect ut test finish.")  # noqa: T201  # test diagnostic output


class TestDeviceLogCollect(AssertTest):
    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_device_log_collect_success(self, mocker):
        mocker.patch(
            "collect.log.device_log_collect.collect_host_driver", return_value=True
        )
        mocker.patch(
            "collect.log.device_log_collect.collect_system_info", return_value=True
        )
        mocker.patch(
            "common.FileOperate.list_dir", return_value=["dev-os-3", "dev-os-7"]
        )
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        self.assertTrue(collect_device_logs("./", "./output"))

        mocker.patch("common.FileOperate.list_dir", return_value=["dev-os-0"])
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        self.assertTrue(collect_device_logs("./", "./output"))

    def test_device_log_collect_failed(self, mocker):
        mocker.patch(
            "common.FileOperate.list_dir", return_value=["dev-os-0", "device-os"]
        )
        mocker.patch("common.FileOperate.collect_dir", return_value=False)
        self.assertTrue(not collect_device_logs("./", "./output"))

    def test_collect_device_firmware_skips_app_and_os_dirs(self, mocker):
        # The firmware feature is "device-": with a plain startswith it also
        # captured device-app/device-os and archived them twice (once here,
        # once in their own collect_* pass).
        from collect.log.device_log_collect import collect_device

        collected = []

        def fake_collect_dir(source, target, _mode):
            collected.append((source, target))
            return True

        def fake_list_dir(path):
            if path.endswith(os.path.join("dev-os-0", "debug")):
                return ["device-0", "device-app-140561", "device-os"]
            if path.endswith("slog"):
                return ["dev-os-0"]
            return []

        mocker.patch("common.FileOperate.list_dir", side_effect=fake_list_dir)
        mocker.patch("common.FileOperate.collect_dir", side_effect=fake_collect_dir)
        self.assertTrue(collect_device("./", "./output", ["debug"], "device-"))

        firmware_sources = [s for s, _t in collected]
        self.assertTrue(
            os.path.join(".", "slog", "dev-os-0", "debug", "device-0")
            in firmware_sources
        )
        self.assertTrue(
            all(
                "device-app" not in s and "device-os" not in s for s in firmware_sources
            )
        )

    def test__device_log_collect_host_driver(self, mocker):
        mocker.patch("collect.log.device_log_collect.collect_slogd", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        mocker.patch("common.FileOperate.remove_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(not collect_device_logs("./", "./output"))

        mocker.patch("common.FileOperate.list_dir", return_value=["host"])
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=False)
        self.assertTrue(not collect_device_logs("./", "./output"))

        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        mocker.patch(
            "collect.log.device_log_collect.collect_system_info", return_value=True
        )
        self.assertTrue(collect_device_logs("./", "./output"))

    def test_collect_slogd_failed(self, mocker, caplog):
        mocker.patch(
            "collect.log.device_log_collect.collect_messages", return_value=True
        )
        mocker.patch(
            "collect.log.device_log_collect.collect_stackcore", return_value=True
        )
        mocker.patch("collect.log.device_log_collect.collect_bbox", return_value=True)
        mocker.patch(
            "collect.log.device_log_collect.collect_host_driver", return_value=True
        )
        mocker.patch(
            "collect.log.device_log_collect.collect_system_info", return_value=True
        )
        mocker.patch(
            "common.FileOperate.list_dir", return_value=["dev-os-0", "device-os"]
        )
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=False)
        self.assertTrue(not collect_device_logs("./", "./output"))

    def test_collect_system_info_merges_with_existing_typed_output(self, tmp_path):
        # One export archives system_info first (event/); the other one
        # later merges its own system_info (tee/) into the same dfx directory.
        # Both sub-directories must coexist after both archivals, regardless
        # of which export produced which sub-directory.
        from collect.log.device_log_collect import collect_system_info

        source = tmp_path / "full_export" / "system_info" / "dev-os-0" / "event"
        source.mkdir(parents=True)
        (source / "event.log").write_text("event", encoding="utf-8")
        output_root = tmp_path / "asys_output"
        typed = output_root / "dfx" / "system_info" / "dev-os-0" / "tee"
        typed.mkdir(parents=True)
        (typed / "tee.log").write_text("tee", encoding="utf-8")

        self.assertTrue(
            collect_system_info(str(tmp_path / "full_export"), str(output_root))
        )
        merged = output_root / "dfx" / "system_info" / "dev-os-0"
        self.assertTrue((merged / "event" / "event.log").is_file())
        self.assertTrue((merged / "tee" / "tee.log").is_file())

    def test_collect_system_info_missing_dir(self, tmp_path):
        from collect.log.device_log_collect import collect_system_info

        self.assertTrue(not collect_system_info(str(tmp_path), str(tmp_path / "out")))
