# PROFILING\_OPTIONS

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:00:59.757Z pushedAt=2026-10-15T10:09:14.846Z -->

## Description

In training or online inference scenarios, developers can configure Profiling options through the PROFILING\_OPTIONS environment variable.

### output

Path for saving Profiling collection result files. Both absolute paths and relative paths (relative to the current path when the command is executed) are supported. The path cannot contain the following special characters: "\\n", "\\f", "\\r", "\\b", "\\t", "\\v", "\\u007F".

- An absolute path starts with "/", for example, /home/output.
- A relative path starts directly with a directory name, for example, output.
- This parameter has a higher priority than ASCEND\_WORK\_PATH.
- This path does not need to be created by the user in advance; it is automatically created during collection.

### storage\_limit

Specifies the maximum file capacity allowed in the disk directory. When the Profiling data files are about to occupy the maximum storage space set by this parameter on the disk, or when the remaining total disk space is about to be used up (remaining total space <= 20 MB), the earliest files on the disk are aged out and deleted.
<br>Range \[200, 4294967295\], in MB. When setting this parameter, the unit must be included, for example, 200MB.
<br>If this parameter is not configured, data is not written to disk before collection when the available disk space is less than 20 MB.

### training\_trace

Switch for collecting iteration trajectory data, that is, the software information of the training task and the AI software stack, to perform performance analysis of the training task, focusing on data such as forward and backward computation and gradient aggregation and update. When collecting forward and backward operator data, this parameter must be set to on.

### task\_trace, task\_time

Switch that controls the collection of operator dispatch time and operator execution time. The related time is output to files such as task\_time, op\_summary, and op\_statistic. Values:

- **on**: enable. This is the default value and has the same effect as **l1**.
- **off**: disable.
- **l0**: collect operator dispatch time and operator execution time. Compared with l1, since basic operator information data is not collected, the performance overhead during collection is lower, allowing more accurate statistics of the related time consumption data.
- **l1**: collect operator dispatch time, operator execution time, and basic operator information data, providing more comprehensive performance analysis data.

When training profiling mode is enabled, that is, when training Profiling data is collected, task\_trace must be set to on and training\_trace must also be set to on.

### ge\_api

Collects time-consuming data of dynamic shape operators during the Host scheduling phase. Values:

- **off**: disabled. The default is off.
- **l0**: collects time consumption data of dynamic shape operators in the main phases of Host scheduling, allowing more accurate statistics on the related time consumption data.
- **l1**: collects finer-grained time consumption data of dynamic shape operators during the Host scheduling phase, providing more comprehensive performance analysis data.

### hccl

Controls the switch for communication data collection. The value can be on or off, and the default is off.

> [!NOTE]
> This switch will be deprecated in later versions. Use the task\_time switch to control related data collection.

### aicpu

Collects detailed information about AICPU operators, such as operator execution time and data copy time. The value can be on or off, and the default is off.

### fp\_point

Specifies the start position of the forward operator in the training network iteration trajectory, which is used to record the start timestamp of forward computation. The configuration value is the name of the first forward operator. In the training script, you can save the graph as a .pbtxt file through tf.io.write\_graph, obtain the name from the file, and fill it in. Alternatively, you can leave it empty so that the system automatically identifies the start position of the forward operator, for example, "fp\_point":"".

### bp\_point

Specifies the end position of the backward operator in the training network iteration trajectory, and records the backward computation end timestamp. bp\_point and fp\_point can be used to calculate the forward and backward time. The configuration value is the name of the last backward operator. In the training script, you can save the graph as a .pbtxt file through tf.io.write\_graph, obtain the name from the file, and fill it in. You can also leave it empty, in which case the system automatically identifies the end position of the backward operator, for example, "bp\_point":"".

### aic\_metrics

AI Core performance metric collection items. The values are as follows:

- ArithmeticUtilization: statistics on the proportion of various computation metrics.
- PipeUtilization: proportion of time consumed by computation units and data transfer units. This is the default value.
- Memory: proportion of external memory read/write instructions.
- MemoryL0: proportion of internal L0 memory read/write instructions.
- MemoryUB: proportion of internal UB memory read/write instructions.
- ResourceConflictRatio: proportion of pipeline queue instructions.
- L2Cache: number of L2 cache read/write hits and the number of reallocations after misses.

  <!-- npu="310p" id6 -->
  Atlas inference products do not support this parameter.
  <!-- end id6 -->

  <!-- npu="910" id7 -->
  Atlas training products do not support this parameter.
  <!-- end id7 -->
- MemoryAccess: bandwidth data volume of operator memory access on the core.

  <!-- npu="310p" id8 -->
  Atlas inference products do not support this parameter.
  <!-- end id8 -->

  <!-- npu="910" id9 -->
  Atlas training products do not support this parameter.
  <!-- end id9 -->

  <!-- npu="950" id10 -->
  Ascend 950PR&950DT products: this parameter is not supported.
  <!-- end id10 -->

  > [!NOTE]
  > You can customize the registers to be collected, for example: "aic\_metrics":"**Custom:**_0x49,0x8,0x15,0x1b,0x64,0x10_".
  > - The Custom field indicates a custom type, configured as a specific register value, with the range \[0x1, 0x6E\].
  > - A maximum of 8 registers can be configured, separated by commas (,).
  > - Register values support hexadecimal or decimal format.

### l2

Switch that controls the hit rate of the L2 cache and TLB page table cache. The value can be on or off, and the default is off. If Profiling is enabled during model execution in the aclgraph scenario, this collection item does not take effect.

<!-- npu="310p" id11 -->
- Atlas inference products: support collection of the L2 cache hit rate.
<!-- end id11 -->

<!-- npu="910" id12 -->
- Atlas training products: support collection of the L2 cache hit rate.
<!-- end id12 -->

<!-- npu="910b" id13 -->
- Atlas A2 products: support collection of the hit rates of the L2 cache and TLB page table cache. To analyze the number of L2 hits by the AI Core, it is recommended to use aic-metrics=L2Cache.
<!-- end id13 -->

<!-- npu="A3" id14 -->
- Atlas A3 products: support collection of the hit rates of the L2 cache and TLB page table cache. To analyze the number of L2 hits by the AI Core, it is recommended to use aic-metrics=L2Cache.
<!-- end id14 -->

<!-- npu="950" id15 -->
- Ascend 950PR&950DT products: support collection of the hit rates of the L2 cache and TLB page table cache. To analyze the number of L2 hits by the AI Core, it is recommended to use aic-metrics=L2Cache.
<!-- end id15 -->

### msproftx

Controls the switch for msproftx users and upper-layer framework programs to output performance data. The value can be on or off, and the default is off.
<br>Before using this option, add the following mstx API or msproftx API to the application script. The mstx API is recommended.

### runtime\_api

Controls the switch for runtime API performance data collection. The value can be on or off, and the default is off. It supports collection of runtime API performance data, including the latency of synchronous and asynchronous memory copy between Host and Device and between Devices.

### sys\_hardware\_mem\_freq

Collection switches for on-chip memory, QoS transmission bandwidth, LLC L3 cache bandwidth, accelerator bandwidth, SoC transmission bandwidth, component memory usage, and so on. The collection content varies slightly by product. The actual result prevails. Range \[1,100\], in Hz.

<!-- npu="950" id16 -->
For Ascend 950PR&950DT products, the maximum collection frequency supported by QoS and SoC can be configured to 10000, while the maximum collection frequency supported by other collection items remains 100. If the configured value exceeds the range, other collection items are collected at the maximum collection frequency of 100.
<!-- end id16 -->

It is known that collecting memory data in an environment with glibc earlier than 2.34 may trigger a known glibc [Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329). This issue can be resolved by upgrading the glibc version of the environment.

<!-- npu="A3,910b,310b" id17 -->
For the following models, after a collection task ends, you are not advised to increase the collection frequency. Otherwise, SoC transmission bandwidth data may be lost.
<!-- end id17 -->

<!-- npu="310b" id18 -->
Atlas 200I/500 A2 inference product
<!-- end id18 -->

<!-- npu="910b" id19 -->
Atlas A2 products
<!-- end id19 -->

<!-- npu="A3" id20 -->
Atlas A3 products
<!-- end id20 -->

### llc\_profiling

LLC Profiling collection events can be set to:

- read: read event, L3 cache read rate. The default is read.
- write: write event, L3 cache write rate.

### sys\_io\_sampling\_freq

Collection frequency of NIC, ROCE, and UB bandwidth data. Range \[1,100\], in Hz.

<!-- npu="310p" id21 -->
Atlas inference products: this parameter is not supported.
<!-- end id21 -->

<!-- npu="910b" id22 -->
Atlas A2 products: support the collection of NIC and ROCE.
<!-- end id22 -->

<!-- npu="A3" id23 -->
Atlas A3 products: support collection of NIC and ROCE.
<!-- end id23 -->

<!-- npu="950" id24 -->
Ascend 950PR&950DT products: support collection of UB bandwidth data.
<!-- end id24 -->

### sys\_interconnection\_freq

Collection frequency of collective communication bandwidth data (HCCS), collective communication hardware acceleration unit (CCU) bandwidth data, SIO data, PCIe data, and UB bandwidth data, as well as collection frequency of inter-chip transmission bandwidth information. Range: \[1,50\]; unit: Hz.

<!-- npu="910" id25 -->
- Atlas training products: support collection of HCCS and PCIe data.
<!-- end id25 -->

<!-- npu="910b" id26 -->
- Atlas A2 products: support collection of HCCS, PCIe data, and inter-chip transmission bandwidth information.
<!-- end id26 -->

<!-- npu="A3" id27 -->
- Atlas A3 products: support collection of HCCS, PCIe data, inter-chip transmission bandwidth information, and SIO data.
<!-- end id27 -->

<!-- npu="950" id28 -->
- Ascend 950PR&950DT products: support collection of PCIe data, inter-chip transmission bandwidth information, CCU bandwidth data, SIO data, and UB bandwidth data.
<!-- end id28 -->

### dvpp\_freq

DVPP collection frequency. Range \[1,100\], in Hz.

### instr\_profiling

Switch for collecting bandwidth and latency data of AI Core and AI Vector. Supported only in single-operator scenarios. The value can be on or off, and the default is off.

<!-- npu="910" id29 -->
- Atlas training products: This function is not supported.
<!-- end id29 -->

<!-- npu="910b" id30 -->
- Atlas A2 products: This switch is not supported. This function is controlled by instr\_profiling\_freq.
<!-- end id30 -->

<!-- npu="A3" id31 -->
- Atlas A3 products: This switch is not supported. This function is controlled by instr\_profiling\_freq.
<!-- end id31 -->

<!-- npu="950" id32 -->
- Ascend 950PR&950DT products: Supported. However, the statistics may be inaccurate because the statistical time of the last instruction segment is excessively long. You are advised to use the msprof op method for collection.
<!-- end id32 -->

### instr\_profiling\_freq

Switch for collecting the bandwidth and latency of AI Core and AI Vector. Configuring the collection frequency enables the related collection capability. This switch is supported only in single-operator scenarios. The value range is \[300,30000\], in Hz.

<!-- npu="910" id33 -->
- Atlas training products: This function is not supported.
<!-- end id33 -->

<!-- npu="910b" id34 -->
- Atlas A2 products: Supported.
<!-- end id34 -->

<!-- npu="A3" id35 -->
- Atlas A3 products: Supported.
<!-- end id35 -->

<!-- npu="950" id36 -->
- Ascend 950PR&950DT products: This switch is not supported. This function is controlled by instr\_profiling.
<!-- end id36 -->

### host\_sys

Switch for Host-side performance data collection. The value can be one or more of the following options. Separate multiple options with commas (,), for example, "host\_sys": "cpu,mem".

- cpu: CPU utilization rate at the process level.
- mem: Memory utilization rate at the process level.
- disk: Disk I/O utilization rate at the process level. To collect Host-side disk performance data, install the third-party open-source tool iotop. To collect osrt performance data, install the third-party open-source tools perf and ltrace.
- network: Network I/O utilization rate at the system level.
- osrt: syscall and pthreadcall at the process level.

### host\_sys\_usage

Collects CPU and memory data of the Host-side system and all processes. The value can be cpu or mem, or both. When multiple values are selected, separate them with English commas.

### host\_sys\_usage\_freq

Configures the collection frequency of CPU and memory data of the Host-side system and all processes. The value range is \[1,50\], the default is 50, and the unit is Hz.

> [!NOTE] Note
>
>- In scenarios other than the dynamic shape scenario, fp\_point and bp\_point are automatically configured and do not need to be manually configured by users. In the dynamic shape scenario, automatic configuration of fp/bp is not supported, and users need to set them manually.
>- Online inference supports task\_trace and aicpu, but does not support training\_trace.

## Configuration Example

```sh
export PROFILING_OPTIONS='{"output":"/tmp/profiling","training_trace":"on","task_trace":"on","fp_point":"","bp_point":"","aic_metrics":"PipeUtilization"}'
```

## Usage Constraints

- This environment variable applies only to TensorFlow training or online inference scenarios.
- Before using this environment variable, enable the Profiling collection function through the environment variable PROFILING\_MODE.

## Supported Models

<!-- npu="910" id1 -->
Atlas training products
<!-- end id1 -->

<!-- npu="310p" id2 -->
Atlas inference products
<!-- end id2 -->

<!-- npu="910b" id3 -->
Atlas A2 products
<!-- end id3 -->

<!-- npu="A3" id4 -->
Atlas A3 products
<!-- end id4 -->

<!-- npu="950" id5 -->
Ascend 950PR&950DT products
<!-- end id5 -->
