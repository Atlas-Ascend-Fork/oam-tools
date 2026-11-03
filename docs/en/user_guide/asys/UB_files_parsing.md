# UB File Parsing

## Description

Parses UB maintenance and debugging information files.

For details about how to obtain the Unified Bus \(UB\) file, see  Exporting System Logs and Other Maintenance and Test Information from the Device \> Exporting System Logs and Other Maintenance and Test Information from the Device at a Time  in  [msnpureport Tool](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743?category=reference-guides&subcategory=command-reference).

## Command Format

```bash
asys analyze -r=ub --path=directory --output=path
```

## Parameters

- **r**: This parameter is mandatory. It specifies the parsing mode. Set it to  **UB**  to the UB maintenance and debugging information collection file in binary format for subsequent fault locating.
- **path**: It specifies a directory, which is used to parse the binary files in the specified directory. This parameter is mandatory in UB mode. The asys tool reads the following binary files in the specified path and parses them into .txt files with the same names:
    - ubnl\_dfx\_config\_item.bin: configuration entries at the UB network layer
    - ubnl\_dfx\_statistic.bin: statistics at the UB network layer
    - ubnl\_dfx\_ssu\_schedule.bin: statistics on the System Scheduling Unit \(SSU\) scheduling queue and queue packet loss at the UB network layer
    - ubmem\_daw.bin: UB memory configuration entries
    - ubtpl\_acl\_src.bin: key entries and configuration at the UB Transport layer
    - sl\_to\_vl.bin: UB Quality of Service \(QoS\) configuration and entries

- **output**: This parameter is optional. Its value is used as the prefix of the result output directory of the asys tool. That is, the final output directory is  **\{_output_\}/asys\_output\__timestamp_**. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

## Examples and Output Description

```bash
asys analyze -r=ub --path=/home/test/msnpureport/device-0/ub
```

After the command is executed, you can obtain the parsed .txt file based on the path displayed on the terminal. The following is an example:

```text
2026-02-12 14:23:10,020 [ASYS] [INFO]: asys start.
2026-02-12 14:23:10,021 [ASYS] [INFO]: asys output directory: /home/test/asys_output_20260212142310021
2026-02-12 14:23:10,032 [ASYS] [INFO]: Conversion successful! /home/test/msnpureport/device-0/ub/ubnl_dfx_statistic.bin has been converted to text file /home/test/asys_output_20260212142310021/ubnl_dfx_statistic.txt
......
2026-02-12 14:23:10,049 [ASYS] [INFO]: analyze task execute finish.
2026-02-12 14:23:10,049 [ASYS] [INFO]: asys finish.
```
