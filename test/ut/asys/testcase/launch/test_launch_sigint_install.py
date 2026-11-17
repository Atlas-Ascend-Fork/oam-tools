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

import signal

import pytest

import common  # noqa: F401  # imported first to break the params <-> common cycle
import launch.asys_launch as mod
from launch.asys_launch import AsysLaunch
from testcase.conftest import AssertTest


class _Params:
    def set_task_pid(self, pid=0):
        self.pid = pid


class _Process:
    pid = 4321
    returncode = 0

    def __init__(self, seen):
        self._seen = seen
        self.terminated = False
        self.killed = False
        self.waited = []

    def communicate(self):
        # Snapshot the handler state while the child is supposed to be running.
        self._seen.append(signal.getsignal(signal.SIGINT))
        return "done", 0

    def poll(self):
        # Still running: the failure paths below must terminate and reap it.
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.waited.append(timeout)
        return 0

    def kill(self):
        self.killed = True


def _launch(user_cmd="true"):
    obj = object.__new__(AsysLaunch)  # __init__ needs the whole CLI state
    obj.user_cmd = user_cmd
    obj.finish_flag = False
    obj.console_output = ""
    return obj


class TestLaunchSigintInstall(AssertTest):
    @pytest.fixture(autouse=True)
    def _restore(self, mocker):
        before = signal.getsignal(signal.SIGINT)
        original_popen = mod.subprocess.Popen
        original_params = mod.ParamDict
        mod.ParamDict = _Params
        # wait_view spins at 10 Hz writing spinner chars to sys.stdout until
        # finish_flag is set; on the failure paths below that never happens,
        # so the thread would outlive the test and pollute later capsys users
        # in the same session.
        mocker.patch.object(AsysLaunch, "wait_view")
        yield
        signal.signal(signal.SIGINT, before)
        mod.subprocess.Popen = original_popen
        # Leaving the stub in place broke every later test in the session.
        mod.ParamDict = original_params

    def test_failed_launch_leaves_the_default_handler(self):
        # Popen raising used to leave the interrupt handler installed while the
        # closure's `pro` was never bound, so Ctrl-C raised NameError and asys
        # kept running (#347).
        def boom(*_a, **_k):
            raise FileNotFoundError("bash not available")

        mod.subprocess.Popen = boom
        before = signal.getsignal(signal.SIGINT)

        with pytest.raises(FileNotFoundError):
            _launch().execute_task()

        # The handler must be exactly what it was: nothing was installed.
        self.assertTrue(signal.getsignal(signal.SIGINT) is before)

    def test_running_child_has_the_handler_and_it_is_restored(self):
        seen = []
        process = _Process(seen)
        mod.subprocess.Popen = lambda *_a, **_k: process

        _launch().execute_task()

        self.assertTrue(seen and seen[0] is not signal.SIG_DFL)
        self.assertTrue(signal.getsignal(signal.SIGINT) is signal.SIG_DFL)
        # The child already exited (communicate returned), so nothing to reap.
        self.assertTrue(not process.terminated)

    def test_communicate_failure_still_restores_the_handler(self):
        class _Broken(_Process):
            def communicate(self):
                raise OSError("boom")

        mod.subprocess.Popen = lambda *_a, **_k: _Broken([])

        with pytest.raises(OSError):
            _launch().execute_task()

        self.assertTrue(signal.getsignal(signal.SIGINT) is signal.SIG_DFL)

    def test_communicate_failure_stops_the_spinner_and_reaps_the_child(self):
        # The except arm must set finish_flag (stopping wait_view), join the
        # thread and terminate a still-running child; the spinner thread
        # itself is patched out by the fixture, so assert on the child side.
        class _Broken(_Process):
            def communicate(self):
                raise OSError("boom")

        process = _Broken([])

        def make_process(*_a, **_k):
            return process

        mod.subprocess.Popen = make_process
        launch_obj = _launch()

        with pytest.raises(OSError):
            launch_obj.execute_task()

        self.assertTrue(process.terminated)
        self.assertTrue(process.waited == [5])
        self.assertTrue(not process.killed)
        self.assertTrue(launch_obj.finish_flag is True)

    def test_thread_start_failure_still_restores_the_handler(self):
        # t.start() and set_task_pid sit between the install and the old
        # communicate-restore, so a RuntimeError from Thread.start() used to
        # leave the handler behind as well.
        class _Broken(_Process):
            pass

        def broken_thread(*_a, **_k):
            raise RuntimeError("can't start new thread")

        mod.subprocess.Popen = lambda *_a, **_k: _Broken([])
        original_thread = mod.threading.Thread
        mod.threading.Thread = broken_thread
        try:
            with pytest.raises(RuntimeError):
                _launch().execute_task()
        finally:
            mod.threading.Thread = original_thread

        self.assertTrue(signal.getsignal(signal.SIGINT) is signal.SIG_DFL)
