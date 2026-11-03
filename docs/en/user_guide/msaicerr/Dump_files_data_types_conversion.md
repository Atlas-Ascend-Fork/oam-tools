# Converting the Data Type of a Dump File

## Description

Convert the data type of a dump file in \*.bin format.

Dump files in \*.bin format can be obtained from  [Parsing Dump Files](Dump_files_parsing.md).

## Command Format

```bash
python3 msaicerr.py -d path1 -out path2 -dtype int8
```

## Parameters

- **-d**  or  **--data**: This parameter is mandatory. It specifies the path of the dump file in \*.bin format, including the file name.
- **-out**  or  **--output\_path**: The parameter is optional. It specifies the path for storing the .npy result file. If the path is not specified, the result file is stored in the same path as the dump file by default.
- **-dtype**  or  **--dest\_dtype**: This parameter is mandatory. It specifies the data type of the dump file to be converted. If the specified data type is different from that in the source dump file, a warning message is displayed when the parsing command is executed, and the data is parsed based on the user-specified data type.

    Value range: float32, float16, float64, int8, int16, int32, int64, uint8, uint16, uint32, uint64, bool, complex64, complex128, bfloat16

## Command Example and Output Description

```bash
python3 msaicerr.py -d /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370.input.0.bin -dtype int8
```

Output example:

```text
[INFO] The dump file directory will be used to as the output directory of the parsed results.
[INFO] Success convert bin to npy: /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370.input.0.bin -> /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370.input.0.int8.npy
```

Obtain the conversion result file as prompted.

After the msaicerr.py tool is executed, the  **debug\_info.txt**  file is generated in the same directory as the msaicerr.py tool to record the log information generated during the tool execution.
