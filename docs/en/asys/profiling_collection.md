# Performance Data Collection

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:45:12.728Z pushedAt=2026-10-15T09:26:03.165Z -->

## Description

Collects performance data.

<!-- npu="910,310p,310b" id1 -->
## Precautions

For Atlas 200I/500 A2 inference products, Atlas inference products, and Atlas training products, the performance data collection function is not supported.

<!-- end id1 -->
## Command Format

```bash
asys profiling -r=aicore -p=time -d=deviceId --output=./ --aic_metrics=PipeUtilization
```

## Description

- **r**: Mandatory parameter. Specifies the collection type, which is a string enumeration. The following values are supported. You can enter multiple enumeration types separated by commas (,).
    - dvpp: Collects dvpp performance data, such as execution time and utilization.
    - aicore: Collects AI Core performance data, such as the duration and proportion of cube and vector instructions, and the duration and proportion of compute units and data transfer units.
    - os: Collects system memory data, AI CPU utilization, Ctrl CPU utilization, and so on.
    - memory: Collects memory read rate and bandwidth data, including on-chip memory and L3 cache.
    - link: Collects bandwidth data, such as collective communication bandwidth and PCIe bandwidth.
    - power: Collects low-power data.

- **p**: Mandatory parameter. Specifies the collection interval in seconds. The minimum value is 1 and the maximum value is 30\*24\*3600.
- **d**: Optional parameter. Specifies the deviceId to be operated. Only a single deviceId is supported. The default value is 0.
- **output**: optional parameter. Its value is used as the path prefix of the result output directory of the asys tool, that is, the final output directory is \{output\}/asys\_profiling\_result\__timestamp_. If the output parameter is not specified in the command line, the output result is stored in the directory where the command is executed. If the value specified for output is empty, an invalid string, or the specified path directory has no write permission, or directory creation fails, the asys tool exits and reports an error.

    For details about the result files, see  [Performance Data File Reference](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/profile_data_file_references.md) in [*Performance Tuning Tool*](https://hiascend.com/document/redirect/CannCommunityToolProfiling).

- **aic\_metrics**: optional parameter. AI Core PMU (performance monitor unit) type. This parameter takes effect when the collection type includes aicore.

    Value range:

    - PipeUtilization: default value. Ratio of time consumed by compute units and transfer units.
    - ArithmeticUtilization: time consumed by and ratio of cube and vector type instructions.
    - Memory: memory read/write bandwidth rate.
    - MemoryL0: L0 read/write bandwidth rate.
    - MemoryUB: UB read/write bandwidth rate.
    - ResourceConflictRatio: resource conflict ratio.
    - L2Cache: L2Cache hit rate.
    - MemoryAccess: memory access bandwidth data volume of operators on the AI Core.

## Usage Examples and Output Description

```bash
# Collect AI Core performance data
asys profiling -r=aicore -p=10 -d=0 --output=./ --aic_metrics=PipeUtilization
```

After the command is executed successfully, the following information is displayed, and the collection result file is generated in the \{output\}/asys\_profiling\_result\_timestamp directory:

```bash
2025-11-27 20:15:45,141 [ASYS] [INFO]: asys start.
2025-11-27 20:15:45,141 [ASYS] [INFO]: Start run: msprof --output=./ --sys-period=10 --sys-devices=0 --ai-core=on --aic-mode=sample-based --aic-metrics=PipeUtilization, please wait about 10 seconds.
2025-11-27 20:16:04,335 [ASYS] [INFO]: Succeeded in running aicore profiling, [INFO] Start profiling....
[INFO] Start export data in PROF_000001_20251127201545157_03062849EPFNHDPB.
......
[INFO] Query all data in PROF_000001_20251127201545157_03062849EPFNHDPB done.
[INFO] Profiling finished.
[INFO] Process profiling data complete. Data is saved in /xxx/ascend_system_advisor/asys/asys_profiling_result_20251127201545110/PROF_000001_20251127201545157_03062849EPFNHDPB
2025-11-27 20:16:04,336 [ASYS] [INFO]: profiling task execute finish.
2025-11-27 20:16:04,336 [ASYS] [INFO]: asys finish.
```
