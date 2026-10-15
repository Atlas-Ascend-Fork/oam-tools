# Profiling options参数解释

- output：Profiling采集结果文件保存路径。支持配置绝对路径或相对路径（相对执行命令行时的当前路径）。路径中不能包含特殊字符："\\n"、"\\f"、"\\r"、"\\b"、"\\t"、"\\v"、"\\u007F"。
  - 绝对路径配置以“/”开头，例如：/home/output。
  - 相对路径配置直接以目录名开始，例如：output。
  - 该参数优先级高于ASCEND\_WORK\_PATH。
  - 该路径无需用户提前创建，采集过程中会自动创建。

- storage\_limit：指定落盘目录允许存放的最大文件容量。当Profiling数据文件在磁盘中即将占满本参数设置的最大存储空间或剩余磁盘总空间即将被占满时（总空间剩余<=20MB），则将磁盘内最早的文件进行老化删除处理。

    范围\[200, 4294967295\]，单位为MB，设置该参数时必须带单位，例如200MB。

    未配置本参数时，采集前，如果磁盘可用空间小于20MB时，则不落盘数据。

- training\_trace：采集迭代轨迹数据开关，即训练任务及AI软件栈的软件信息，实现对训练任务的性能分析，重点关注前后向计算和梯度聚合更新等相关数据。当采集正向和反向算子数据时该参数必须配置为on。
- task\_trace、task\_time：控制采集算子下发耗时、算子执行耗时和迭代轨迹数据的开关。涉及在task\_time、op\_summary、op\_statistic等文件中输出相关耗时数据。配置值：

  - on：开启，默认值，和配置为l1的效果一样。
  - off：关闭。
  - l0：采集算子下发耗时、算子执行耗时数据。与l1相比，由于不采集算子基本信息数据，采集时性能开销较小，可更精准统计相关耗时数据。
  - l1：采集算子下发耗时、算子执行耗时数据以及算子基本信息数据，提供更全面的性能分析数据。

    当训练profiling mode开启即采集训练Profiling数据时，配置task\_trace为on的同时training\_trace也必须配置为on。

- ge\_api：采集动态shape算子在Host调度阶段的耗时数据。取值：
  - off：关闭，默认为off。
  - l0：采集动态shape算子在Host调度主要阶段的耗时数据，可更精准统计相关耗时数据。
  - l1：采集动态shape算子在Host调度阶段更细粒度的耗时数据，提供更全面的性能分析数据。

- hccl：控制通信数据采集开关，可选on或off，默认为off。

    > [!NOTE]说明
    >此开关后续版本会废弃，请使用task\_time开关控制相关数据采集。

- aicpu：采集AICPU算子的详细信息，如：算子执行时间、数据拷贝时间等。取值on/off，默认为off。
- fp\_point：指定训练网络迭代轨迹正向算子的开始位置，用于记录前向计算开始时间戳。配置值为指定的正向第一个算子名字。用户可以在训练脚本中，通过tf.io.write\_graph将graph保存成.pbtxt文件，并获取文件中的name名称填入；也可直接配置为空，由系统自动识别正向算子的开始位置，例如"fp\_point":""。
- bp\_point：指定训练网络迭代轨迹反向算子的结束位置，记录后向计算结束时间戳，bp\_point和fp\_point可以计算出正反向时间。配置值为指定的反向最后一个算子名字。用户可以在训练脚本中，通过tf.io.write\_graph将graph保存成.pbtxt文件，并获取文件中的name名称填入；也可直接配置为空，由系统自动识别反向算子的结束位置，例如"bp\_point":""。
- aic\_metrics：AI Core性能指标采集项，取值如下：

  - ArithmeticUtilization：各种计算类指标占比统计。
  - PipeUtilization：计算单元和搬运单元耗时占比，该项为默认值。
  - Memory：外部内存读写类指令占比。
  - MemoryL0：内部L0内存读写类指令占比。
  - MemoryUB：内部UB内存读写类指令占比。
  - ResourceConflictRatio：流水线队列类指令占比。
  - L2Cache：读写L2 Cache命中次数和缺失后重新分配次数。

    <!-- npu="310p" id1 -->
    - Atlas推理系列产品不支持该参数。
    <!-- end id1 -->
    <!-- npu="910" id2 -->
    - Atlas训练系列产品不支持该参数。
    <!-- end id2 -->

  - MemoryAccess：算子在核上访存的带宽数据量。

    <!-- npu="310p" id3 -->
    - Atlas推理系列产品不支持该参数。
    <!-- end id3 -->
    <!-- npu="910" id4 -->
    - Atlas训练系列产品不支持该参数。
    <!-- end id4 -->
    <!-- npu="950" id5 -->
    - Ascend 950PR&950DT系列产品：不支持该参数。
    <!-- end id5 -->

    > [!NOTE]说明
    >支持自定义需要采集的寄存器，例如："aic\_metrics":"Custom:0x49,0x8,0x15,0x1b,0x64,0x10"。
    >- Custom字段表示自定义类型，配置为具体的寄存器值，范围\[0x1, 0x6E\]。
    >- 配置的寄存器数最多不能超过8个，寄存器通过“,”区分开。
    >- 寄存器的值支持十六进制或十进制。

- l2：控制L2 Cache和TLB页表缓存命中率的开关，可选on或off，默认为off。若在aclgraph场景执行模型阶段开启Profiling，则该采集项无法生效。
  <!-- npu="310p" id6 -->
  - Atlas推理系列产品：支持采集L2 Cache的命中率
  <!-- end id6 -->
  <!-- npu="910" id7 -->
  - Atlas训练系列产品：支持采集L2 Cache的命中率
  <!-- end id7 -->
  <!-- npu="910b" id8 -->
  - Atlas A2系列产品：支持采集L2 Cache和TLB页表缓存的命中率；分析AI Core命中L2次数推荐使用aic-metrics=L2Cache。
  <!-- end id8 -->
  <!-- npu="A3" id9 -->
  - Atlas A3系列产品：支持采集L2 Cache和TLB页表缓存的命中率；分析AI Core命中L2次数推荐使用aic-metrics=L2Cache。
  <!-- end id9 -->
  <!-- npu="950" id10 -->
  - Ascend 950PR&950DT系列产品：支持采集L2 Cache和TLB页表缓存的命中率；分析AI Core命中L2次数推荐使用aic-metrics=L2Cache。
  <!-- end id10 -->

- msproftx：控制msproftx用户和上层框架程序输出性能数据的开关，可选on或off，默认值为off。

    需要先在应用程序脚本中添加如下mstx API或msproftx API，推荐使用mstx API。

- runtime\_api：控制runtime API性能数据采集开关，可选on或off，默认为off。可采集runtime API性能数据，包括Host与Device之间、Device间的同步异步内存复制时延等。
- sys\_hardware\_mem\_freq：片上内存、QoS传输带宽、LLC三级缓存带宽、加速器带宽、SoC传输带宽、组件内存占用等的采集开关。不同产品的采集内容略有差异，请以实际结果为准。范围\[1,100\]，单位Hz。

    <!-- npu="950" id11 -->
    Ascend 950PR&950DT系列产品，Qos和SoC支持的采集频率最大支持配置10000，其他采集项支持的最大采集频率仍为100，若配置超出范围，其他采集项则按照最大采集频率100进行采集。<!-- end id11 -->

    已知在安装有glibc<2.34的环境上采集memory数据，可能触发glibc的一个已知[Bug 19329](https://sourceware.org/bugzilla/show_bug.cgi?id=19329)，通过升级环境的glibc版本可解决此问题。

    <!-- npu="A3,910b,310b" id12 -->
    对于以下型号，采集任务结束后，不建议用户增大采集频率，否则可能导致SoC传输带宽数据丢失。
    <!-- end id12 -->
    <!-- npu="310b" id13 -->
    - Atlas 200I/500 A2推理产品
    <!-- end id13 -->
    <!-- npu="910b" id14 -->
    - Atlas A2系列产品
    <!-- end id14 -->
    <!-- npu="A3" id15 -->
    - Atlas A3系列产品
    <!-- end id15 -->

- llc\_profiling：LLC Profiling采集事件，可以设置为：
  - read：读事件，三级缓存读速率，默认为read。
  - write：写事件，三级缓存写速率。

- sys\_io\_sampling\_freq：NIC、ROCE、UB带宽数据采集频率。范围\[1,100\]，单位Hz。

    <!-- npu="310p" id16 -->
    - Atlas推理系列产品：不支持该参数。
    <!-- end id16 -->
    <!-- npu="910b" id17 -->
    - Atlas A2系列产品：支持采集NIC、ROCE
    <!-- end id17 -->
    <!-- npu="A3" id18 -->
    - Atlas A3系列产品：支持采集NIC、ROCE
    <!-- end id18 -->
    <!-- npu="950" id19 -->
    - Ascend 950PR&950DT系列产品：支持采集UB带宽数据
    <!-- end id19 -->

- sys\_interconnection\_freq：集合通信带宽数据（HCCS）、集合通信硬件加速单元（CCU）带宽数据、SIO数据、PCIe数据、UB带宽数据采集频率以及片间传输带宽信息采集频率。范围\[1,50\]，单位Hz。

  <!-- npu="910" id20 -->
  - Atlas训练系列产品：支持采集HCCS、PCIe数据。
  <!-- end id20 -->
  <!-- npu="910b" id21 -->
  - Atlas A2系列产品：支持采集HCCS、PCIe数据、片间传输带宽信息。
  <!-- end id21 -->
  <!-- npu="A3" id22 -->
  - Atlas A3系列产品：支持采集HCCS、PCIe数据、片间传输带宽信息、SIO数据。
  <!-- end id22 -->
  <!-- npu="950" id23 -->
  - Ascend 950PR&950DT系列产品：支持采集PCIe数据、片间传输带宽信息、CCU带宽数据、SIO数据、UB带宽数据。
  <!-- end id23 -->

- dvpp\_freq：DVPP采集频率。范围\[1,100\]，单位Hz。
- instr\_profiling：AI Core和AI Vector的带宽和延时采集开关。仅单算子场景支持。取值on/off，默认为off。
  <!-- npu="910" id24 -->
  - Atlas训练系列产品：不支持该功能。
  <!-- end id24 -->
  <!-- npu="910b" id25 -->
  - Atlas A2系列产品：不支持该开关，通过instr\_profiling\_freq控制该功能。
  <!-- end id25 -->
  <!-- npu="A3" id26 -->
  - Atlas A3系列产品：不支持该开关，通过instr\_profiling\_freq控制该功能。<!-- end id26 -->
  <!-- npu="950" id27 -->
  - Ascend 950PR&950DT系列产品：支持，但可能会因最后一段指令的统计时间超长导致统计不准确，建议使用msprof op方式采集。
  <!-- end id27 -->

- instr\_profiling\_freq：AI Core和AI Vector的带宽和延时采集开关，配置了采集频率即开启相关采集能力。仅单算子场景支持。范围\[300,30000\]，单位Hz。
  <!-- npu="910" id28 -->
  - Atlas训练系列产品：不支持该功能。
  <!-- end id28 -->
  <!-- npu="910b" id29 -->
  - Atlas A2系列产品：支持。
  <!-- end id29 -->
  <!-- npu="A3" id30 -->
  - Atlas A3系列产品：支持。
  <!-- end id30 -->
  <!-- npu="950" id31 -->
  - Ascend 950PR&950DT系列产品：不支持该开关，通过instr\_profiling控制该功能。
  <!-- end id31 -->

- host\_sys：Host侧性能数据采集开关。取值如下，可选其中的一项或多项，选多项时用英文逗号隔开，例如"host\_sys": "cpu,mem"。
  - cpu：进程级别的CPU利用率。
  - mem：进程级别的内存利用率。
  - disk：进程级别的磁盘I/O利用率。采集Host侧disk性能数据需要安装第三方开源工具iotop，采集osrt性能数据需要安装第三方开源工具perf和ltrace。
  - network：系统级别的网络I/O利用率。
  - osrt：进程级别的syscall和pthreadcall。

- host\_sys\_usage：采集Host侧系统及所有进程的CPU和内存数据。取值包括cpu和mem，可选其中的一项或多项，选多项时用英文逗号隔开。
- host\_sys\_usage\_freq：配置Host侧系统和所有进程CPU、内存数据的采集频率。范围\[1,50\]，默认值50，单位Hz。
