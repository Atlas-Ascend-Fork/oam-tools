# Collecting Performance Data Using the acl.json Configuration File

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:27:31.263Z pushedAt=2026-10-16T03:47:22.026Z -->

In offline inference scenarios, you can call the acl.json file in the inference program to read performance collection parameters, thereby automatically collecting raw performance data.

After raw performance data is collected successfully, you can transfer the collected raw data to a development environment with the tools installed for performance data parsing and view the parsing results.

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
For parsing operations, see [Using the msprof Command to Parse, Query, and Export Performance Data](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/msprof_parsing_instruct.md). For an introduction to the parsing result files, see [Performance Data File Reference](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/profile_data_file_references.md).
<!-- end id1 -->

<!-- npu="950,A3,910b,910,310p,310b" id50 -->
This section only describes how to enable performance data collection in the inference program. For the complete development process of an inference application, see *[Application Development \(C&C++\)](https://gitcode.com/cann/docs/blob/9.2.0/docs/zh/app-dev/README.md)*.
<!-- end id50 -->

## Prerequisites

- Before enabling performance data collection, ensure that the inference program can run properly.
- Be sure to call `aclInit()` and `aclFinalize()` to complete initialization and deinitialization.

## Procedure

Complete the acl.json file configuration and then compile and run the application project by following the steps below:

1. Open the inference application project code file where the `aclInit()` function is located, and obtain the acl.json file path.

    ```cpp
    // ACL init
    const char *aclConfigPath = "../src/acl.json";
    aclError ret = aclInit(aclConfigPath);
    if (ret != ACL_ERROR_NONE) {
        ERROR_LOG("acl init failed");
        return FAILED;
    }
    INFO_LOG("acl init success");
    ```

    > [!NOTE]
    > If `aclInit()` is initialized with an empty value, modify the function to add the acl.json file path created in "Step 2".

2. In the located directory, modify the acl.json file (if the file does not exist, create it; it is recommended to place it in the src directory after project compilation), and add the Profiling-related configuration in the following format.

    ```cpp
    {
    "profiler": {
            "switch": "on",
            "output": "output"
            }
    }
    ```

   For details about each parameter, see [Parameters](#parameters).

3. After the acl.json file is configured, recompile the application project and run it.
   <!-- npu="950,A3,910b,910,310p,310b" id51 -->
   For details about application development, see [Application Development \(C&C++\)](https://gitcode.com/cann/docs/blob/9.2.0/docs/zh/app-dev/README.md).
   <!-- end id51 -->

    The raw Profiling performance data is generated in the path specified by "output", as shown below.

    ```sh
    total 16
    drwxr-x--- 4 . ./ Jan 29 01:47
    drwxr-xr-x 21 .. ../ Feb 9 20:24
    drwxr-x--- 3 PROF_000001_20220129014731273_KEDKPORHMAGPGDCC/ Jan 29 01:47
    ```

    > [!NOTE] Note
    > If the acl.json file already exists and you only modify the file content to add Profiling-related configuration, you do not need to recompile the application project.
    >- In the asynchronous inference scenario, the executable file of the application project keeps running and does not call the Profiling stop API. Therefore, it is recommended that you manually stop the process. Otherwise, the collected raw performance data may fill up the disk. Ensure that sufficient disk space is reserved.
    >- Running an application process that depends on libslog.so by using `./app process name` does not generate debug logs. To generate debug logs, use the pmupload tool to start the application process as follows:<br>
    >   `pmupload app_path/app arg` <br>
    >   app\_path/app indicates the app process path and app name; arg indicates the input parameters of the app process.

## Parameters

### switch

Profiling switch. Values include on and off.
<br>on indicates that Profiling is enabled, and off indicates that Profiling is disabled. If this parameter is missing or its value is not on, Profiling is disabled.
<br>After the Profiling switch is enabled, data such as Runtime APIs and Task Scheduler task scheduling information is automatically collected.

### output

Path for storing Profiling performance data. If this parameter is not configured, the performance data is stored in the directory where the executable file of the application project is located by default.
<br>The path cannot contain special characters:

```sh
"\n", "\\n", "\f", "\\f", "\r", "\\r", "\b", "\\b", "\t", "\\t", "\v", "\\v", "\u007F", "\\u007F", "\"", "\\\"", "'", "\'", "\\", "\\\\", "%", "\\%", ">", "\\>", "<", "\\<", "|", "\\|", "&", "\\&", "$", "\\$", ";", "\\;", "`", "\\`"
```

<br>After Profiling collection is complete, a directory prefixed with PROF is generated in this directory to store the raw performance data collected by Profiling. Both absolute paths and relative paths (relative to the current path when the command is executed) are supported:

- An absolute path starts with "/".
- A relative path starts directly with a directory name, for example, output.
- The directory specified by this parameter must be readable and writable by the running user configured during installation. If the directory specified here is not readable or writable, the collection result data is stored in the directory where the executable file of the application project is located by default (ensure that the running user configured during installation has read and write permissions on that directory).
- This parameter has a higher priority than ASCEND\_WORK\_PATH.

### storage\_limit

Specifies the maximum file capacity allowed in the directory where data is written to disk. When the Profiling data files on the disk are about to occupy the maximum storage space set by this parameter, or when the remaining total disk space is about to be fully occupied (remaining total space <= 20 MB), the earliest files on the disk are aged out and deleted.
<br>Range \[200, 4294967295\], in MB, for example, `storage_limit=200MB`. By default, this parameter is not configured.
<br>When this parameter is configured, if the available disk space is less than 20 MB before collection, data is not written to disk.

<!-- npu="950,A3,910b,910,310p,310b" id2 -->

### aicpu

 Collects detailed information about AI CPU operators, such as operator execution time and data copy time. The value can be on or off, and the default value is off.
 <!-- end id2 -->

### aic_metrics

AI Core performance metric collection items. This parameter takes effect when task_time or task_trace is set to on, l1, or l2. When task_time or task_trace is set to l0 or off, this parameter is not collected. Values include:

- ArithmeticUtilization: proportion of time consumed by computation instructions
- PipeUtilization: time consumed by computation and data movement instructions and their proportion. This value is required when collecting `*_icache_miss_rate`.
- Memory: memory read/write bandwidth rate
- MemoryL0: L0 read/write bandwidth rate
- MemoryUB: UB read/write bandwidth rate
- ResourceConflictRatio: resource conflict proportion
- L2Cache: L2 Cache hit rate
  <!-- npu="310p" id3 -->
  - Atlas inference products: Not supported
  <!-- end id3 -->
- PipelineExecuteUtilization: time consumption and proportion of compute and move instructions. This value is required when counting `fixpipe_exe_ratio`.

  <!-- npu="310p" id4 -->
  - Atlas inference products: Not supported
  <!-- end id4 -->
  <!-- npu="910" id5 -->
  - Atlas training products: Not supported
  <!-- end id5 -->
  <!-- npu="910b" id6 -->
  - Atlas A2 products: Not supported
  <!-- end id6 -->
  <!-- npu="A3" id7 -->
  - Atlas A3 products: Not supported
  <!-- end id7 -->
  <!-- npu="950" id8 -->
  - Ascend 950PR&950DT products: Not supported
  <!-- end id8 -->

- MemoryAccess:

  <!-- npu="310b" id9 -->
  - Atlas 200I/500 A2 inference product: Not supported
  <!-- end id9 -->
  <!-- npu="310p" id10 -->
  - Atlas inference products: Not supported
  <!-- end id10 -->
  <!-- npu="910" id11 -->
  - Atlas training products: Not supported
  <!-- end id11 -->
  <!-- npu="950" id12 -->
  - Ascend 950PR&950DT products: Not Supported
  <!-- end id12 -->

Default:

<!-- npu="310b" id13 -->
- Atlas 200I/500 A2 inference products: PipelineExecuteUtilization
<!-- end id13 -->
<!-- npu="310b" id14 -->
- Atlas inference products: PipeUtilization
<!-- end id14 -->
<!-- npu="910" id15 -->
- Atlas training products: PipeUtilization
<!-- end id15 -->
<!-- npu="910b" id16 -->
- Atlas A2 products: PipeUtilization
<!-- end id16 -->
<!-- npu="A3" id17 -->
- Atlas A3 products: PipeUtilization
<!-- end id17 -->
<!-- npu="950" id18 -->
- Ascend 950PR&950DT products: PipeUtilization
<!-- end id18 -->

<!-- @ref: oam-tools/res/docs/en/profiling/other_method/with_acljson_config_file_res.md#id00001 -->

Custom collection of registers is supported. For example: "aic_metrics":"Custom:0x49,0x8,0x15,0x1b,0x64,0x10".

- The Custom field indicates a custom type and is configured with specific register values in the range [0x1, 0x7FFFFFFF]. Not all possible values have corresponding PMU registers. If a configured value has no corresponding PMU register, the collection result may be 0.
- The number of configured registers cannot exceed 8, and registers are separated by commas (,).
- Register values support hexadecimal or decimal format.

### l2

Controls the switch for L2 Cache hit rate and TLB page table cache hit rate collection. The value can be on or off, and the default is off. If Profiling is enabled during the model execution phase in the aclgraph scenario, this collection item does not take effect.

<!-- npu="310b" id19 -->
- Atlas 200I/500 A2 inference products: support collecting the L2 Cache hit rate. To analyze the number of AI Core hits on L2, it is recommended to use aic-metrics=L2Cache.
<!-- end id19 -->
<!-- npu="310p" id20 -->
- Atlas inference products: support collection of the L2 Cache hit rate
<!-- end id20 -->
<!-- npu="910" id21 -->
- Atlas training products: support collecting the L2 Cache hit rate
<!-- end id21 -->
<!-- npu="910b" id22 -->
- Atlas A2 products: support collecting the L2 Cache and TLB page table cache hit rates. To analyze the number of AI Core hits on L2, it is recommended to use aic-metrics=L2Cache.
<!-- end id22 -->
<!-- npu="A3" id23 -->
- Atlas A3 products: support collection of the L2 Cache and TLB page table cache hit rates. To analyze the number of AI Core hits on L2, it is recommended to use aic\_metrics=L2Cache.
<!-- end id23 -->
<!-- npu="950" id24 -->
- Ascend 950PR&950DT products: support collection of the L2 Cache and TLB page table cache hit rates. To analyze the number of AI Core hits on L2, it is recommended to use aic_metrics=L2Cache.
<!-- end id24 -->

### hccl

Controls the switch for communication data collection. This data is generated only in multi-card, multi-node, or cluster scenarios.

- When this parameter is configured in the JSON file, it can be set to on or off.
- When this parameter is not configured in the JSON file, it defaults to empty and no data is collected. When task\_time is set to on, this parameter is automatically set to on.

This switch will be deprecated in later versions. Use the task\_time switch to control the related data collection.

### task\_time

Switch that controls the collection of operator dispatch time and operator execution time. The related time-consuming data is output to files such as task\_time, op\_summary, and op\_statistic. Configuration values:

- on: Enable. The default value is on.
- off: Disable.
  - l0: Collect operator dispatch time and operator execution time data. Compared with l1, since basic operator information data is not collected, the performance overhead during collection is lower, allowing more accurate statistics of the related time-consuming data.
  - l1: Collect operator dispatch time, operator execution time, and basic operator information data, providing more comprehensive performance analysis data. The effect is the same as setting the value to on.

### ge\_api

Collects the time-consuming data of dynamic shape operators during the Host scheduling phase. Values include:

- off: Disables collection. The default value is off.
- l0: Collects the time-consuming data of dynamic shape operators during the main stages of Host scheduling, enabling more accurate statistics of the related time-consuming data.
- l1: Collects more fine-grained time-consuming data of dynamic shape operators during the Host scheduling phase, providing more comprehensive performance analysis data.

### ascendcl

 Controls the switch for collecting acl API performance data. The value can be on or off, and the default is on. It can collect acl API performance data, including the latency of synchronous and asynchronous memory copy between Host and Device and between Devices.

### runtime\_api

Controls the switch for runtime API performance data collection. The value can be on or off, and the default is on. It collects runtime API performance data, including synchronous and asynchronous memory copy latency between Host and Device and between Devices.

### sys\_hardware\_mem\_freq

Collection frequency of on-chip memory read/write rate, QoS transmission bandwidth, LLC L3 cache bandwidth, accelerator bandwidth, SoC transmission bandwidth, component memory usage, and etc. The collection content varies slightly by product. Refer to actual results. Range \[1,100\], unit: Hz. Not collected by default.

<!-- npu="950" id25 -->
For Ascend 950PR&950DT products, the maximum collection frequency supported by QoS and SoC is 10000, while the maximum collection frequency supported by other collection items remains 100. If the configured value exceeds the range, other collection items are collected at the maximum collection frequency of 100.
<!-- end id25 -->

It is known that collecting memory data in an environment with glibc earlier than 2.34 may trigger a known glibc [Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329). This issue can be resolved by upgrading the glibc version of the environment.

<!-- npu="A3,910b,310b" id26 -->
For the following models, after the collection task ends, it is not recommended to increase the collection frequency. Otherwise, SoC transmission bandwidth data may be lost.
<!-- end id26 -->
<!-- npu="310b" id27 -->
- Atlas 200I/500 A2 inference product
<!-- end id27 -->
<!-- npu="910b" id28 -->
- Atlas A2 products
<!-- end id28 -->
<!-- npu="A3" id29 -->
- Atlas A3 products
<!-- end id29 -->

### llc\_profiling

LLC Profiling collection events. Collecting this data requires setting sys\_hardware\_mem\_freq. Values include:

- read: read event, L3 cache read rate. The default is read.
- write: write event, L3 cache write rate.

 <!-- npu="950,A3,910b,910,310p,310b" id30 -->

### sys\_io\_sampling\_freq

 Collection frequency of NIC, ROCE, and UB bandwidth data. The collected content may vary slightly by product. Refer to the actual results. Range \[1,100\], unit: Hz.
 <!-- end id30 -->

<!-- npu="310b" id31 -->
- Atlas 200I/500 A2 inference products: NIC collection is supported only in RC scenarios. The parameter does not take effect in container scenarios.
<!-- end id31 -->
<!-- npu="310p" id32 -->
- Atlas inference products: This parameter is not supported.
<!-- end id32 -->
<!-- npu="910" id33 -->
- Atlas training products: NIC and ROCE collection is supported.
<!-- end id33 -->
<!-- npu="910b" id34 -->
- Atlas A2 products: NIC and ROCE collection is supported.
<!-- end id34 -->
<!-- npu="A3" id35 -->
- Atlas A3 products: NIC and ROCE collection is supported.
<!-- end id35 -->
<!-- npu="950" id36 -->
- Ascend 950PR&950DT products: UB bandwidth data.
<!-- end id36 -->

<!-- npu="950,A3,910b,910,310p" id37 -->
### sys\_interconnection\_freq

Collection frequency of collective communication bandwidth data (HCCS), collective communication hardware acceleration unit (CCU) bandwidth data, SIO data, PCIe data, inter-chip transmission bandwidth information, and UB bandwidth data. The collection content of different products has slight differences. Refer to actual results. Range \[1,50\], unit: Hz. Not collected by default.
<!-- end id37 -->

<!-- npu="310b" id38 -->
- Atlas 200I/500 A2 inference products do not support this parameter.
<!-- end id38 -->
<!-- npu="310p" id39 -->
- Atlas inference products: support collection of PCIe data.
<!-- end id39 -->
<!-- npu="910" id40 -->
- Atlas training products: support collection of HCCS and PCIe data.
<!-- end id40 -->
<!-- npu="910b" id41 -->
- Atlas A2 products: support collection of HCCS data, PCIe data, and inter-chip transmission bandwidth information.
<!-- end id41 -->
<!-- npu="A3" id42 -->
- Atlas A3 products: support collection of HCCS data, PCIe data, inter-chip transmission bandwidth information, and SIO data.
<!-- end id42 -->
<!-- npu="950" id43 -->
- Ascend 950PR&950DT products: support collection of PCIe data, inter-chip transmission bandwidth information, SIO data, CCU bandwidth data, and UB bandwidth data.
<!-- end id43 -->

<!-- npu="950,A3,910b,910,310p,310b" id44 -->

### dvpp\_freq

DVPP collection frequency. Range \[1,100\], unit Hz.
<!-- end id44 -->

<!-- npu="950" id45 -->

### instr\_profiling

Switch for the bandwidth and latency collection frequency of AI Core and AI Vector.

<br>Supported only in single-operator scenarios. Supported only on Ascend 950PR&950DT products.
<br>The statistics may be inaccurate because the statistical time of the last instruction segment is excessively long. It is recommended to use the msprof op method for collection.
<!-- end id45 -->

<!-- npu="A3,910b" id46 -->

### instr\_profiling\_freq

Collection frequency of the bandwidth and latency of AI Core and AI Vector, range \[300,30000\], unit Hz.
<br>Supported only in single-operator scenarios.
<br>This parameter is supported only on the following models:

<!-- end id46 -->
<!-- npu="910b" id47 -->
- Atlas A2 products
<!-- end id47 -->
<!-- npu="A3" id48 -->
- Atlas A3 products
<!-- end id48 -->

<!-- npu="950,A3,910b,910,310p,310b" id52 -->
### host\_sys

Switch for Host-side performance data collection. Values include:

- cpu: CPU utilization at the process level.
- mem: Memory utilization at the process level.
- disk: Disk I/O utilization at the process level.
- network: Network I/O utilization at the system level.
- osrt: syscall and pthreadcall at the process level.

Select one or more of them. When selecting multiple items, separate them with commas, for example "host\_sys": "cpu,mem".
<!-- end id52 -->

<!-- npu="950,A3,910b,910,310p,310b" id49 -->

### host\_sys\_usage

Collects CPU and memory data of the Host-side system and all processes. Values include cpu and mem. You can select one or more of them. When selecting multiple items, separate them with commas, for example "host\_sys\_usage": "cpu,mem".
<!-- end id49 -->

### host\_sys\_usage\_freq

Configures the collection frequency of CPU and memory data of the host system and all processes. Range \[1,50\], default value 50, unit Hz.

### msproftx

Controls the switch for outputting performance data by the msproftx user and upper-layer framework programs. The value can be on or off, and the default value is off.
<br>Before Profiling enables the msproftx function, you need to call the msproftx-related APIs in the program to enable the output of the program's Profiling data stream, and enable recording of the time span during which specific events occur while the application is running.
