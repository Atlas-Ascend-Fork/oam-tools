# AI Core Error Information Parsing

## Description

During service execution, if the log file or information printed on the screen contains AI Core error information \(for example, "there is an aivec error exception" or "there is an aicore error exception"\), use the AI Core error information parsing function to quickly locate the cause of the AI Core error, thus improving troubleshooting efficiency.

## Notes

1. To ensure the accuracy of the parsed data, clear the service running logs and plog logs before reproducing the AI Core error.
2. To avoid cyclic copy, the  **--output**  directory cannot be the  **--path**  directory or its subdirectory.

## Command Format

```bash
# In the following command, aic_err_info_timestamp indicates the directory for storing AI Core error information. Replace it with the actual directory.
asys analyze -r=aicore_error -d=deviceId --path=${HOME}/aic_err_info_timestamp
```

## Parameters

- **r**: This parameter is mandatory. It specifies the parsing mode. Set it to  **aicore\_error**.
- **d**: This parameter is optional. It specifies the ID of the device to be operated. If this parameter is not set, the fault information of device 0 is parsed by default.
- **path**: This parameter is optional. It specifies the directory for storing fault information such as logs and dump files.

    If this parameter is not set, the asys tool automatically collects fault information. Automatic collection is affected by environment variables. Therefore, when you run the asys command, the environment variable values must be the same as those used during service running. Otherwise, the collected information may be incorrect. The following environment variables are involved:  **ASCEND\_PROCESS\_LOG\_PATH**,  **NPU\_COLLECT\_PATH**,  **DUMP\_GRAPH\_PATH**,  **ASCEND\_WORK\_PATH**,  **ASCEND\_CACHE\_PATH**,  **ASCEND\_CUSTOM\_OPP\_PATH**. For details about the environment variables and their restrictions, see  [Environment Variables](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/envvar/envref_07_0001.html). If these environment variables do not exist, fault information is collected from the current directory where the asys command is executed.

- **output**: This parameter is optional. It specifies the result output directory of the asys tool. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

## Command Example and Output Description

```bash
# In the following command, aic_err_info_timestamp indicates the directory for storing AI Core error information. Replace it with the actual directory.
asys analyze -r=aicore_error --path=${HOME}/aic_err_info_timestamp
```

After the command is executed, you can analyze and locate the fault based on the prompt information in the  **info.txt**  file, the path of which is displayed on the terminal interface. If the collected information contains multiple AI Core errors, the tool parses the AI Core error that occurs for the first time based on the log time.
