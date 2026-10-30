# Collecting AI Processor System Data

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:26:42.627Z pushedAt=2026-10-16T03:34:37.767Z -->

## Function

msprof supports collecting system data of AI processors and can automatically parse performance data and write the results to files after collection.

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
## Command Format

Log in to the running environment and run the following command.

```sh
msprof --output=<path> --sys-devices=<ID> --sys-period=<period> [options]
```

You can also collect system data while collecting performance data of AI tasks. In this case, you need to pass in the user program or execution script, and --output, --sys-devices, and --sys-period are optional:

```sh
msprof [options] <app>
```

- For details about the app parameters, see [app Parameters](general_collect_commands.md#app-parameters). For details about the options parameters, see [Parameters](#parameters).
- In the Ascend EP scenario, when you use the msprof CLI to collect inference profiling data of the entire network, if you configure the `--llc-profiling`, `--sys-cpu-profiling`, `--sys-profiling`, and `--sys-pid-profiling` collection items to collect the corresponding data, after the collection is complete, no data is generated for any collection item except `--sys-cpu-profiling`, which generates only TS CPU data. However, when no user program is passed in, data is generated for all the preceding collection items.
<!-- end id1 -->

<!-- npu="950,A3" id2 -->
- For the following models, the --sys-profiling, --sys-pid-profiling, and --sys-cpu-profiling parameters do not support collecting data from two Devices that share the same OS simultaneously. For example, if the Device is \[0,7\], but 0 and 1, 2 and 3, 4 and 5, and 6 and 7 share the OS respectively, then --sys-devices cannot be configured with 0 and 1, 2 and 3, 4 and 5, or 6 and 7 at the same time. You can configure 0, 2, 4, and 6, or 1, 3, 5, and 7.

  <!-- npu="A3" id3 -->
  - Atlas A3 products
  <!-- end id3 -->
  <!-- npu="950" id52 -->
  - Ascend 950PR & 950DT products
  <!-- end id52 -->
<!-- end id2 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00001 -->

## Parameters

### sys-period

--sys-period=<sys-period-value\>: This parameter is mandatory when no user program is passed in. It specifies the system sampling duration. The value range is greater than 0, with an upper limit of 30\*24\*3600, in seconds. This parameter does not take effect when a user program is passed in.

### sys-devices

--sys-devices=<sys-devices-value\>: This parameter is mandatory when no user program is passed in. Device ID. The value can be all or multiple device IDs separated by commas. This parameter does not take effect when a user program is passed in.

### ai-core

--ai-core=<aicore-value\>: Optional. Switch for AI Core data collection.

### aic-mode

--aic-mode=<aic-mode-value\>: Optional. Specifies the collection type of AI Core hardware. The value can be task-based or sample-based. This parameter takes effect only when `--ai-core` is set to on. task-based collects performance data at task granularity, while sample-based collects performance data at fixed time intervals.

When collecting AI processor system data, sample-based is recommended. If this parameter is not configured, sample-based is used by default.

### aic-freq

--aic-freq=<aic-freq-value\>: Optional. Sampling frequency in the sample-based scenario. Default Value: 100. Range: 1\~100. Unit: Hz. This parameter can be configured only when `--ai-core` is set to on.

### aic-metrics

aic-metrics=<aic-metrics-value\>: Optional. AI Core performance metric collection items. This parameter can be configured only when --ai-core is set to on. The values are as follows:

- ArithmeticUtilization: proportion of time consumed by compute instructions
- PipeUtilization: time consumed and proportion of compute and data movement instructions. This value is required when collecting `*_icache_miss_rate`.
- Memory: memory read/write bandwidth rate
- MemoryL0: L0 read/write bandwidth rate
- MemoryUB: UB read/write bandwidth rate
- ResourceConflictRatio: resource conflict proportion
- L2Cache: L2 Cache hit rate

    <!-- npu="310p" id5 -->
    - Atlas inference products: Not supported
    <!-- end id5 -->
- PipelineExecuteUtilization: time consumption and proportion of compute and data movement instructions. This value is required when collecting `fixpipe_exe_ratio`.

    <!-- npu="310p" id6 -->
    - Atlas inference products: Not supported
    <!-- end id6 -->
    <!-- npu="910" id7 -->
    - Atlas training products: Not supported
    <!-- end id7 -->
    <!-- npu="910b" id8 -->
    - Atlas A2 products: Not supported
    <!-- end id8 -->
    <!-- npu="A3" id9 -->
    - Atlas A3 products: Not supported
    <!-- end id9 -->
    <!-- npu="950" id10 -->
    - Ascend 950PR&950DT products: Not supported
    <!-- end id10 -->

- MemoryAccess:

    <!-- npu="310b" id11 -->
    - Atlas 200I/500 A2 inference products: Not supported
    <!-- end id11 -->
    <!-- npu="310p" id12 -->
    - Atlas inference products: Not supported
    <!-- end id12 -->
    <!-- npu="910" id13 -->
    - Atlas training products: Not supported
    <!-- end id13 -->
    <!-- npu="950" id14 -->
    - Ascend 950PR&950DT products: Not supported
    <!-- end id14 -->

Default Value:

<!-- npu="310b" id15 -->
- Atlas 200I/500 A2 inference products: PipelineExecuteUtilization
<!-- end id15 -->
<!-- npu="310b" id16 -->
- Atlas inference products: PipeUtilization
<!-- end id16 -->
<!-- npu="910" id17 -->
- Atlas training products: PipeUtilization
<!-- end id17 -->
<!-- npu="910b" id18 -->
- Atlas A2 products: PipeUtilization
<!-- end id18 -->
<!-- npu="A3" id19 -->
- Atlas A3 products: PipeUtilization
<!-- end id19 -->
<!-- npu="950" id20 -->
- Ascend 950PR&950DT products: PipeUtilization
<!-- end id20 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00002 -->

Supports customizing the registers to be collected, for example: --aic-metrics=Custom:0x49,0x8,0x15,0x1b,0x64,0x10. The Custom field indicates a custom type, configured with specific register values, in the range \[0x1, 0x7FFFFFFF\]. Not all possible values have corresponding PMU registers. If a configured value has no corresponding PMU register, the collection result may be 0. The number of configured registers cannot exceed 8, and registers are separated by ",". Register values support hexadecimal or decimal.

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00003 -->

### sys-hardware-mem

--sys-hardware-mem=<sys-hardware-mem-value\>: Optional. Collection switch for on-chip memory read/write rate, QoS transmission bandwidth, LLC L3 Cache bandwidth, accelerator bandwidth, SoC transmission bandwidth, component memory usage, and so on. The value can be on or off, and the default is off. The collection content varies slightly by model. To collect component memory data, you need to collect AI task performance data (that is, pass in a user program) to obtain specific performance data.

It is known that collecting memory data in an environment with glibc earlier than 2.34 may trigger a known glibc [Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329). This problem can be resolved by upgrading the glibc version of the environment.

<!-- npu="950,A3,910b,910,310p,310b" id60 -->
### sys-hardware-mem-freq

--sys-hardware-mem-freq=<sys-hardware-mem-freq-value\>: Optional. Collection frequency of --sys-hardware-mem. Range: \[1,100\]. Default value: 50. Unit: Hz.

<!-- npu="950" id21 -->
For Ascend 950PR&950DT products, the maximum collection frequency supported by QoS and SoC can be configured to 10000, while the maximum collection frequency supported by other collection items remains 100. If the configured value exceeds the range, other collection items are collected at the maximum collection frequency of 100.
<!-- end id21 -->
To set this parameter, set `--sys-hardware-mem` to on.
<!-- npu="A3,910b,310b" id22 -->
For the following models, after the collection task ends, you are not advised to change the collection frequency. Otherwise, data may be lost.
<!-- end id22 -->
<!-- npu="310b" id23 -->
- Atlas 200I/500 A2 inference product
<!-- end id23 -->
<!-- npu="910b" id24 -->
- Atlas A2 products
<!-- end id24 -->
<!-- npu="950,A3,910b,910,310p,310b" id25 -->
- Atlas A3 products
<!-- end id25 -->
<!-- end id60 -->
<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id3 -->
### llc-profiling

--llc-profiling=<llc-profiling-value\>: Optional. LLC Profiling collection event. `--sys-hardware-mem` must be set to on. The value can be:

- read: read event, L3 Cache read rate. The default value is read.
- write: write event, L3 Cache write rate.

### sys-cpu-profiling

--sys-cpu-profiling=<sys-cpu-profiling-value\>: Optional. Collection switch for CPUs (AI CPU, Ctrl CPU, etc.). The value can be on or off. Default Value: off.

### sys-cpu-freq

--sys-cpu-freq=<sys-cpu-freq-value\>: Optional. CPU collection frequency, ranging from \[1,50\], with a default value of 50 and a unit of Hz. To set this parameter, set `--sys-cpu-profiling` to on.

### sys-profiling

--sys-profiling=<sys-profiling-value\>: Optional. Collection switch for system CPU usage and system memory. The value can be on or off, and the default value is off.

After this command is used, the Profiling tool calls the Perf tool on the device side. Perf only collects the relevant performance data and cannot obtain other runtime information, so the actual risk is low.

### sys-sampling-freq

--sys-sampling-freq=<sys-sampling-freq-value\>: Optional. Collection frequency of system CPU usage and system memory, ranging from \[1,10\]. Default Value: 10, in Hz. To set this parameter, set `--sys-profiling` to on.

### sys-pid-profiling

--sys-pid-profiling=<sys-pid-profiling-value\>: Optional. Collection switch for the CPU usage and memory of all processes. The value can be on or off, and the default value is off.

### sys-pid-sampling-freq

--sys-pid-sampling-freq=<sys-pid-sampling-freq-value\>: Optional. Collection frequency of CPU usage and memory of all processes. The value range is \[1,10\], the default value is 10, and the unit is Hz. To set this parameter, set `--sys-pid-profiling` to on.

<!-- npu="950,A3,910b,910,310p,310b" id26 -->
### sys-io-profiling
<!-- end id26 -->

<!-- npu="950,A3,910b,910,310p,310b" id27 -->
--sys-io-profiling=<sys-io-profiling-value\>: Optional. Collection switch for NIC, ROCE, MAC, and UB bandwidth data. The value can be on or off, and the default value is off.
<!-- end id27 -->

<!-- npu="310b" id28 -->
- Atlas 200I/500 A2 Inference Product: NIC collection is supported only in RC scenarios. This parameter does not take effect in container scenarios.
<!-- end id28 -->
<!-- npu="310p" id29 -->
- Atlas inference products: This parameter is not supported.
<!-- end id29 -->
<!-- npu="910" id30 -->
- Atlas training products: NIC and ROCE collection is supported.
<!-- end id30 -->
<!-- npu="910b" id31 -->
- Atlas A2 products: NIC, ROCE, and MAC collection is supported.
<!-- end id31 -->
<!-- npu="A3" id32 -->
- Atlas A3 products: NIC, ROCE, and MAC collection is supported.
<!-- end id32 -->
<!-- npu="950" id33 -->
- Ascend 950PR & 950DT products: UB bandwidth data collection is supported.
<!-- end id33 -->

<!-- npu="950,A3,910b,910,310p,310b" id34 -->
### sys-io-sampling-freq
<!-- end id34 -->

<!-- npu="950,A3,910b,910,310p,310b" id35 -->
--sys-io-sampling-freq=<sys-io-sampling-freq-value\>: Optional. Bandwidth data collection frequency for NIC, ROCE, MAC, and UB. Range: \[1,100\]. Default Value: 100. Unit: Hz. To set this parameter, `--sys-io-profiling` must be set to on.
<!-- end id35 -->

<!-- npu="310p" id36 -->
The Atlas 200I/500 A2 Inference Product does not support this parameter.
<!-- end id36 -->

<!-- npu="950,A3,910b,910,310p,310b" id37 -->
### sys-interconnection-profiling

--sys-interconnection-profiling=<sys-interconnection-profiling-value\>: Optional. Collection switch for collective communication bandwidth data (HCCS), collective communication hardware acceleration unit (CCU) bandwidth data, PCIe data, inter-chip transmission bandwidth information, SIO data, and UB bandwidth data. The collection content varies slightly by model. The value can be on or off. Default Value: off.
<!-- end id37 -->

<!-- npu="310b" id38 -->
- This parameter is not supported on Atlas 200I/500 A2 inference products.
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
- Ascend 950PR&950DT products: support collection of CCU bandwidth data, PCIe data, inter-chip transmission bandwidth information, SIO data, and UB bandwidth data.
<!-- end id43 -->

<!-- npu="950,A3,910b,910,310p,310b" id44 -->
### sys-interconnection-freq

--sys-interconnection-freq=<sys-interconnection-freq-value\>: Optional. Collection frequency of collective communication bandwidth data (HCCS), collective communication hardware acceleration unit (CCU) bandwidth data, PCIe data, inter-chip transmission bandwidth information, SIO data, and UB bandwidth data. Range: \[1,50\]. Default value: 50. Unit: Hz.

<!-- npu="A3,910b" id57 -->
For the following models, after a collection task ends, you are not advised to change the collection frequency. Otherwise, data may be lost.

<!-- npu="910b" id58 -->
- Atlas A2 products
<!-- end id58 -->
<!-- npu="A3" id59 -->
- Atlas A3 products
<!-- end id59 -->
<!-- end id57 -->

To set this parameter, set the `--sys-interconnection-profiling` parameter to on.

<!-- npu="310b" id45 -->
This parameter is not supported by the Atlas 200I/500 A2 Inference Product.
<!-- end id45 -->

<!-- end id44 -->

### dvpp-profiling

--dvpp-profiling=<dvpp-profiling-value\>: Optional. DVPP Collection Switch. The value can be on or off. Default Value: off.

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id1 -->

### dvpp-freq

--dvpp-freq=<dvpp-freq-value\>: Optional. DVPP collection frequency. Range: \[1,100\]. Default Value: 50. Unit: Hz. To set this parameter, set `--dvpp-profiling` to on.

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id2 -->

<!-- npu="950,A3,910b" id46 -->
### instr-profiling

--instr-profiling=<instr-profiling-value\>: Optional. Collection switch for the bandwidth and latency of AI Core (including AIC and AIV cores). The value can be on or off, and the default value is off.

This parameter is supported only by the following models:

<!-- end id46 -->
<!-- npu="910b" id47 -->
- Atlas A2 products
<!-- end id47 -->
<!-- npu="A3" id48 -->
- Atlas A3 products
<!-- end id48 -->
<!-- npu="950" id49 -->
- Ascend 950PR&950DT products
<!-- end id49 -->

<!-- npu="950,A3,910b" id50 -->
Specific performance data can be collected only when AI task performance data is collected in the single-operator scenario (that is, when a user program is passed in).
<!-- end id50 -->
<!-- npu="950" id51 -->
For Ascend 950PR&950DT products, the statistics may be inaccurate because the statistical time of the last instruction segment is excessively long. It is recommended that you use the msprof op mode for collection.
<!-- end id51 -->

<!-- npu="A3,910b" id53 -->
### instr-profiling-freq

--instr-profiling-freq=<instr-profiling-freq-value\>: Optional. Sampling interval for the bandwidth and latency of the AI Core (including AIC and AIV cores). Range: \[300,30000\]. Default Value: 1000. Unit: cycle. The actual collection frequency of the system for AI Core bandwidth and latency = the processor operating frequency / the value of this parameter. For example, if the AI Core operating frequency is 5000 Hz and this parameter is set to 1000, the final Collection Frequency is 5 Hz, that is, five samples are collected per second.

Before using this parameter, set `--instr-profiling` to on.

This parameter is supported only by the following models:
<!-- end id53 -->

<!-- npu="910b" id54 -->
- Atlas A2 products
<!-- end id54 -->
<!-- npu="A3" id55 -->
- Atlas A3 products
<!-- end id55 -->

<!-- npu="950,A3,910b,910,310p,310b" id4 -->

<!-- npu="950" id61 -->
### sys-lp

--sys-lp=<sys-lp-value\>: Optional. Collects low-power data. The default value is on, indicating that the collection switch is enabled. You can manually set it to off to disable the collection. This parameter is supported only by the following models:

Ascend 950PR & 950DT products

### sys-lp-freq

--sys-lp-freq=<sys-lp-freq-value\>: Optional. Low-power data collection frequency. Value range: [1,100]. Default value: 100. Unit: Hz. This parameter is supported only by the following models:

Ascend 950PR&950DT products
<!-- end id61 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id4 -->
## Usage Example

Log in to the running environment and run the following command in any directory:

```sh
msprof --output=/home/projects/output --sys-devices=<ID> --sys-period=<period> --ai-core=on --sys-hardware-mem=on --sys-cpu-profiling=on --sys-profiling=on --sys-pid-profiling=on --dvpp-profiling=on
```

In the Ascend EP scenario, a PROF_XXX directory is generated in the directory specified by --output to store the automatically parsed performance data. For details about the result files, see [Performance Data File Reference](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/profile_data_file_references.md).

In the Ascend RC scenario, a PROF_XXX directory is generated in the directory specified by --output. The files in this directory cannot be viewed without parsing. You need to upload the PROF_XXX directory to the development environment for data parsing. For details, see [Parsing, Querying, and Exporting Performance Data Using the msprof Command](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/msprof_parsing_instruct.md).
<!-- end id4 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00004 -->
