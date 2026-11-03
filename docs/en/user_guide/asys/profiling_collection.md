# Profiling

## Description

Collect profile data.

<!-- npu="910,310p,310b" id1 -->
## Notes

Atlas 200I/500 A2 inference products,  Atlas inference products, and  Atlas training products  do not support performance data collection.
<!-- end id1 -->

## Command Format

```bash
asys profiling -r=aicore -p=time -d=deviceId --output=./ --aic_metrics=PipeUtilization
```

## Parameters

- **r**: This parameter is mandatory. It specifies the collection type. The value is an enumerated string. The options are listed below. Multiple enumerated types can be entered and separated by commas \(,\).
    - **dvpp**: collecting DVPP profile data, such as the execution time and usage.
    - **aicore**: collecting AI Core profile data, such as time consumptions and percentages of Cube and Vector instructions, and percentages of time taken by compute units and MTEs.
    - **os**: collecting system memory data, AI CPU usage, and Ctrl CPU usage.
    - **memory**: collecting memory read speed and bandwidth data, including on-chip memory and L3 cache.
    - **link**: collecting bandwidth data, such as collective communication bandwidth and PCIe bandwidth.
    - **power**: low-power data profiling.

- **p**: This parameter is mandatory. It specifies the collection interval, in seconds. The value ranges from 1 to 30 x 24 x 3600.
- **d**: This parameter is optional. It specifies the ID of the device to be operated. Only one device ID can be entered. The default value is 0.
- **output**: This parameter is optional. Its value is used as the prefix of the result output directory of the asys tool. That is, the final output directory is  **\{_output_\}/asys\_profiling\_result\__timestamp_**. If the command does not contain the  **output**  parameter, the output is stored in the command execution directory. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and an error is reported.

    For details about the result file, see "Profile Data File References" in  [Performance Tuning Tool](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/devaids/Profiling/atlasprofiling_16_0001.html).

- **aic\_metrics**: This parameter is optional. It specifies the AI Core performance monitor unit \(PMU\) type. This parameter is valid only when the collection type contains AI Cores.

    Value range:

    - **PipeUtilization**: percentages of time taken by compute units and MTEs. This is the default value.
    - **ArithmeticUtilization**: time consumptions and percentages of Cube and Vector instructions.
    - **Memory**: memory read/write bandwidth rate.
    - **MemoryL0**: L0 read/write bandwidth rate.
    - **MemoryUB**: UB read/write bandwidth rate.
    - **ResourceConflictRatio**: resource conflict ratio
    - **L2Cache**: L2 cache hit ratio.
    - MemoryAccess: bandwidth of the operator's memory access on AI Cores.

## Command Example and Output Description

```bash
# Collect AI Core profile data.
asys profiling -r=aicore -p=10 -d=0 --output=./ --aic_metrics=PipeUtilization
```

After the command is executed successfully, the following information is displayed and the collection result file is generated in the  **\{output\}/asys\_profiling\_result\_timestamp**  directory:

```text
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
