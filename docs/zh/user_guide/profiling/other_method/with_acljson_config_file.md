# 使用acl.json配置文件采集性能数据

离线推理场景下，用户可以在推理程序中调用acl.json文件，读取性能采集参数，从而自动采集性能原始数据。

采集性能原始数据成功后，可将采集的原始数据取到装有工具的开发环境上进行性能数据解析，展示性能数据解析结果。

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
解析操作请参见[使用msprof命令解析、查询与导出性能数据](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/msprof_parsing_instruct.md)，解析结果文件介绍请参见[性能数据文件参考](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/profile_data_file_references.md)。
<!-- end id1 -->

<!-- npu="950,A3,910b,910,310p,310b" id50 -->
本节仅介绍如何在推理程序中开启性能数据采集，推理应用完整开发过程请参见[《应用开发 \(C&C++\)》](https://hiascend.com/document/redirect/cannCommunityadevguide)。
<!-- end id50 -->

## 前提条件

- 在开启性能数据采集之前，请确保推理程序可正常执行。
- 务必调用`aclInit()`和`aclFinalize()`完成初始化和去初始化。

## 操作步骤

参考以下步骤完成acl.json文件配置，并完成应用工程编译和运行：

1. 打开`aclInit()`函数所在的推理应用工程代码文件，获取acl.json文件路径。

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

    > [!NOTE]说明
    >如果`aclInit()`初始化为空，则需要修改该函数，补充“步骤2”创建的acl.json文件路径。

2. 在查出的目录下修改acl.json文件（如不存在该文件，则需要新建，建议放在工程编译后的src目录下），添加Profiling相关配置，格式如下所示。

    ```cpp
    {
    "profiler": {
            "switch": "on",
            "output": "output"
            }
    }
    ```

   各参数解释请参考[参数说明](#参数说明)。

3. 配置acl.json文件完成后，请重新编译应用工程、并运行应用工程。
   <!-- npu="950,A3,910b,910,310p,310b" id51 -->
   应用开发详细内容请参考[《应用开发 \(C&C++\)》](https://hiascend.com/document/redirect/cannCommunityadevguide)
   <!-- end id51 -->

    “output”指定路径下生成Profiling性能原始数据，如下所示。

    ```sh
    total 16
    drwxr-x--- 4 . ./ Jan 29 01:47
    drwxr-xr-x 21 .. ../ Feb 9 20:24
    drwxr-x--- 3 PROF_000001_20220129014731273_KEDKPORHMAGPGDCC/ Jan 29 01:47
    ```

    > [!NOTE]说明
    >如果acl.json文件之前已经存在，此处仅是修改文件内容、添加Profiling相关配置，则不需要重新编译应用工程。
    >- 异步推理的场景下，应用工程的可执行文件会一直执行，不会调用Proﬁling的stop接口，所以，建议手动停止进程。否则，采集的性能原始数据有可能将磁盘存满，请确保预留足够的磁盘空间。
    >- 通过./app进程名方式运行依赖libslog.so的应用进程，不会产生调试日志。如果需要产生调试日志，需要使用pmupload工具启动应用进程，方法如下：<br>
    >   `pmupload app_path/app arg` <br>
    >   app\_path/app表示app进程路径及app名称；arg表示app进程的传入参数。

## 参数说明

### switch

Profiling开关，取值on或off。
<br>on表示开启Profiling，off表示关闭Profiling；如果缺失该参数或参数值不为on，则表示关闭Profiling。
<br>开启Profiling开关后自动采集Runtime等接口和Task Scheduler任务调度信息数据。

### output

Profiling性能数据落盘路径。未配置本参数时，性能数据默认落盘到应用工程可执行文件所在目录。
<br>路径中不能包含特殊字符：

```sh
"\n", "\\n", "\f", "\\f", "\r", "\\r", "\b", "\\b", "\t", "\\t", "\v", "\\v", "\u007F", "\\u007F", "\"", "\\\"", "'", "\'", "\\", "\\\\", "%", "\\%", ">", "\\>", "<", "\\<", "|", "\\|", "&", "\\&", "$", "\\$", ";", "\\;", "`", "\\`"
```

<br>Profiling采集结束后，在该目录下生成PROF开头目录，存放Profiling采集的性能原始数据。支持配置绝对路径或相对路径（相对执行命令行时的当前路径）：

- 绝对路径配置以“/”开头
- 相对路径配置直接以目录名开始，例如：output。
- 该参数指定的目录需要确保安装时配置的运行用户具有读写权限。如果该处设置的目录没有读写权限，默认存放采集结果数据到应用工程可执行文件所在目录（确保安装时配置的运行用户具有该目录的读写权限）。
- 该参数优先级高于ASCEND\_WORK\_PATH。

### storage\_limit

指定落盘目录允许存放的最大文件容量。当Profiling数据文件在磁盘中即将占满本参数设置的最大存储空间或剩余磁盘总空间即将被占满时（总空间剩余<=20MB），则将磁盘内最早的文件进行老化删除处理。
<br>范围\[200, 4294967295\]，单位为MB，例`storage_limit=200MB`，默认未配置本参数。
<br>配置本参数时，采集前，如果磁盘可用空间小于20MB时，则不落盘数据。

<!-- npu="950,A3,910b,910,310p,310b" id2 -->

### aicpu

 采集AI CPU算子的详细信息，如：算子执行时间、数据拷贝时间等。可选on或off，默认值为off。
 <!-- end id2 -->

### aic_metrics

AI Core性能指标采集项。task_time或task_trace配置为on、l1或l2时，该参数生效；task_time或task_trace配置为l0或off时，不执行该参数采集。取值包括：

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

<!-- @ref: oam-tools/res/docs/zh/profiling/other_method/with_acljson_config_file_res.md#id00001 -->

支持自定义需要采集的寄存器，例如："aic_metrics":"Custom:0x49,0x8,0x15,0x1b,0x64,0x10"。

- Custom字段表示自定义类型，配置为具体的寄存器值，范围[0x1, 0x7FFFFFFF]。并非所有的可取值都有对应的PMU寄存器，若配置的值无对应PMU寄存器，则采集结果可能为0。
- 配置的寄存器数最多不能超过8个，寄存器通过“,”区分开。
- 寄存器的值支持十六进制或十进制。

### l2

控制L2 Cache命中率和TLB页表缓存命中率采集开关，可选on或off，默认为off。若在aclgraph场景执行模型阶段开启Profiling，则该采集项无法生效。

<!-- npu="310b" id19 -->
- Atlas 200I/500 A2推理产品：支持采集L2 Cache的命中率；分析AI Core命中L2次数推荐使用aic-metrics=L2Cache。
<!-- end id19 -->
<!-- npu="310p" id20 -->
- Atlas推理系列产品：支持采集L2 Cache的命中率
<!-- end id20 -->
<!-- npu="910" id21 -->
- Atlas训练系列产品：支持采集L2 Cache的命中率
<!-- end id21 -->
<!-- npu="910b" id22 -->
- Atlas A2系列产品：支持采集L2 Cache和TLB页表缓存的命中率；分析AI Core命中L2次数推荐使用aic-metrics=L2Cache。
<!-- end id22 -->
<!-- npu="A3" id23 -->
- Atlas A3系列产品：支持采集L2 Cache和TLB页表缓存的命中率；分析AI Core命中L2次数推荐使用aic\_metrics=L2Cache。
<!-- end id23 -->
<!-- npu="950" id24 -->
- Ascend 950PR&950DT系列产品：支持采集L2 Cache和TLB页表缓存的命中率；分析AI Core命中L2次数推荐使用aic\_metrics=L2Cache。
<!-- end id24 -->

### hccl

控制通信数据采集开关。该数据只在多卡、多节点或集群场景下生成。

- json文件中配置该参数时，可选配on或off。
- json文件中未配置该参数时，默认为空，不采集；当task\_time设置为on时，该参数联动被设置为on。

此开关后续版本会废弃，请使用task\_time开关控制相关数据采集。

### task\_time

控制采集算子下发耗时和算子执行耗时的开关。涉及在task\_time、op\_summary、op\_statistic等文件中输出相关耗时数据。配置值：

- on：开启。默认为on。
- off：关闭。
  - l0：采集算子下发耗时、算子执行耗时数据。与l1相比，由于不采集算子基本信息数据，采集时性能开销较小，可更精准统计相关耗时数据。
  - l1：采集算子下发耗时、算子执行耗时数据以及算子基本信息数据，提供更全面的性能分析数据，和配置为on的效果一样。

### ge\_api

采集动态shape算子在Host调度阶段的耗时数据。取值：

- off：关闭，默认为off。
- l0：采集动态shape算子在Host调度主要阶段的耗时数据，可更精准统计相关耗时数据。
- l1：采集动态shape算子在Host调度阶段更细粒度的耗时数据，提供更全面的性能分析数据。

### ascendcl

 控制acl接口性能数据采集的开关，可选on或off，默认为on。可采集acl接口性能数据，包括Host与Device之间、Device间的同步异步内存复制时延等。

### runtime\_api

控制runtime API性能数据采集开关，可选on或off，默认为on。可采集runtime API性能数据，包括Host与Device之间、Device间的同步异步内存复制时延等。

### sys\_hardware\_mem\_freq

片上内存读写速率、QoS传输带宽、LLC三级缓存带宽、加速器带宽、SoC传输带宽、组件内存占用等的采集频率。不同产品的采集内容略有差异，请以实际结果为准。范围\[1,100\]，单位Hz。默认不采集。

<!-- npu="950" id25 -->
Ascend 950PR&950DT系列产品，QoS和SoC支持的采集频率最大支持配置10000，其他采集项支持的最大采集频率仍为100，若配置超出范围，其他采集项则按照最大采集频率100进行采集。
<!-- end id25 -->

已知在安装有glibc<2.34的环境上采集memory数据，可能触发glibc的一个已知[Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329)，通过升级环境的glibc版本可解决此问题。

<!-- npu="A3,910b,310b" id26 -->
对于以下型号，采集任务结束后，不建议用户增大采集频率，否则可能导致SoC传输带宽数据丢失。
<!-- end id26 -->
<!-- npu="310b" id27 -->
- Atlas 200I/500 A2推理产品
<!-- end id27 -->
<!-- npu="910b" id28 -->
- Atlas A2系列产品
<!-- end id28 -->
<!-- npu="A3" id29 -->
- Atlas A3系列产品
<!-- end id29 -->

### llc\_profiling

LLC Profiling采集事件。采集该数据需要设置sys\_hardware\_mem\_freq。取值包括：

- read：读事件，三级缓存读速率，默认为read。
- write：写事件，三级缓存写速率。

 <!-- npu="950,A3,910b,910,310p,310b" id30 -->

### sys\_io\_sampling\_freq

 NIC、ROCE、UB带宽数据采集频率。不同产品的采集内容略有差异，请以实际结果为准。范围\[1,100\]，单位Hz。
 <!-- end id30 -->

<!-- npu="310b" id31 -->
- Atlas 200I/500 A2推理产品：仅RC场景支持采集NIC，容器场景参数不生效
<!-- end id31 -->
<!-- npu="310p" id32 -->
- Atlas推理系列产品：不支持该参数。
<!-- end id32 -->
<!-- npu="910" id33 -->
- Atlas训练系列产品：支持采集NIC和ROCE
<!-- end id33 -->
<!-- npu="910b" id34 -->
- Atlas A2系列产品：支持采集NIC和ROCE
<!-- end id34 -->
<!-- npu="A3" id35 -->
- Atlas A3系列产品：支持采集NIC和ROCE
<!-- end id35 -->
<!-- npu="950" id36 -->
- Ascend 950PR&950DT系列产品：UB带宽数据
<!-- end id36 -->

<!-- npu="950,A3,910b,910,310p" id37 -->
### sys\_interconnection\_freq

集合通信带宽数据（HCCS）、集合通信硬件加速单元（CCU）带宽数据、SIO数据、PCIe数据采集频率，片间传输带宽信息、UB带宽数据采集频率。不同产品的采集内容略有差异，请以实际结果为准。范围\[1,50\]，单位Hz。默认不采集。
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
- Atlas A3系列产品：支持采集HCCS、PCIe数据、片间传输带宽信息、SIO数据
<!-- end id42 -->
<!-- npu="950" id43 -->
- Ascend 950PR&950DT系列产品：支持采集PCIe数据、片间传输带宽信息、SIO数据、CCU带宽数据、UB带宽数据
<!-- end id43 -->

<!-- npu="950,A3,910b,910,310p,310b" id44 -->

### dvpp\_freq

DVPP采集频率。范围\[1,100\]，单位Hz。
<!-- end id44 -->

<!-- npu="950" id45 -->

### instr\_profiling

AI Core和AI Vector的带宽和延时采集频率开关。

<br>仅单算子场景支持。仅Ascend 950PR&950DT系列产品支持。
<br>可能会因最后一段指令的统计时间超长导致统计不准确，建议使用msprof op方式采集。
<!-- end id45 -->

<!-- npu="A3,910b" id46 -->

### instr\_profiling\_freq

AI Core和AI Vector的带宽和延时采集频率，范围\[300,30000\]，单位Hz。
<br>仅单算子场景支持。
<br>仅以下型号支持该参数：

<!-- end id46 -->
<!-- npu="910b" id47 -->
- Atlas A2系列产品
<!-- end id47 -->
<!-- npu="A3" id48 -->
- Atlas A3系列产品
<!-- end id48 -->

<!-- npu="950,A3,910b,910,310p,310b" id52 -->
### host\_sys

Host侧性能数据采集开关，取值包括：

- cpu：进程级别的CPU利用率。
- mem：进程级别的内存利用率。
- disk：进程级别的磁盘I/O利用率。
- network：系统级别的网络I/O利用率。
- osrt：进程级别的syscall和pthreadcall。

可选其中的一项或多项，选多项时用英文逗号隔开，例如"host\_sys": "cpu,mem"。
<!-- end id52 -->

<!-- npu="950,A3,910b,910,310p,310b" id49 -->

### host\_sys\_usage

采集Host侧系统及所有进程的CPU和内存数据，取值包括cpu和mem。可选其中的一项或多项，选多项时用英文逗号隔开，例如"host\_sys\_usage": "cpu,mem"。
<!-- end id49 -->

### host\_sys\_usage\_freq

配置Host侧系统和所有进程CPU、内存数据的采集频率。范围\[1,50\]，默认值50，单位Hz。

### msproftx

控制msproftx用户和上层框架程序输出性能数据的开关，可选on或off，默认值为off。
<br>Profiling开启msproftx功能之前，需要在程序内调用msproftx相关接口来开启程序的Profiling数据流的输出，并开启记录应用程序执行期间特定事件发生的时间跨度。
