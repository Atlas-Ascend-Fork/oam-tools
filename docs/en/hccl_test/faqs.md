# FAQs

<!-- md-trans-meta sourceCommit=38db658ea4f8dfa2b0e1aaf6e53782372ffc7974 translatedAt=2026-10-10T12:02:02.244Z pushedAt=2026-10-15T10:42:37.453Z -->

## gethostbyname failed

### Symptom

When the mpirun command is executed, the "gethostbyname failed" error is reported, as follows:

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

### Solution

Add the IP address and the corresponding host name of the current node to the "/etc/hosts" file. For example, in the environment where the preceding error occurs, the host name is "HW-AI-LC-1-1". Assuming its IP address is 172.16.0.100, add the following information to the "/etc/hosts" file:

```text
172.16.0.100 HW-AI-LC-1-1
```

## MPI Library File Linking Error

### Symptom

When the mpirun command is executed, the following error is reported: "error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory", as follows:

```text
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
./all_reduce_test: error while loading shared libraries: libmpi.so.12: cannot open shared object file: No such file or directory
```

### Solution

Add the MPI lib library to the LD_LIBRARY_PATH environment variable, for example:

```bash
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/mpich/lib
```

## "bash:orted: command not found" Error

### Symptom

In a cluster scenario, when you run the mpirun command, the error "bash: orted: command not found" is reported, as follows:

```text
bash: orted: command not found
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

### Possible Causes

There are hccl_test processes that have not exited in the cluster.

### Solution

Use the MPI capability to terminate the residual hccl_test processes.

1. Prepare the Hostfile configured when running the HCCL Test tool, for example, a file named "hostfile".
2. Terminate the hccl_test processes involved on all nodes in the cluster.
    - For the MPICH scenario, the command example is as follows:

        **mpirun -f hostfile -n 512 pkill -9 -f "all_reduce_test|mpirun"**

        - -f: MPICH command parameter, indicating the Hostfile node list file.
        - -n: MPICH command parameter, indicating the total number of NPUs to be terminated, i.e., the number of nodes \* the number of NPUs that participate in training on each node. Please adjust according to the actual situation.
        - pkill: Linux command. The immediately following "-f" is a pkill parameter used to specify the pattern of the process name or command-line parameter to be matched. In the example, "all_reduce_test" is the previously executed HCCL test command. Please modify it according to the actually executed command.

    - For the Open MPI scenario, the command example is as follows:

        **mpirun -hostfile hostfile -n 512 pkill -9 -f "all_reduce_test|openmpi**"

        - -hostfile: Open MPI command parameter, indicating the Hostfile node list file.
        - -n: Open MPI command parameter, indicating the total number of NPUs to be terminated, i.e., the number of nodes \* the number of NPUs that participate in training on each node. Please adjust according to the actual situation.
        - pkill: Linux command. The immediately following "-f" is a pkill parameter, used to specify the pattern of the process name or command-line parameter to be matched. In the command example, "all_reduce_test" is the previously executed HCCL test command. Please modify it according to the actually executed command.

3. After the preceding steps are completed, run the HCCL Test tool again to perform the test.

## HCCL Test Returns "retcode: 7" Error

### Symptom

In a cluster scenario, when the HCCL Test command is executed, the HCCL Test tool starts successfully. However, after the header containing the data volume, time, and bandwidth is printed, an error occurs during subsequent execution. An example of the error is as follows:

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

### Possible Causes

There is an unterminated hccl_test process on a node in the cluster that communicates with the current node.

### Solution

Use the MPI capability to terminate the residual hccl_test processes.

1. Prepare the Hostfile configured when running the HCCL Test tool, for example, a file named "hostfile".
2. Terminate the hccl_test processes participating on all nodes in the cluster.
    - In the scenario where MPICH is installed, the command example is as follows:

        **mpirun -f hostfile -n 512 pkill -9 -f "all_reduce_test|mpirun**"

        - -f: MPICH command parameter, indicating the Hostfile node list file.
        - -n: MPICH command parameter, indicating the total number of NPUs to be terminated, i.e., the number of nodes \* the number of NPUs participating in training on each node. Please adjust according to the actual situation.
        - pkill: Linux command. The immediately following "-f" is a pkill parameter, used to specify the pattern of the process name or command-line parameter to be matched. In the command example, "all_reduce_test" is the previously executed HCCL test command. Please adjust it according to the actually executed command.

    - In the scenario where Open MPI is installed, the command example is as follows:

        **mpirun -hostfile hostfile -n 512 pkill -9 -f "all_reduce_test|openmpi**"

        - -hostfile: Open MPI command parameter, indicating the Hostfile node list file.
        - -n: Open MPI command parameter, indicating the total number of NPUs to be terminated, i.e., the number of nodes \* the number of NPUs on each node that participate in training. Please adjust according to the actual situation.
        - pkill: Linux command. The immediately following "-f" is a pkill parameter used to specify the pattern of the process name or command-line parameter to be matched. In the command example, "all_reduce_test" is the previously executed HCCL test command. Please adjust it according to the actually executed command.

3. After the preceding steps are completed, run the HCCL Test tool again to perform the test.
