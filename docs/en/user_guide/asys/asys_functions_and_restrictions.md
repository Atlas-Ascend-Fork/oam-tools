# Functions and Restrictions of the asys Tool

<a id="section8451192217185"></a>

## Functions

To improve the efficiency of system fault maintenance and debugging, the asys fault information collection tool is provided for one-click collection of fault information. This tool can be used only in  Ascend EP  mode.

The tools support the following functions:

- **[Fault information collection](fault_information_collection.md)**: Collect fault information such as software and hardware information and logs without service re-run.
- **[Service re-run and fault information collection](rerun_fault_information_collection.md)**: Collect fault information such as software and hardware information and logs after services are re-run.
- **[Display of software, hardware, and device status information](software_hardware_device_status_info_display.md)**: Collect the installation package version information, device temperature, and power.
- **[Health check](health_check.md)**: Check the health status of all devices or specified devices. If a device is unhealthy, an error message is displayed.
- **[Comprehensive detection](comprehensive_detection.md)**: Involve the stress test, HBM hardware detection, CPU detection and AI Core STL hardware detection.
- **[Component detection](component_diagnostics.md)**: Currently, only the AI Vector component detection is supported; parallel execution is not supported.
- **[Trace](trace_files_parsing.md)/[Core dump](coredump_files_parsing.md)/[Stackcore](stackcore_files_parsing.md)/[Coretrace](coretrace_files_parsing.md)/[UB file parsing](UB_files_parsing.md)**: Parse various files to facilitate subsequent fault locating.
- **[Real-time stack export](stack_export.md)**: This function is used to export stack information to locate faults when service processes are suspended.
- **[Environment configuration](environment_configuration.md)**: Obtain or restore the specified configuration.
- **[AI Core error information parsing](AI_Core_error_analysis.md)**: During service execution, if the log file or information printed on the screen contains AI Core error information \(for example, "there is an aivec error exception" or "there is an aicore error exception"\), use the AI Core error information parsing function to quickly locate the cause of the AI Core error, thus improving troubleshooting efficiency.
- **[Performance data collection](profiling_collection.md)**: Collects key performance data to help users analyze performance issues.

**Table  1**  Information that can be collected by the asys tool

| Category | Description |
| --- | --- |
| Software information | Software package version, environment variables, software dependency, and system information. |
| Log information | The information includes:<br><br>  - CANN software stack logs on the host.<br>  - Message logs on the host.<br>  - Device firmware logs: device-* logs (requiring the root permission)<br>  - Device system logs: message logs and device-os logs (requiring the root permission)<br>  - Black box, stackcore files, and coretrace files (requiring the root permission)<br>  - Task print logs<br>  - Runfile installation logs (available only when the runfile installation user is the same as the application execution user) |
| Dump information | The information includes:<br><br>  - GE dump graphs.<br>  - TF Adapter dump graphs.<br>  - Dump file generated when an AI Core error occurs. |
| *.o and*.json files for operator compilation | - |
| Operator compilation process file | Only the operator compilation process information is collected during service re-run. The information includes compilation success or failure, reused memory, online compilation, and binary compilation results.<br>Whether the asys tool can collect the operator compilation process information depends on whether the NPU_COLLECT_PATH environment variable (used to set the path for saving fault information) is specified. If it is set, the system creates the /extra-info/ops/ subdirectory in the directory specified by the environment variable, creates op_compile_stats.log in the subdirectory, and writes the operator compilation process information to the log file. In this case, the asys tool can collect the operator compilation process information. If this environment variable is not set, the system does not generate the corresponding log file. Therefore, the asys tool does not collect the file. |
| Custom operator configuration (*.json file) | Whether the asys tool can collect the custom operator configuration depends on whether the following environment variables are set:<br><br>  - If the ASCEND_OPP_PATH environment variable (used to set the installation path of the operator library) is set, the asys tool collects the custom operator configuration (that is, the config/*.json file) in the ${ASCEND_OPP_PATH}/vendors directory based on the load_priority field in the ${ASCEND_OPP_PATH}/vendors/config.ini file. Otherwise, the asys tool does not collect the information.<br>  - If the ASCEND_CUSTOM_OPP_PATH environment variable (used to set the installation path of the custom operator package) is set, the custom operator configuration (that is, the config/*.json file) in the ${ASCEND_CUSTOM_OPP_PATH} directory is collected. Otherwise, the asys tool does not collect the information. |
| Commands executed in user cases | - |
| Binary information of the debugging version | Information in the ${ASCEND_OPP_PATH}/debug_kernel directory. You need to configure the ASCEND_OPP_PATH environment variable (used to set the installation directory of the operator library) in advance. If the ASCEND_OPP_PATH environment variable is not configured or incorrectly configured, the binary information of the debugging version is not collected by default. |

>**NOTE:**
>For details about how to set environment variables, see  [Environment Variables](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/envvar/envref_07_0001.html).

## Restrictions

1. This function cannot be used in  Ascend RC  mode.
2. If more than one process is operated by the same user on a machine at the same time, the collected data may overlap.
3. Only limited data can be collected by a non-root user. For details about the limitations, see the privilege requirements in  [Functions](#section8451192217185).
4. The one-click tool cannot be used to collect fault information in cluster, container, VM, and cloud scenarios.
5. The asys tool collects a large amount of maintenance and debugging information. Therefore, memory usage is involved. You are advised not to run multiple processes in parallel. Otherwise, an error may occur during the execution of the asys tool or the environment may encounter exceptions.
6. The asys tool searches for the related information in the directory where trace logs are stored. If there are too many trace log files, the execution of the asys tool may take a long time.

    By default, trace logs are stored in the  **_$HOME_/ascend/atrace/**  directory. For details about trace logs, see  Viewing Trace Logs  in  _[Log Reference](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/logreference/logreference_0001.html)_.
