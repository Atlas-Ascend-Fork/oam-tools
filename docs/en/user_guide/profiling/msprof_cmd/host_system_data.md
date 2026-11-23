# Collecting Host-Side System Data

<!-- md-trans-meta sourceCommit=52a1849c3143fba6c070ffcd840fb2770e037b1c translatedAt=2026-11-16T09:05:18.695Z pushedAt=2026-11-17T01:14:35.478Z nl=2 -->

## Description

msprof supports collection of Host-side system data (CPU utilization, CPU frequency, memory utilization, disk I/O utilization, network I/O utilization, and so on), Host-side scheduling and interrupt events (ftrace), and Host CPU PMU hardware and kernel software event counters. The PMU counters help analyze IPC, cache hit rates, TLB pressure, page faults, and scheduling. Collected performance data can be automatically parsed and written to disk.

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

**Table 1**  Parameter description

|Parameter|**Optional/Required**| Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
|--|--|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|--host-sys|Either --host-sys or --host-sys-usage is required.| Switch for Host-side system data collection. The values include cpu, mem, disk, network, and osrt. One or more values can be selected, and multiple values are separated by commas. When this parameter is configured, the `host-sys-pid` parameter must be configured or a user program must be passed in.<br>The meaning of each value is as follows:<br>- cpu: process-level CPU utilization and CPU frequency.<br>- mem: process-level memory utilization.<br>- disk: process-level disk I/O utilization.<br>- network: system-level network I/O utilization.<br>- osrt: process-level syscall and pthreadcall.<br>- numa: total read bandwidth, local node read bandwidth, cross-node (remote) read bandwidth, and internal (self) read bandwidth; the ratio of cross-node read traffic to total read traffic; the ratio of local node read traffic to total read traffic.<br>Configuration example: `--host-sys`=cpu,mem,disk,network.<br>**Description**:<br>- Collection of Host-side CPU frequency performance data depends on the kernel cpufreq driver. If the /sys/.../scaling_cur_freq file does not exist, install the related driver.<br>- Collection of Host-side disk performance data requires the third-party open-source tool iotop, and collection of osrt performance data requires the third-party open-source tools perf and ltrace. For the installation method, see [Installing the perf-iotop-ltrace Tools](../appendices/install_perf_iotop_ltrace.md). After installation, configure user permissions by referring to [Configuring User Permissions](../appendices/config_user_permission.md). The permissions must be reconfigured each time the CANN software package is reinstalled.<br>- Using the open-source tool ltrace to collect osrt performance data causes high CPU usage, which is related to pthread locking and unlocking in the application project and affects the process running speed.<br>- The --host-sys=osrt parameter is supported on the KylinV10SP1 OS of the x86_64 architecture, but is not supported on the KylinV10SP1 OS of the aarch64 architecture.<br>- The --host-sys=network parameter is not supported on the Euler2.9 system in a virtualization environment. |
|--host-sys-usage|Either --host-sys or --host-sys-usage is required.| Switch for collecting performance data of the Host-side system and all processes. The value can be cpu or mem. You can specify one or more of them, separated by commas (,). When this parameter is configured, if the `host-sys-pid` parameter is configured, the CPU or memory utilization rate of the specified Host-side process is collected. The values are described as follows:<br>- cpu: CPU utilization rate of the system and all processes.<br>- mem: Memory utilization rate of the system and all processes.<br>Configuration example: `--host-sys-usage=cpu,mem`.                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|--host-sys-pid|Optional| PID of the host-side application whose data is to be collected. When the AI task runtime is used, this parameter does not need to be configured, and any configuration is invalid.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|--host-sys-usage-freq|Optional| Collection frequency of the CPU utilization rate and memory utilization rate. The value ranges from 1 to 50, in Hz. The default value is 50.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|--ftrace|Optional| Switch for collection of Host-side ftrace events. The value is a string in the `subsystem/event` format. Multiple values are separated by commas, for example, `--ftrace=sched/sched_switch,irq/irq_handler_entry`. The collection result is used to associate and analyze Host-side scheduling and interrupt events with the performance data of AI tasks.<br>**Description**:<br>- This parameter depends on the kernel tracefs and requires root permission or password-free sudo permission (`sudo -n`) to execute. If neither permission is available, or if tracefs is not mounted in the container, this parameter does not take effect, and the failure cause is provided in the collection log.<br>- Only one collector is allowed to work on the same node at the same time. During concurrent collection of multiple tasks, only the first task can collect ftrace data. |
|--ftrace-period|Optional| Collection window of Host-side ftrace, in seconds. The value range is [0, 86400], and the default value is 0. The value 0 indicates that the window follows the profiling lifecycle, that is, from the start of collection to the end of collection. A positive integer indicates that the timing starts from the beginning of collection, and ftrace collection stops after the specified duration is reached. A longer window produces a larger amount of data. A 1-second window produces approximately 400 MB of raw data on a 256-core node. It is recommended to set the value as required. |
|--ftrace-bufsize|Optional| Ring buffer size of each CPU for Host-side ftrace, in KB. The value range is [1024, 4194304], and the default value is 4096. A larger buffer reduces event loss but consumes more Host-side kernel memory. |
|--event-sample|Optional| Host CPU PMU counting switch. Values are `none` and `system-wide`; the default is `none`. `system-wide` counts each online CPU and reports the total for all processes scheduled on that CPU. Specifying either `--cpu-core-events` or `--os-events` also enables counting, so this switch is not required when either event option is present. The collection scope is independent of `--host-sys-pid`. System-wide counting requires `perf_event_paranoid` to be 0 or lower, or the `CAP_PERFMON` capability. Output is written per CPU to `data/pmu/host_pmu_cpu<N>.data`; values are cumulative counts and are analyzed by interval differences. See [Configuring User Permissions](../appendices/config_user_permission.md). |
|--cpu-core-events|Optional| Comma-separated CPU PMU hardware event names, for example, `--cpu-core-events=cycles,instructions,l1d_cache`. Set the value to `help` to print the event names available on the current node and exit without collecting data. Only event names are accepted: numeric event IDs and raw encodings such as `raw:0x13` are not supported. Names may contain letters, digits, underscores, and hyphens, but not colons; each name can be at most 64 characters. Events unsupported on the current node keep their output column, with the corresponding value left empty; other events continue to be collected. |
|--os-events|Optional| Comma-separated kernel software events. Accepted values are `page-faults`, `minor-faults`, `major-faults`, `context-switches`, `cpu-migrations`, `alignment-faults`, `emulation-faults`, `task-clock`, and `cpu-clock`. Set the value to `help` to print the accepted values and exit. Invalid names are rejected. These events do not depend on CPU PMU hardware and can be collected when no usable PMU is available. |
|--event-sampling-interval|Optional| PMU counter read interval in milliseconds. The range is [1, 3600000], and the default is 100 ms. Smaller intervals produce more data. For example, on a 256-core node with 4 events and a 100 ms interval, approximately 1.5 million sample rows are produced per minute (256 × 4 × 600); check available disk space before reducing the interval. |

### Host CPU PMU Collection Notes

- `--cpu-core-events` and `--os-events` can be used together. Their combined, de-duplicated event count must not exceed 32. Both event types are written to the same per-CPU file and row, with the source shown in each column name.
- Use `--cpu-core-events=help` and `--os-events=help` to list the supported names. Numeric machine-specific IDs and raw PMU encodings are not accepted.
- Each CPU needs one file descriptor per event, plus a data file and a timing sidecar. If the descriptor limit cannot accommodate all CPUs at once, collection automatically rotates through CPU batches. In that case, the effective interval per CPU is approximately the number of batches multiplied by the configured interval. Raise the file descriptor limit with `ulimit -n`, the systemd `LimitNOFILE` setting, or the container `--ulimit nofile` option when needed. Profiling and the target application continue if batching is required.
- Put msprof options before the application name; options after the application are not parsed.

Common event combinations include `--cpu-core-events=cycles,instructions` for IPC, `--cpu-core-events=l1d_cache,l1d_cache_refill` for L1 data cache hit rate, `--cpu-core-events=l1d_tlb_refill,dtlb_walk` for TLB page-walk pressure, `--os-events=page-faults,minor-faults,major-faults` for page-fault activity, and `--os-events=context-switches,cpu-migrations` for scheduling activity. Use event names listed by the current node's help output.

## Usage Example

Log in to the runtime environment and run the following command in any directory:

```sh
msprof --output=/home/projects/output --host-sys=cpu /home/projects/MyApp/out/main
```

Collect Host-side scheduling and interrupt events (ftrace) with a collection window of 5 seconds:

```sh
msprof --output=/home/projects/output --host-sys=cpu --ftrace=sched/sched_switch,sched/sched_wakeup,irq/irq_handler_entry --ftrace-period=5 /home/projects/MyApp/out/main
```

Or:

```sh
msprof --output=/home/projects/output --cpu-core-events=cycles,instructions,l1d_cache,l1d_cache_refill --os-events=page-faults,context-switches --event-sampling-interval=100 /home/projects/MyApp/out/main
```

List the event names supported by the current node:

```sh
msprof --cpu-core-events=help
msprof --os-events=help
```

Or:

```sh
msprof --output=/home/projects/output --sys-devices=<ID> --sys-period=<period> --sys-hardware-mem=on --host-sys-pid=<pid> --host-sys=cpu
```

A PROF_XXX directory is generated in the directory specified by **--output** to store the automatically parsed performance data. When CPU PMU counting is enabled, raw per-CPU data is stored under `PROF_XXX/host/data/pmu/`. The parsed database contains the `PMU_EVENTS`, `PMU_COUNTERS`, and `PMU_COUNTER_SAMPLES` tables.
