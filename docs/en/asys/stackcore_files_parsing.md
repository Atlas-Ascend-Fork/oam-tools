# Stackcore File Parsing

## Description

Parse the stackcore file.

A stackcore file can be obtained from the following sources:

- Stackcore file \(**stackcore\_tracer\__\*_.txt**\) on the host. For details about how to obtain the stackcore file, see  Viewing Trace Logs  in[Log Reference](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/logreference/logreference_0001.html).
- Stackcore file on the device. For details about how to export the stackcore file, see  Exporting System Logs and Other Maintenance and Test Information from the Device \> Exporting System Logs and Other Maintenance and Test Information from the Device at a Time  in  [msnpureport Tool](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743?category=reference-guides&subcategory=command-reference).
- Stackcore file obtained by using the  [core dump file parsing](coredump_files_parsing.md)  function of the asys tool.

## Notes

The stackcore parsing function uses the readelf tool to obtain file information and the addr2line tool to parse stack function names and line numbers. Both of the tools are built-in tools of the Linux system. Ensure that the readelf and addr2line tools are installed, and that the user has the permission to execute scripts.

You need to run the stackcore file parsing command in the environment where the stackcore file is obtained. Otherwise, the parsing result may be inaccurate.

## Command Format

```bash
asys analyze -r=stackcore --file=filename --symbol_path=path1,path2 --output=path3
```

Or

```bash
asys analyze -r=stackcore --path=directory --symbol_path=path1,path2 --output=path3
```

## Parameters

- **r**: This parameter is mandatory. It specifies the parsing mode. Set it to  **stackcore**  to parse stackcore files \(**_\*_.txt**  files\) for subsequent fault locating.
- **file**: It specifies a single file to be parsed. Set this parameter to the file name with the path. In **stackcore** mode, select either **file** or **path**. The two parameters cannot coexist.
- **path**: It specifies a directory for parsing multiple files in the specified directory and its subdirectories. In  **stackcore**  mode, select either the  **path**  or  **file**  parameter. The two parameters cannot coexist.
- **symbol\_path**: It specifies the dynamic library directory required for parsing in  **stackcore**  mode. Multiple directories can be transferred and separated by commas \(,\). Only the dynamic libraries in the current directory are scanned. Path 1 is scanned followed by path 2. Subdirectories are not scanned. To prevent incorrect parsing, you are advised to place related dynamic libraries in the same path. The  **symbol\_path**  parameter is optional in  **stackcore**  mode. If the parameter is not specified, the required dynamic library paths are obtained from the stackcore file. To ensure that the dynamic library files can be found, you are advised to use this parameter only in the environment where the core dump error occurs.
- **output**: This parameter is optional. Its value is used as the prefix of the result output directory of the asys tool. That is, the final output directory is  **\{_output_\}/asys\_output\__timestamp_**. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

## Examples and Output Description

```bash
asys analyze -r=stackcore --file=stackcore_tracer_test.txt --symbol_path=$HOME/test1,$HOME/test2 --output=$HOME/dfx_info
```

The following is an example of the parsed .txt file. In the file, the thread information starts with  **Thread  _num_  \(_Thread ID_,  _Thread name_\)**. If the thread name fails to be obtained,  **unknown**  is displayed.

```text
[process]
crash reason:6
crash pid:37246
crash tid:37246
crash stack base:0x00007ffea1e96000
crash stack top:0x00007ffea1e91770

[stack]
Thread 1 (37246, python3.7)
#00 0x00007fbad83792bf lookdict_unicode in dictobject.c:811 from libpython3.7m.so.1.0
#01                    lookdict_unicode in dictobject.c:783 from libpython3.7m.so.1.0
#02 0x00007fbad83d8c22 PyDict_GetItem in dictobject.c:1328 from libpython3.7m.so.1.0
#03 0x00007fbad83e9648 _PyObject_GenericGetAttrWithDict in object.c:1269 from libpython3.7m.so.1.0
#04 0x00007fbad83e6729 module_getattro in moduleobject.c:704 from libpython3.7m.so.1.0
#05 0x00007fbad83e937b _PyObject_GetMethod in object.c:1137 from libpython3.7m.so.1.0
......

[maps]
e0000380000-e0000381000 rw-p 00000000 00:00 0
e00003c0000-e00003c1000 rw-p 00000000 00:00 0
562677ed1000-562677ed2000 r--p 00000000 fd:00 13113992                   /usr/local/python3.7.5/bin/python3.7
562677ed2000-562677ed3000 r-xp 00001000 fd:00 13113992                   /usr/local/python3.7.5/bin/python3.7
562677ed3000-562677ed4000 r--p 00002000 fd:00 13113992                   /usr/local/python3.7.5/bin/python3.7
......
```

- If the parsed .txt file contains  **?**, the possible causes are as follows:
    - Compile option: The  **-g**  option is not used during compilation of the dynamic library file; as a result, debugging information is not retained in the file.
    - Link parameter not added:  **-rdynamic**  is not used to instruct the linker to add all symbols to the dynamic symbol table.
    - Dynamic library not found: No matching dynamic library is found.

- When the stackcore parsing function parses function names and line numbers, the line numbers parsed from some dynamic libraries are slightly different from the actual situation. The reasons are as follows:
    - Compile option: Different compile options, especially those related to debugging information, may have impacts.
    - Optimization level: A higher optimization level may cause code reorganization and optimization, resulting in deviation between the line numbers and the raw source codes.
