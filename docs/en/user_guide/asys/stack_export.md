# Real-time Stack Export

## Description

This function is used to export stack information to locate faults when training or inference service processes are suspended. When the service is not suspended, real-time stack export may fail due to signal sending failure, Bin file generation timeout, or Bin file parsing failure. In addition, the stack information of the same suspended process cannot be exported concurrently. Otherwise, the command may fail to be executed.

## Notes

When exporting real-time stack information, the asys tool searches for the directory where trace logs are stored \(**_$HOME_/ascend/atrace/**  by default\). If there are too many trace log files, the execution of the asys tool may take a long time. Therefore, you are advised to clear trace logs before using the asys tool to export real-time stack information. For details about trace logs, see  Viewing Trace Logs  in  [Log Reference](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/logreference/logreference_0001.html).

## Command Format

```bash
asys collect -r=stacktrace --remote=pid --all --quiet --timeout=num --output=path
```

## Parameters

- **r**: This parameter is mandatory. Set it to  **stacktrace**  to export stack information in real time for subsequent fault locating. If this parameter is not set, fault information is collected. In this case, the  **--remote**,  **--all**  and  **--quiet**  parameters cannot be used.

    After the command is executed successfully, obtain the exported file as prompted.

- **remote**: It specifies the ID of the process that is suspended. This parameter is mandatory when  **-r**  is set to  **stacktrace**. The ID must be greater than or equal to 2. If the input process ID does not exist, the asys command reports an error and exits.
- **all**: If this parameter is set, the stack information of all threads in the suspended process is exported. This parameter is mandatory when  **-r**  is set to  **stacktrace**.
- **quiet**  \(optional\): If this parameter is set, user interaction is disabled during stack information export. If this parameter is not set, user interaction is enabled by default, and you need to confirm whether the signal set for trace processing is enabled on the current server \(when  **ASCEND\_COREDUMP\_SIGNAL**  is not set or is set to a value other than  **none**, the signal set is enabled\). This parameter can be used when  **-r**  is set to  **stacktrace**.

    When real-time stack information is exported, signal 35 needs to be sent to the specified process. If the signal set for trace processing is disabled, the suspended process is stopped and stack information cannot be exported.

    For details about the  **ASCEND\_COREDUMP\_SIGNAL**  environment variable and the signal sets for trace processing, see  [Environment Variables](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/envvar/envref_07_0001.html).

- **timeout**  \(optional\): It specifies the timeout for exporting real-time stack information. The value range is \[1, 60\], in seconds. If this parameter is not set, a default value of 10 seconds applies.

    **output**: This parameter is optional. Its value is used as the prefix of the result output directory of the asys tool. That is, the final output directory is  **\{_output_\}/asys\_output\__timestamp_**. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

## Examples and Output Description

```bash
asys collect -r=stacktrace --remote=892839 --all --quiet --timeout=10 --output=./
```

Output example:

```text
2026-06-26 03:12:35,573 [ASYS] [INFO]: asys start.
2026-06-26 03:12:35,615 [ASYS] [WARNING]: This command sends signal 35 to the process:892839. If the process is executed to disable signal receiving through the environment variable ASCEND_COREDUMP_SIGNAL=none, the process:892839 will be killed.
2026-06-26 03:12:35,615 [ASYS] [INFO]: bin file generate path is /root/ascend/atrace, get from default path.
2026-06-26 03:12:36,236 [ASYS] [INFO]: bin file generated, awaiting stack trace completion.
2026-06-26 03:12:36,988 [ASYS] [INFO]: start parse bin file
2026-06-26 03:12:36,997 [ASYS] [INFO]: stackcore file path: /root/ascend/atrace/trace_892633_892633_20260626030851615735/stackcore_event_892839_20260626031235677855/stackcore_tracer_35_892839_aoe_20260626031235677902.txt
2026-06-26 03:12:36,998 [ASYS] [INFO]: Stacktrace output directory: /root/asys_output_20260626031235573
2026-06-26 03:12:36,998 [ASYS] [INFO]: collect task execute finish.
2026-06-26 03:12:36,998 [ASYS] [INFO]: asys finish.
```
