# Parsing Dump Files

<!-- md-trans-meta sourceCommit=2a887466d2e2283344c9f9e8c9427fce31c3c901 translatedAt=2026-10-10T12:12:48.067Z pushedAt=2026-10-16T02:09:45.715Z -->

## Function

Parses Dump files into .bin or .npy files, which record information such as the inputs, outputs, and workspace of operators.

## Command Format

```bash
python3 msaicerr.py -d path1 -out path2
```

## Parameters

- **-d or --data**: mandatory parameter that specifies the path of the Dump file, including the file name, when parsing the Dump file.
- **-out or --output\_path****: optional parameter that specifies the directory for storing the parsing result files. If not specified, the parsing results are stored in the same directory as the Dump file by default.

## Usage Examples and Output Description

```bash
python3 msaicerr.py -d /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370
```

The following is an example of the output:

```bash
[INFO] The dump file directory will be used to as the output directory of the parsed results.
[INFO] Parse dump file finished, result path is: /demo/dfx/data-dump/0
```

Obtain the parsing result file as prompted.

After you run the msaicerr.py tool, a debug\_info.txt file is generated in the same directory where the msaicerr.py tool is executed, to record the log information generated during tool execution. If debug\_info.txt indicates "Can not read with dtype _xxx_", it means that the tool cannot recognize the data type, and you need to install the third-party library file by yourself. For example, if "Can not read with dtype bfloat16" is indicated, you need to install the bfloat16ext library.
