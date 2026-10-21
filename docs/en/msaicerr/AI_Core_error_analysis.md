# Analyzing AI Core Errors

## Description

Analyze the fault information about AI Core errors to help locate the errors.

During service execution, if the log file or information displayed on the screen contains the following AI Core error information, you need to obtain the fault information related to the AI Core error, and then use the msaicerr tool to analyze the fault information to help locate the AI Core error.

```text
# Error message
there is an xx aicore error

# Or error example
there is an xx aivec error
```

## Notes

In the collected fault information, check whether dump files or abnormal operator compilation information \(\*.o and \*.json files\) exist in the  **dfx/data-dump**  directory in advance. Check whether log files exist in the  **dfx/log/host/cann**  directory. If no log file exists, the msaicerr tool cannot be used to extract AI Core error information.

## Command Format

```bash
python3 msaicerr.py -p path1 -out path2 -dev 0
```

## Parameters

- **-p**  or  **--report\_path**: The parameter is mandatory. It specifies the directory for storing AI Core error information during AI Core error analysis. Do not run the msaicerr tool in the directory or subdirectory specified by the  **-p**  parameter. Otherwise, the tool parsing may be suspended or fail.
- **-out**  or  **--output\_path**: The parameter is optional. It specifies the path for storing the parsing result file. If the path is not specified or is empty, the parsing result is stored in the current path where the command is executed by default. The directory specified by the  **-out**  parameter cannot be the directory or subdirectory specified by the  **-p**  parameter. Otherwise, the tool parsing may be suspended or fail. If the value of  **-out**  is invalid, the specified directory does not have the write permission, or the directory fails to be created, the msaicerr tool exits and an error is reported.
- **-dev**  or  **--device\_id**: The parameter is optional. It specifies the ID of the device where the built-in operator sample runs. If this parameter is not set, the default device ID is  **0**. When analyzing AI Core errors, the msaicerr tool runs a built-in operator sample to check whether the software and hardware environments are normal.

## Command Example and Output Description

```bash
python3 msaicerr.py -p $HOME/aic_err_info -out $HOME/result
```

After the command is executed, you can analyze and locate the fault based on the prompt information in the  **info.txt**  file, the path of which is displayed on the terminal interface. If the fault information contains multiple AI Core errors, the msaicerr tool parses the AI Core error that occurs for the first time based on the log time.

After the msaicerr.py tool is executed, the  **debug\_info.txt**  or  **info\_\{_timestamp_\}/debug\_info.txt**  file is generated in the same directory as the msaicerr.py tool to record the log information generated during the tool execution.
