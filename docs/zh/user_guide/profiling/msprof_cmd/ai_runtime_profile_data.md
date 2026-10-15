# 采集AI任务运行性能数据

## 功能说明

msprof支持采集AI任务运行时相关的性能数据，并且在采集后可以自动进行性能数据解析和文件落盘。

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
## 命令格式

登录运行环境，可在任意目录下执行以下命令。

```sh
msprof [options] <app>
```

app为必选，相关参数说明请参见[app参数说明](general_collect_commands.md#app参数说明)，options参数说明请参见[参数说明](#参数说明)。
<!-- end id1 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00001 -->

## 参数说明

### ascendcl

--ascendcl=<ascendcl-value\>：可选，控制acl接口性能数据采集的开关，可选on或off，默认为on。可采集acl接口性能数据，包括Host与Device之间、Device间的同步异步内存复制时延等。

<!-- npu="950,A3,910b,910,310p,310b" id29 -->
### model-execution

--model-execution=<model-execution-value\>：可选，控制ge model execution性能数据采集开关，可选on或off，默认为off。此开关后续版本会废弃，请使用--task-time开关控制相关数据采集。
<!-- end id29 -->

### runtime-api

--runtime-api=<runtime-api-value\>：可选，控制runtime API性能数据采集开关，可选on或off，默认为off。可采集runtime API性能数据，包括Host与Device之间、Device间的同步异步内存复制时延等。

<!-- npu="950,A3,910b,910,310p,310b" id28 -->
### hccl

--hccl=<hccl-value\>：可选，控制通信数据采集开关，可选on或off，默认为off。该数据只在多卡、多节点或集群场景下生成。此开关后续版本会废弃，请使用--task-time开关控制相关数据采集。
<!-- end id28 -->

### task-time

--task-time=<task-time-value\>：可选，控制采集算子下发耗时和算子执行耗时的开关。涉及在task\_time、op\_summary、op\_statistic等文件中输出相关耗时数据。配置值：

- l0：采集算子下发耗时、算子执行耗时数据。与l1相比，由于不采集算子基本信息数据，采集时性能开销较小，可更精准统计相关耗时数据。
- l1：采集算子下发耗时、算子执行耗时数据、算子基本信息数据，提供更全面的性能分析数据。该参数支持采集集合通信算子数据。
- l2：采集算子下发耗时、算子执行耗时数据、算子基本信息数据（包括attr信息），提供更全面的性能分析数据。该参数支持采集集合通信算子数据。
- l3：采集PyPTO算子性能数据。该特性为试用特性，后续版本可能会存在变更，不支持应用于生产环境中。
- on：开启，默认值，和配置为l1的效果一样。
- off：关闭。

<!-- npu="950,A3,910b,910,310p,310b" id2 -->
### aicpu

--aicpu=<aicpu-value\>：可选，采集AICPU算子的详细信息，如：计算耗时、数据拷贝耗时等。可选on或off，默认值为off。
<!-- end id2 -->

### ai-core

--ai-core=<aicore-value\>：可选，AI Core数据采集开关。取值可选on或off，--task-time配置为on、l1时，默认为on；--task-time配置为off、l0时，默认为off。

### aic-mode

--aic-mode=<aic-mode-value\>：可选，AI Core硬件的采集类型，可选值task-based或sample-based。该参数配置前提是--ai-core参数设置为on。task-based是以task为粒度进行性能数据采集，sample-based是以固定的时间周期进行性能数据采集。

采集AI任务性能数据时建议使用task-based，如果不配置默认为task-based。

### aic-freq

--aic-freq=<aic-freq-value\>：可选，sample-based场景下的采样频率，默认值100，范围1\~100，单位Hz。该参数配置前提是--ai-core参数设置为on。

### aic-metrics

aic-metrics=<aic-metrics-value\>：可选，AI Core性能指标采集项。该参数配置前提是--ai-core参数设置为on。取值包括：

- ArithmeticUtilization：计算类指令耗时占比
- PipeUtilization：计算类和搬运类指令耗时和占比，统计`*_icache_miss_rate`时，需要使用该取值。
- Memory：内存读写带宽速率
- MemoryL0：L0读写带宽速率
- MemoryUB：UB读写带宽速率
- ResourceConflictRatio：资源冲突占比
- L2Cache：L2 Cache命中率

    <!-- npu="310p" id3 -->
  - Atlas推理系列产品：不支持
    <!-- end id3 -->
- PipelineExecuteUtilization：计算类和搬运类指令耗时和占比，统计`fixpipe_exe_ratio`时，需要使用该取值。

    <!-- npu="310p" id4 -->
  - Atlas推理系列产品：不支持
    <!-- end id4 -->
    <!-- npu="910" id5 -->
  - Atlas训练系列产品：不支持
    <!-- end id5 -->
    <!-- npu="910b" id6 -->
  - Atlas A2系列产品：不支持
    <!-- end id6 -->
    <!-- npu="A3" id7 -->
  - Atlas A3系列产品：不支持
    <!-- end id7 -->
    <!-- npu="950" id8 -->
  - Ascend 950PR&950DT系列产品：不支持
    <!-- end id8 -->

- MemoryAccess：

    <!-- npu="310b" id9 -->
  - Atlas 200I/500 A2推理产品：不支持
    <!-- end id9 -->
    <!-- npu="310p" id10 -->
  - Atlas推理系列产品：不支持
    <!-- end id10 -->
    <!-- npu="910" id11 -->
  - Atlas训练系列产品：不支持
    <!-- end id11 -->
    <!-- npu="950" id12 -->
  - Ascend 950PR&950DT系列产品：不支持
    <!-- end id12 -->

默认值：

<!-- npu="310b" id13 -->
- Atlas 200I/500 A2推理产品：PipelineExecuteUtilization
<!-- end id13 -->
<!-- npu="310b" id14 -->
- Atlas推理系列产品：PipeUtilization
<!-- end id14 -->
<!-- npu="910" id15 -->
- Atlas训练系列产品：PipeUtilization
<!-- end id15 -->
<!-- npu="910b" id16 -->
- Atlas A2系列产品：PipeUtilization
<!-- end id16 -->
<!-- npu="A3" id17 -->
- Atlas A3系列产品：PipeUtilization
<!-- end id17 -->
<!-- npu="950" id18 -->
- Ascend 950PR&950DT系列产品：PipeUtilization
<!-- end id18 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00002 -->

支持自定义需要采集的寄存器，例如：--aic-metrics=Custom:0x49,0x8,0x15,0x1b,0x64,0x10。Custom字段表示自定义类型，配置为具体的寄存器值，范围\[0x1, 0x7FFFFFFF\]。并非所有的可取值都有对应的PMU寄存器，若配置的值无对应PMU寄存器，则采集结果可能为0。配置的寄存器数最多不能超过8个，寄存器通过“,”区分开。寄存器的值支持十六进制或十进制。

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00003 -->

### sys-hardware-mem

--sys-hardware-mem=<sys-hardware-mem-value\>：可选，片上内存读写速率、QoS传输带宽、LLC三级缓存带宽、加速器带宽、SoC传输带宽、组件内存占用等的采集开关，可选on或off，默认为off。不同型号的采集内容略有差异，请以实际结果为准。

已知在安装有glibc<2.34的环境上采集memory数据，可能触发glibc的一个已知[Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329)，通过升级环境的glibc版本可解决此问题。

<!-- npu="950,A3,910b,910,310p,310b" id30 -->

### sys-hardware-mem-freq

--sys-hardware-mem-freq=<sys-hardware-mem-freq-value\>：可选，--sys-hardware-mem的采集频率，范围\[1,100\]，默认值为50，单位Hz。

<!-- npu="950" id19 -->
Ascend 950PR&950DT系列产品，QoS和SoC支持的采集频率最大支持配置10000，其他采集项支持的最大采集频率仍为100，若配置超出范围，其他采集项则按照最大采集频率100进行采集。
<!-- end id19 -->

设置该参数需要`--sys-hardware-mem`参数设置为on。

<!-- npu="A3,910b,310b" id20 -->
对于以下型号，采集任务结束后，不建议用户改变采集频率，否则可能导致数据丢失。
<!-- end id20 -->
<!-- npu="310b" id21 -->
- Atlas 200I/500 A2推理产品
<!-- end id21 -->
<!-- npu="910b" id22 -->
- Atlas A2系列产品
<!-- end id22 -->
<!-- npu="A3" id23 -->
- Atlas A3系列产品
<!-- end id23 -->
<!-- end id30 -->
<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id1 -->
### l2

--l2=<l2-value\>：可选，采集L2 Cache、TLB页表缓存的命中率，可选on或off，默认为off。若在aclgraph场景执行模型阶段开启Profiling，则该采集项无法生效。

<!-- npu="910b" id24 -->
- Atlas A2系列产品：分析AI Core命中L2次数推荐使用--aic-metrics=L2Cache。
<!-- end id24 -->
<!-- npu="A3" id25 -->
- Atlas A3系列产品：分析AI Core命中L2次数推荐使用--aic-metrics=L2Cache。
<!-- end id25 -->

### ge-api

--ge-api=<ge-api-value\>：可选，采集动态Shape算子在Host调度阶段的耗时数据。相关数据生成在msprof\_\*.json和api\_statistic\_\*.csv文件中。取值：

- off：关闭，默认off。
- l0：采集动态Shape算子在Host调度主要阶段的耗时数据，可更精准统计相关耗时数据。
- l1：采集动态Shape算子在Host调度阶段更细粒度的耗时数据，提供更全面的性能分析数据。

### task-memory

--task-memory=<task-memory-value\>：可选，CANN算子级内存占用情况采集开关，用于优化内存使用。取值：

- on：开启
- off：关闭，默认为off

图模式单算子场景下，按照GE组件维度和算子维度采集算子内存大小及生命周期信息（单算子API执行场景不采集GE组件内存）；静态图和静态子图场景下，按照算子维度采集算子内存大小及生命周期信息。

### aicore-shape

--aicore-shape=<aicore-shape-value\>：可选，CANN层算子的Shape数据采集开关，仅在--task-time=l0时生效。取值：

- on：开启
- off：关闭，默认为off

<!-- npu="950" id26 -->

### task-block

--task-block=<task-block-value\>：可选，采集block级别的profiling数据。

仅以下型号支持该参数：

Ascend 950PR&950DT系列产品：可选on或off，默认值为off。
<!-- end id26 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00005 -->

<!-- npu="950,A3,910b,910,310p,310b" id27 -->

## 使用示例

登录运行环境，在任意路径下执行以下命令：

```sh
msprof --output=/home/projects/output --ascendcl=on --runtime-api=on --task-time=on --aicpu=on --ai-core=on /home/projects/MyApp/out/main
```

Ascend EP场景下，在--output指定的目录下生成PROF_XXX目录，存放自动解析后的性能数据，相关结果文件请参见[性能数据文件参考](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/profile_data_file_references.md)。

Ascend RC场景下，在--output指定的目录下生成PROF_XXX目录，该目录下的文件未经解析无法查看，您需要将PROF_XXX目录上传到开发环境进行数据解析，具体操作方法请参见[使用msprof命令解析、查询与导出性能数据](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/msprof_parsing_instruct.md)。
<!-- end id27 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/ai_runtime_profile_data_res.md#id00004 -->
