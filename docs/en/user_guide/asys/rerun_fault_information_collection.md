# Service Re-run And Fault Information Collection

## Description

Collect fault information such as software and hardware information and logs after services are re-run.

## Notes

- By default, the function of collecting operator compilation files, GE dump graphs, and TF Adapter dump graphs is enabled during service re-run.
- When you run the  **asys launch**  command, the environment variables  **NPU\_COLLECT\_PATH**,  **ASCEND\_PROCESS\_LOG\_PATH**,  **ASCEND\_HOST\_LOG\_FILE\_NUM**,  **ASCEND\_WORK\_PATH**  are automatically enabled to temporarily store the collected information. After the  **asys launch**  command is executed, these environment variables are automatically disabled. If you manually set these environment variables before running the  **asys launch**  command, the settings of these environment variables will be overwritten and do not take effect. If the script of the re-run task includes these environment variables, the environment variables set by the asys tool may be overwritten and do not take effect. As a result, the corresponding information cannot be collected. For details about the environment variables and their restrictions, see  [Environment Variables](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/envvar/envref_07_0001.html).
- The  **asys launch**  command starts the subprocess to execute the service command. If you stop the  **launch**  command, the service subprocess may not exit. In this case, you need to stop the service subprocess.

## Command Format

```bash
asys launch --task="sh ../app_run.sh" --tar="True" --output=path
```

## Parameters

- **task**  \(mandatory\): It indicates the execution command of a re-run task, which must be a complete command, for example,  **sh ../app\_run.sh**.  **sh**  is the command for executing the task, and  **../app\_run.sh**  is the task script to be executed.

    The tool cannot be directly executed in the background inside the original execution script. For example, the original cases are executed by the  **sh cmd.sh**  command. However, in the implementation of  **cmd.sh**,  **python3 test.py &**  is included to execute in the background. This task is not supported because the end point cannot be detected.

- **tar**  \(optional\): It controls whether to compress the result output directory of the asys tool into a  **\*.tar.gz**  file. If this parameter is set to  **T**  or  **True**, the result output directory is compressed into a  **\*.tar.gz**  file and the original directory is not retained. If this parameter is set to  **F**  or  **False**, the directory is not compressed into a  **\*.tar.gz**  file. By default, the directory is not compressed. The parameter value is case insensitive.
- **output**: This parameter is optional. Its value is used as the prefix of the result output directory of the asys tool. That is, the final output directory is  **\{_output_\}/asys\_output\__timestamp_**. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

## Examples and Output Description

1. \(Optional\) Modify the configuration items related to service re-run. If the configuration items are not modified, the default configurations are used.

    The default configurations are as follows. You can modify specific parameters in the  **ascend\_system\_advisor/asys/conf/asys.ini**  file in the asys tool directory to enable or disable the functions of collecting operator compilation files and dump graphs.

    ```text
    [launch]
    graph = TRUE                    // Specifying whether to collect graph information. The value range is as follows: TRUE: collect; FALSE: not collect. If this parameter is set to FALSE, the settings of dump_ge_graph and dump_graph_level do not take effect.
    ops = TRUE                      // Specifying whether to collect operator compilation information. The value range is as follows: TRUE: collect; FALSE: not collect.
    dump_ge_graph = 2               // Specifying the content of the dump graph, which is the basic version without data like weights. The value is 2, and the corresponding environment variable is DUMP_GE_GRAPH.
    dump_graph_level = 3            // Specifying the number of the dump graph. The value is 3. Graphs generated in the last dump phase correspond to the environment variable DUMP_GRAPH_LEVEL.
    log_level = INFO                // Indicating the global log level for application logs and the log level for each module, corresponding to the environment variable ASCEND_GLOBAL_LOG_LEVEL.
    log_event_enable = TRUE         // Determining whether to enable the event log for application logs. The value range is as follows: TRUE: enabled; FALSE: disabled. The corresponding environment variable is ASCEND_GLOBAL_EVENT_ENABLE.
    log_print_to_stdout = FALSE     // Determining whether to enable log printing to the terminal screen. The value range is as follows: TRUE: enabled; FALSE: disabled. The corresponding environment variable is ASCEND_SLOG_PRINT_TO_STDOUT.
    ```

    By default, the environment variables upon asys startup use the values configured in this file. If these environment variables are set to other values in the script of the re-run task, the environment variables will be overwritten, and the values set in the re-run task script will be used. Therefore, the collected maintenance and debugging information may not meet the fault locating requirements.

2. Run the command to re-run the service and collect fault information.

    ```bash
    asys launch --task="sh ../run.sh" --tar="True" --output=$HOME/dfx_info
    ```

    After the command is executed, the fault information files in  **\{output\}/asys\_output\_timestamp**  are as follows:

    ```text
    ├── asys_output_timestamp
       ├── software_info.txt            // Installation package version, environment variables, dependent software, and system information.
       ├── hardware_info.txt            // Collecting host and device hardware information. The host information includes the kernel version, CPU model, memory usage, and disk usage. The device information includes the number of devices and the number of AI CPUs.
       ├── status_info.txt              // Collecting device information, including the chip model, CPU usage, and AI Core usage.
       ├── health_result.txt            // Collecting device health information, including fault codes and fault information.
       └── dfx
           ├── bbox                     // Black box information on the device.
           ├── data-dump                // Dump file generated when an AI Core error occurs.
           ├── graph                    // Dump graph information, including the dump graphs of the GE and TF Adapter.
           ├── ops                      // Operator compilation information, including *.o and *.json files of operator compilation, operator compilation process information, and custom operator configuration information
           ├── stackcore                // Information about the core file generated when a core dump is triggered by an error.
           ├── atrace                  // Trace flush information, including the plaintext file parsed from the trace binary file.
           └── log
               ├── device
               │     ├──dev-os-{id}
               │           ├── firmware      // Logs generated by the firmware.
               │           ├── slogd         // Maintenance and debugging logs of log-related processes.
               │           ├── application   // The non-event application logs generated by the service process.
               │           └── system        // Logs generated by resident process.
               └── host
                    ├── message         // messages or syslogs.
                    ├── install         // Logs about the history installation of the package.
                    ├── cann            // Application logs.
                    ├── driver          // Driver logs on the host.
                    ├── screen.txt      // Logs printed on the terminal screen. (If the content is empty, redirection may be set in the application task.)
                    └── user_cmd        // Command used by a user to execute a task.
    ```

    **You can accordingly customize the version information of the third-party dependent software collected in the software\_info.txt file.**  In the  **ascend\_system\_advisor/conf/dependent\_package.csv**  file in the asys tool directory, add or delete configuration items. Each line corresponds to a configuration item. Use commas \(,\) to separate dependency item names and query commands. There should be no space after each comma. The following is an example:

    ```text
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
