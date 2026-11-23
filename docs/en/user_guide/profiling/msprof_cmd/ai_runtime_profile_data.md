# Collecting AI Task Runtime Performance Data

<!-- md-trans-meta sourceCommit=3c4ea0bb0691e4727713884a46295d73c956022e translatedAt=2026-11-16T08:56:57.962Z pushedAt=2026-11-17T01:01:09.522Z nl=2 -->

## Description

msprof supports collecting performance data related to AI task runtime. After collection, it can automatically parse the performance data and write the files to disk.

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
## Command Format

Log in to the runtime environment and run the following command in any directory.

```sh
msprof [options] <app>
```

app is mandatory. For details about the related parameters, see [app Parameters](general_collect_commands.md#app-parameters). For details about the options parameters, see [Parameters](#parameters).
<!-- end id1 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00001 -->

## Parameters

### ascendcl

--ascendcl=<ascendcl-value\>: Optional. Controls the switch for collecting ACL API performance data. The value can be on or off, and the default value is on. It collects ACL API performance data, including the latency of synchronous and asynchronous memory copy between the Host and Device and between Devices.

<!-- npu="950,A3,910b,910,310p,310b" id29 -->
### model-execution

--model-execution=<model-execution-value\>: Optional. Controls the collection switch for GE model execution performance data. The value can be on or off, and the default value is off. This switch will be deprecated in later versions. Use the --task-time switch to control the collection of related data.
<!-- end id29 -->

### runtime-api

--runtime-api=<runtime-api-value\>: Optional. Controls the performance data collection switch for runtime API. The value can be **on** or **off**, and the default value is **off**. It can collect runtime API performance data, including the synchronous and asynchronous memory copy latency between the host and device and between devices.

<!-- npu="950,A3,910b,910,310p,310b" id28 -->
### hccl

--hccl=<hccl-value\>: Optional. Controls the communication data collection switch. The value can be on or off, and the default value is off. This data is generated only in multi-card, multi-node, or cluster scenarios. This switch will be deprecated in later versions. Use the --task-time switch to control the collection of related data.
<!-- end id28 -->

### task-time

--task-time=<task-time-value\>: optional. Controls the switch for collecting the delivery time and execution time of operators. Outputs the related time-consuming data to files such as task\_time, op\_summary, and op\_statistic. Configuration values:

- l0: Collect operator dispatch time and operator execution time data. Compared with l1, since basic operator information data is not collected, the performance overhead during collection is lower, allowing more accurate statistics of the related time-consuming data.
- l1: collects the delivery time, execution time, and basic information of operators, providing more comprehensive performance analysis data. This parameter supports collecting data of collective communication operators.
- l2: collects the delivery time, execution time, and basic information (including attr information) of operators, providing more comprehensive performance analysis data. This parameter supports collecting data of collective communication operators.
- l3: collects PyPTO operator performance data. This is a trial feature that may change in later versions and is not supported in production environments.
- on: enables collection. This is the default value and has the same effect as l1.
- off: Disable.

<!-- npu="950,A3,910b,910,310p,310b" id2 -->
### aicpu

--aicpu=<aicpu-value\>: Optional. Collects detailed information about AICPU operators, such as computation time and data copy time. The value can be on or off, and the default value is off.
<!-- end id2 -->

### ai-core

--ai-core=<aicore-value\>: Optional. AI Core data collection switch. The value can be on or off. When --task-time is set to on or l1, the default value is on. When --task-time is set to off or l0, the default value is off.

### aic-mode

--aic-mode=<aic-mode-value\>: Optional. Specifies the collection type of AI Core hardware. The value can be task-based or sample-based. This parameter can be configured only when --ai-core is set to on. task-based collects performance data at the task granularity, and sample-based collects performance data at a fixed time interval.

When collecting performance data of AI tasks, you are advised to use task-based. If this parameter is not configured, task-based is used by default.

### aic-freq

--aic-freq=<aic-freq-value\>: Optional. Sampling frequency in the sample-based scenario. Default value is 100, with a scope of 1\~100, in Hz. The configuration prerequisite for this parameter is that the --ai-core parameter is set to on.

### aic-metrics

--aic-metrics=<aic-metrics-value\>: Optional. AI Core performance metric collection items. This parameter can be configured only when --ai-core is set to on. The values are as follows:

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
  - Atlas 200I/500 A2 inference products: Not supported
    <!-- end id9 -->
    <!-- npu="310p" id10 -->
  - Atlas inference products: Not supported
    <!-- end id10 -->
    <!-- npu="910" id11 -->
  - Atlas training products: Not supported
    <!-- end id11 -->
    <!-- npu="950" id12 -->
  - Ascend 950PR&950DT products: Not supported
    <!-- end id12 -->

Default:

<!-- npu="310b" id13 -->
- Atlas 200I/500 A2 inference products: PipelineExecuteUtilization
<!-- end id13 -->
<!-- npu="310p" id14 -->
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

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00002 -->

Supports customizing the registers to be collected, for example: --aic-metrics=Custom:0x49,0x8,0x15,0x1b,0x64,0x10. The Custom field indicates a custom type, configured with specific register values, in the range \[0x1, 0x7FFFFFFF\]. Not all possible values have corresponding PMU registers. If a configured value has no corresponding PMU register, the collection result may be 0. The number of configured registers cannot exceed 8, and registers are separated by ",". Register values support hexadecimal or decimal.

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00003 -->

### sys-hardware-mem

--sys-hardware-mem=<sys-hardware-mem-value\>: Optional. Collection switch for the on-chip memory read/write rate, QoS transmission bandwidth, LLC L3 cache bandwidth, accelerator bandwidth, SoC transmission bandwidth, and component memory usage. The value can be on or off, and the default is off. The collection content varies slightly by model. The actual result prevails.

It is known that collecting memory data in an environment with glibc earlier than 2.34 may trigger a known glibc [Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329). This issue can be resolved by upgrading the glibc version of the environment.

<!-- npu="950,A3,910b,910,310p,310b" id30 -->

### sys-hardware-mem-freq

--sys-hardware-mem-freq=<sys-hardware-mem-freq-value\>: Optional. Collection frequency of --sys-hardware-mem. Range: \[1,100\]. Default value: 50. Unit: Hz.

<!-- npu="950" id19 -->
For Ascend 950PR&950DT products, the maximum collection frequency supported by QoS and SoC is 10000, while the maximum collection frequency supported by other collection items remains 100. If the configured value exceeds the range, other collection items are collected at the maximum collection frequency of 100.
<!-- end id19 -->

To set this parameter, set `--sys-hardware-mem` to on.

<!-- npu="A3,910b,310b" id20 -->
For the following models, after the collection task ends, you are not advised to change the collection frequency. Otherwise, data may be lost.
<!-- end id20 -->
<!-- npu="310b" id21 -->
- Atlas 200I/500 A2 inference products
<!-- end id21 -->
<!-- npu="910b" id22 -->
- Atlas A2 products
<!-- end id22 -->
<!-- npu="A3" id23 -->
- Atlas A3 products
<!-- end id23 -->
<!-- end id30 -->
<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id1 -->
### l2

--l2=<l2-value\>: Optional. Collects the hit rates of the L2 cache and TLB page table cache. The value can be on or off, and the default value is off. If Profiling is enabled during the model execution phase in the aclgraph scenario, this collection item does not take effect.

<!-- npu="910b" id24 -->
- Atlas A2 products: To analyze the number of times the AI Core hits L2, it is recommended to use --aic-metrics=L2Cache.
<!-- end id24 -->
<!-- npu="A3" id25 -->
- Atlas A3 products: To analyze the number of times the AI Core hits L2, you are advised to use --aic-metrics=L2Cache.
<!-- end id25 -->

### ge-api

--ge-api=<ge-api-value\>: Optional. Collects the time-consuming data of dynamic shape operators during the Host scheduling phase. The related data is generated in the msprof\_\*.json and api\_statistic\_\*.csv files. Value:

- off: Disables collection. The default value is off.
- l0: Collects the time-consuming data of dynamic shape operators in the main phases of Host scheduling, enabling more accurate statistics of the related time-consuming data.
- l1: Collects more fine-grained time-consuming data of dynamic shape operators during the Host scheduling phase, providing more comprehensive performance analysis data.

### task-memory

--task-memory=<task-memory-value\>: Optional. Collection switch for CANN operator-level memory usage, used to optimize memory usage. Values:

- on: Enable
- off (default): Disable

In the graph mode single-operator scenario, the operator memory size and lifecycle information is collected in GE component dimension and operator dimension (GE component memory is not collected in the single-operator API execution scenario). In the static graph and static subgraph scenarios, the operator memory size and lifecycle information is collected in operator dimension.

### aicore-shape

--aicore-shape=<aicore-shape-value\>: Optional. Collection switch for the Shape data of CANN-layer operators. It takes effect only when --task-time is set to l0. Value:

- on: Enable
- off (default): Disable

<!-- npu="950" id26 -->

### task-block

--task-block=<task-block-value\>: Optional. Collects block-level profiling data.

This parameter is supported only by the following models:

Ascend 950PR&950DT products: on or off can be selected. The default value is off.
<!-- end id26 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00005 -->

<!-- npu="950,A3,910b,910,310p,310b" id27 -->

## Usage Example

Log in to the running environment and run the following command in any directory:

```sh
msprof --output=/home/projects/output --ascendcl=on --runtime-api=on --task-time=on --aicpu=on --ai-core=on /home/projects/MyApp/out/main
```

In the Ascend EP scenario, a PROF_XXX directory is generated in the directory specified by --output to store the automatically parsed performance data. For details about the result files, see [Performance Data File Reference](https://gitcode.com/Ascend/msprof/blob/master/docs/en/user_guide/profile_data_file_references.md).

In the Ascend RC scenario, a PROF_XXX directory is generated in the directory specified by --output. The files in this directory cannot be viewed without parsing. You need to upload the PROF_XXX directory to the development environment for data parsing. For details, see [Parsing, Querying, and Exporting Performance Data Using the msprof Command](https://gitcode.com/Ascend/msprof/blob/master/docs/en/user_guide/msprof_parsing_instruct.md).
<!-- end id27 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00004 -->
