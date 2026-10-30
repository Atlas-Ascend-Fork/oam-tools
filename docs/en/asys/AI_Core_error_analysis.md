# AI Core Error Information Parsing

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:38:48.914Z pushedAt=2026-10-15T08:00:49.991Z -->

## Description

When executing services, if the log file or screen output contains an AI Core Error (for example, "there is an aivec error exception" or "there is an aicore error exception"), you can use the AI Core Error information parsing function to quickly locate the cause of the AI Core Error issue and improve troubleshooting efficiency.

## Precautions

1. To ensure the accuracy of the parsed data, it is recommended that you clear the service running logs and plog logs before reproducing the AI Core Error issue.
2. To avoid circular copying, the --output directory must not be the --path directory or any of its subdirectories.

## Command Format

```bash
# In the following command, aic_err_info_timestamp is the directory that stores AI Core Error information. Replace it with the actual value.
asys analyze -r=aicore_error -d=deviceId --path=${HOME}/aic_err_info_timestamp
```

## Description

- **r**: mandatory parameter, parsing mode, set to aicore\_error here.
- **d**: optional parameter, specifies the deviceId to be operated. If this parameter is not set, the fault information of device 0 is parsed by default.
- **path**: optional parameter, the directory that stores fault information such as logs and dump files.

    If this parameter is not configured, the asys tool automatically collects the fault information. Automatic collection is affected by environment variables. Therefore, when the asys command is executed, the environment variable values must be consistent with those during service running; otherwise, the collected information may be inaccurate. The involved environment variables are as follows: ASCEND\_PROCESS\_LOG\_PATH, NPU\_COLLECT\_PATH, DUMP\_GRAPH\_PATH, ASCEND\_WORK\_PATH, ASCEND\_CACHE\_PATH, ASCEND\_CUSTOM\_OPP\_PATH. For details and constraints of each environment variable, see [*Environment Variable Reference*](https://hiascend.com/document/redirect/CannCommunityEnvRef). If none of these environment variables exist, the fault information is collected from the current directory where the asys command is executed.

- **output**: optional parameter, whose value is used as the result output directory of the asys tool. If the output parameter is not specified in the command line, the output result is stored in the directory where the command is executed. If the value specified for output is empty, an invalid string, or a directory path without write permission, or if directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

```bash
# In the following command, aic_err_info_timestamp is the directory that stores AI Core Error information. Replace it with the actual directory.
asys analyze -r=aicore_error --path=${HOME}/aic_err_info_timestamp
```

After the command is executed, the user analyzes and locates the issue based on the prompt information in the info.txt file, whose path is displayed on the terminal. If the collected information contains multiple AI Core Error issues, the tool parses the first AI Core Error issue in log time order.
