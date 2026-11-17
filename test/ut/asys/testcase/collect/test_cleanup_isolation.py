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

import logging
import os
from contextlib import contextmanager

import collect.trace.trace_collect as trace_collect
from collect.trace.trace_collect import ParseTrace
from testcase.conftest import AssertTest

# Bound before the test patches trace_collect.os, so the stub can delegate to
# the real remove without recursing into the patch.
_REAL_REMOVE = os.remove


class _Recorder(logging.Handler):
    """Collects the messages the root logger emits."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


@contextmanager
def _warnings():
    """Capture the WARNING records the root logger emits.

    close_log() disables the WARNING level globally, so "the warning was
    never emitted" would look exactly like "the warning was emitted and
    then swallowed". Reset the level for the duration of the capture and
    restore the previous state afterwards.
    """
    manager = logging.getLogger().manager
    previous = manager.disable
    manager.disable = logging.NOTSET
    recorder = _Recorder()
    root = logging.getLogger()
    root.addHandler(recorder)
    try:
        yield recorder
    finally:
        root.removeHandler(recorder)
        manager.disable = previous


class TestCleanupIsolation(AssertTest):
    @staticmethod
    def _record_into(written):
        def _write(_msg, path):
            written.append(path)

        return _write

    def test_failed_remove_still_counts_as_parsed(self, tmp_path, mocker):
        # The result .txt was already written, so failing on the delete would
        # fail the whole command on the single-file path (asys analyze -r
        # trace --file hands this return value to the CLI). The batch path is
        # not affected either way: run() gives every .bin its own daemon
        # thread.
        parser = ParseTrace(is_file=True)
        parser.parse = lambda _path: "parsed"  # noqa: E731  # test stub
        parser.write_res_txt = lambda _msg, _path: None  # noqa: E731  # test stub
        target = str(tmp_path / "gone.bin")

        # A permission error, not just a missing file: the cleanup can fail
        # for reasons that have nothing to do with the file being absent.
        mocker.patch.object(
            trace_collect.os,
            "remove",
            side_effect=PermissionError(13, "Permission denied"),
        )

        with _warnings() as recorder:
            self.assertTrue(parser.start_parse_file(target) is True)

        # The failure has to be reported, not swallowed: the .bin is still on
        # disk and the user has to learn why.
        self.assertTrue(any(target in msg for msg in recorder.records))

    def test_batch_keeps_parsing_after_a_failed_remove(self, tmp_path, mocker):
        # The batch path never dropped a trace: run() gives every .bin its own
        # daemon thread, so a failing os.remove only leaves a traceback inside
        # that thread. Pin that here so the single-file guard is not credited
        # with a batch-wide effect it never had (#341).
        atrace = tmp_path / "dfx" / "atrace"
        atrace.mkdir(parents=True)
        for i in range(3):
            (atrace / f"trace{i}.bin").write_bytes(b"dummy")

        # A fixed target pins the failure to trace1.bin: a shared counter
        # would race across the three daemon threads and could let every
        # call succeed, turning the case into the happy path.
        def flaky_remove(path):
            if os.path.basename(path) == "trace1.bin":
                raise FileNotFoundError(2, "No such file or directory", path)
            return _REAL_REMOVE(path)

        mocker.patch.object(trace_collect.os, "remove", side_effect=flaky_remove)
        mocker.patch.object(
            trace_collect.f,
            "walk_dir",
            return_value=[
                (str(atrace), [], ["trace0.bin", "trace1.bin", "trace2.bin"])
            ],
        )
        # run() builds a fresh ParseTrace per .bin file, so the stubs have to
        # live on the class, not on the outer instance. write_res_txt is a
        # staticmethod called as self.write_res_txt(msg, path).
        written = []
        mocker.patch.object(ParseTrace, "parse", lambda self, _path: "parsed")
        mocker.patch.object(
            ParseTrace,
            "write_res_txt",
            staticmethod(self._record_into(written)),
        )

        self.assertTrue(ParseTrace(is_file=True).run(str(atrace)) is True)
        self.assertTrue(len(written) == 3)
        # The failure must actually have been injected, otherwise the case
        # proves nothing about the failing path.
        self.assertTrue(trace_collect.os.remove.call_count == 3)

    def test_unremovable_output_dir_does_not_fail_compression(self, tmp_path, mocker):
        import shutil

        import common.compress_output_dir as compress

        out_dir = tmp_path / "asys_output_x"
        out_dir.mkdir()
        (out_dir / "a.txt").write_text("x", encoding="utf-8")

        class _Params:
            asys_output_timestamp_dir = str(out_dir)

        mocker.patch.object(compress, "ParamDict", _Params)
        mocker.patch.object(shutil, "rmtree", side_effect=PermissionError(13, "denied"))

        with _warnings() as recorder:
            compress.compress_output_dir_tar()

        archive = tmp_path / "asys_output_x.tar.gz"
        self.assertTrue(archive.exists())  # the archive must still be produced
        # The archive is complete but the source directory is still there, so
        # the user has to be told about it.
        self.assertTrue(any(str(out_dir) in msg for msg in recorder.records))

    def test_successful_compression_still_removes_the_dir(self, tmp_path, mocker):
        import common.compress_output_dir as compress

        out_dir = tmp_path / "asys_output_x"
        out_dir.mkdir()
        (out_dir / "a.txt").write_text("x", encoding="utf-8")

        class _Params:
            asys_output_timestamp_dir = str(out_dir)

        mocker.patch.object(compress, "ParamDict", _Params)

        compress.compress_output_dir_tar()

        self.assertTrue((tmp_path / "asys_output_x.tar.gz").exists())
        self.assertTrue(not out_dir.exists())

    def test_missing_output_dir_compresses_nothing(self, tmp_path, mocker):
        import common.compress_output_dir as compress

        class _Params:
            asys_output_timestamp_dir = str(tmp_path / "not-there")

        mocker.patch.object(compress, "ParamDict", _Params)

        # Must not raise and must not create an archive.
        compress.compress_output_dir_tar()
        self.assertTrue(list(tmp_path.iterdir()) == [])

    def test_no_warning_when_remove_succeeds(self, tmp_path, mocker):
        # The guard added for #341/#342 must not warn on the happy path.
        bin_file = tmp_path / "trace.bin"
        bin_file.write_bytes(b"dummy")
        parser = ParseTrace(is_file=True)
        parser.parse = lambda _path: "parsed"  # noqa: E731  # test stub
        parser.write_res_txt = lambda _msg, _path: None  # noqa: E731  # test stub

        with _warnings() as recorder:
            self.assertTrue(parser.start_parse_file(str(bin_file)) is True)

        self.assertTrue(recorder.records == [])
        self.assertTrue(not bin_file.exists())
