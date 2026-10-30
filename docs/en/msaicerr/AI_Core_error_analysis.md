# Analyzing AI Core Error Issues

<!-- md-trans-meta sourceCommit=2a887466d2e2283344c9f9e8c9427fce31c3c901 translatedAt=2026-10-10T12:11:58.507Z pushedAt=2026-10-16T02:09:42.286Z -->

## Description

Analyze the fault information of AI Core Error issues to help locate AI Core Error issues.

When executing a service, if the log file or screen output contains the following AI Core Error messages, you need to first obtain the fault information related to the AI Core Error issue, and then use msaicerr to analyze the fault information of the AI Core Error issue to help locate the issue.

```bash
# Error example
there is an xx aicore error

# Or error example
there is an xx aivec error
```

## Precautions

In the collected fault information, check in advance whether dump files and abnormal operator compilation information (operator compilation \*.o and \*.json files) exist in the dfx/data-dump directory, and whether log files exist in the dfx/log/host/cann directory. If they do not exist, the msaicerr tool cannot be used to extract AI Core Error information.

## Command Format

```bash
python3 msaicerr.py -p path1 -out path2 -dev 0
```

## Parameters

- **-p or --report\_path****: Mandatory parameter. When analyzing AI Core Error issues, it specifies the directory where the AI Core Error fault information is located. Do not run the msaicerr tool in the directory or a subdirectory specified by the -p parameter; otherwise, the tool may hang or fail during parsing.
- **-out or --output\_path****: Optional parameter. It specifies the storage path of the parsing result file. If not specified, the parsing result is stored in the current directory where the command is executed by default. The directory specified by the -out parameter must not be the directory or a subdirectory specified by the -p parameter; otherwise, the tool may hang or fail during parsing. If the value specified by the -out parameter is empty or an invalid string, or the specified directory has no write permission, or directory creation fails, the msaicerr tool exits and reports an error.
- **-dev or --device\_id****: Optional parameter. It specifies the Device ID for running the built-in operator sample. If this parameter is not set, the default Device ID is 0. When analyzing AI Core Error issues, the msaicerr tool runs a built-in operator sample to check whether the software and hardware environment is normal.

## Usage Examples and Output Description

```bash
python3 msaicerr.py -p $HOME/aic_err_info -out $HOME/result
```

After the command is executed, the user locates the path of the info.txt file indicated in the terminal interface and uses the prompt information in the info.txt file to analyze and locate the issue. If the fault information contains multiple AI Core Error issues, the msaicerr tool parses the first AI Core Error issue according to the log time.

After the msaicerr.py tool is executed, a “debug\_info.txt” or “info\_\{ timestamp \}/debug\_info.txt” file is generated in the same directory as the msaicerr.py tool to record the log information generated during tool execution.
