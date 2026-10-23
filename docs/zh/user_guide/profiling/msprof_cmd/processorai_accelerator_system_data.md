# 采集AI处理器系统数据

## 功能说明

msprof支持采集AI处理器的系统数据，并且在采集后可以自动进行性能数据解析和文件落盘。

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
## 命令格式

登录运行环境，执行如下命令。

```sh
msprof --output=<path> --sys-devices=<ID> --sys-period=<period> [options]
```

也可以在采集AI任务运行性能数据时，同时采集系统数据，此时需要传入用户程序或执行脚本，--output、--sys-devices、--sys-period非必选：

```sh
msprof [options] <app>
```

- app参数说明请参见[app参数说明](general_collect_commands.md#app参数说明)，options参数说明请参见[参数说明](#参数说明)。
- Ascend EP场景下，使用msprof命令行方式采集整网推理Profiling数据时，如果通过配置`--llc-profiling`、`--sys-cpu-profiling`、`--sys-profiling`和`--sys-pid-profiling`采集项采集相应数据，采集完成后，除`--sys-cpu-profiling`采集项仅生成TS CPU数据外，其余采集项均不会生成数据；但在不传入用户程序时，配置上述几个采集项均会有数据生成。
<!-- end id1 -->

<!-- npu="950,A3" id2 -->
- 对于以下型号，--sys-profiling、--sys-pid-profiling、--sys-cpu-profiling参数不支持同时采集共用OS的两个Device。例如：该Device为\[0,7\]，但0和1、2和3、4和5、6和7分别共用OS，那么此时--sys-devices则不能同时配置0和1、2和3、4和5、6和7，可以配置0、2、4、6或1、3、5、7。

  <!-- npu="A3" id56 -->
  - Atlas A3系列产品
  <!-- end id56 -->

  <!-- npu="950" id3 -->
  - Ascend 950PR&950DT系列产品
  <!-- end id3 -->
<!-- end id2 -->
<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00001 -->

## 参数说明

### sys-period

--sys-period=<sys-period-value\>：不传入用户程序时，该参数必选。系统的采样时长，取值范围大于0，上限为30\*24\*3600，单位s。传入用户程序时，该参数不生效。

### sys-devices

--sys-devices=<sys-devices-value\>：不传入用户程序时，该参数必选。设备ID。可以为all或多个设备ID（以逗号分隔）。传入用户程序时，该参数不生效。

### ai-core

--ai-core=<aicore-value\>：可选，AI Core数据采集开关。

### aic-mode

--aic-mode=<aic-mode-value\>：可选，AI Core硬件的采集类型，可选值task-based或sample-based。该参数配置前提是`--ai-core`参数设置为on。task-based是以task为粒度进行性能数据采集，sample-based是以固定的时间周期进行性能数据采集。

采集AI处理器系统数据时建议使用sample-based，如果不配置默认为sample-based。

### aic-freq

--aic-freq=<aic-freq-value\>：可选，sample-based场景下的采样频率，默认值100，范围1\~100，单位Hz。该参数配置前提是`--ai-core`参数设置为on。

### aic-metrics

aic-metrics=<aic-metrics-value\>：可选，AI Core性能指标采集项。该参数配置前提是--ai-core参数设置为on。取值包括：

- ArithmeticUtilization：计算类指令耗时占比
- PipeUtilization：计算类和搬运类指令耗时和占比，统计`*_icache_miss_rate`时，需要使用该取值。
- Memory：内存读写带宽速率
- MemoryL0：L0读写带宽速率
- MemoryUB：UB读写带宽速率
- ResourceConflictRatio：资源冲突占比
- L2Cache：L2 Cache命中率

    <!-- npu="310p" id5 -->
  - Atlas推理系列产品：不支持
    <!-- end id5 -->
- PipelineExecuteUtilization：计算类和搬运类指令耗时和占比，统计`fixpipe_exe_ratio`时，需要使用该取值。

    <!-- npu="310p" id6 -->
  - Atlas推理系列产品：不支持
    <!-- end id6 -->
    <!-- npu="910" id7 -->
  - Atlas训练系列产品：不支持
    <!-- end id7 -->
    <!-- npu="910b" id8 -->
  - Atlas A2系列产品：不支持
    <!-- end id8 -->
    <!-- npu="A3" id9 -->
  - Atlas A3系列产品：不支持
    <!-- end id9 -->
    <!-- npu="950" id10 -->
  - Ascend 950PR&950DT系列产品：不支持
    <!-- end id10 -->

- MemoryAccess：

    <!-- npu="310b" id11 -->
  - Atlas 200I/500 A2推理产品：不支持
    <!-- end id11 -->
    <!-- npu="310p" id12 -->
  - Atlas推理系列产品：不支持
    <!-- end id12 -->
    <!-- npu="910" id13 -->
  - Atlas训练系列产品：不支持
    <!-- end id13 -->
    <!-- npu="950" id14 -->
  - Ascend 950PR&950DT系列产品：不支持
    <!-- end id14 -->

默认值：

<!-- npu="310b" id15 -->
- Atlas 200I/500 A2推理产品：PipelineExecuteUtilization
<!-- end id15 -->
<!-- npu="310p" id16 -->
- Atlas推理系列产品：PipeUtilization
<!-- end id16 -->
<!-- npu="910" id17 -->
- Atlas训练系列产品：PipeUtilization
<!-- end id17 -->
<!-- npu="910b" id18 -->
- Atlas A2系列产品：PipeUtilization
<!-- end id18 -->
<!-- npu="A3" id19 -->
- Atlas A3系列产品：PipeUtilization
<!-- end id19 -->
<!-- npu="950" id20 -->
- Ascend 950PR&950DT系列产品：PipeUtilization
<!-- end id20 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00002 -->

支持自定义需要采集的寄存器，例如：--aic-metrics=Custom:0x49,0x8,0x15,0x1b,0x64,0x10。Custom字段表示自定义类型，配置为具体的寄存器值，范围\[0x1, 0x7FFFFFFF\]。并非所有的可取值都有对应的PMU寄存器，若配置的值无对应PMU寄存器，则采集结果可能为0。配置的寄存器数最多不能超过8个，寄存器通过“,”区分开。寄存器的值支持十六进制或十进制。

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00003 -->

### sys-hardware-mem

--sys-hardware-mem=<sys-hardware-mem-value\>：可选，片上内存读写速率、QoS传输带宽、LLC三级缓存带宽、加速器带宽、SoC传输带宽、组件内存占用等的采集开关，可选on或off，默认为off。不同型号的采集内容略有差异，请以实际结果为准。采集组件内存数据需要在采集AI任务性能数据（即传入用户程序）时才能采集到具体性能数据。

已知在安装有glibc<2.34的环境上采集memory数据，可能触发glibc的一个已知[Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329)，通过升级环境的glibc版本可解决此问题。

<!-- npu="950,A3,910b,910,310p,310b" id60 -->
### sys-hardware-mem-freq

--sys-hardware-mem-freq=<sys-hardware-mem-freq-value\>：可选，--sys-hardware-mem的采集频率，范围\[1,100\]，默认值为50，单位Hz。

<!-- npu="950" id21 -->
Ascend 950PR&950DT系列产品，QoS和SoC支持的采集频率最大支持配置10000，其他采集项支持的最大采集频率仍为100，若配置超出范围，其他采集项则按照最大采集频率100进行采集。
<!-- end id21 -->
设置该参数需要`--sys-hardware-mem`参数设置为on。
<!-- npu="A3,910b,310b" id22 -->
对于以下型号，采集任务结束后，不建议用户改变采集频率，否则可能导致数据丢失。
<!-- end id22 -->
<!-- npu="310b" id23 -->
- Atlas 200I/500 A2推理产品
<!-- end id23 -->
<!-- npu="910b" id24 -->
- Atlas A2系列产品
<!-- end id24 -->
<!-- npu="A3" id25 -->
- Atlas A3系列产品
<!-- end id25 -->
<!-- end id60 -->
<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id3 -->
### llc-profiling

--llc-profiling=<llc-profiling-value\>：可选，LLC Profiling采集事件，需`--sys-hardware-mem`设置为on。取值包括：

- read：读事件，三级缓存读速率，默认为read。
- write：写事件，三级缓存写速率。

### sys-cpu-profiling

--sys-cpu-profiling=<sys-cpu-profiling-value\>：可选，CPU（AI CPU、Ctrl CPU等）采集开关。可选on或off，默认值为off。

### sys-cpu-freq

--sys-cpu-freq=<sys-cpu-freq-value\>：可选，CPU采集频率，范围\[1,50\]，默认值为50，单位Hz。设置该参数需要`--sys-cpu-profiling`参数设置为on。

### sys-profiling

--sys-profiling=<sys-profiling-value\>：可选，系统CPU usage及System memory采集开关。可选on或off，默认值为off。

使用该命令后，Profiling工具会调用Device侧的Perf工具，Perf仅执行相关性能数据采集，无法获取其他运行态信息，实际风险小。

### sys-sampling-freq

--sys-sampling-freq=<sys-sampling-freq-value\>：可选，系统CPU usage及System memory采集频率，范围\[1,10\]，默认值为10，单位Hz。设置该参数需要`--sys-profiling`参数设置为on。

### sys-pid-profiling

--sys-pid-profiling=<sys-pid-profiling-value\>：可选，所有进程的CPU usage及所有进程的memory采集开关。可选on或off，默认值为off。

### sys-pid-sampling-freq

--sys-pid-sampling-freq=<sys-pid-sampling-freq-value\>：可选，所有进程的CPU usage及所有进程的memory采集频率，范围\[1,10\]，默认值为10，单位Hz。设置该参数需要`--sys-pid-profiling`参数设置为on。

<!-- npu="950,A3,910b,910,310p,310b" id26 -->
### sys-io-profiling
<!-- end id26 -->

<!-- npu="950,A3,910b,910,310p,310b" id27 -->
--sys-io-profiling=<sys-io-profiling-value\>：可选，NIC、ROCE、MAC、UB带宽数据采集开关。可选on或off，默认值为off。
<!-- end id27 -->

<!-- npu="310b" id28 -->
- Atlas 200I/500 A2推理产品：仅RC场景支持采集NIC，容器场景参数不生效
<!-- end id28 -->
<!-- npu="310p" id29 -->
- Atlas推理系列产品：不支持该参数。
<!-- end id29 -->
<!-- npu="910" id30 -->
- Atlas训练系列产品：支持采集NIC和ROCE
<!-- end id30 -->
<!-- npu="910b" id31 -->
- Atlas A2系列产品：支持采集NIC、ROCE和MAC
<!-- end id31 -->
<!-- npu="A3" id32 -->
- Atlas A3系列产品：支持采集NIC、ROCE和MAC
<!-- end id32 -->
<!-- npu="950" id33 -->
- Ascend 950PR&950DT系列产品：支持采集UB带宽数据
<!-- end id33 -->

<!-- npu="950,A3,910b,910,310p,310b" id34 -->
### sys-io-sampling-freq
<!-- end id34 -->

<!-- npu="950,A3,910b,910,310p,310b" id35 -->
--sys-io-sampling-freq=<sys-io-sampling-freq-value\>：可选，NIC、ROCE、MAC、UB带宽数据采集频率，范围\[1,100\]，默认值为100，单位Hz。设置该参数需要`--sys-io-profiling`参数设置为on。
<!-- end id35 -->

<!-- npu="310p" id36 -->
Atlas 200I/500 A2推理产品不支持该参数。
<!-- end id36 -->

<!-- npu="950,A3,910b,910,310p,310b" id37 -->
### sys-interconnection-profiling

--sys-interconnection-profiling=<sys-interconnection-profiling-value\>：可选，集合通信带宽数据（HCCS）、集合通信硬件加速单元（CCU）带宽数据、PCIe数据、片间传输带宽信息、SIO数据、UB带宽数据采集开关。不同型号的采集内容略有差异，请以实际结果为准。可选on或off，默认值为off。
<!-- end id37 -->

<!-- npu="310b" id38 -->
- Atlas 200I/500 A2推理产品不支持该参数。
<!-- end id38 -->
<!-- npu="310p" id39 -->
- Atlas推理系列产品：支持采集PCIe数据
<!-- end id39 -->
<!-- npu="910" id40 -->
- Atlas训练系列产品：支持采集HCCS、PCIe数据
<!-- end id40 -->
<!-- npu="910b" id41 -->
- Atlas A2系列产品：支持采集HCCS、PCIe数据、片间传输带宽信息
<!-- end id41 -->
<!-- npu="A3" id42 -->
- Atlas A3系列产品：支持采集HCCS、PCIe数据、片间传输带宽信息、SIO数据。
<!-- end id42 -->
<!-- npu="950" id43 -->
- Ascend 950PR&950DT系列产品：支持采集CCU带宽数据、PCIe数据、片间传输带宽信息、SIO数据、UB带宽数据。
<!-- end id43 -->

<!-- npu="950,A3,910b,910,310p,310b" id44 -->
### sys-interconnection-freq

--sys-interconnection-freq=<sys-interconnection-freq-value\>：可选，集合通信带宽数据（HCCS）、集合通信硬件加速单元（CCU）带宽数据、PCIe数据采集频率、片间传输带宽信息采集频率、SIO数据采集频率、UB带宽数据采集频率，范围\[1,50\]，默认值为50，单位Hz。

<!-- npu="A3,910b" id57 -->
对于以下型号，采集任务结束后，不建议用户改变采集频率，否则可能导致数据丢失。

<!-- npu="910b" id58 -->
- Atlas A2系列产品
<!-- end id58 -->
<!-- npu="A3" id59 -->
- Atlas A3系列产品
<!-- end id59 -->
<!-- end id57 -->

设置该参数需`--sys-interconnection-profiling`参数设置为on。

<!-- npu="310b" id45 -->
Atlas 200I/500 A2推理产品不支持该参数。
<!-- end id45 -->

<!-- end id44 -->

### dvpp-profiling

--dvpp-profiling=<dvpp-profiling-value\>：可选，DVPP采集开关，可选on或off，默认值为off。

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id1 -->

### dvpp-freq

--dvpp-freq=<dvpp-freq-value\>：可选，DVPP采集频率，范围\[1,100\]，默认值为50，单位Hz。设置该参数需要`--dvpp-profiling`参数设置为on。

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id2 -->

<!-- npu="950,A3,910b" id46 -->
### instr-profiling

--instr-profiling=<instr-profiling-value\>：可选，AI Core（包括AIC和AIV核）的带宽和时延采集开关，可选on或off，默认值为off。

仅以下型号支持该参数：

<!-- end id46 -->
<!-- npu="910b" id47 -->
- Atlas A2系列产品
<!-- end id47 -->
<!-- npu="A3" id48 -->
- Atlas A3系列产品
<!-- end id48 -->
<!-- npu="950" id49 -->
- Ascend 950PR&950DT系列产品
<!-- end id49 -->

<!-- npu="950,A3,910b" id50 -->
仅在单算子场景下采集AI任务性能数据（即传入用户程序）时才能采集到具体性能数据。
<!-- end id50 -->
<!-- npu="950" id51 -->
对于Ascend 950PR&950DT系列产品，可能会因最后一段指令的统计时间超长导致统计不准确，建议使用msprof op方式采集。
<!-- end id51 -->

<!-- npu="A3,910b" id53 -->
### instr-profiling-freq

--instr-profiling-freq=<instr-profiling-freq-value\>：可选，AI Core（包括AIC和AIV核）的带宽和时延采样间隔，范围\[300,30000\]，默认值为1000，单位cycle。系统对AI Core带宽和延时的真实采集频率=处理器的运行频率/该参数取值，假设AI Core运行频率为5000Hz，该参数取值为1000，则最终采集频率为5Hz，即每秒钟采集5次。

该参数使用前需要`--instr-profiling`设置为on。

仅以下型号支持该参数：
<!-- end id53 -->

<!-- npu="910b" id54 -->
- Atlas A2系列产品
<!-- end id54 -->
<!-- npu="A3" id55 -->
- Atlas A3系列产品
<!-- end id55 -->

<!-- npu="950,A3,910b,910,310p,310b" id4 -->

<!-- npu="950" id61 -->
### sys-lp

--sys-lp=<sys-lp-value\>：可选，采集低功耗数据。默认值为on，表示开启，可手动配置为off，表示关闭。仅以下型号支持该参数：

Ascend 950PR&950DT系列产品

### sys-lp-freq

--sys-lp-freq=<sys-lp-freq-value\>：可选，低功耗数据采集频率。取值范围：[1,100]，默认值：100，单位：Hz。仅以下型号支持该参数：

Ascend 950PR&950DT系列产品
<!-- end id61 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id4 -->
## 使用示例

登录运行环境，在任意路径下执行以下命令：

```sh
msprof --output=/home/projects/output --sys-devices=<ID> --sys-period=<period> --ai-core=on --sys-hardware-mem=on --sys-cpu-profiling=on --sys-profiling=on --sys-pid-profiling=on --dvpp-profiling=on
```

Ascend EP场景下，在--output指定的目录下生成PROF_XXX目录，存放自动解析后的性能数据，相关结果文件请参见[性能数据文件参考](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/zh/user_guide/profile_data_file_references.md)。

Ascend RC场景下，在--output指定的目录下生成PROF_XXX目录，该目录下的文件未经解析无法查看，您需要将PROF_XXX目录上传到开发环境进行数据解析，具体操作方法请参见[使用msprof命令解析、查询与导出性能数据](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/zh/user_guide/msprof_parsing_instruct.md)。
<!-- end id4 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/processorai_accelerator_system_data_res.md#id00004 -->
