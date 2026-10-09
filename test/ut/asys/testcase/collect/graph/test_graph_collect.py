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

import pytest
import os

from testcase.conftest import ut_root_path

from collect.graph import collect_graph
from params import ParamDict
from common import FileOperate
from common import consts
from testcase.conftest import AssertTest


@pytest.mark.parametrize(
    "file_name,category",
    [
        ("ge_proto_00292_Build.txt", "ge"),
        ("ge_onnx_00292_Build.pbtxt", "ge"),
        ("TF_GeOp_00292_Build.pbtxt", "tf"),
    ],
)
def test_graph_files_keep_process_device_directories(tmp_path, file_name, category):
    from collect.graph.graph_collect import collect_graph_files

    source = tmp_path / "graphs"
    target = tmp_path / "collected"
    for device in (0, 1):
        directory = source / f"pid_53343_deviceid_{device}"
        directory.mkdir(parents=True)
        (directory / file_name).write_bytes(f"device{device}_graph".encode("ascii"))

    assert collect_graph_files(str(source), str(target))
    assert {graph.read_bytes() for graph in target.rglob(file_name)} == {
        b"device0_graph",
        b"device1_graph",
    }
    for device in (0, 1):
        relative = f"pid_53343_deviceid_{device}/{file_name}"
        expected = f"device{device}_graph".encode("ascii")
        assert (target / category / relative).read_bytes() == expected
        assert (source / relative).read_bytes() == expected


def test_graph_files_keep_flat_source_layout(tmp_path):
    from collect.graph.graph_collect import collect_graph_files

    source = tmp_path / "graphs"
    source.mkdir()
    graph = source / "ge_proto_00292_Build.txt"
    graph.write_bytes(b"single_process_graph")
    target = tmp_path / "collected"

    assert collect_graph_files(str(source), str(target))
    assert (target / "ge" / graph.name).read_bytes() == graph.read_bytes()


def test_collect_graph_keeps_multiple_device_dumps(tmp_path, monkeypatch):
    import sys

    from cmdline import CommandLineParser
    from common import RetCode

    for device in (0, 1):
        directory = tmp_path / "graphs" / f"pid_53343_deviceid_{device}"
        directory.mkdir(parents=True)
        (directory / "ge_proto_00292_Build.txt").write_bytes(
            f"device{device}_graph".encode("ascii")
        )
    # Isolate the shared command state while using the real CLI parser and files.
    params = ParamDict()
    monkeypatch.setattr(params, "_ParamDict__args", {})
    monkeypatch.setattr(params, "_ParamDict__command", None)
    monkeypatch.setattr(params, "_ParamDict__env_type", "EP")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["asys", "collect", "--task_dir", "graphs"])
    assert CommandLineParser().parse() == RetCode.SUCCESS

    collect_graph("output")

    assert {
        graph.read_bytes() for graph in (tmp_path / "output").rglob("ge_proto*.txt")
    } == {b"device0_graph", b"device1_graph"}
    for device in (0, 1):
        graph = (
            tmp_path
            / "output/dfx/graph/ge"
            / f"pid_53343_deviceid_{device}"
            / "ge_proto_00292_Build.txt"
        )
        assert graph.read_bytes() == f"device{device}_graph".encode("ascii")


def setup_module():
    print("TestGraphCollect ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestGraphCollect ut test finish.")  # noqa: T201  # test diagnostic output


class TestGraphCollect(AssertTest):
    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_graph_collect_success(self, mocker):
        os.environ["DUMP_GRAPH_PATH"] = "./graph"
        ret = [
            (
                "dir",
                ["subdir"],
                ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"],
            ),
            (
                "dir/subdir",
                [],
                ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"],
            ),
        ]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_graph("./output") is None)

        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="bash ./test.bash")
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        ParamDict.asys_output_timestamp_dir = ut_root_path
        self.assertTrue(collect_graph("./output") is None)
        if os.getenv("DUMP_GRAPH_PATH"):
            os.environ.pop("DUMP_GRAPH_PATH")

    @pytest.mark.parametrize("task", [consts.collect_cmd, consts.launch_cmd])
    def test_collect_graph_no_exec(self, mocker, task):
        ret = [
            (
                "dir",
                ["subdir"],
                ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"],
            ),
            (
                "dir/subdir",
                [],
                ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"],
            ),
        ]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=task)
        mocker.patch("params.ParamDict.get_ini", return_value="0")
        mocker.patch("params.ParamDict.get_arg", return_value=False)
        mocker.patch("os.path.join", return_value=ut_root_path)
        self.assertTrue(collect_graph("./output") is None)
        if task == consts.launch_cmd:
            os.path.join.assert_not_called()
        else:
            os.path.join.assert_called()

    def test_collect_task_graph_collect_copy_failed(self, mocker, caplog):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("params.ParamDict.get_arg", return_value=ut_root_path)
        ret = [
            (
                "dir",
                ["subdir"],
                ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"],
            ),
            (
                "dir/subdir",
                [],
                ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"],
            ),
        ]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=False)
        self.assertTrue(collect_graph("./output") is None)

    def test_launch_task__graph_collect_get_none_source_dir(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        mocker.patch("common.FileOperate.copy_dir")
        ParamDict.asys_output_timestamp_dir = ut_root_path
        self.assertTrue(collect_graph("./output") is None)
        FileOperate.copy_dir.assert_not_called()

    def test_graph_collect_success_from_npu_path(self, mocker):
        os.environ["NPU_COLLECT_PATH"] = "./graph"
        ret = [
            (
                "dir",
                ["subdir"],
                ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"],
            ),
            (
                "dir/subdir",
                [],
                ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"],
            ),
        ]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_graph("./output") is None)
        if os.getenv("NPU_COLLECT_PATH"):
            os.environ.pop("NPU_COLLECT_PATH")

    def test_graph_collect_success_from_work_path(self, mocker):
        os.environ["ASCEND_WORK_PATH"] = "./graph"
        ret = [
            (
                "dir",
                ["subdir"],
                ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"],
            ),
            (
                "dir/subdir",
                [],
                ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"],
            ),
        ]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_graph("./output") is None)
        if os.getenv("ASCEND_WORK_PATH"):
            os.environ.pop("ASCEND_WORK_PATH")
