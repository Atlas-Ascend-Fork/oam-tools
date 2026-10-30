# asys Tool Functions and Constraints

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:38:55.007Z pushedAt=2026-10-15T08:10:49.939Z -->

## Introduction

To improve the efficiency of system fault maintenance and testing, the **fault information collection tool asys** is provided for one-click information collection. **This tool is supported only in Ascend EP mode.**

The tool supports the following functions:

- **[Fault Information Collection](fault_information_collection.md)**: Collects only fault information, such as software and hardware information and logs, without rerunning services.
- **[Rerun + Fault Information Collection](rerun_fault_information_collection.md)**: Reruns services and then collects fault information, such as software and hardware information and logs.
- **[Software/Hardware and Device Status Information Display](software_hardware_device_status_info_display.md)**: Collects installation package version information, Device temperature, power, and so on.
- **[Health Check](health_check.md)**: Checks the health status of all Devices or a specified Device (if unhealthy, error information is displayed).
- **[Comprehensive Detection](comprehensive_detection.md)**: Involves stress detection, HBM hardware detection, CPU detection, AI Core STL hardware detection, and other functions.
- **[Component Diagnostics](component_diagnostics.md)**: Currently supports only AI Vector component diagnostics and does not support parallel execution.
- **[trace File Parsing](trace_files_parsing.md)/[coredump File Parsing](coredump_files_parsing.md)/[stackcore File Parsing](stackcore_files_parsing.md)/[coretrace File Parsing](coretrace_files_parsing.md)/[UB File Parsing](UB_files_parsing.md)**: Parses various files to facilitate subsequent problem locating.
- **[Real-time Stack Export](stack_export.md)**: This feature applies to scenarios where a service process is stuck, allowing stack information to be exported to locate problems.
- **[Environment Configuration](environment_configuration.md)**: Obtains or restores the specified configuration.
- **[AI Core Error Fault Information Parsing](AI_Core_error_analysis.md)**: When running a service, if the log file or screen output contains an AI Core Error (for example, "there is an aivec error exception" or "there is an aicore error exception"), you can use the AI Core Error fault information parsing feature to quickly locate the cause of the AI Core Error and improve troubleshooting efficiency.
- **[Performance Data Collection](profiling_collection.md)**: Collects key performance data to help you analyze performance issues.

**Table 1** **List of information that the asys tool supports collecting**

| Classification | Description |
| --- | --- |
| Software information | Involves software package versions, environment variables, software dependencies, and system information. |
| Log information | Includes the following information:<br><br>  - Host-side CANN software stack logs.<br>  - Host-side message logs.<br>  - Device-side firmware logs: device-* logs (root permission required).<br>  - Device-side system logs: message logs and device-os logs (root permission required).<br>  - Black box, stackcore files, and coretrace files (root permission required).<br>  - Task print logs.<br>  - run package installation logs (collectable only when the run package installation user is the same as the application execution user). |
| dump information | Includes the following information:<br><br>  - GE dump graphs.<br>  - TF Adapter dump graphs.<br>  - dump files generated when an AI Core Error occurs. |
| Operator build \*.o and \*.json files | - |
| Operator build process information files | Operator build process information files can be collected only during service rerun. The file content includes build success or failure, and whether the build result is a reused cache, online build, or binary.<br>Whether the asys tool can collect operator build process information depends on whether you set the NPU_COLLECT_PATH environment variable (used to set the save path of fault information). If it is set, the system creates a subdirectory /extra-info/ops/ under the directory specified by this environment variable, creates op_compile_stats.log in the subdirectory, and writes the operator build process information to the log file. In this case, the asys tool can collect the operator build process information file. If it is not set, the system does not generate the corresponding log file, and therefore the asys tool does not collect this file. |
| Custom operator configuration information (*.json files) | Whether the asys tool can collect custom operator configuration information depends on whether you set the following environment variables:<br><br>  - If you set the ASCEND_OPP_PATH environment variable (used to set the installation path of the operator library), the asys tool collects the custom operator configuration information (that is, config/*.json files) under the **\${ASCEND_OPP_PATH}/vendors** directory based on the **load_priority** field in the **\${ASCEND_OPP_PATH}/vendors/config.ini** file. Otherwise, the asys tool does not collect it.<br>  - If you set the ASCEND_CUSTOM_OPP_PATH environment variable (used to set the installation path of the custom operator package), the custom operator configuration information (that is, config/*.json files) under the ${ASCEND_CUSTOM_OPP_PATH} directory is collected. Otherwise, the asys tool does not collect it. |
| Command information executed by user test cases | - |
| Debug version binary information | That is, the information under the ${ASCEND_OPP_PATH}/debug_kernel directory. However, the ASCEND_OPP_PATH environment variable (used to set the installation path of the operator library) must be configured in advance. If the ASCEND_OPP_PATH environment variable is not configured or is configured incorrectly, the debug version binary information is not collected by default. |

>**Note:**
>For detailed configuration of environment variables, see [*Environment Variable Reference*](https://hiascend.com/document/redirect/CannCommunityEnvRef).

## Constraints

1. It is not supported in Ascend RC mode.
2. When the same user runs jobs on the same machine within the same period of time, the collected data may overlap.
3. For non-root users, the scope of data that can be obtained is limited. For specific restrictions, see the permission requirements in the table above.
4. One-click fault information collection is not supported in cluster, container, virtual machine, or cloud scenarios.
5. The asys tool collects a large amount of maintenance and test information, which consumes memory. Therefore, running multiple processes in parallel is not recommended, as it may cause the asys tool to fail or the environment to become abnormal.
6. The asys tool scans the directory where trace logs are stored. If there are too many trace log files, the asys tool may take a long time to execute.

    Trace logs are stored in $HOME/ascend/atrace/ by default. For details about trace logs, see "Viewing Trace Logs" in [*Log Reference*](https://hiascend.com/document/redirect/CannCommunitylogref).
