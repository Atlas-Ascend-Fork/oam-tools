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

import os.path
import shlex
import threading

from common.const import GET_DEVICES_INFO_TIMEOUT, STACKTRACE
from common import timeout_decorator
from params import ParamDict
from common import log_error, log_info
from common import run_cmd_output
from common import FileOperate as f
from drv.env_type import LoadSoType
from info import AsysInfo
from health import AsysHealth

from view.progress_display import waiting

from collect.stacktrace.stacktrace_collect import AsysStackTrace
from collect.log import collect_device_logs
from collect.log import collect_host_logs
from collect.log import collect_rc_logs
from collect.graph import collect_graph
from collect.ops import collect_ops
from collect.trace import collect_trace
from collect.data_dump import collect_data_dump

__all__ = ["AsysCollect"]


class AsysCollect:
    def __init__(self):
        self.output_root_path = ParamDict().asys_output_timestamp_dir
        self.finish_flag = False

    @staticmethod
    @timeout_decorator(GET_DEVICES_INFO_TIMEOUT, raise_on_error=True)
    def collect_status_info():
        """
        no redundant plog temporary directory is generated when the status and health information is collected.
        """
        if ParamDict().get_env_type() == "EP":
            # collect software, hardware and status information
            AsysInfo().write_info()
        else:
            AsysInfo().get_software_info(write_file=True)

    @staticmethod
    @timeout_decorator(GET_DEVICES_INFO_TIMEOUT, raise_on_error=True)
    def collect_health_info():
        if ParamDict().get_env_type() == "EP":
            # collect health check result
            AsysHealth().run()

    def _device_file_export(self):
        def run_msnpureport(export_dir_path):
            f.create_dir(export_dir_path)
            export_dir_cmd = "cd " + shlex.quote(export_dir_path)
            export_tool = "msnpureport -f"
            export_cmd = "{0};{1}".format(export_dir_cmd, export_tool)
            cmd_res = run_cmd_output(export_cmd)
            if not cmd_res[0]:
                log_error(
                    'Call msnpureport tool failed, sys.stderr: "{}"'.format(
                        cmd_res[1].strip()
                    )
                )
                f.remove_dir(export_dir_path)
                return False
            return True

        export_dir_path = os.path.join(self.output_root_path, "export_tmp")
        if not run_msnpureport(export_dir_path):
            return False
        # export success
        in_export_dir = f.list_dir(export_dir_path)
        if not in_export_dir:
            log_error("No files or directories in {0}".format(export_dir_path))
            return False
        msnpureport_output_dir = os.path.join(export_dir_path, in_export_dir[0])
        return msnpureport_output_dir

    def collect(self):
        # check params
        if (
            ParamDict().get_arg("remote") is not False
            or ParamDict().get_arg("all")
            or ParamDict().get_arg("quiet")
        ):
            log_error(
                "'--remote', '--all' and '--quiet' can be used only when '-r=stacktrace'."
            )
            return False

        log_info("Collect task start, running:")
        # When the main program exits, the system checks whether there is a sub-thread whose daemon value is False.
        # If it exists, the main program exits after the sub-thread exits. Default daemon value is False.
        t = threading.Thread(target=self.wait_view, daemon=True)
        t.start()

        if ParamDict().get_env_type() == "EP":
            # collect log files
            collect_host_logs(self.output_root_path)
            # export device files
            msnpureport_output_dir = self._device_file_export()
            if msnpureport_output_dir:
                collect_device_logs(msnpureport_output_dir, self.output_root_path)
            else:
                log_error("msnpureport tool export device files failed.")
        else:
            collect_rc_logs(self.output_root_path)

        # collect graph
        collect_graph(self.output_root_path)

        # collect_data_dump
        collect_data_dump(self.output_root_path)

        # collect ops
        collect_ops(self.output_root_path)

        # collect trace
        collect_trace(self.output_root_path)

        #  plog are generated when health and status are collected.
        LoadSoType().dll_close()
        try:
            self.collect_status_info()
        except TimeoutError:
            log_error("Timeout in retrieving device status information.")
        except ChildProcessError as err:
            log_error(f"Failed to collect device status information: {err}")

        try:
            self.collect_health_info()
        except TimeoutError:
            log_error("Timeout in retrieving device health information.")
        except ChildProcessError as err:
            log_error(f"Failed to collect device health information: {err}")

        self.finish_flag = True
        t.join()  # wait print process_display end
        return True

    def wait_view(self):
        while not self.finish_flag:
            waiting()
            continue

    def clean_work(self):
        msnpureport_export_path = os.path.join(self.output_root_path, "export_tmp")
        dir_list = [msnpureport_export_path]
        f.delete_dirs(dir_list)

    def run(self):
        if ParamDict().get_arg("run_mode") == STACKTRACE:
            return AsysStackTrace().run()
        else:
            task_res = self.collect()
            self.clean_work()
            return task_res
