# Coretrace File Parsing

## Description

Parse the coretrace file.

For details about how to obtain the coretrace file, see  Exporting System Logs and Other Maintenance and Test Information from the Device \> Exporting System Logs and Other Maintenance and Test Information from the Device at a Time  in  [msnpureport Tool](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743?category=reference-guides&subcategory=command-reference).

## Notes

- The coretrace parsing function uses addr2line, a built-in tool of the Linux system, to parse stack function names and line numbers. Ensure that the addr2line tool has been installed, and that the user has the permission to execute the script.
- You need to run the coretrace file parsing command in the environment where the coretrace file is obtained. Otherwise, the parsing result may be inaccurate.
<!-- npu="910,310p,310b" id1 -->
- For  Atlas 200I/500 A2 inference products,  Atlas inference products, and  Atlas training products, the coretrace file parsing function is not supported.
<!-- end id1 -->

## Command Format

```bash
asys analyze -r=coretrace --file=filename --symbol_path=path1,path2 --output=path3
```

Or

```bash
asys analyze -r=coretrace --path=directory --symbol_path=path1,path2 --output=path3
```

## Parameters

- **r**: This parameter is mandatory. It specifies the parsing mode. Set it to  **coretrace**  to parse coretrace files \(**coretrace._\*_**  files\) for subsequent fault locating.
- **file**: It specifies a single file to be parsed. Set this parameter to a file name with the path. In **coretrace** mode, select either **file** or **path**. The two parameters cannot coexist.
- **path**: It specifies a directory for parsing multiple files in the specified directory and its subdirectories. In  **coretrace**  mode, select either the  **path**  or  **file**  parameter. The two parameters cannot coexist.
- **symbol\_path**: It specifies the dynamic library directory required for parsing in  **coretrace**  mode. Multiple directories can be transferred and separated by commas \(,\). Only the dynamic libraries in the current directory are scanned. Path 1 is scanned followed by path 2. Subdirectories are not scanned. To prevent incorrect parsing, you are advised to place related dynamic libraries in the same path. The  **symbol\_path**  parameter is optional in  **coretrace**  mode. If the parameter is not specified, the required dynamic library paths are obtained from coretrace files. To ensure that the dynamic library files can be obtained, you are advised to use this parameter only in the environment where a core dump error occurs.
- **output**: This parameter is optional. Its value is used as the prefix of the result output directory of the asys tool. That is, the final output directory is  **\{_output_\}/asys\_output\__timestamp_**. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

## Examples and Output Description

```bash
asys analyze -r=coretrace --file=coretrace.log-daemon.12335.11.1749181305 --symbol_path=$HOME/test1,$HOME/test2 --output=$HOME/dfx_info
```

The following is an example of the parsed file. In the file, the thread information starts with  **PID  _num_  \(_Thread ID_,  _Thread name_\)**, and the parsed content is output in the format of  **\{_Address_\} \{_Function name_\} \{_Binary name_\}**, for example,  **0xdfffcac78a68 0x00000000000b4a68: clock\_nanosleep at ??:?** **/usr/lib64/libc.so.6"**. If the function name fails to be obtained, the hexadecimal value automatically calculated during the parsing is displayed. In this case, check whether the directory specified by  **symbol\_path**  is correct and whether the dynamic library file in this directory is correct.

```text
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

- If the parsed file contains  **?**, the possible causes are as follows:
    - Compile option: The  **-g**  option is not used during compilation of the dynamic library file; as a result, debugging information is not retained in the file.
    - Link parameter not added:  **-rdynamic**  is not used to instruct the linker to add all symbols to the dynamic symbol table.
    - Dynamic library not found: No matching dynamic library is found.

- When the coretrace parsing function is used to parse function names and line numbers, the line numbers parsed from some dynamic libraries are slightly different from that in original source codes. The reasons are as follows:
    - Compile option: Different compile options, especially those related to debugging information, may have impacts.
    - Optimization level: A higher optimization level may cause code reorganization and optimization, resulting in deviation between the line numbers and the raw source codes.
