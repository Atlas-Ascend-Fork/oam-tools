# trace File Parsing

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:49:04.822Z pushedAt=2026-10-15T09:38:14.077Z -->

## Description

Parses trace files.

To obtain a trace file (in \*.bin format), see "Viewing Trace Logs" in [*Log Reference*](https://hiascend.com/document/redirect/CannCommunitylogref).

## Command Format

```bash
asys analyze -r=trace --file=filename --output=path
```

## Description

- **r**: Mandatory parameter, indicating the parsing mode. Set this parameter to trace to parse a trace log file (\*.bin file) into a .txt file. The environment version of the asys tool must be consistent with the environment version that generated the trace logs.
- **file**: Used to parse a single file. Set this parameter to the file name including the path. This parameter is mandatory in trace mode.
- **output**: Optional parameter. Its value is used as the path prefix of the output directory for the asys tool results, that is, the final output directory is **\{output\}/asys\_output\_timestamp**. If the **output** parameter is not specified in the command line, the output results are stored in the directory where the command is executed. If the value of **output** is empty, is an invalid string, the specified path directory has no write permission, or the directory fails to be created, the asys tool exits and reports an error.

## Usage Examples and Output Description

```bash
asys analyze -r=trace --file=schedule_tracer_demo.bin --output=$HOME/dfx_info
```

Example of the parsed txt file content:

```bash
2024-05-09 19:08:12.408.800 demo0: tid0[0], count0[0], tag0[struct0 tag], streamId0[0], deviceIdArray0[0, 1], hostIdArray0[1, 2, 3, 4]
2024-05-09 19:08:12.408.804 demo1: tag1[struct1 tag], streamId1[0], deviceIdArray1[0, 1], hostIdArray1[1, 2, 3, 4]
```
