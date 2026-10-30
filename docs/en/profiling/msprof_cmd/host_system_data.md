# Collecting Host-Side System Data

<!-- md-trans-meta sourceCommit=96d529e157b2b0534c59599383e1083b69a9d49d translatedAt=2026-10-10T12:22:08.431Z pushedAt=2026-10-16T02:42:14.380Z -->

## Description

msprof supports the collection of Host-side system data (CPU utilization rate, CPU frequency, memory utilization rate, disk I/O utilization rate, network I/O utilization rate, and so on), and can automatically parse the performance data and persist the files to disk after collection.

## Command Format

You can collect Host-side system data while collecting performance data of AI task running:

```sh
msprof [options] <app>
```

You can also collect Host-side system data while collecting AI processor system data:

```sh
msprof --output=<path> --sys-devices=<ID> --sys-period=<period> [options]
```

## Parameters

**Table 1**  Parameters

|Parameter|**Optional/Required**| Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|--|--|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|--host-sys|Either --host-sys or --host-sys-usage is required.| Switch for collecting Host-side system data. The value can be cpu, mem, disk, network, or osrt. You can specify one or more of them, separated by commas (,). When this parameter is configured, the `host-sys-pid` parameter must be configured or a user program must be passed in.<br>The values are described as follows:<br>- cpu: CPU utilization rate and CPU frequency at the process level.<br>- mem: Memory utilization rate at the process level.<br>- disk: Disk I/O utilization rate at the process level.<br>- network: Network I/O utilization rate at the system level.<br>- osrt: syscall and pthreadcall at the process level.<br>- numa: Total read bandwidth, local node read bandwidth, cross-node (remote) read bandwidth, and internal (self) read bandwidth; ratio of cross-node read traffic to total read traffic; ratio of local node read traffic to total read traffic.<br>Configuration example: `--host-sys`=cpu,mem,disk,network.<br>**Note**:<br>- To collect Host-side disk performance data, install the third-party open-source tool iotop. To collect osrt performance data, install the third-party open-source tools perf and ltrace. For the installation method, see [Installing perf, iotop, and ltrace](../appendices/install_perf_iotop_ltrace.md). After the installation, configure user permissions by referring to [Configuring User Permissions](../appendices/config_user_permission.md). The permissions must be reconfigured each time the CANN software package is reinstalled.<br>- Using the open-source tool ltrace to collect osrt performance data causes high CPU usage. It is related to the pthread locking and unlocking of the application project and affects the process running speed.<br>- The --host-sys=osrt parameter is supported on KylinV10SP1 of the x86_64 architecture, but not on KylinV10SP1 of the aarch64 architecture.<br>- The --host-sys=network parameter is not supported on the Euler2.9 system in a virtualization environment. |
|--host-sys-usage|Either --host-sys or --host-sys-usage is required.| Switch for collecting performance data of the Host-side system and all processes. The value can be cpu or mem. You can specify one or more of them, separated by commas (,). When this parameter is configured, if the `host-sys-pid` parameter is configured, the CPU or memory utilization rate of the specified Host-side process is collected. The values are described as follows:<br>- cpu: CPU utilization rate of the system and all processes.<br>- mem: Memory utilization rate of the system and all processes.<br>Configuration example: `--host-sys-usage=cpu,mem`.                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|--host-sys-pid|Optional| PID of the host-side application whose data is to be collected. When the AI task runtime is used, this parameter does not need to be configured, and any configuration is invalid.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|--host-sys-usage-freq|Optional| Collection frequency of the CPU utilization rate and memory utilization rate. The value ranges from 1 to 50, in Hz. The default value is 50.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

## Usage Example

Log in to the running environment and run the following command in any directory:

```sh
msprof --output=/home/projects/output --host-sys=cpu /home/projects/MyApp/out/main
```

Or:

```sh
msprof --output=/home/projects/output --sys-devices=<ID> --sys-period=<period> --sys-hardware-mem=on --host-sys-pid=<pid> --host-sys=cpu
```

A PROF_XXX directory is generated in the directory specified by --output to store the automatically parsed performance data. For details about the result files, see Table 1.
