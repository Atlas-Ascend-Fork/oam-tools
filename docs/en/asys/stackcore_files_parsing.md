# stackcore File Parsing

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:48:26.897Z pushedAt=2026-10-15T09:37:04.678Z -->

## Description

Parses stackcore files.

stackcore files can be obtained from multiple sources:

- Host-side stackcore files (stackcore\_tracer\_\*.txt). For details about how to obtain stackcore files, see "Viewing Trace Logs" in *Log Reference*.
- Device-side stackcore files. For details about how to export stackcore files, see "Exporting Device-Side System Logs and Other Maintenance Information \> Exporting Device-Side System Logs and Other Maintenance Information at a Time" in *msnpureport Tool*.
- stackcore files obtained using the [coredump file parsing](coredump_files_parsing.md) function of the asys tool.

## Precautions

The stackcore parsing function relies on readelf to obtain file information and on addr2line to parse stack function names and line numbers. Both are built-in tools of the Linux system. Ensure that readelf and addr2line are installed and that the user executing the script has the permission to run them.

Run the stackcore file parsing command in the environment where the stackcore file is obtained. Otherwise, the parsing result may be inaccurate.

## Command Format

```bash
asys analyze -r=stackcore --file=filename --symbol_path=path1,path2 --output=path3
```

or

```bash
asys analyze -r=stackcore --path=directory --symbol_path=path1,path2 --output=path3
```

## Description

- **r**: Required parameter, parsing mode. Set it to stackcore to parse files in stackcore format (\*.txt files) for subsequent locating.
- **file**: Used to parse a single file. Set it to the file name including the path. This parameter is mandatory in stackcore mode.
- **path**: Specifies a directory, used to parse multiple files in the specified directory and its subdirectories. In stackcore mode, select either the path parameter or the file parameter; the two cannot coexist.
- **symbol\_path**: Directory of dynamic libraries required for parsing in stackcore mode. You can pass multiple directories separated by commas. symbol\_path scans only the dynamic libraries in the current directory, searching path 1 first and then path 2, without scanning subdirectories. To prevent incorrect parsing, it is recommended that you place the related dynamic libraries in a single path. This parameter is optional in stackcore mode. If the symbol\_path parameter is not specified, the required dynamic library paths are obtained from the stackcore file. To prevent failure to find the dynamic library files, it is recommended that you use this parameter only in the environment where the coredump error occurs.
- **output**: Optional parameter. Its value is used as the path prefix of the result output directory of the asys tool, that is, the final output directory is \{output\}/asys\_output\_timestamp. If the output parameter is not specified in the command line, the output results are stored in the directory where the command is executed. If the value specified for output is empty, is an invalid string, or the specified path directory has no write permission, or directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

```bash
asys analyze -r=stackcore --file=stackcore_tracer_test.txt --symbol_path=$HOME/test1,$HOME/test2 --output=$HOME/dfx_info
```

An example of the parsed txt file is as follows, where thread information starts with "Thread  _num_  \(_thread ID_, _thread name_\)"", and "unknown" is displayed if the thread name fails to be obtained:

```bash
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

- If the character ? exists in the parsed txt file, the possible causes are as follows:
    - Compilation options: The -g option was not used when compiling the dynamic library file, so no debugging information was retained in the file.
    - Link parameter not added: -rdynamic was not used to instruct the linker to add all symbols to the dynamic symbol table.
    - Dynamic library not found: No matching dynamic library was found.

- When stackcore parses function names and line numbers, the line numbers parsed from some dynamic libraries may deviate slightly. The causes are as follows:
    - Compilation options: Different compilation options, especially those related to debugging information, may have an impact.
    - Optimization level: A higher optimization level may cause code restructuring and optimization, resulting in a deviation between the line numbers and the original source code.
