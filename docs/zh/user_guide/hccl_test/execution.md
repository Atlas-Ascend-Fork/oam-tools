# 工具执行

## 前提条件

- 运行环境已关闭防火墙。
- 由于Master节点允许处理的并发建链数受Linux内核参数“somaxconn”与“tcp_max_syn_backlog”的限制，所以，针对大规模集群组网，若“somaxconn”与“tcp_max_syn_backlog”取值较小会导致部分客户端概率性提前异常退出，进而集群初始化失败。

    大规模集群组网场景下，建议开发者根据集群数量在Master节点适当调整“somaxconn”与“tcp_max_syn_backlog”参数的值，例如：

    ```bash
    sysctl -w net.core.somaxconn=65535
    sysctl -w net.ipv4.tcp_max_syn_backlog=65535
    ```

- 执行HCCL Test前，建议临时将当前shell环境的文件描述符上限设置为65535，以防止资源耗尽导致工具运行失败。

  ```bash
  ulimit -n 65535
  ```

## 操作步骤

1. 配置HCCL Test工具启动依赖的环境变量。

    - 安装MPICH的场景：

        ```bash
        export INSTALL_DIR=/usr/local/Ascend/cann
        export PATH=/usr/local/mpich/bin:$PATH
        export LD_LIBRARY_PATH=/usr/local/mpich/lib:${INSTALL_DIR}/lib64:$LD_LIBRARY_PATH
        ```

    - 安装Open MPI的场景：

        ```bash
        export INSTALL_DIR=/usr/local/Ascend/cann
        export PATH=/usr/local/openmpi/bin:$PATH
        export LD_LIBRARY_PATH=/usr/local/openmpi/lib:${INSTALL_DIR}/lib64:$LD_LIBRARY_PATH
        ```

    “INSTALL_DIR”是CANN软件安装后文件存储路径，其中“/usr/local/Ascend/cann”为root用户的默认安装路径，如果使用普通用户安装，或指定路径安装，请自行替换。

    “/usr/local/mpich”以及“/usr/local/openmpi”为MPI安装路径，请根据实际情况替换。

    如果环境中已存在上述环境变量，无需再次配置。

2. 配置HCCL集合通信相关环境变量。
    1. 在训练进程拉起节点配置通信域初始化时使用的通信网卡相关信息。

        配置HCCL初始化时Host侧使用的网卡名及通信网卡使用的IP协议版本，HCCL可通过配置的网卡名获取Host IP，完成通信域创建。

        ```bash
        # 配置HCCL初始化时通信网卡使用的IP协议版本，AF_INET：IPv4；AF_INET6：IPv6
        export HCCL_SOCKET_FAMILY=AF_INET

        # 支持以下格式的网卡名配置（4种规格自行选择1种即可，环境变量中可配置多个网卡，多个网卡间使用英文逗号分隔，取最先匹配到的网卡作为通信网卡）
        # 精确匹配网卡
        export HCCL_SOCKET_IFNAME==eth0,enp0   # 使用指定的eth0或enp0网卡
        export HCCL_SOCKET_IFNAME=^=eth0,enp0     # 不使用eth0与enp0网卡

        # 模糊匹配网卡
        export HCCL_SOCKET_IFNAME=eth,enp       # 使用所有以eth或enp为前缀的网卡
        export HCCL_SOCKET_IFNAME=^eth,enp      # 不使用任何以eth或enp为前缀的网卡
        ```

       > [!CAUTION]注意
       > 如果参与集合通信的不同节点的网卡名字不同，例如node1的网卡名为eth1，node2的网卡名为eth2，若后续环境变量会从当前节点同步到其他节点，建议使用模糊匹配网卡的方式进行环境变量配置。

    2. 调整socket建链超时等待时间。

        集合通信场景中，设备间socket建链超时等待时间默认值为120s，当Master节点需要建链和处理的数据量较大时，默认值120秒无法满足建链需求，需要适当进行调整。

        例如，若集群组网中卡数为3K，建议调整为240s；若集群组网中卡数为5K，建议调整为600s。

        ```bash
        export HCCL_CONNECT_TIMEOUT=600
        ```

    3. 调整NPU之间共享缓冲区的大小。

        集合通信中，每个通信域都默认占用200MB的缓存区，此缓存区大小可通过环境变量HCCL_BUFFSIZE进行调整，单位为MB。

        若集群中存在较多的通信域，整体缓存占用会增加，可能影响模型数据的正常存储。此种场景下，可通过调小该环境变量的值以降低通信域占用的缓存空间；若业务的模型数据量较小，但通信数据量较大，可适当调大该环境变量的值以增大通信域占用的缓存空间，以提升数据通信效率。

        使用hccl_test工具进行性能测试的场景下，通信数据量通常较大，此种场景下，可适当增大HCCL_BUFFSIZE的值，提升数据通信效率。针对集合通信算子，当测试数据量超过HCCL_BUFFSIZE的取值时，可能会出现性能下降的情况，建议HCCL_BUFFSIZE的取值大于测试数据量。

        配置示例：

        ```bash
        export HCCL_BUFFSIZE=2048
        ```

        更多环境变量可参见《HCCL集合通信库》中的“[环境变量参考](https://gitcode.com/cann/hccl/blob/master/docs/zh/user_guide/hccl_env/README.md)”。

    4. （可选）配置HCCL Test工具辅助环境变量。
       - 指定Device执行HCCL Test。

         ```bash
         # HCCL_TEST_USE_DEVS后的数字为需要执行HCCL Test的Device Id，多个Device之间使用“,”分隔
         export HCCL_TEST_USE_DEVS="4,5,6,7"
         ```

       - 执行HCCL Test时采集性能数据。

         ```bash
         # “1”代表开启profiling，“0”代表关闭profiling，默认值为“0”，开启时，执行HCCL Test时采集性能数据
         export HCCL_TEST_PROFILING=1
         # 指定profiling数据存放路径，默认为“/var/log/npu/profiling”
         export HCCL_TEST_PROFILING_PATH=/home/profiling
         ```

         若开启HCCL_TEST_PROFILING，HCCL Test工具执行完成后会在HCCL_TEST_PROFILING_PATH指定目录下生成profiling数据，性能数据的解析可参见《[性能调优工具](https://gitcode.com/cann/docs/blob/master/docs/zh/profiling/profiling_menu.md)》的“msProf性能数据解析”章节。

         > [!CAUTION]注意
         > 开启Profiling后，会对集合通信算子性能产生影响。

3. 配置Hostfile文件。

    Hostfile文件用于指定需要在哪些节点上启动通信进程，Hostfile文件是文本文件，需要用户自定义。

    “$\{INSTALL_DIR\}/tools/hccl_test/”路径下已存在默认Hostfile模版文件，命名为“hostfile”，您可以直接基于该模版进行编辑，也可以自定义文件存储路径与名称。

    - 安装MPICH的场景，仅支持通信协议IPv4，内容格式如下：

        ```text
        节点ip:每节点的进程数
        ```

        例如，定义Hostfile文件的名称为“hostfile”，内容如下：

        ```text
        10.10.130.22:8
        10.10.130.21:8
        ```

    - 安装Open MPI的场景，既支持通信协议IPv4，又支持通信协议IPv6，内容格式如下：

        ```text
        节点名 slots=每节点的进程数
        ```

        例如，定义Hostfile文件的名称为“hostfile”，内容如下：

        ```text
        node3 slots=8
        node4 slots=8
        ```

   注意：
     <!-- npu="A3" id1 -->
   - 针对Atlas A3系列产品，Hostfile文件中，请将属于同一超节点的AI Server信息配置在一起。假设有两个超节点，标识分别为“0”和“1”，请在Hostfile中先配置“0”中的AI Server信息，再配置“1”中的AI Server信息，不支持“0”中的AI Server信息与“1”中的AI Server信息交叉配置。
     <!-- end id1 -->
   - 针对单机场景，Hostfile文件可不配置。

4. 执行HCCL Test工具。

    开发者需要在“$\{INSTALL_DIR\}/tools/hccl_test”目录下执行HCCL Test工具。

    - 安装MPICH的场景，命令格式如下：

        ```bash
        mpirun [-f <hostfile>] -n <number> ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
        ```

        命令示例如下：

        ```bash
        mpirun -f hostfile -n 16 ./bin/all_reduce_test -p 8 -b 8K -e 64M -f 2 -d fp32 -o sum
        ```

        - mpirun后跟随的是MPI命令相关参数。
        - ./bin/_&lt;executable_file\>_后跟随的是HCCL Test工具相关参数。

        关于MPICH及集合通信测试命令相关参数的详细说明可参见[参数说明](./cmdline_options_desc.md)。**需要注意，本文中给出的MPICH参数仅为常用参数，关于MPICH参数的详细使用方法及使用过程中的问题解决方法可参见[MPICH官方文档](https://www.mpich.org/)。**

        注意：

        安装MPICH的场景下，执行mpirun命令时，会默认将当前节点的环境变量同步到其他节点，若各节点的环境变量存在差异，建议将环境变量设置命令写入执行脚本，并将执行脚本传入mpirun命令，例如：
        1. 创建执行脚本run.sh，内容示例如下：

           ```bash
           export HCCL_TEST_USE_DEVS="4,5,6,7"
           $1
           ```

        2. 执行mpirun命令，示例如下：

           ```bash
           mpirun -n 4 ./run.sh "./all_reduce_test -b 8K -e 64M -f 2 -p 4"
           ```

    - 安装Open MPI的场景，命令格式如下：

        ```bash
        mpirun [--prefix <mpi_install_path>] [-hostfile <hostfile>] -n <number> -x <env> [--allow-run-as-root] [--mca <key value>] ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
        ```

        命令示例如下：

        ```bash
        mpirun --prefix /usr/local/openmpi -hostfile hostfile -x ASCEND_HOME_PATH -x LD_LIBRARY_PATH -x HCCL_SOCKET_FAMILY -x HCCL_SOCKET_IFNAME -x HCCL_CONNECT_TIMEOUT -x HCCL_BUFFSIZE --allow-run-as-root --mca btl_tcp_if_include eth0 --mca opal_set_max_sys_limits 1 -n 16 ./bin/all_reduce_test -p 16 -b 8K -e 64M -i 0 -o sum -d fp32 -w 3 -n 3
        ```

        - mpirun后跟随的是MPI命令相关参数。
        - ./bin/<executable_file\>后跟随的是HCCL Test工具相关参数。

        关于Open MPI及集合通信测试命令相关参数的详细说明可参见[参数说明](./cmdline_options_desc.md)。**需要注意，本文中给出的Open MPI参数仅为常用参数，关于Open MPI参数的详细使用方法及使用过程中的问题解决方法可参见[Open MPI官方文档](https://www.open-mpi.org/)。**

## 结果说明

命令示例：

```bash
# mpirun -n 8 ./bin/all_reduce_test -b 8K -e 64M -f 2 -d fp32 -o sum -p 8
```

执行结果示例如下：

```text
the minbytes is 8192, maxbytes is 67108864, iters is 20, warmup_iters is 5
data_size(Bytes): |   avg_time(us): | alg_bandwidth(GB/s): | check_result:
8192              |     764.55    |       0.00998        | success
16384             |     858.80    |       0.01777        | success
32768             |     901.10    |       0.03387        | success
65536             |     900.00    |       0.06782        | success
131072            |     928.50    |       0.13147        | success
262144            |    1573.45    |       0.15516        | success
524288            |    1831.25    |       0.26664        | success
1048576           |    1778.30    |       0.54916        | success
2097152           |    1763.30    |       1.10765        | success
4194304           |    1801.75    |       2.16803        | success
8388608           |    1767.65    |       4.41971        | success
16777216          |    1940.90    |       8.05039        | success
33554432          |    1714.85    |      18.22317        | success
67108864          |    2630.20    |      23.76245        | success
```

各字段含义如下：

**data_size**：单个NPU上参与集合通信的数据量，单位为Bytes。

**aveg_time**：集合通信算子执行耗时，单位为us。

**alg_bandwidth**：集合通信算子执行带宽，单位为GB/s。

> [!NOTE]说明
> 此处的集合通信算子执行带宽指的是算法带宽，计算方式为：“集合通信数据量/耗时”。

**check_result**：集合通信算子执行结果校验标识，取值为：success、failed、NULL。

- 若执行工具时“-c”参数配置为“0”，即未开启结果校验，check_result状态为NULL。
- 当算子计算结果出现溢出或超出可精确表达的数值范围时，不会开启结果校验，check_result状态为NULL。

  HCCL Test工具通过将算子输入初始化为固定值，并检验算子输出是否符合预期来判断通信结果是否正确。由于计算机数值表达范围和表示精度有限，针对某些操作，如果卡数过多，可能会出现结果溢出或超出可精确表达的数值范围的情况，导致HCCL Test工具无法准确校验，此种情况check_result状态会显示为NULL。

  - 针对归约类算子，乘与加操作在不同的算子类型与数据类型下，结果校验所能支持的最大卡数如下表所示：

    <table>
      <thead>
        <tr>
          <th rowspan="2">操作类型</th>
          <th rowspan="2">算子类型</th>
          <th colspan="7">数据类型</th>
        </tr>
        <tr>
          <th>INT8</th>
          <th>INT16</th>
          <th>INT32</th>
          <th>INT64</th>
          <th>FP32</th>
          <th>FP16</th>
          <th>BF16</th>
        </tr>
      </thead>
    <tbody>
    <tr>
      <td rowspan="3">乘（Prod）</td>
      <td>AllReduce</td>
      <td rowspan="3">6</td>
      <td rowspan="3">14</td>
      <td rowspan="3">30</td>
      <td rowspan="3">62</td>
      <td rowspan="3">127</td>
      <td rowspan="3">15</td>
      <td rowspan="3">127</td>
    </tr>
    <tr>
      <td>Reduce</td>
    </tr>
    <tr>
      <td>ReduceScatter</td>
    </tr>
    <tr>
      <td rowspan="4">加（Sum）</td>
      <td>AllReduce</td>
      <td rowspan="2">63</td>
      <td rowspan="2">16383</td>
      <td rowspan="2">~1e9</td>
      <td rowspan="2">~1e18</td>
      <td rowspan="2">~1e6</td>
      <td rowspan="2">511</td>
      <td rowspan="2">63</td>
    </tr>
    <tr>
      <td>Reduce</td>
    </tr>
    <tr>
      <td>ReduceScatter</td>
      <td>11</td>
      <td>181</td>
      <td>46340</td>
      <td>~1e9</td>
      <td>2896</td>
      <td>31</td>
      <td>11</td>
    </tr>
    <tr>
      <td>ReduceScatterV</td>
      <td>11</td>
      <td>181</td>
      <td>46340</td>
      <td>~1e9</td>
      <td>2896</td>
      <td>31</td>
      <td>11</td>
    </tr>
    </tbody>
    </table>

  - 针对AllGather、AllGatherV、AlltoAll、AlltoAllV、AlltoAllVC、Scatter算子，当数据类型是int8或uint8时，最大支持的卡数为127。
