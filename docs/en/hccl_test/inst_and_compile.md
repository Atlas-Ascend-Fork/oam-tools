# Tool Installation and Compilation

<!-- md-trans-meta sourceCommit=38db658ea4f8dfa2b0e1aaf6e53782372ffc7974 translatedAt=2026-10-10T12:05:24.566Z pushedAt=2026-10-15T10:29:19.310Z -->

The HCCL Test tool relies on MPI to start multiple processes. Therefore, you need to install the MPI software before compiling the HCCL Test tool.

## MPI Installation and Configuration

> [!CAUTION]Note
> The following operations on MPI software are for reference only. The steps have been verified only on EulerOS 2.12 SP12 (aarch64 architecture, kernel: 5.10.0-136.12.0.86.h1498). Other MPI versions may have compatibility issues. When actually installing and configuring MPI, follow the official documentation of the corresponding MPI version.

- If the communication NIC uses only the IPv4 protocol:
    <!-- npu="950" id1 -->
  - For Ascend 950PR&950DT product series, install [MPICH 4.1.3](https://www.mpich.org/static/downloads/) or [Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/).
    <!-- end id1 -->
    <!-- npu="A3" id2 -->
  - For Atlas A3 product series, install [MPICH 4.1.3](https://www.mpich.org/static/downloads/) or [Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/).
    <!-- end id2 -->
    <!-- npu="910b" id3 -->
  - For Atlas A2 product series, install [MPICH 3.2.1](https://www.mpich.org/static/downloads/) or [Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/).
    <!-- end id3 -->
    <!-- npu="910" id4 -->
  - For Atlas training product series, install [MPICH 3.2.1](https://www.mpich.org/static/downloads/) or [Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/).
    <!-- end id4 -->
    <!-- npu="310p" id5 -->
  - For Atlas inference product series, install [MPICH 3.2.1](https://www.mpich.org/static/downloads/) or [Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/).
    <!-- end id5 -->

- If the communication NIC needs to use the IPv6 protocol, install [Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/).

The following describes the installation and configuration process of MPICH and Open MPI respectively.

### MPICH Installation and Configuration

1. Install the MPICH software package.
   1. Download and decompress the MPICH software package.

       MPICH software package download address: [MPI download address](https://www.mpich.org/static/downloads/).

       After obtaining mpich-$\{version\}.tar.gz, run the following command to decompress the software package.

        ```bash
        tar -zxvf mpich-${version}.tar.gz
        ```

        $\{version\} is the version number of MPICH.

   2. Enter the decompressed MPICH path and configure the compilation options.

        ```bash
        cd mpich-${version}
        ./configure --disable-fortran  --prefix=/usr/local/mpich --with-device=ch3:nemesis
        ```

        - --disable-fortran: disables Fortran language support.
        - --prefix: specifies the MPI installation path, which can be customized by the user.
        - --with-device: specifies the communication protocol. If this parameter is not added, the OFI protocol is used by default. When it is set to ch3:nemesis, the TCP protocol is used. Note that for MPICH 4.1.3, the TCP protocol must be used.

   3. Compile and install MPICH.

        ```bash
        make && make install
        ```

        After the preceding commands are executed, MPICH is installed under the "/usr/local/mpich" path.

        > [!NOTE]
        > During compilation, you can add the "-j " option to enable multi-threaded compilation, thereby improving compilation efficiency. For example:
        > make -j 32 && make install

2. Configure the network node information.

    Add the IP addresses of the runtime environment to the "/etc/hosts" file in the format of "IP address host name". An example is as follows:

    ```text
    172.16.0.100 node3
    ```

    In the example, "node3" is the host name, which can be obtained by running the " hostname" command.

    Note that if the operating system is Euler OS, run the following command to make the updated "/etc/hosts" file take effect:

    ```text
    nmcli c reload
    ```

3. Configure the SSH trust relationship from the current operation node to the cluster communication nodes to support remote SSH login to the cluster communication nodes.

    The following is only an operation example:

    1. Generate key information on the current operation node (if the key already exists in the environment, this step can be skipped):

        ```bash
        ssh-keygen -t rsa
        ```

        For example, after the key information is generated, it is stored in the "$HOME/.ssh/id_rsa.pub" file.

    2. Copy the public key file of the operation node to other nodes in the cluster communication to implement SSH key-based login to remote hosts.

        An example is as follows, where $\{node_X__ip_address\} is the IP address of the node that needs to communicate with the operation node.

        ```bash
        ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node3_ip_address}
        ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node4_ip_address}
        ```

    3. Log in to the node for which the trust relationship has been set up as described above via SSH, and confirm whether you can log in directly.

### Open MPI Installation and Configuration

1. Download and decompress the Open MPI software package.

    See [Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/) to download the software package of version 4.1.5, for example, openmpi-4.1.5.tar.gz, and then run the following command to decompress the software package.

    ```bash
    tar -zxvf openmpi-4.1.5.tar.gz
    ```

    After decompression, the Open MPI source code is stored under the openmpi-4.1.5 path.

2. Edit the relevant configuration files of the Open MPI source code to modify the maximum number of Hosts supported by Open MPI.
    1. Enter the path where the Open MPI source code is stored.

        ```bash
        cd openmpi-4.1.5
        ```

    2. Modify the "orte/mca/routed/radix/routed_radix_component.c" configuration file.

        ```text
        vi orte/mca/routed/radix/routed_radix_component.c
        ```

        Modify the value of the configuration parameter "mca_routed_radix_component.radix" to "total number of cards in the cluster / number of cards in a single Server", for example:

        ```text
        mca_routed_radix_component.radix = 1024;
        ```

        Save and exit.

    3. Modify the "orte/mca/plm/rsh/plm_rsh_component.c" configuration file.

        ```text
        vi orte/mca/plm/rsh/plm_rsh_component.c
        ```

        Modify the value of the configuration parameter "mca_plm_rsh_component.num_concurrent" to "total number of cards in the cluster / number of cards in a single server", for example:

        ```text
        mca_plm_rsh_component.num_concurrent = 1024;
        ```

        Save and exit.

3. Configure the compilation options.

    ```bash
    ./configure --disable-fortran --enable-ipv6 --prefix=/usr/local/openmpi
    ```

    - --disable-fortran: Disable Fortran language support.
    - --enable-ipv6: Enable IPv6 support.
    - --prefix: Installation path of Open MPI to be configured, which can be customized by the user.

4. Compile and install Open MPI.

    ```bash
    make && make install
    ```

    After the preceding commands are executed, Open MPI is installed under the "/usr/local/openmpi" path.

    > [!NOTE] Note
    > During compilation, you can add the "-j " option to enable multi-threaded compilation, thereby improving compilation efficiency, for example:
    > make -j 32 && make install

5. Configure the network node information.

    Add the host information of the running environment to the "/etc/hosts" file in the format "IP address host name" (the host name can be obtained by running the "hostname" command). An example is as follows:

    ```text
    172.16.0.100 node1
    172.16.1.200 node2
    fec0::b6ef:69dc:337d:9a12 node3
    fec0::b6ef:998f:f3eb:4617 node4
    ```

    Note that if the operating system is Euler OS, run the following command to make the updated "/etc/hosts" file take effect:

    ```text
    nmcli c reload
    ```

6. Configure the SSH trust relationship from the current operation node to the cluster communication nodes to support remote SSH login to the cluster communication nodes.

    The following is only an operation example:

    1. Generate key information on the current operation node (if it already exists in the environment, you do not need to run this step again):

        ```bash
        ssh-keygen -t rsa
        ```

        For example, after the key information is generated, it is stored in the "$HOME/.ssh/id_rsa.pub" file.

    2. Copy the public key of the operation node to other cluster communication nodes to implement SSH key-based login to remote hosts.
        - If the communication NIC uses an IPv4 address, the public key copy command is as follows:

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node1_ipv4_address}
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node2_ipv4_address}
            ```

            For example:

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub 172.16.0.100
            ```

        - If the communication NIC uses an IPv6 address, the public key copy command is as follows:

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node3_ipv6_address}%NIC name
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node4_ipv6_address}%NIC name
            ```

            For example:

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub fec0::b6ef:998f:f3eb:4617%enp189s0f0
            ```

    3. Log in to the node on which the trust relationship is configured over SSH and confirm that you can log in directly.

7. Configure the Open MPI startup parameters. This step is required only when the communication NIC uses the IPv6 protocol. If the IPv4 protocol is used, skip this step.

    ```bash
    export HYDRA_LAUNCHER_EXTRA_ARGS="-B IPv6 NIC name of the local node"
    ```

## HCCL Test Tool Compilation

After the MPI software is installed, you need to compile the HCCL Test performance test tool.

1. Configure the environment variables required for compilation.

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

    "INSTALL_DIR" is the path where CANN software files are stored after installation. "/usr/local/Ascend/cann" is the default installation path for the root user. If you install CANN as a non-root user or to a custom path, replace it accordingly.

    "/usr/local/mpich" and "/usr/local/openmpi" are the MPI installation paths. Replace them based on the actual situation.

2. Enter the directory where the HCCL performance test tool source code is stored.

    ```bash
    cd ${INSTALL_DIR}/tools/hccl_test
    ```

3. Compile the HCCL performance test tool.

    - Scenario where MPICH is installed:

        ```bash
        make MPI_HOME=/usr/local/mpich ASCEND_DIR=${INSTALL_DIR}
        ```

    - Scenario for installing Open MPI:

        ```bash
        make MPI_HOME=/usr/local/openmpi ASCEND_DIR=${INSTALL_DIR}
        ```

    "MPI_HOME" is the MPI installation path, and "ASCEND_DIR" is the path where CANN software files are stored after installation.

    After successful compilation, executable files of the collective communication performance test tool are generated under the $\{INSTALL_DIR\}/tools/hccl_test/bin directory, for example:

    all_gather_test, all_reduce_test, and so on. Each executable file corresponds to a collective communication operator.
