# Tool Execution

<!-- md-trans-meta sourceCommit=f7fbbcc40f113a6951c74ffbb825c5398cd1453e translatedAt=2026-10-10T12:00:52.262Z pushedAt=2026-10-15T10:25:53.430Z -->

## Prerequisites

- The firewall is disabled in the running environment.
- Because the number of concurrent connection establishments that the master node can process is limited by the Linux kernel parameters "somaxconn" and "tcp_max_syn_backlog", for large-scale cluster networking, if the values of "somaxconn" and "tcp_max_syn_backlog" are small, some clients may exit abnormally in advance with a certain probability, causing cluster initialization to fail.

    In large-scale cluster networking scenarios, developers are advised to appropriately adjust the values of the "somaxconn" and "tcp_max_syn_backlog" parameters on the master node based on the cluster size. For example:

    ```bash
    sysctl -w net.core.somaxconn=65535
    sysctl -w net.ipv4.tcp_max_syn_backlog=65535
    ```

- Before running HCCL Test, it is recommended to temporarily set the file descriptor limit of the current shell environment to 65535 to prevent resource exhaustion from causing the tool to fail.

  ```bash
  ulimit -n 65535
  ```

## Procedure

1. Configure the environment variables required for starting the HCCL Test tool.

    - Scenario where MPICH is installed:

        ```bash
        export INSTALL_DIR=/usr/local/Ascend/cann
        export PATH=/usr/local/mpich/bin:$PATH
        export LD_LIBRARY_PATH=/usr/local/mpich/lib:${INSTALL_DIR}/lib64:$LD_LIBRARY_PATH
        ```

    - Scenario where Open MPI is installed:

        ```bash
        export INSTALL_DIR=/usr/local/Ascend/cann
        export PATH=/usr/local/openmpi/bin:$PATH
        export LD_LIBRARY_PATH=/usr/local/openmpi/lib:${INSTALL_DIR}/lib64:$LD_LIBRARY_PATH
        ```

    "INSTALL_DIR" is the path where CANN software files are stored after installation. "/usr/local/Ascend/cann" is the default installation path for the root user. If you install CANN as a non-root user or to a custom path, replace it with the actual path.

    "/usr/local/mpich" and "/usr/local/openmpi" are the MPI installation paths. Replace them based on the actual situation.

    If the preceding environment variables already exist in the environment, you do not need to configure them again.

2. Configure the environment variables related to HCCL collective communication.
    1. On the node where the training process is started, configure the information about the communication NIC used during communication domain initialization.

        Configure the NIC name used on the host side during HCCL initialization and the IP protocol version used by the communication NIC. HCCL can obtain the host IP through the configured NIC name to complete communication domain creation.

        ```bash
        # Configure the IP protocol version used by the communication NIC during HCCL initialization. AF_INET: IPv4; AF_INET6: IPv6
        export HCCL_SOCKET_FAMILY=AF_INET

        # The following NIC name configuration formats are supported (select one of the four formats as needed. You can configure multiple NICs in the environment variable, separated by commas. The first matched NIC is used as the communication NIC.)
        # Exact NIC matching
        export HCCL_SOCKET_IFNAME==eth0,enp0   # Use the specified eth0 or enp0 NIC
        export HCCL_SOCKET_IFNAME=^=eth0,enp0     # Do not use the eth0 or enp0 NIC

        # Fuzzy NIC matching
        export HCCL_SOCKET_IFNAME=eth,enp       # Use all NICs whose names start with eth or enp
        export HCCL_SOCKET_IFNAME=^eth,enp      # Do not use any NIC whose name starts with eth or enp
        ```

       > [!CAUTION] Caution
       > If the NIC names of different nodes participating in collective communication are different, for example, the NIC name of node1 is eth1 and that of node2 is eth2, and the environment variable will be synchronized from the current node to other nodes later, you are advised to configure the environment variable using fuzzy NIC matching.

    2. Adjust the socket connection timeout period.

        In collective communication scenarios, the default timeout for socket connection between devices is 120s. When the Master node needs to establish connections and process a large amount of data, the default value of 120 seconds cannot meet the connection establishment requirements and needs to be adjusted appropriately.

        For example, if the number of cards in the cluster is 3K, it is recommended to adjust the value to 240s; if the number of cards in the cluster is 5K, it is recommended to adjust the value to 600s.

        ```bash
        export HCCL_CONNECT_TIMEOUT=600
        ```

    3. Adjust the size of the shared buffer between NPUs.

        In collective communication, each communication domain occupies a 200MB buffer by default. The size of this buffer can be adjusted through the environment variable HCCL_BUFFSIZE, and the unit is MB.

        If there are many communication domains in the cluster, the overall buffer usage increases, which may affect the normal storage of model data. In this scenario, you can reduce the value of this environment variable to lower the buffer space occupied by communication domains. If the model data volume of the service is small but the communication data volume is large, you can appropriately increase the value of this environment variable to enlarge the buffer space occupied by communication domains, thereby improving data communication efficiency.

        In the scenario where the hccl_test tool is used for performance testing, the communication data volume is usually large. In this scenario, you can appropriately increase the value of HCCL_BUFFSIZE to improve data communication efficiency. For collective communication operators, when the test data volume exceeds the value of HCCL_BUFFSIZE, performance degradation may occur. It is recommended that the value of HCCL_BUFFSIZE be greater than the test data volume.

        Configuration example:

        ```bash
        export HCCL_BUFFSIZE=2048
        ```

         For more environment variables, see "[Environment Variable Reference](https://gitcode.com/cann/hccl/blob/9.2.0/docs/en/user_guide/hccl_env/README.md)" in *HCCL Collective Communication Library*.

    4. (Optional) Configure auxiliary environment variables for the HCCL Test tool.
       - Specify the Device to run HCCL Test.

         ```bash
         # The number after HCCL_TEST_USE_DEVS is the Device ID on which HCCL Test is to be executed. Separate multiple devices with ",".
         export HCCL_TEST_USE_DEVS="4,5,6,7"
         ```

       - Collect performance data when executing HCCL Test.

         ```bash
         # "1" indicates enabling profiling, and "0" indicates disabling profiling. The default value is "0". When profiling is enabled, performance data is collected during HCCL Test execution.
         export HCCL_TEST_PROFILING=1
         # Specify the storage path of profiling data. The default path is "/var/log/npu/profiling".
         export HCCL_TEST_PROFILING_PATH=/home/profiling
         ```

         If HCCL_TEST_PROFILING is enabled, profiling data is generated in the directory specified by HCCL_TEST_PROFILING_PATH after HCCL Test execution is complete. For details about how to parse the performance data, see the "msProf Performance Data Parsing" section in *[Performance Tuning Tool](https://gitcode.com/cann/docs/blob/9.2.0/docs/en/profiling/profiling_menu.md)*.

         > [!CAUTION] Caution
         > Enabling profiling affects the performance of collective communication operators.

3. Configure the Hostfile.

    The Hostfile specifies the nodes on which communication processes are to be started. The Hostfile is a text file and must be customized by the user.

    A default Hostfile template named "hostfile" already exists in the **$\{INSTALL_DIR\}/tools/hccl_test/** path. You can edit the template directly or customize the file storage path and name.

    - In the MPICH installation scenario, only the IPv4 communication protocol is supported. The content format is as follows:

        ```text
        Node IP:number of processes per node
        ```

        For example, define the Hostfile file name as "hostfile" with the following content:

        ```text
        10.10.130.22:8
        10.10.130.21:8
        ```

    - In the scenario where Open MPI is installed, both the IPv4 and IPv6 communication protocols are supported. The content format is as follows:

        ```text
        Node name slots=number of processes per node
        ```

        For example, define the Hostfile file name as "hostfile" with the following content:

        ```text
        node3 slots=8
        node4 slots=8
        ```

   Note:
     <!-- npu="A3" id1 -->
   - For Atlas A3 products, in the Hostfile, configure the AI Server information belonging to the same supernode together. Assume that there are two supernodes with identifiers "0" and "1". In the Hostfile, configure the AI Server information in "0" first, and then configure the AI Server information in "1". Cross-configuration of the AI Server information in "0" and "1" is not supported.
     <!-- end id1 -->
   - For a single-node scenario, the Hostfile does not need to be configured.

4. Execute the HCCL Test tool.

    Developers need to execute the HCCL Test tool in the “$\{INSTALL_DIR\}/tools/hccl_test” directory.

    - In the scenario where MPICH is installed, the command format is as follows:

        ```bash
        mpirun [-f <hostfile>] -n <number> ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
        ```

        The command example is as follows:

        ```bash
        mpirun -f hostfile -n 16 ./bin/all_reduce_test -p 8 -b 8K -e 64M -f 2 -d fp32 -o sum
        ```

        - The parameters following mpirun are MPI command-related parameters.
        - The parameters following ./bin/_&lt;executable_file\>_ are HCCL Test tool-related parameters.

        For details about the parameters related to MPICH and collective communication test commands, see [Parameter Description](./cmdline_options_desc.md). **Note that the MPICH parameters provided in this document are only common parameters. For details about how to use MPICH parameters and how to resolve issues during use, see the [MPICH official documentation](https://www.mpich.org/).**

        Note:

        In the scenario where MPICH is installed, when you run the mpirun command, the environment variables of the current node are synchronized to other nodes by default. If the environment variables of each node differ, you are advised to write the environment variable configuration commands into an execution script and pass the execution script to the mpirun command. For example:
        1. Create the execution script run.sh. The following is an example of its content:

           ```bash
           export HCCL_TEST_USE_DEVS="4,5,6,7"
           $1
           ```

        2. Run the mpirun command. The following is an example:

           ```bash
           mpirun -n 4 ./run.sh "./all_reduce_test -b 8K -e 64M -f 2 -p 4"
           ```

    - In the scenario where Open MPI is installed, the command format is as follows:

        ```bash
        mpirun [--prefix <mpi_install_path>] [-hostfile <hostfile>] -n <number> -x <env> [--allow-run-as-root] [--mca <key value>] ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
        ```

        The command example is as follows:

        ```bash
        mpirun --prefix /usr/local/openmpi -hostfile hostfile -x ASCEND_HOME_PATH -x LD_LIBRARY_PATH -x HCCL_SOCKET_FAMILY -x HCCL_SOCKET_IFNAME -x HCCL_CONNECT_TIMEOUT -x HCCL_BUFFSIZE --allow-run-as-root --mca btl_tcp_if_include eth0 --mca opal_set_max_sys_limits 1 -n 16 ./bin/all_reduce_test -p 16 -b 8K -e 64M -i 0 -o sum -d fp32 -w 3 -n 3
        ```

        - mpirun is followed by MPI command-related parameters.
        - ./bin/<executable_file\> is followed by HCCL Test tool-related parameters.

        For details about the Open MPI and collective communication test command parameters, see [Parameter Description](./cmdline_options_desc.md). **Note that the Open MPI parameters provided in this document are only common parameters. For details about how to use Open MPI parameters and how to resolve issues during use, see the [Open MPI official documentation](https://www.open-mpi.org/).**

## Result Description

Command example:

```bash
# mpirun -n 8 ./bin/all_reduce_test -b 8K -e 64M -f 2 -d fp32 -o sum -p 8
```

The following is an example of the execution result:

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

The meaning of each field is as follows:

**data_size**: amount of data involved in collective communication on a single NPU. The unit is Bytes.

**aveg_time**: time consumed by collective communication operator execution. The unit is us.

**alg_bandwidth**: bandwidth of collective communication operator execution. The unit is GB/s.

> [!NOTE] Note
> The bandwidth of collective communication operator execution here refers to the algorithm bandwidth, which is calculated as "collective communication data volume / time consumed".

**check_result**: result verification flag of collective communication operator execution. The value can be success, failed, or NULL.

- If the "-c" parameter is set to "0" when running the tool, that is, result verification is not enabled, the check_result status is NULL.
- When the operator computation result overflows or exceeds the precisely representable numeric range, result verification is not enabled, and the check_result status is NULL.

  The HCCL Test tool determines whether the communication result is correct by initializing the operator inputs to fixed values and checking whether the operator outputs meet expectations. Due to the limited numeric representation range and precision of computers, for certain operations, if the number of cards is too large, the result may overflow or exceed the precisely representable numeric range, causing the HCCL Test tool to be unable to verify accurately. In this case, the check_result status is displayed as NULL.

  - For reduction operators, the maximum number of cards supported by result verification for multiplication and addition operations under different operator types and data types is shown in the following table:

    <table>
      <thead>
        <tr>
          <th rowspan="2">Operation Type</th>
          <th rowspan="2">Operator Type</th>
          <th colspan="7">Data Type</th>
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
      <td rowspan="3">Prod</td>
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
      <td rowspan="4">Sum</td>
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

  - For the AllGather, AllGatherV, AlltoAll, AlltoAllV, AlltoAllVC, and Scatter operators, when the data type is int8 or uint8, the maximum number of supported cards is 127.
