# 参数说明

本节介绍HCCL Test性能测试工具执行时的相关参数说明。

## 命令格式

- 安装MPICH的场景

    ```bash
    mpirun [-f <hostfile>] -n <number> ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
    ```

- 安装Open MPI的场景

    ```bash
    mpirun [--prefix <mpi_install_path>] [-hostfile <hostfile>] -n <number> -x <env> [--allow-run-as-root] [--mca <key value>] ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
    ```

- mpirun后跟随的是MPI命令相关参数，MPI命令相关参数说明请参见[MPICH命令参数](#mpich命令参数)与[Open MPI命令参数](#open-mpi命令参数)。
- ./bin/&lt;executable_file\>后跟随的是HCCL Test工具相关参数，HCCL Test工具相关参数说明请参见[HCCL Test工具相关参数](#hccl-test工具相关参数)。

## MPICH命令参数

此处仅给出MPICH工具常见参数说明，更多参数介绍可参见[MPICH官方文档](https://www.mpich.org/)。

- **-f \<hostfile\>**：可选，Hostfile节点列表文件。

  单机场景下无需配置此文件；多机场景下，需要配置此文件。可配置为Hostfile文件的绝对路径，或相对于当前执行命令的相对路径。
- **-n \<number\>**：必选，需要启动的NPU总数，即节点数量 * 每个节点上参与训练的NPU个数。

## Open MPI命令参数

此处仅给出Open MPI工具常见参数说明，更多参数介绍可参见[open-mpi官方文档](https://www.open-mpi.org/doc/v4.1/man1/mpirun.1.php)。

- **--prefix \<mpi_install_path\>**：可选，配置Open MPI的安装路径。

  一般单机场景下无需配置此参数，多机场景下需要配置，否则可能会出现无法获取MPI库文件的问题。
- **-hostfile \<hostfile\>**：可选，指定Hostfile节点列表文件。

  单机场景下无需配置此文件；多机场景下，需要配置此文件。可配置为Hostfile文件的绝对路径，或相对于当前执行命令的相对路径。
- **-n \<number\>**：必选，设置需要启动的NPU总数，即节点数量 * 每个节点上参与训练的NPU个数。
- **-x \<env\>**：必选，指定需要传递给远程节点的环境变量名称。
- **--allow-run-as-root**：可选，允许mpirun使用root用户执行。
- **--mca \<key value\>**：可选，设置mca参数，Open MPI的设计以组件架构（MPI Component Architecture, MCA）为中心，可通过运行时在mpirun命令中设置mca参数来加载openmpi的各类组件模块，实现特定功能。

  常用的命令有：
  - --mca btl_tcp_if_include *<nic_name>*

    使用指定的网卡进行节点间通信，例如：

    ```text
    --mca btl_tcp_if_include eth0
    ```

  - --mca opal_set_max_sys_limits 1

    设置Open MPI运行时的系统限制（文件描述符数量等）沿用系统的ulimit配置，确保Open MPI进程执行时不会因为资源限制而出现问题。当集群中卡的数量较多时，建议增加此配置以避免资源不足。

## HCCL Test工具相关参数

- **./bin/\<executable_file\>**：必选，集合通信性能测试工具的执行命令。

  其中\<executable_file\>为集合通信性能测试工具的可执行文件，即支持的测试命令。

  HCCL Test工具支持的测试命令包括：broadcast_test，all_gather_test，all_gatherv_test，reduce_test，all_reduce_test，scatter_test，reduce_scatter_test，reduce_scatterv_test，alltoall_test，alltoallv_test，alltoallvc_test。

  > [!NOTE]说明
  > 各测试命令在不同产品上的支持情况，以对应通信算子接口的实际支持能力为准，详细可参见[通信算子接口](https://gitcode.com/cann/hccl/blob/master/docs/zh/api_ref/comm_op_interface/README.md)。

- **-p \<npus\>或--npus \<npus\>**：可选，单个计算节点上参与训练的NPU个数。

  默认为当前节点的NPU总数。若单个计算节点上参与训练的NPU个数小于当前节点的NPU总数，此参数为必填项。

  集合通信测试工具会按照用户配置的参与训练的NPU个数启动相应的Device，此参数的配置约束可参见[规格约束](./restrictions.md)。

- **-b \<minbytes\>或--minbytes \<minbytes\>**：可选，测试数据大小的起始值，即最小值。默认值：64M，单位：K、M、G。

- **-e \<maxbytes\>或--maxbytes \<maxbytes\>**：可选，测试数据大小的结束值，即最大值。默认值：64M，单位：K、M、G。

  - 当“-e”取值等于“-b”时，每次迭代按照固定的数据量大小进行测试。
  - 当“-e”的取值大于“-b”时，需要设置数据增量类型，“-i”与“-f”二选一进行配置即可。

- **-i \<incsize\>或--stepbytes \<incsize\>**：可选，数据增量类型为步长方式，单位Bytes。例如配置为100，则代表每次的增量步长为100 Bytes（注意，配置值仅为数字，无需带单位Bytes）。

  - 默认开启“-i”增量步长方式，默认步长大小的计算方式为：（测试数据大小的结束值-测试数据大小的起始值）/10。
  - 当“-i”取值为0时，会按照测试数据大小起始值（即“-b”定义的数据量大小）持续测试。

    > [!NOTE]说明
    > HCCL Test工具执行时会对部分算子的-b、-e、-i参数所输入的数据量进行地址对齐或rank size倍数的微调，以达到更优性能。

- **-f \<incfactor\>或--stepfactor \<incfactor\>**：可选，数据增量类型为乘法因子方式。

  **配置示例：**

  - **-b 100M -e 400M -i 0**：代表按照测试数据大小起始值100MB持续测试。
  - **-b 100M -e 400M -i 500**：代表测试数据以100MB为起始值，以每步增长500 Bytes的步长进行测试，直至结束。
  - **-b 100M -e 400M -f 2**：代表测试数据大小起始值为100MB，结束值为400MB，数据增量乘法因子为2，则每次迭代会分别取大小为100MB、200MB、400MB的数据进行测试。

- **-o \<operator\>或 --op \<operator\>**：可选，Reduce相关执行命令的操作类型，包含：sum、prod、max、min，默认值为sum。

  Reduce相关的执行命令有：all_reduce_test、reduce_scatter_test、reduce_scatterv_test、reduce_test。

  > [!NOTE]说明
  > 各测试命令在不同产品上的支持情况，以对应通信算子接口的实际支持能力为准，详细可参见[通信算子接口](https://gitcode.com/cann/hccl/blob/master/docs/zh/api_ref/comm_op_interface/README.md)。

- **-r \<root\>或--root \<root\>**：可选，执行命令为broadcast_test、reduce_test、scatter_test时，需要通过此参数指定根节点的Device ID。

  取值范围：[0, 实际Device数量-1]，默认值为：0。

- **-d \<datatype\>或--datatype \<datatype\>**：可选，HCCL Test支持的数据类型，默认值为fp32。

  HCCL Test支持配置的数据类型包括：int8、uint8、int16、uint16、int32、uint32、int64、uint64、fp16、fp32、fp64、bfp16、fp8e5m2、fp8e4m3、fp8e8m0、hif8。

  > [!NOTE]说明
  > 各测试命令在不同产品上支持的数据类型，以对应通信算子接口的实际支持能力为准，详细可参见[通信算子接口](https://gitcode.com/cann/hccl/blob/master/docs/zh/api_ref/comm_op_interface/README.md)。

  <!-- npu="A3" id1 -->
- **-z \<0/1\>或--zero_copy \<0/1\>**：可选，是否开启零拷贝功能。

  单算子模式下由于输入输出buffer动态变化，所以HCCL会使用中间buffer进行中转完成集合通信，但会引入额外的内存拷贝开销。零拷贝功能就是降低内存拷贝开销，直接对业务传入的内存进行操作，从而进行性能提升。

  > [!NOTE]说明
  > “零拷贝”为试用功能，后续可能存在变更，暂不支持应用于生产环境。

  此参数支持如下取值：
  - 0（默认值）：不开启零拷贝功能。
  - 1：开启零拷贝功能。

  **零拷贝功能生效有如下约束条件：**

  - 仅支持Atlas A3系列产品。
  - 仅支持执行reduce_scatter_test、all_gather_test、all_reduce_test，broadcast_test命令。
  - 仅支持通信算法的编排展开位置在AI CPU的场景。
  <!-- end id1 -->

  <!-- npu="950,A3" id2 -->
- **-m \<0/1>或--symmetric_memory \<0/1>**：可选，是否开启对称内存功能。

  单算子模式下由于输入输出buffer动态变化，所以HCCL会使用中间buffer进行中转完成集合通信，但会引入额外的内存拷贝开销。对称内存功能可以降低内存拷贝开销，直接对业务传入的内存进行操作，从而提升性能。

  此参数支持如下取值：
  - 0（默认值）：不开启对称内存功能。
  - 1：开启对称内存功能。

  **对称内存功能生效有如下约束条件：**
  - 仅支持Ascend 950PR&950DT系列产品、Atlas A3系列产品。
  - 仅支持通信算子展开模式为AI CPU的场景。
  - 针对Ascend 950PR&950DT系列产品：
    - 仅支持超节点内通信。
    - 仅支持执行reduce_scatter_test、all_gather_test、all_reduce_test、alltoall_test、alltoallvc_test、broadcast_test命令。
      关于通信算子展开模式的详细说明可参见HCCL_OP_EXPANSION_MODE环境变量。
    - 仅支持URMA通信场景。
  - 针对Atlas A3系列产品：
    - 仅支持超节点内通信。
    - 仅支持执行reduce_scatter_test、all_gather_test、all_reduce_test、alltoall_test命令。
      关于通信算子展开模式的详细说明可参见HCCL_OP_EXPANSION_MODE环境变量。
    - 仅支持超节点内AI Server间使用HCCS链路进行SDMA通信的场景，不支持使用RoCE进行RDMA通信的场景（即不支持设置环境变量HCCL_INTER_HCCS_DISABLE为“TRUE”，单机场景该环境变量无效）。
    - 仅支持对称组网，即每个server内卡数相同的场景。

  **注：不支持零拷贝和对称内存功能同时开启。**
  <!-- end id2 -->

  <!-- npu="950" id3 -->
- **-a \<HcclAccelerator\>或--accelerator \<HcclAccelerator\>**：可选，该参数仅支持Ascend 950PR&950DT系列产品，用于设置加速模式。
  - default：使用默认自适应加速模式，会根据组网、数据量等情况自动选择合适的模式。
  - aicpu_ts：使用Device侧的AI CPU计算单元加速。
  - aiv：使用Device侧的Vector Core计算单元加速，大数据量情况下可能会回退到其他加速模式。
  - ccu_ms：使用CCU MS（Memory Slice）模式加速。Ascend 950PR不支持此配置。
  - ccu_sched：使用CCU调度模式加速。
  - host_ts：不支持此配置。
  - aiv_only：使用Device侧的AI Core计算单元加速，相较于aiv加速模式，不会发生回退情况。

  **注：该配置的优先级高于环境变量HCCL_OP_EXPANSION_MODE。**
  <!-- end id3 -->

- **-s \<0/1\>或--nslb \<0/1\>**：可选，是否启用NSLB-DP（Network Scale Load Balance-Data Plane：数据面网络级负载均衡）功能。
  - 0（默认值）：不启用。
  - 1：启用。

- **-n \<iters_count\>或--iters \<iters_count\>**：可选，迭代次数，默认值为20。

- **-w \<warmup_iters_count\>或--warmup_iters \<warmup_iters_count\>**：可选，预热迭代次数，此参数不参与性能统计，仅影响HCCL Test工具的执行耗时，默认值：10。

    > [!NOTE]说明
    > 由于前几轮迭代可能存在影响性能测试的操作（例如，首轮迭代的socket建链操作等），建议将前几轮迭代设置为预热迭代，不进入性能统计。

- **-t 或 --onlydevicetime**：可选，将通信算子在Host侧的软件耗时与kernel加载耗时排除在通信执行耗时之外，仅统计Device侧的执行时间（即影响HCCL Test执行耗时的关键部分）。

  - 0（默认值）：不开启该功能，统计通信算子执行的全部耗时。
  - 1：开启该功能，仅统计Device侧执行耗时。

      开启该功能时，需要注意以下几点：
    - 仅支持通信算法的编排展开位置为Device侧的Vector Core或CCU。
    - HCCL_BUFFSIZE的配置值需要大于100MB，否则不生效。
    - “-w”与“-n”参数取值不能大于“100”。

- **-c \<0/1\>或--check \<0/1\>**：可选，是否开启集合通信操作结果正确性校验。

  - 0：不开启校验。
  - 1（默认值）：开启校验，不输出详细错误信息。
  - 2：开启校验，并输出详细错误信息。

    > [!NOTE]说明
    > 大规模集群场景下，开启结果校验会使HCCL Test工具的执行耗时增加。
