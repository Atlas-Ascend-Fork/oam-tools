# Parsing Dump Files

## Description

Parse dump files into .bin or .npy files, which record operator information such as input, output, and workspace.

## Command Format

```bash
python3 msaicerr.py -d path1 -out path2
```

## Parameters

- **-d**  or  **--data**: The parameter is mandatory. It specifies the path of the dump file to be parsed, which contains the file name.
- **-out**  or  **--output\_path**: The parameter is optional. It specifies the path for storing the parsing result file. If the path is not specified, the parsing result is stored in the same path as the dump file by default.

## Command Example and Output Description

```bash
python3 msaicerr.py -d /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370
```

Output example:

```text
[INFO] The dump file directory will be used to as the output directory of the parsed results.
[INFO] Parse dump file finished, result path is: /demo/dfx/data-dump/0
```

Obtain the parsing result file as prompted.

After the msaicerr.py tool is executed, the  **debug\_info.txt**  file is generated in the same directory as the msaicerr.py tool to record the log information generated during the tool execution. If "Can not read with dtype xxx" is displayed in the  **debug\_info.txt**  file, a data type that cannot be identified by the tool exists. In this case, you need to install the corresponding third-party library file. For example, if "Can not read with dtype bfloat16" is displayed, you need to install the bfloat16ext library.
