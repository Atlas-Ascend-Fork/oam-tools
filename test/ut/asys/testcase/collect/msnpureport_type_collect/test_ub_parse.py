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
import struct

from collect.msnpureport_type_collect.ub_parse import parse_ub_in_place


class TestUbParse:
    def setup_method(self):
        self.root = os.path.join(os.path.dirname(__file__), "ub_parse_tmp")
        if os.path.exists(self.root):
            shutil.rmtree(self.root)
        self.ub_info = os.path.join(self.root, "ub_info")

    def teardown_method(self):
        if os.path.exists(self.root):
            shutil.rmtree(self.root)

    def test_parse_ub_in_place_removes_bin_after_txt_is_created(self):
        mami = os.path.join(self.ub_info, "dev-os-0", "mami")
        os.makedirs(mami)
        with open(os.path.join(mami, "ubmem_daw.bin"), "wb") as fw:
            fw.write(struct.pack("4B", 1, 2, 3, 4))

        assert parse_ub_in_place(self.ub_info) is True
        assert os.path.isfile(os.path.join(mami, "ubmem_daw.txt"))
        assert not os.path.exists(os.path.join(mami, "ubmem_daw.bin"))

    def test_parse_ub_in_place_keeps_bin_when_parse_fails(self):
        mami = os.path.join(self.ub_info, "dev-os-0", "mami")
        os.makedirs(mami)
        with open(os.path.join(mami, "ubmem_daw.bin"), "wb") as fw:
            fw.write(b"ab")

        assert parse_ub_in_place(self.ub_info) is True
        assert os.path.isfile(os.path.join(mami, "ubmem_daw.bin"))
        assert not os.path.exists(os.path.join(mami, "ubmem_daw.txt"))

    def test_unknown_file_name_is_skipped_not_raised(self):
        # A name without a matching converter must be skipped (warning) instead
        # of raising KeyError through collect(), regression guard for the
        # globals() dispatch hardening.
        from collect.msnpureport_type_collect.ub_parse import _convert_ub_file

        os.makedirs(self.root, exist_ok=True)
        bin_path = os.path.join(self.root, "unknown.bin")
        with open(bin_path, "wb") as fw:
            fw.write(b"ab")
        assert _convert_ub_file(bin_path, bin_path + ".txt", "unknown_type") is False
        assert (
            _convert_ub_file(bin_path, bin_path + ".txt", "ubnl_dfx_unknown") is False
        )
        assert not os.path.exists(bin_path + ".txt")

    def test_parse_ub_in_place_missing_dir(self):
        assert parse_ub_in_place(os.path.join(self.root, "missing")) is False

    def test_parse_ub_in_place_handles_multiple_devices(self):
        for device_id in range(2):
            mami = os.path.join(self.ub_info, f"dev-os-{device_id}", "mami")
            os.makedirs(mami)
            with open(os.path.join(mami, "ubmem_daw.bin"), "wb") as fw:
                fw.write(struct.pack("4B", device_id, 2, 3, 4))

        assert parse_ub_in_place(self.ub_info) is True
        for device_id in range(2):
            mami = os.path.join(self.ub_info, f"dev-os-{device_id}", "mami")
            assert not os.path.exists(os.path.join(mami, "ubmem_daw.bin"))
            assert os.path.isfile(os.path.join(mami, "ubmem_daw.txt"))
