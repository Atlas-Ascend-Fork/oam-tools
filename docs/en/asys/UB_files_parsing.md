# UB File Parsing

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:49:47.677Z pushedAt=2026-10-15T09:42:03.524Z -->

## Description

Parses UB diagnostic information files.

To obtain a Unified Bus (UB) file, see the "Exporting Device-Side System Logs and Other Diagnostic Information \> Exporting Device-Side System Logs and Other Diagnostic Information at a Time" section in [*msnpureport Tool*](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743?category=reference-guides&subcategory=command-reference) to export the UB file.

## Command Format

```bash
asys analyze -r=ub --path=directory --output=path
```

## Description

- **r**: Mandatory parameter, parsing mode. Set this parameter to **ub** to parse the binary UB maintenance and test information collection file for subsequent troubleshooting.
- **path**: Specifies a directory for parsing binary files in the directory. This parameter is mandatory in ub mode. asys reads the following binary files in the path directory and parses them into .txt files with the same names.
    - ubnl\_dfx\_config\_item.bin: UB network layer configuration entries
    - ubnl\_dfx\_statistic.bin: UB network layer statistics
    - ubnl\_dfx\_ssu\_schedule.bin: UB network layer SSU (System Scheduling Unit) scheduling queue statistics and queue packet loss statistics
    - ubmem\_daw.bin: UB memory configuration entries
    - ubtpl\_acl\_src.bin: UB Transport layer key entries and configurations
    - sl\_to\_vl.bin: UB QOS (Quality of Service) configurations and entries

- **output**: Optional parameter. Its value is used as the path prefix for the result output directory of the asys tool, that is, the final output directory is **\{output\}/asys\_output\_timestamp**. If the output parameter is not specified in the command line, the output results are stored in the directory where the command is executed. If the value specified by output is empty, an invalid string, or a path directory without write permission, or if directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

```bash
asys analyze -r=ub --path=/home/test/msnpureport/device-0/ub
```

After running the command, you can obtain the parsed txt file from the path displayed on the terminal, as shown in the following example:

```bash
2026-02-12 14:23:10,020 [ASYS] [INFO]: asys start.
2026-02-12 14:23:10,021 [ASYS] [INFO]: asys output directory: /home/test/asys_output_20260212142310021
2026-02-12 14:23:10,032 [ASYS] [INFO]: Conversion successful! /home/test/msnpureport/device-0/ub/ubnl_dfx_statistic.bin has been converted to text file /home/test/asys_output_20260212142310021/ubnl_dfx_statistic.txt
......
2026-02-12 14:23:10,049 [ASYS] [INFO]: analyze task execute finish.
2026-02-12 14:23:10,049 [ASYS] [INFO]: asys finish.
```
