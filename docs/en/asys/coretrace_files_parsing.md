# coretrace File Parsing

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:41:08.168Z pushedAt=2026-10-15T09:02:58.381Z -->

## Description

Parses a coretrace file.

To obtain a coretrace file, see the "Exporting Device-Side System Logs and Other Maintenance Information \> Exporting Device-Side System Logs and Other Maintenance Information at a Time" section in [*msnpureport Tool*](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743?category=reference-guides&subcategory=command-reference) to export the coretrace file.

## Precautions

- The coretrace parsing function depends on addr2line to parse stack function names and line numbers. addr2line is a built-in Linux tool. Ensure that addr2line is installed and that the user executing the script has the permission to run it.
- Run the coretrace file parsing command in the environment where the coretrace file is obtained. Otherwise, the parsing result may be inaccurate.
<!-- npu="950" id1 -->
- Only the Ascend 950PR&950DT product series supports the coretrace file parsing function.
<!-- end id1 -->
<!-- npu="A3,910b" id2 -->
- The Atlas A3 series and Atlas A2 series do not support the coretrace file parsing function.
<!-- end id2 -->
<!-- npu="910,310p,310b" id3 -->
- The Atlas 200I/500 A2 inference product, Atlas inference series, and Atlas training series do not support the coretrace file parsing function.
<!-- end id3 -->

## Command Format

```bash
asys analyze -r=coretrace --file=filename --symbol_path=path1,path2 --output=path3
```

or

```bash
asys analyze -r=coretrace --path=directory --symbol_path=path1,path2 --output=path3
```

## Description

- **r**: Required parameter, parsing mode. Set it to coretrace, which is used for parsing files in coretrace format (coretrace.\* files) for subsequent locating.
- **file**: Used for parsing a single file. Set it to the file name with the path. This parameter is mandatory in coretrace mode.
- **path**: Specifies a directory, used for parsing multiple files in the specified directory and its subdirectories. In coretrace mode, select either the path parameter or the file parameter; the two cannot coexist.
- **symbol\_path**: Directory of dynamic libraries required for parsing in coretrace mode. Multiple directories can be passed, separated by commas. symbol\_path scans only the dynamic libraries in the current directory, searching path 1 first and then path 2, without scanning subdirectories. To prevent incorrect parsing, it is recommended to place the related dynamic libraries in a single path. This parameter is optional in coretrace mode. If symbol\_path is not specified, the required dynamic library paths are obtained from the coretrace file. To prevent failure to find the dynamic library files, it is recommended to use this parameter only in the environment where the coredump error occurs.
- **output**: Optional parameter. Its value serves as the path prefix of the result output directory of the asys tool, that is, the final output directory is \{output\}/asys\_output\_timestamp. If the output parameter is not specified in the command line, the output results are stored in the directory where the command is executed. If the value specified for output is empty, an invalid string, or the specified path directory has no write permission, or directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

```bash
asys analyze -r=coretrace --file=coretrace.log-daemon.12335.11.1749181305 --symbol_path=$HOME/test1,$HOME/test2 --output=$HOME/dfx_info
```

The following is an example of a parsed file. Thread information starts with "PID  _num_  \(_thread id_, _thread name_\)", and the parsed content is output in the format of “\{address\} \{function name\} \{binary name\}”, for example, "0xdfffcac78a68    0x00000000000b4a68: clock\_nanosleep at ??:?    /usr/lib64/libc.so.6". If the function name fails to be obtained, the hexadecimal value automatically calculated during parsing is displayed. In this case, check whether the **symbol\_path** configuration directory is correct and whether the dynamic library files in that directory are correct.

```bash
Signal 11 pid 12335

PID 12335 TGID 12335 comm log-daemon
0xdfffcac78a68    0x00000000000b4a68: clock_nanosleep at ??:?    /usr/lib64/libc.so.6
0xdfffcac7dc4c    0x00000000000b9c48: __nanosleep at ??:?    /usr/lib64/libc.so.6
0xdfffcaca6d88    0x00000000000e2d84: usleep at ??:?    /usr/lib64/libc.so.6
0xaaaad1e22dec    0x0000000000012de8: ToolSleep at log_system_api.c:704    /var/log-daemon
0xaaaad1e1cb58    0x000000000000cb54: main at log_daemon.c:217    /var/log-daemon
0xdfffcabef040    0x000000000002b03c: __libc_init_first at ??:?    /usr/lib64/libc.so.6
0xdfffcabef118    0x000000000002b114: __libc_start_main at ??:?    /usr/lib64/libc.so.6
0xaaaad1e1c680    0x000000000000c67c: $x at start.os:?    /var/log-daemon

PID 12356 TGID 12335 comm adx_get_file_th
0xdfffcaca550c    0x00000000000e150c: ioctl at ??:?    /usr/lib64/libc.so.6
0xdfffcbc413fc    0x00000000000543f8: HiIam::AppIoctl(int, unsigned long, void*, unsigned int&, bool) at ??:?    /usr/lib64/libiam.so.0.1.0.0
0xdfffcbc415ec    0x00000000000545e8: ioctl at ??:?    /usr/lib64/libiam.so.0.1.0.0
0xdfffcb2d61ec    0x000000000006f1e8: mmIoctl at hdc_pcie_drv.c:?    /usr/lib64/libascend_hal.so
0xdfffcb2d678c    0x000000000006f788: hdcIoctl at hdc_pcie_drv.c:?    /usr/lib64/libascend_hal.so
0xdfffcb2d8550    0x000000000007154c: hdcPcieEpollWait at ??:?    /usr/lib64/libascend_hal.so
0xdfffcb2dabf4    0x0000000000073bf0: drvHdcPcieEpollWait at hdc_pcie_epoll.c:?    /usr/lib64/libascend_hal.so
0xdfffcb2da7f4    0x00000000000737f0: drvHdcEpollWait at ??:?    /usr/lib64/libascend_hal.so
0xaaaad1e6dc60    0x000000000005dc5c: Adx::AdxHdcEpoll::EpollWait(std::vector<Adx::EpollEvent, std::allocator<Adx::EpollEvent> >&, int, int) at ??:?    /var/log-daemon
0xaaaad1e6c51c    0x000000000005c518: Adx::AdxServerManager::ComponentWaitEvent() at :?    /var/log-daemon
0xaaaad1e6c780    0x000000000005c77c: Adx::AdxServerManager::Run() at ??:?    /var/log-daemon
0xaaaad1e6ea0c    0x000000000005ea08: Adx::Runnable::Process(void*) at ??:?    /var/log-daemon
0xdfffcac46168    0x0000000000082164: pthread_condattr_setpshared at ??:?    /usr/lib64/libc.so.6
0xdfffcacad8dc    0x00000000000e98d8: clone at ??:?    /usr/lib64/libc.so.6
......
```

- If the character ? appears in the parsed file, the possible causes are as follows:
    - Compilation options: The -g option was not used when compiling the dynamic library file, so no debugging information was retained in the file.
    - Missing link parameter: -rdynamic was not used to instruct the linker to add all symbols to the dynamic symbol table.
    - Dynamic library not found: No matching dynamic library was found.

- When coretrace parses function names and line numbers, the line numbers parsed from some dynamic libraries may deviate slightly. The causes are as follows:
    - Compilation options: Different compilation options, especially those related to debugging information, may have an impact.
    - Optimization level: A higher optimization level may cause code restructuring and optimization, resulting in a deviation between the line numbers and the original source code.
