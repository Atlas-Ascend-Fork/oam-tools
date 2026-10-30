# Profiling options Parameter Description

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:16:24.759Z pushedAt=2026-10-15T11:15:53.920Z -->

- output: Path for saving Profiling collection result files. You can configure an absolute path or a relative path (relative to the current path when the command is executed). The path cannot contain the following special characters: "\\n", "\\f", "\\r", "\\b", "\\t", "\\v", "\\u007F".
  - An absolute path starts with "/", for example, /home/output.
  - A relative path starts directly with a directory name, for example, output.
  - This parameter has a higher priority than **ASCEND\_WORK\_PATH**.
  - This path does not need to be created by the user in advance. It is created automatically during collection.

- **storage\_limit**: Specifies the maximum file capacity allowed in the directory where data is written to disk. When the Profiling data files on the disk are about to occupy the maximum storage space set by this parameter, or the remaining total disk space is about to be fully occupied (remaining total space <= 20 MB), the earliest files on the disk are aged out and deleted.

    Range: \[200, 4294967295\], in MB. When setting this parameter, you must specify the unit, for example, 200MB.

    If this parameter is not configured, before collection, if the available disk space is less than 20 MB, data is not written to disk.

- **training\_trace**: Switch for collecting iteration trace data, that is, the software information of the training task and the AI software stack, to implement performance analysis of the training task, focusing on data such as forward and backward computation and gradient aggregation and update. When collecting forward and backward operator data, this parameter must be set to on.
- **task\_trace**, **task\_time**: switches that control the collection of operator dispatch latency, operator execution latency, and iteration trace data. The related latency data is output to files such as task\_time, op\_summary, and op\_statistic. Values:

  - **on**: enabled, the default value, with the same effect as **l1**.
  - **off**: disabled.
  - **l0**: collects operator dispatch latency and operator execution latency data. Compared with l1, because basic operator information data is not collected, the performance overhead during collection is lower, allowing more accurate statistics of the related latency data.
  - **l1**: collects operator dispatch latency, operator execution latency, and basic operator information data, providing more comprehensive performance analysis data.

    When training profiling mode is enabled, that is, when training Profiling data is collected, task\_trace must be set to on, and training\_trace must also be set to on.

- **ge\_api**: collects the latency data of dynamic shape operators during the Host scheduling phase. Values:
  - **off**: disabled, the default value.
  - **l0**: collects the latency data of dynamic shape operators in the main phases of Host scheduling, allowing more accurate statistics of the related latency data.
  - **l1**: collects more fine-grained latency data of dynamic shape operators during the Host scheduling phase, providing more comprehensive performance analysis data.

- **hccl**: Controls the switch for communication data collection. The value can be on or off, and the default is off.

    > [!NOTE] Note
    >This switch will be deprecated in later versions. Use the task\_time switch to control the collection of related data.

- aicpu: Collects detailed information about AICPU operators, such as operator execution time and data copy time. The value can be on or off, and the default is off.
- fp\_point: Specifies the start position of the forward operator in the training network iteration trace, and is used to record the start timestamp of forward computation. The configured value is the name of the first forward operator. In the training script, you can save the graph as a .pbtxt file through tf.io.write\_graph, obtain the name from the file, and fill it in. You can also leave it empty so that the system automatically identifies the start position of the forward operator, for example, "fp\_point":"".
- bp\_point: Specifies the end position of the backward operator in the training network iteration trace, and records the end timestamp of backward computation. bp\_point and fp\_point can be used to calculate the forward and backward time. The configured value is the name of the last backward operator. In the training script, you can save the graph as a .pbtxt file through tf.io.write\_graph, obtain the name from the file, and fill it in. You can also leave it empty so that the system automatically identifies the end position of the backward operator, for example, "bp\_point":"".
- aic\_metrics: AI Core performance metric collection item. The values are as follows:

  - ArithmeticUtilization: Statistics on the proportion of various computation metrics.
  - PipeUtilization: Proportion of time consumed by the compute unit and the transfer unit. This is the default value.
  - Memory: Proportion of external memory read/write instructions.
  - MemoryL0: Proportion of internal L0 memory read/write instructions.
  - MemoryUB: proportion of internal UB memory read/write instructions.
  - ResourceConflictRatio: proportion of pipeline queue instructions.
  - L2Cache: number of L2 cache read/write hits and reallocation count after misses.

    <!-- npu="310p" id1 -->
    - This parameter is not supported by Atlas inference products.
    <!-- end id1 -->
    <!-- npu="910" id2 -->
    - This parameter is not supported by Atlas training products.
    <!-- end id2 -->

  - MemoryAccess: bandwidth data volume of operator memory access on the core.

    <!-- npu="310p" id3 -->
    - This parameter is not supported by Atlas inference products.
    <!-- end id3 -->
    <!-- npu="910" id4 -->
    - This parameter is not supported by Atlas training products.
    <!-- end id4 -->
    <!-- npu="950" id5 -->
    - Ascend 950PR&950DT product series: this parameter is not supported.
    <!-- end id5 -->

    > [!NOTE] Note
    > Custom collection of registers is supported, for example: "aic\_metrics":"Custom:0x49,0x8,0x15,0x1b,0x64,0x10".
    > - The Custom field indicates a custom type, configured as a specific register value, in the range \[0x1, 0x6E\].
    > - A maximum of eight registers can be configured, separated by commas (,).
    > - Register values support hexadecimal or decimal format.

- l2: switch that controls the hit rate of L2 Cache and TLB page table cache. The value can be on or off, and the default value is off. If Profiling is enabled during the model execution phase in the aclgraph scenario, this collection item does not take effect.
  <!-- npu="310p" id6 -->
  - Atlas inference products: support collection of the L2 Cache hit rate.
  <!-- end id6 -->
  <!-- npu="910" id7 -->
  - Atlas training products: support collection of the L2 Cache hit rate.
  <!-- end id7 -->
  <!-- npu="910b" id8 -->
  - Atlas A2 products: support collection of the hit rate of L2 Cache and TLB page table cache. To analyze the number of AI Core hits on L2, aic-metrics=L2Cache is recommended.
  <!-- end id8 -->
  <!-- npu="A3" id9 -->
  - Atlas A3 products: support collection of the hit rate of L2 Cache and TLB page table cache. To analyze the number of AI Core hits on L2, aic-metrics=L2Cache is recommended.
  <!-- end id9 -->
  <!-- npu="950" id10 -->
  - Ascend 950PR&950DT products: support collection of the hit rate of L2 Cache and TLB page table cache. To analyze the number of AI Core hits on L2, aic-metrics=L2Cache is recommended.
  <!-- end id10 -->

- msproftx: switch that controls the output of performance data by msproftx users and upper-layer framework programs. The value can be on or off, and the default value is off.

    You need to first add the following mstx API or msproftx API to the application script. The mstx API is recommended.

- runtime\_api: switch that controls runtime API performance data collection. The value can be on or off, and the default value is off. It can collect runtime API performance data, including the latency of synchronous and asynchronous memory copy between the Host and Device and between Devices.
- sys\_hardware\_mem\_freq: collection switch for on-chip memory, QoS transmission bandwidth, LLC L3 cache bandwidth, accelerator bandwidth, SoC transmission bandwidth, and component memory usage. The collection content varies slightly by product. The actual result prevails. The range is \[1,100\], and the unit is Hz.

    <!-- npu="950" id11 -->
    For Ascend 950PR&950DT product series, the maximum collection frequency supported by Qos and SoC can be configured to 10000, while the maximum collection frequency supported by other collection items remains 100. If the configured value exceeds the range, other collection items are collected at the maximum collection frequency of 100.<!-- end id11 -->

    It is known that collecting memory data in an environment with glibc earlier than 2.34 may trigger a known glibc [Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329). This issue can be resolved by upgrading the glibc version of the environment.

    <!-- npu="A3,910b,310b" id12 -->
    For the following models, after a collection task ends, it is not recommended to increase the collection frequency. Otherwise, the SoC transmission bandwidth data may be lost.
    <!-- end id12 -->
    <!-- npu="310b" id13 -->
    - Atlas 200I/500 A2 inference product
    <!-- end id13 -->
    <!-- npu="910b" id14 -->
    - Atlas A2 product series
    <!-- end id14 -->
    <!-- npu="A3" id15 -->
    - Atlas A3 product series
    <!-- end id15 -->

- llc\_profiling: LLC Profiling collection event. It can be set to:
  - read: read event, L3 cache read rate. The default value is read.
  - write: write event, L3 cache write rate.

- sys\_io\_sampling\_freq: collection frequency of NIC, ROCE, and UB bandwidth data. Range \[1,100\], in Hz.

    <!-- npu="310p" id16 -->
    - Atlas inference series: This parameter is not supported.
    <!-- end id16 -->
    <!-- npu="910b" id17 -->
    - Atlas A2 series: Supports collection of NIC and ROCE.
    <!-- end id17 -->
    <!-- npu="A3" id18 -->
    - Atlas A3 series: Supports collection of NIC and ROCE.
    <!-- end id18 -->
    <!-- npu="950" id19 -->
    - Ascend 950PR&950DT series: Supports collection of UB bandwidth data.
    <!-- end id19 -->

- sys\_interconnection\_freq: Collection frequency of collective communication bandwidth data (HCCS), collective communication hardware acceleration unit (CCU) bandwidth data, SIO data, PCIe data, and UB bandwidth data, as well as inter-chip transmission bandwidth information collection frequency. Range \[1,50\], unit: Hz.

  <!-- npu="910" id20 -->
  - Atlas training series: Supports collection of HCCS and PCIe data.
  <!-- end id20 -->
  <!-- npu="910b" id21 -->
  - Atlas A2 series: Supports collection of HCCS, PCIe data, and inter-chip transmission bandwidth information.
  <!-- end id21 -->
  <!-- npu="A3" id22 -->
  - Atlas A3 series: Supports collection of HCCS, PCIe data, inter-chip transmission bandwidth information, and SIO data.
  <!-- end id22 -->
  <!-- npu="950" id23 -->
  - Ascend 950PR&950DT series: Supports collection of PCIe data, inter-chip transmission bandwidth information, CCU bandwidth data, SIO data, and UB bandwidth data.
  <!-- end id23 -->

- dvpp\_freq: DVPP collection frequency. Range \[1,100\], unit: Hz.
- instr\_profiling: Switch for collecting the bandwidth and latency of AI Core and AI Vector. Supported only in single-operator scenarios. The value can be on or off, and the default value is off.
  <!-- npu="910" id24 -->
  - Atlas training products: This function is not supported.
  <!-- end id24 -->
  <!-- npu="910b" id25 -->
  - Atlas A2 products: This switch is not supported. This function is controlled by instr\_profiling\_freq.
  <!-- end id25 -->
  <!-- npu="A3" id26 -->
  - Atlas A3 products: This switch is not supported. This function is controlled by instr\_profiling\_freq.<!-- end id26 -->
  <!-- npu="950" id27 -->
  - Ascend 950PR&950DT products: Supported. However, the statistics may be inaccurate because the statistical time of the last instruction segment may be excessively long. It is recommended to use the msprof op method for collection.
  <!-- end id27 -->

- instr\_profiling\_freq: Switch for collecting the bandwidth and latency of AI Core and AI Vector. Once the collection frequency is configured, the related collection capability is enabled. Supported only in single-operator scenarios. The range is \[300,30000\], in Hz.
  <!-- npu="910" id28 -->
  - Atlas training products: This function is not supported.
  <!-- end id28 -->
  <!-- npu="910b" id29 -->
  - Atlas A2 products: Supported.
  <!-- end id29 -->
  <!-- npu="A3" id30 -->
  - Atlas A3 products: Supported.
  <!-- end id30 -->
  <!-- npu="950" id31 -->
  - Ascend 950PR&950DT products: This switch is not supported. This function is controlled by instr\_profiling.
  <!-- end id31 -->

- host\_sys: switch for collecting Host-side performance data. The value can be one or more of the following, separated by commas when multiple values are selected, for example, "host\_sys": "cpu,mem".
  - cpu: CPU utilization at the process level.
  - mem: memory utilization at the process level.
  - disk: disk I/O utilization at the process level. To collect Host-side disk performance data, the third-party open-source tool iotop must be installed. To collect osrt performance data, the third-party open-source tools perf and ltrace must be installed.
  - network: network I/O utilization at the system level.
  - osrt: syscall and pthreadcall at the process level.

- host\_sys\_usage: collects CPU and memory data of the Host-side system and all processes. The value can be cpu and/or mem, separated by commas when multiple values are selected.
- host\_sys\_usage\_freq: configures the collection frequency of CPU and memory data of the Host-side system and all processes. The value range is \[1,50\], and the default value is 50, in Hz.
