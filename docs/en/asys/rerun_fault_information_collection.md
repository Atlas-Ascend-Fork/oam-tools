# Service Rerun and Fault Information Collection

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:46:40.947Z pushedAt=2026-10-15T09:31:27.437Z -->

## Description

Collect fault information, such as software and hardware information and logs, after rerunning the service.

## Precautions

- Business rerun enables the collection of operator compilation files, GE dump graphs, and TF Adapter dump graphs by default.
- When the asys launch command is executed, the NPU\_COLLECT\_PATH, ASCEND\_PROCESS\_LOG\_PATH, and ASCEND\_WORK\_PATH environment variables are automatically enabled to temporarily store the collected information. When the asys launch command finishes, these environment variables are automatically disabled. If you manually set these environment variables before executing the asys launch command, the values you set will be overwritten and will not take effect. If the user task script for rerun involves the NPU\_COLLECT\_PATH, ASCEND\_PROCESS\_LOG\_PATH, and ASCEND\_WORK\_PATH environment variables, the environment variables set by the asys tool may be overwritten and become ineffective, which may prevent the corresponding information from being collected. For details and constraints of each environment variable, see [*Environment Variable Reference*](https://hiascend.com/document/redirect/CannCommunityEnvRef).
- The asys launch command starts a child process to execute the service command. If you proactively terminate the launch command, the service child process may not exit. In this case, you need to terminate the service child process by yourself.

## Command Format

```bash
asys launch --task="sh ../app_run.sh" --tar="True" --output=path
```

## Description

- **task**: Required parameter. It specifies the command for rerunning the business, and the complete command must be provided. For example, **sh ../app\_run.sh**, where **sh** is the command for executing the task and **../app\_run.sh** is the task script to be executed.

    Direct background execution inside the original execution script is not supported. For example, the original test case runs sh cmd.sh on the command line to start the test case, while cmd.sh internally executes python3 test.py & in the background. Such tasks are not supported because their end point cannot be detected.

- **tar:** Optional parameter. It specifies whether to compress the result output directory of the asys tool into a \*.tar.gz file. By default, no compression is performed. When the value is T or True, the directory is compressed into a \*.tar.gz file and the original directory is not retained. When the value is F or False, the directory is not compressed into a \*.tar.gz file. The parameter value is case-insensitive.
- **output**: Optional parameter. Its value is used as the path prefix of the result output directory of the asys tool, that is, the final output directory is \{output\}/asys\_output\_timestamp. When the output parameter is not specified on the command line, the output result is stored in the directory where the command is executed. If the value specified for output is empty, is an invalid string, or the specified path directory has no write permission, or directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

1. (Optional) Modify the configuration items related to business rerun. If they are not modified, the default configuration is used.

    The default configuration is as follows. You can enable or disable the collection of operator compilation files and dump graphs by modifying the parameters in the “ascend\_system\_advisor/asys/conf/asys.ini” file in the asys tool directory:

    ```bash
    [launch]
    graph = TRUE                    // Controls whether to collect Graph information. Value range: TRUE (collect), FALSE (do not collect). If set to FALSE, the dump_ge_graph and dump_graph_level configurations do not take effect.
    ops = TRUE                      // Controls whether to collect operator compilation information. Value range: TRUE (collect), FALSE (do not collect).
    dump_ge_graph = 2               // Controls the amount of dump graph content. Value 2 indicates the basic dump without data such as weights, corresponding to the environment variable DUMP_GE_GRAPH.
    dump_graph_level = 3            // Controls the number of dump graphs. Value 3 indicates dumping the graphs generated in the final stage, corresponding to the environment variable DUMP_GRAPH_LEVEL.
    log_level = INFO                // Global log level of application logs and the log level of each module, corresponding to the environment variable ASCEND_GLOBAL_LOG_LEVEL.
    log_event_enable = TRUE         // Controls whether to enable Event logs for application logs. Value range: TRUE (enable), FALSE (disable), corresponding to the environment variable ASCEND_GLOBAL_EVENT_ENABLE.
    log_print_to_stdout = FALSE     // Controls whether to print logs to the terminal screen. Value range: TRUE (enable), FALSE (disable), corresponding to the environment variable ASCEND_SLOG_PRINT_TO_STDOUT.
    ```

    When the asys tool starts, the environment variables use the configuration values in this file by default. However, if these environment variables are configured to other values in the rerun task script, environment variable overriding occurs, and the values set in the rerun task script take precedence. As a result, the collected maintenance and diagnostic information may not meet the locating requirements.

2. Execute the service rerun and fault information collection command.

    ```bash
    asys launch --task="sh ../run.sh" --tar="True" --output=$HOME/dfx_info
    ```

    After the command is executed, the fault information file directory under the \{output\}/asys\_output\_timestamp path is as follows:

    ```bash
    ├── asys_output_timestamp
       ├── software_info.txt            // Installation package version, environment variables, dependent software, and system information
       ├── hardware_info.txt            // Hardware information collected from the host and device sides. Host information includes the kernel version, CPU model, and memory and disk usage. Device information includes the number of devices and the number of AICore units.
       ├── status_info.txt              // Device information collected, including the chip model and the CPU and AI Core utilization.
       ├── health_result.txt            // Device health information collected, including fault codes and fault information.
       └── dfx
           ├── bbox                     // Black box information on the device side
           ├── data-dump                // Dump files generated when an Aicore error occurs
           ├── graph                    // Dump graph information, including dump graphs from GE and TF Adapter
           ├── ops                      // Operator compilation information, including operator compilation *.o and *.json files, operator compilation process information, custom operator configuration information, etc.
           ├── stackcore                // Core file information when an error triggers coredump
           ├── atrace                   // Trace dump information, including plaintext files parsed from trace binary files
           └── log
               ├── device
               │     ├──dev-os-{id}
               │           ├── firmware      // Logs generated by the firmware
               │           ├── slogd         // Maintenance and test logs of log-related processes
               │           ├── application   // Non-EVENT-level application logs generated by service processes
               │           └── system        // Logs generated by resident processes
               └── host
                    ├── message         // message/syslog logs
                    ├── install         // Logs of historical package installation
                    ├── cann            // Application logs
                    ├── driver          // Host-side driver logs
                    ├── screen.txt      // Logs printed to the terminal screen (if the content is empty, redirection may have been set in the application task.)
                    └── user_cmd        // Command used by the user to execute the task
    ```

    **Users can define the version information of third-party dependency software collected in the software\_info.txt file as required.** In the “ascend\_system\_advisor/conf/dependent\_package.csv” file in the asys tool directory, add or delete configuration items. Each line corresponds to one configuration item, with the dependency name and query command separated by a comma, and no space after the comma. The following is an example snippet:

    ```bash
    make,make --version
    cmake,cmake --version
    unzip,unzip -v
    zlib1g,dpkg -l zlib1g| grep zlib1g| grep ii
    zlib1g-dev,dpkg -l zlib1g-dev| grep zlib1g-dev| grep ii
    libsqlite3-dev,dpkg -l libsqlite3-dev| grep libsqlite3-dev| grep ii
    openssl,dpkg -l openssl| grep openssl| grep ii
    libssl-dev,dpkg -l libssl-dev| grep libssl-dev| grep ii
    libffi-dev,dpkg -l libffi-dev| grep libffi-dev| grep ii
    ```
