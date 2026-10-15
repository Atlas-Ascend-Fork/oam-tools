# 常见问题及解决方法

## gethostbyname failed

### 问题现象

执行mpirun命令时，报“gethostbyname failed”的错误，如下所示：

```text
Fatal error in MPI_Init: Other MPI error, error stack:
MPIR_Init_thread(474)...................:
MPID_Init(190)..........................: channel initialization failed
MPIDI_CH3_Init(89)......................:
MPID_nem_init(320)......................:
MPID_nem_tcp_init(173)..................:
MPID_nem_tcp_get_business_card(420):
MPID_nem_tcp_init(379)..................: gethostbyname failed, HW-AI-LC-1-1 (errno 2)
```

### 解决方法

在“/etc/hosts”文件中添加当前节点IP地址与对应的主机名信息，例如，上述报错环境其主机名为“HW-AI-LC-1-1”，假设其IP地址为172.16.0.100，则“/etc/hosts”文件中需要添加如下信息：

```text
172.16.0.100 HW-AI-LC-1-1
```

## MPI库文件链接错误

### 问题现象

执行mpirun命令时，报“error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory”的错误，如下所示：

```text
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
```

### 解决方法

在环境变量LD_LIBRARY_PATH中加入MPI的lib库，例如：

```bash
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/mpich/lib
```

## “bash:orted:未找到命令”错误

### 问题现象

集群场景下，执行mpirun命令时，报“bash: orted: 未找到命令”的错误，如下所示：

```text
bash: orted: 未找到命令
--------------------------------------------------------------------------
A daemon (pid 8793) died unexpectedly with status 127 while attempting
to launch so we are aborting.

There may be more information reported by the environment (see above).

This may be because the daemon was unable to find all the needed shared
libraries on the remote node. You may set your LD_LIBRARY_PATH to have the
location of the shared libraries on the remote nodes and this will
automatically be forwarded to the remote nodes.
--------------------------------------------------------------------------
--------------------------------------------------------------------------
mpirun noticed that the job aborted, but has no info as to the process
that caused that situation.
```

### 可能原因

集群中存在未退出的hccl_test进程。

### 解决方法

利用MPI的能力，终止残余的hccl_test进程。

1. 准备好执行HCCL Test工具时配置的Hostfile文件，例如文件名为“hostfile”。
2. 终止集群中所有节点上参与的hccl_test进程。
    - 安装MPICH的场景，命令示例如下：

        **mpirun -f hostfile -n 512 pkill -9 -f "all_reduce_test|mpirun**"

        - -f：MPICH命令参数，表示Hostfile节点列表文件。
        - -n：MPICH命令参数，表示需要终止的NPU总数，即节点数量\*每个节点上参与训练的NPU个数，请根据实际情况修改。
        - pkill：Linux命令，紧跟的“-f”为pkill参数，用于指定要匹配的进程名或命令行参数的模式，其中命令示例中的“all_reduce_test”是之前执行的HCCL测试命令，请根据实际执行的命令进行修改。

    - 安装Open MPI的场景，命令示例如下：

        **mpirun -hostfile hostfile -n 512 pkill -9 -f "all_reduce_test|openmpi**"

        - -hostfile：Open MPI命令参数，表示Hostfile节点列表文件。
        - -n：Open MPI命令参数，表示需要终止的NPU总数，即节点数量\*每个节点上参与训练的NPU个数，请根据实际情况修改。
        - pkill：Linux命令，紧跟的“-f”为pkill参数，用于指定要匹配的进程名或命令行参数的模式，其中命令示例中的“all_reduce_test”是之前执行的HCCL测试命令，请根据实际执行的命令进行修改。

3. 以上步骤执行完成后，再次执行HCCL Test工具进行测试即可。

## HCCL Test执行时返回“retcode: 7”错误

### 问题现象

集群场景下，执行HCCL Test测试命令时，HCCL Test工具已启动成功，但打印出数据量，时间，带宽的表头后，后续执行报错，报错示例如下所示：

```text
the minbytes is 8192, maxbytes is 2147483648, iters is 20, warmup_iters is 5
hccl interface return err ./common/src/hccl_test_common.cc:538, retcode: 7
This is an error in init_hcclComm.
hccl interface return err ./common/src/hccl_test_common.cc:538, retcode: 7
This is an error in init_hcclComm.
hccl interface return err ./common/src/hccl_test_common.cc:538, retcode: 7
This is an error in init_hcclComm.
hccl interface return err ./common/src/hccl_test_common.cc:538, retcode: 7
This is an error in init_hcclComm.
```

### 可能原因

集群中与当前节点通信的节点上存在未退出的hccl_test进程。

### 解决方法

利用MPI的能力，终止残余的hccl_test进程。

1. 准备好执行HCCL Test工具时配置的Hostfile文件，例如文件名为“hostfile”。
2. 终止集群中所有节点上参与的hccl_test进程。
    - 安装MPICH的场景，命令示例如下：

        **mpirun -f hostfile -n 512 pkill -9 -f "all_reduce_test|mpirun**"

        - -f：MPICH命令参数，表示Hostfile节点列表文件。
        - -n：MPICH命令参数，表示需要终止的NPU总数，即节点数量\*每个节点上参与训练的NPU个数，请根据实际情况修改。
        - pkill：Linux命令，紧跟的“-f”为pkill参数，用于指定要匹配的进程名或命令行参数的模式，其中命令示例中的“all_reduce_test”是之前执行的HCCL测试命令，请根据实际执行的命令进行修改。

    - 安装Open MPI的场景，命令示例如下：

        **mpirun -hostfile hostfile -n 512 pkill -9 -f "all_reduce_test|openmpi**"

        - -hostfile：Open MPI命令参数，表示Hostfile节点列表文件。
        - -n：Open MPI命令参数，表示需要终止的NPU总数，即节点数量\*每个节点上参与训练的NPU个数，请根据实际情况修改。
        - pkill：Linux命令，紧跟的“-f”为pkill参数，用于指定要匹配的进程名或命令行参数的模式，其中命令示例中的“all_reduce_test”是之前执行的HCCL测试命令，请根据实际执行的命令进行修改。

3. 以上步骤执行完成后，再次执行HCCL Test工具进行测试即可。
