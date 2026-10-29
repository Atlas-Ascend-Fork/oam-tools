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

import sys

import pytest

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)


class TestGoldenOpMethods(CommonAssert):
    def test_get_block_dim_uses_vector_core_count(self, mocker):
        mock_dsmi = mocker.patch("ms_interface.golden_op.DSMIInterface")
        mock_instance = mock_dsmi.return_value
        mock_instance.get_vector_core_count.return_value = 8
        mock_instance.get_aicore_count.return_value = 16

        from ms_interface.golden_op import GoldenOp

        result = GoldenOp.get_block_dim(0)
        self.assertEqual(result, 8)
        mock_instance.get_vector_core_count.assert_called_once_with(0)

    def test_get_block_dim_fallback_to_aicore_count(self, mocker):
        mock_dsmi = mocker.patch("ms_interface.golden_op.DSMIInterface")
        mock_instance = mock_dsmi.return_value
        mock_instance.get_vector_core_count.return_value = 0
        mock_instance.get_aicore_count.return_value = 24

        from ms_interface.golden_op import GoldenOp

        result = GoldenOp.get_block_dim(0)
        self.assertEqual(result, 24)
        mock_instance.get_aicore_count.assert_called_once_with(0)

    @pytest.mark.skip
    @staticmethod
    def test_run_golden_op_success(mocker, tmp_path):
        mocker.patch(
            "ms_interface.golden_op.get_compile_file",
            return_value=(str(tmp_path / "test.o"), str(tmp_path / "test.json")),
        )
        mocker.patch("ms_interface.golden_op.DSMIInterface")
        mocker.patch("ms_interface.golden_op.AscendOpKernel")
        mock_runner = mocker.patch("ms_interface.golden_op.AscendOpKernelRunner")
        mock_instance = mock_runner.return_value.__enter__.return_value
        mock_instance.run.return_value = "success"

        from ms_interface.golden_op import GoldenOp

        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, str(tmp_path))
        assert result

    @pytest.mark.skip
    @staticmethod
    def test_run_golden_op_no_build_result(mocker, tmp_path):
        mocker.patch("ms_interface.golden_op.get_compile_file", return_value=[])

        from ms_interface.golden_op import GoldenOp

        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, str(tmp_path))
        assert not result

    @pytest.mark.skip
    @staticmethod
    def test_run_golden_op_execute_failed(mocker, tmp_path):
        mocker.patch(
            "ms_interface.golden_op.get_compile_file",
            return_value=(str(tmp_path / "test.o"), str(tmp_path / "test.json")),
        )
        mocker.patch("ms_interface.golden_op.DSMIInterface")
        mocker.patch("ms_interface.golden_op.AscendOpKernel")
        mock_runner = mocker.patch("ms_interface.golden_op.AscendOpKernelRunner")
        mock_instance = mock_runner.return_value.__enter__.return_value
        mock_instance.run.return_value = "Execute single op case failed: error"

        from ms_interface.golden_op import GoldenOp

        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, str(tmp_path))
        assert not result

    @pytest.mark.skip
    @staticmethod
    def test_main_entry_success(mocker, tmp_path):
        mocker.patch(
            "ms_interface.golden_op.get_compile_file",
            return_value=(str(tmp_path / "test.o"), str(tmp_path / "test.json")),
        )
        mocker.patch("ms_interface.golden_op.DSMIInterface")
        mocker.patch("ms_interface.golden_op.AscendOpKernel")
        mock_runner = mocker.patch("ms_interface.golden_op.AscendOpKernelRunner")
        mock_instance = mock_runner.return_value.__enter__.return_value
        mock_instance.run.return_value = "success"
        mocker.patch("sys.argv", ["golden_op.py", "Ascend910B1", "0", str(tmp_path)])

        from ms_interface.golden_op import GoldenOp

        # just test run_golden_op directly since __main__ block runs at import
        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, str(tmp_path))
        assert result

    def test_get_block_dim_static_method(self):
        from ms_interface.golden_op import GoldenOp

        assert callable(GoldenOp.get_block_dim)


@pytest.fixture
def golden_runner_setup(mocker, tmp_path):
    """Real metadata parser and runner; binary registration is outside this CPU test."""
    import json
    from unittest.mock import Mock
    from ms_interface import golden_op
    from ms_interface.single_op_test_frame.common.ascend_tbe_op import (
        AscendOpKernelRunner,
    )

    binary = tmp_path / "golden.o"
    binary.write_bytes(b"device registration boundary is replaced")
    metadata = tmp_path / "golden.json"
    metadata.write_text(
        json.dumps(
            {
                "blockDim": 8,
                "kernelName": "golden",
                "magic": "RT_DEV_BINARY_MAGIC_ELF",
                "parameters": [],
                "workspace": {"size": []},
            }
        ),
        encoding="utf-8",
    )
    mocker.patch.object(
        golden_op, "get_compile_file", return_value=(str(binary), str(metadata))
    )
    mocker.patch.object(golden_op.GoldenOp, "get_block_dim", return_value=8)
    device = Mock()
    mocker.patch.object(AscendOpKernelRunner, "get_rts_api", return_value=device)
    return golden_op, AscendOpKernelRunner, device, tmp_path


@pytest.mark.parametrize(
    "launch_ret,sync_ret,expected", [(7, 0, False), (0, 7, False), (0, 0, True)]
)
def test_golden_op_uses_actual_runner_report(
    mocker, golden_runner_setup, launch_ret, sync_ret, expected
):
    golden_op, runner_type, device, directory = golden_runner_setup
    mocker.patch.object(
        runner_type, "exec_single_case", return_value=([], [launch_ret, sync_ret, 0])
    )
    assert (
        golden_op.GoldenOp().run_golden_op("Ascend910B1", 0, str(directory)) is expected
    )
    device.destroy_stream.assert_called_once()
    device.reset.assert_called_once_with(0)


def test_golden_op_keeps_actual_runner_exception_failure(mocker, golden_runner_setup):
    golden_op, runner_type, _, directory = golden_runner_setup
    mocker.patch.object(
        runner_type, "exec_single_case", side_effect=OSError("launch unavailable")
    )
    assert golden_op.GoldenOp().run_golden_op("Ascend910B1", 0, str(directory)) is False


@pytest.mark.parametrize("launch_ret,sync_ret", [(7, 0), (0, 7), (0, 0)])
def test_actual_runner_report_uses_shared_failure_constants(
    mocker, golden_runner_setup, launch_ret, sync_ret
):
    golden_op, runner_type, _, directory = golden_runner_setup
    from ms_interface.constant import NOT_RUN_EXEC_FAILED, NOT_RUN_LAUNCH_FAILED

    assert NOT_RUN_EXEC_FAILED == "Execute single op case failed"
    mocker.patch.object(
        runner_type, "exec_single_case", return_value=([], [launch_ret, sync_ret, 0])
    )
    kernel = golden_op.AscendOpKernel(
        str(directory / "golden.o"), str(directory / "golden.json")
    )
    parameter = golden_op.AscendOpKernelRunnerParam(kernel=kernel)
    with runner_type(device_id=0) as runner:
        report = runner.run(parameter)
    assert isinstance(report, str)
    assert (NOT_RUN_LAUNCH_FAILED in report) is bool(launch_ret or sync_ret)
    assert NOT_RUN_EXEC_FAILED not in report


def test_actual_runner_exception_uses_legacy_failure_constant(
    mocker, golden_runner_setup
):
    golden_op, runner_type, _, directory = golden_runner_setup
    from ms_interface.constant import NOT_RUN_EXEC_FAILED

    mocker.patch.object(
        runner_type, "exec_single_case", side_effect=OSError("launch unavailable")
    )
    kernel = golden_op.AscendOpKernel(
        str(directory / "golden.o"), str(directory / "golden.json")
    )
    parameter = golden_op.AscendOpKernelRunnerParam(kernel=kernel)
    with runner_type(device_id=0) as runner:
        assert NOT_RUN_EXEC_FAILED in runner.run(parameter)


@pytest.mark.parametrize("report", [None, "", 0])
def test_golden_op_rejects_invalid_runner_report(mocker, golden_runner_setup, report):
    golden_op, runner_type, device, directory = golden_runner_setup
    mocker.patch.object(runner_type, "run", return_value=report)
    assert golden_op.GoldenOp().run_golden_op("Ascend910B1", 0, str(directory)) is False
    device.destroy_stream.assert_called_once()
