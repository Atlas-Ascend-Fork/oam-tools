# Real-time Stack Export

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:48:09.655Z pushedAt=2026-10-15T09:35:27.929Z -->

## Description

This feature applies to scenarios where a training or inference service process is stuck, allowing you to export stack information to locate the issue. If real-time stack export is performed when the service is not stuck, exceptions such as signal sending failure, bin file generation timeout, or bin file parsing failure may occur, preventing the stack information from being exported normally. In addition, exporting stack information for the same stuck process in parallel is not supported; otherwise, the command may fail to execute.

## Precautions

When exporting real-time stack information, the asys tool searches the directory where trace logs are stored. If there are too many trace log files, the asys tool may take a long time to execute. Therefore, you are advised to clear the trace logs first (the default storage path of trace logs is $HOME/ascend/atrace/) and then run the asys tool to export real-time stack information. For details about trace logs, see "Viewing Trace Logs" in [*Log Reference*](https://hiascend.com/document/redirect/CannCommunitylogref).

## Command Format

```bash
asys collect -r=stacktrace --remote=pid --all --quiet --timeout=num --output=path
```

## Description

- **r**: Mandatory parameter. Set it to stacktrace to export stack information in real time for subsequent troubleshooting. If this parameter is not set, the fault information collection function is executed, but in this case it cannot be used together with the --remote, --all, or --quiet parameter.

    After the command is executed successfully, obtain the exported file according to the prompt on the terminal screen.

- **remote**: Specifies the process ID of the stuck process. This parameter is mandatory when -r=stacktrace. The ID value must be greater than or equal to 2. If the specified process ID does not exist, the asys command reports an error and exits.
- **all**: Setting this parameter exports the stack information of all threads in the stuck process. This parameter is mandatory when -r=stacktrace.
- **quiet**: Optional parameter. During stack information export, setting this parameter disables interaction with the user. If this parameter is not set, interaction is enabled by default, and the user needs to confirm whether the signal set for trace processing is enabled on the current server (when the ASCEND\_COREDUMP\_SIGNAL environment variable is not set or is set to a value other than **none**, the signal set is enabled). This parameter can be used when -r=stacktrace.

    Because exporting real-time stack information requires sending signal 35 to the specified process, if the signal set for trace processing is disabled, the stuck process will be terminated and the stack information cannot be exported.

    For details about the ASCEND\_COREDUMP\_SIGNAL environment variable and the signal set for trace processing, see [*Environment Variable Reference*](https://hiascend.com/document/redirect/CannCommunityEnvRef).

- **timeout**: Optional parameter. Specifies the timeout period for exporting the real-time stack. Value range: \[1, 60\], in seconds. If this parameter is not set, the default value is 10 seconds.

    **output**: Optional parameter. Its value is used as the path prefix of the result output directory of the asys tool, that is, the final output directory is \{output\}/asys\_output\_timestamp. If the output parameter is not specified in the command line, the output result is stored in the directory where the command is executed. If the value specified for output is empty, is an invalid string, or the specified path directory has no write permission, or directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

```bash
asys collect -r=stacktrace --remote=892839 --all --quiet --timeout=10 --output=./
```

The following is an example of the output:

```bash
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
