# Converting Dump File Data Types

<!-- md-trans-meta sourceCommit=2a887466d2e2283344c9f9e8c9427fce31c3c901 translatedAt=2026-10-10T12:12:20.835Z pushedAt=2026-10-16T02:09:43.800Z -->

## Description

Converts the data type in a Dump file in \*.bin format.

A Dump file in \*.bin format can be obtained from [Parsing Dump Files](Dump_files_parsing.md).

## Command Format

```bash
python3 msaicerr.py -d path1 -out path2 -dtype int8
```

## Parameters

- **-d or --data**: Mandatory parameter, specifying the path of the Dump file in \*.bin format, including the file name.
- **-out or --output\_path****: Optional parameter, specifying the storage path of the .npy result file. If not specified, the result file is stored in the same path as the Dump file by default.
- **-dtype or --dest\_dtype**: Mandatory parameter, specifying the data type in the Dump file to be converted. If the specified data type is inconsistent with the data type in the source Dump file, a Warning message is displayed when the parsing command is executed, and the file is parsed according to the user-specified data type.

    Value range: float32, float16, float64, int8, int16, int32, int64, uint8, uint16, uint32, uint64, bool, bfloat16

## Usage Example and Output Description

```bash
python3 msaicerr.py -d /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370.input.0.bin -dtype int8
```

The following is an example of the output:

```bash
[INFO] The dump file directory will be used to as the output directory of the parsed results.
[INFO] Success convert bin to npy: /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370.input.0.bin -> /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370.input.0.int8.npy
```

Obtain the conversion result file as prompted.

After the msaicerr.py tool is executed, a debug\_info.txt file is generated in the same directory as the msaicerr.py tool to record log information during tool execution.
