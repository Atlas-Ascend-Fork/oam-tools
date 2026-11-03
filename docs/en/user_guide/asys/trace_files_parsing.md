# Trace File Parsing

## Description

Parse the trace file.

To obtain the trace file \(**\*.bin**\), see  Viewing Trace Logs  in  [Log Reference](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/logreference/logreference_0001.html).

## Command Format

```bash
asys analyze -r=trace --file=filename --output=path
```

Or

```bash
asys analyze -r=trace --path=directory --output=path
```

## Parameters

- **r**: This parameter is mandatory. It specifies the parsing mode. The value  **trace**  indicates of parsing trace log files \(**\*.bin**  files\) into .txt files. The version of the environment where the asys tool is used must be the same as that of the environment where trace logs are generated.
- **file**: It specifies a single file to be parsed. Set this parameter to the file name with the path. In **trace** mode, select either **file** or **path**. The two parameters cannot coexist.
- **path**: It specifies a directory for parsing files in that directory and its subdirectories. It is mutually exclusive with **file**.
- **output**: This parameter is optional. Its value is used as the prefix of the result output directory of the asys tool. That is, the final output directory is  **\{_output_\}/asys\_output\__timestamp_**. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

## Examples and Output Description

```bash
asys analyze -r=trace --file=schedule_tracer_demo.bin --output=$HOME/dfx_info
```

The following is an example of the parsed .txt file:

```text
2024-05-09 19:08:12.408.800 demo0: tid0[0], count0[0], tag0[struct0 tag], streamId0[0], deviceIdArray0[0, 1], hostIdArray0[1, 2, 3, 4]
2024-05-09 19:08:12.408.804 demo1: tag1[struct1 tag], streamId1[0], deviceIdArray1[0, 1], hostIdArray1[1, 2, 3, 4]
```
