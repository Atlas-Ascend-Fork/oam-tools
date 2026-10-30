# Parameter Description

<!-- md-trans-meta sourceCommit=38db658ea4f8dfa2b0e1aaf6e53782372ffc7974 translatedAt=2026-10-10T12:01:05.089Z pushedAt=2026-10-15T10:42:34.769Z -->

This section describes the parameters of the HCCL Test performance testing tool.

## Command Format

- Scenario where MPICH is installed

    ```bash
    mpirun [-f <hostfile>] -n <number> ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
    ```

- Scenario where Open MPI is installed

    ```bash
    mpirun [--prefix <mpi_install_path>] [-hostfile <hostfile>] -n <number> -x <env> [--allow-run-as-root] [--mca <key value>] ./bin/<executable_file> [-p <npus>] [-b <minbytes>] [-e <maxbytes>] [-f <incfactor>] [-o <operator>] [-r <root>] [-d <datatype>] [-z <0/1>] [-n <iters_count>] [-w <warmup_iters_count>] [-c <0/1>]
    ```

- The parameters following mpirun are MPI command-related parameters. For details about MPI command-related parameters, see [MPICH Command Parameters](#mpich-command-parameters) and [Open MPI Command Parameters](#open-mpi-command-parameters).
- The parameters following ./bin/&lt;executable_file\> are HCCL Test tool-related parameters. For details about HCCL Test tool-related parameters, see [HCCL Test Tool-related Parameters](#hccl-test-tool-related-parameters).

## MPICH Command Parameters

This section lists only the common MPICH tool parameters. For more parameters, see the [MPICH official documentation](https://www.mpich.org/).

- **-f \<hostfile\>**: optional, the Hostfile node list file.

  In a single-machine scenario, this file does not need to be configured. In a multi-machine scenario, it must be configured. It can be set to the absolute path of the Hostfile, or a relative path to the current execution command.
- **-n \<number\>**: required, the total number of NPUs to be started, that is, the number of nodes * the number of NPUs participating in training on each node.

## Open MPI Command Parameters

This section describes only the common parameters of the Open MPI tool. For more parameters, see the [open-mpi official documentation](https://www.open-mpi.org/doc/v4.1/man1/mpirun.1.php).

- **--prefix \<mpi_install_path\>**: optional. Configures the installation path of Open MPI.

  Generally, this parameter does not need to be configured in a single-machine scenario, but it must be configured in a multi-machine scenario. Otherwise, the MPI library files may fail to be obtained.
- **-hostfile \<hostfile\>**: optional. Specifies the Hostfile node list file.

  This file does not need to be configured in a single-machine scenario, but it must be configured in a multi-machine scenario. It can be configured as the absolute path of the Hostfile, or as a relative path to the current execution command.
- **-n \<number\>**: required. Sets the total number of NPUs to be started, that is, the number of nodes * the number of NPUs participating in training on each node.
- **-x \<env\>**: required. Specifies the name of the environment variable to be passed to remote nodes.
- **--allow-run-as-root**: optional. Allows mpirun to be executed by the root user.
- **--mca \<key value\>**: optional. Sets the **mca** parameters. The design of Open MPI centers on the MPI Component Architecture (MCA). You can load various component modules of openmpi by setting the mca parameters in the mpirun command at runtime to implement specific functions.

  Common commands include:
  - --mca btl_tcp_if_include *<nic_name>*

    Uses the specified NIC for inter-node communication, for example:

    ```text
    --mca btl_tcp_if_include eth0
    ```

  - --mca opal_set_max_sys_limits 1

    Sets the Open MPI runtime system limits (such as the number of file descriptors) to follow the system's ulimit configuration, ensuring that Open MPI processes do not encounter issues due to resource limits during execution. When the cluster contains a large number of cards, it is recommended to add this configuration to avoid resource insufficiency.

## HCCL Test Tool-related Parameters

- **./bin/\<executable_file\>**: required. The command for executing the collective communication performance test tool.

  \<executable_file\> is the executable file of the collective communication performance test tool, that is, a supported test command.

  The test commands supported by the HCCL Test tool include: broadcast_test, all_gather_test, all_gatherv_test, reduce_test, all_reduce_test, scatter_test, reduce_scatter_test, reduce_scatterv_test, alltoall_test, alltoallv_test, and alltoallvc_test.

  > [!NOTE] Note
  > The support of each test command on different products is subject to the actual support capability of the corresponding communication operator API. For details, see [Communication Operator API](https://gitcode.com/cann/hccl/blob/9.2.0/docs/en/api_ref/comm_op_interface/README.md).

- **-p \<npus\> or --npus \<npus\>**: optional. Number of NPUs participating in training on a single compute node.

  The default value is the total number of NPUs on the current node. If the number of NPUs participating in training on a single compute node is less than the total number of NPUs on the current node, this parameter is required.

  The collective communication test tool starts the corresponding Device based on the number of NPUs participating in training configured by the user. For the configuration constraints of this parameter, see [Specification Constraints](./restrictions.md).

- **-b \<minbytes\> or --minbytes \<minbytes\>**: optional. Start value of the test data size, that is, the minimum value. Default value: 64M. Unit: K, M, G.

- **-e \<maxbytes\> or --maxbytes \<maxbytes\>**: optional. End value of the test data size, that is, the maximum value. Default value: 64M. Unit: K, M, G.

  - When the value of "-e" equals that of "-b", each iteration is tested with a fixed data size.
  - When the value of "-e" is greater than that of "-b", the data increment type must be set. Configure either "-i" or "-f".

- **-i \<incsize\> or --stepbytes \<incsize\>**: optional. The data increment type is step-based, in bytes. For example, if it is set to 100, the increment step of each iteration is 100 bytes. (Note: The configured value is a number only, without the unit "Bytes".)

  - The "-i" step-based increment mode is enabled by default. The default step size is calculated as follows: (end value of the test data size - start value of the test data size) / 10.
  - When the value of "-i" is 0, testing continues with the start value of the test data size (that is, the data size defined by "-b").

    > [!NOTE] Note
    > When the HCCL Test tool is executed, the data sizes entered for the -b, -e, and -i parameters of some operators are fine-tuned for address alignment or rank size multiples to achieve better performance.

- **-f \<incfactor\> or --stepfactor \<incfactor\>**: optional. The data increment type is multiplication factor-based.

  **Configuration example:**

  - **-b 100M -e 400M -i 0**: testing continues with the start value of the test data size, 100 MB.
  - **-b 100M -e 400M -i 500**: testing starts with 100 MB as the start value and proceeds with a step of 500 bytes per increment until the end.
  - **-b 100M -e 400M -f 2**: indicates that the test data size starts at 100MB and ends at 400MB, with a data increment multiplication factor of 2. Therefore, each iteration tests data of 100MB, 200MB, and 400MB respectively.

- **-o \<operator\> or --op \<operator\>**: optional. Specifies the operation type of Reduce-related execution commands, including sum, prod, max, and min. The default value is sum.

  Reduce-related execution commands include all_reduce_test, reduce_scatter_test, reduce_scatterv_test, and reduce_test.

  > [!NOTE] Note
  > The support for each test command on different products is subject to the actual support capability of the corresponding communication operator API. For details, see [Communication Operator API](https://gitcode.com/cann/hccl/blob/9.2.0/docs/en/api_ref/comm_op_interface/README.md).

- **-r \<root\> or --root \<root\>**: optional. When the execution command is broadcast_test, reduce_test, or scatter_test, use this parameter to specify the Device ID of the root node.

  Value range: [0, actual number of Devices - 1]. The default value is 0.

- **-d \<datatype\> or --datatype \<datatype\>**: optional. Specifies the data type supported by HCCL Test. The default value is fp32.

  The data types supported by HCCL Test include int8, uint8, int16, uint16, int32, uint32, int64, uint64, fp16, fp32, fp64, bfp16, fp8e5m2, fp8e4m3, fp8e8m0, and hif8.

  > [!NOTE] Note
  > The data types supported by each test command on different products are subject to the actual support capability of the corresponding communication operator API. For details, see [Communication Operator API](https://gitcode.com/cann/hccl/blob/9.2.0/docs/en/api_ref/comm_op_interface/README.md).

  <!-- npu="A3" id1 -->
- **-z \<0/1\> or --zero_copy \<0/1\>**: optional. Specifies whether to enable the zero-copy feature.

  In single-operator mode, because the input and output buffers change dynamically, HCCL uses an intermediate buffer for transfer to complete collective communication, which introduces additional memory copy overhead. The zero-copy feature reduces the memory copy overhead by directly operating on the memory passed in by the service, thereby improving performance.

  > [!NOTE] Note
  > "Zero-copy" is a trial feature and may change in the future. It is not supported in production environments.

  This parameter supports the following values:
  - 0 (default value): The zero-copy feature is disabled.
  - 1: The zero-copy feature is enabled.

  **The zero-copy feature takes effect only when the following constraints are met:**

  - Only the Atlas A3 product series is supported.
  - Only the reduce_scatter_test, all_gather_test, all_reduce_test, and broadcast_test commands are supported.
  - Only the scenario where the orchestration expansion position of the communication algorithm is on the AI CPU is supported.
  <!-- end id1 -->

  <!-- npu="950,A3" id2 -->
- **-m \<0/1> or --symmetric_memory \<0/1>**: optional, whether to enable the symmetric memory feature.

  In single-operator mode, because the input and output buffers change dynamically, HCCL uses an intermediate buffer for transfer to complete collective communication, which introduces additional memory copy overhead. The symmetric memory feature can reduce memory copy overhead by directly operating on the memory passed in by the service, thereby improving performance.

  This parameter supports the following values:
  - 0 (default value): The symmetric memory feature is not enabled.
  - 1: The symmetric memory feature is enabled.

  **The symmetric memory feature takes effect only when the following constraints are met:**
  - Only the Ascend 950PR&950DT product series and Atlas A3 product series are supported.
  - Only the scenario where the communication operator expansion mode is AI CPU is supported.
  - For the Ascend 950PR&950DT product series:
    - Only intra-supernode communication is supported.
    - Only the reduce_scatter_test, all_gather_test, all_reduce_test, alltoall_test, alltoallvc_test, and broadcast_test commands are supported.
      For details about the communication operator expansion mode, see the HCCL_OP_EXPANSION_MODE environment variable.
    - Only the URMA communication scenario is supported.
  - For the Atlas A3 product series:
    - Only intra-supernode communication is supported.
    - Only the reduce_scatter_test, all_gather_test, all_reduce_test, and alltoall_test commands are supported.
      For details about the communication operator expansion mode, see the HCCL_OP_EXPANSION_MODE environment variable.
    - Only the SDMA communication scenario that uses HCCS links between AI Servers within a supernode is supported. The RDMA communication scenario that uses RoCE is not supported (that is, setting the HCCL_INTER_HCCS_DISABLE environment variable to "TRUE" is not supported; this environment variable is invalid in the single-machine scenario).
    - Only symmetric networking is supported, that is, the scenario where each server has the same number of cards.

  **Note: Enabling the zero-copy feature and symmetric memory at the same time is not supported.**
  <!-- end id2 -->

  <!-- npu="950" id3 -->
- **-a \<HcclAccelerator\> or --accelerator \<HcclAccelerator\>**: optional. This parameter is supported only by the Ascend 950PR&950DT product series and is used to set the acceleration mode.
  - default: Uses the default adaptive acceleration mode, which automatically selects an appropriate mode based on factors such as networking and data volume.
  - aicpu_ts: Uses the AI CPU compute unit on the Device side for acceleration.
  - aiv: Uses the Vector Core compute unit on the Device side for acceleration. In the case of large data volumes, it may fall back to other acceleration modes.
  - ccu_ms: Uses the CCU MS (Memory Slice) mode for acceleration. Ascend 950PR does not support this configuration.
  - ccu_sched: Uses the CCU scheduling mode for acceleration.
  - host_ts: This configuration is not supported.
  - aiv_only: Uses the AI Core compute unit on the Device side for acceleration. Compared with the aiv acceleration mode, no fallback occurs.

  **Note: The priority of this configuration is higher than that of the environment variable HCCL_OP_EXPANSION_MODE.**
  <!-- end id3 -->

- **-s \<0/1\> or --nslb \<0/1\>**: Optional. Whether to enable the NSLB-DP (Network Scale Load Balance-Data Plane) feature.
  - 0 (default value): Not enabled.
  - 1: Enable.

- **-n \<iters_count\> or --iters \<iters_count\>**: optional, number of iterations, default value: 20.

- **-w \<warmup_iters_count\> or --warmup_iters \<warmup_iters_count\>**: optional, number of warm-up iterations. This parameter is not included in performance statistics and only affects the execution time of the HCCL Test tool. Default value: 10.

    > [!NOTE] Note
    > Because the first few iterations may involve operations that affect performance testing (for example, socket connection establishment in the first iteration), it is recommended that the first few iterations be set as warm-up iterations and excluded from performance statistics.

- **-t or --onlydevicetime**: optional, excludes the software time consumption of the communication operator on the host side and the kernel loading time from the communication execution time, and counts only the execution time on the device side (that is, the key part that affects the execution time of the HCCL Test tool).

  - 0 (default value): disables this feature and counts the total execution time of the communication operator.
  - 1: enables this feature and counts only the execution time on the device side.

      When this feature is enabled, note the following points:
    - Only the Vector Core or CCU on the device side is supported as the orchestration expansion location of the communication algorithm.
    - The configured value of HCCL_BUFFSIZE must be greater than 100 MB; otherwise, this feature does not take effect.
    - The values of "-w" and "-n" cannot be greater than "100".

- **-c \<0/1\> or --check \<0/1\>**: optional. Whether to enable correctness verification of the collective communication operation results.

  - 0: Disables verification.
  - 1 (default value): Enables verification without outputting detailed error information.
  - 2: Enables verification and outputs detailed error information.

    > [!NOTE] Note
    > In large-scale cluster scenarios, enabling result verification increases the execution time of the HCCL Test tool.
