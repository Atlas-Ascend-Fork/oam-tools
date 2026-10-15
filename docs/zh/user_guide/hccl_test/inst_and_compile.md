# 工具安装与编译

HCCL Test工具依赖MPI启动多个进程，所以需要先安装MPI软件，再进行HCCL Test工具的编译。

## MPI安装与配置

> [!CAUTION]注意
> 以下MPI软件的相关操作仅供参考，相关步骤仅在EulerOS 2.12 SP12（aarch64架构，内核：5.10.0-136.12.0.86.h1498）的操作系统上经过验证，其他MPI版本可能存在兼容性问题，用户实际安装配置MPI时请以对应MPI版本的官方文档为准。

- 如果通信网卡仅使用IPv4协议：
    <!-- npu="950" id1 -->
  - 针对Ascend 950PR&950DT系列产品，请安装[MPICH 4.1.3](https://www.mpich.org/static/downloads/)版本或者[Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/)版本。
    <!-- end id1 -->
    <!-- npu="A3" id2 -->
  - 针对Atlas A3系列产品，请安装[MPICH 4.1.3](https://www.mpich.org/static/downloads/)版本或者[Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/)版本。
    <!-- end id2 -->
    <!-- npu="910b" id3 -->
  - 针对Atlas A2系列产品，请安装[MPICH 3.2.1](https://www.mpich.org/static/downloads/)版本或者[Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/)版本。
    <!-- end id3 -->
    <!-- npu="910" id4 -->
  - 针对Atlas训练系列产品，请安装[MPICH 3.2.1](https://www.mpich.org/static/downloads/)版本或者[Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/)版本。
    <!-- end id4 -->
    <!-- npu="310p" id5 -->
  - 针对Atlas推理系列产品，请安装[MPICH 3.2.1](https://www.mpich.org/static/downloads/)版本或者[Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/)版本。
    <!-- end id5 -->

- 如果通信网卡需要使用IPv6协议，请安装[Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/)版本。

下面分别介绍MPICH与Open MPI的安装配置流程。

### MPICH安装配置

1. 安装MPICH软件包。
   1. 下载并解压MPICH软件包。

       MPICH软件包下载地址：[MPI下载地址](https://www.mpich.org/static/downloads/)。

       获取到mpich-$\{version\}.tar.gz后，执行如下命令解压缩软件包。

        ```bash
        tar -zxvf mpich-${version}.tar.gz
        ```

        $\{version\}为MPICH的版本号。

   2. 进入MPICH解压后路径，并配置编译选项。

        ```bash
        cd mpich-${version}
        ./configure --disable-fortran  --prefix=/usr/local/mpich --with-device=ch3:nemesis
        ```

        - --disable-fortran：禁用Fortran语言支持。
        - --prefix：指定的MPI安装路径，用户可自定义。
        - --with-device：指定通信协议，不添加该参数则默认使用OFI协议，配置为ch3:nemesis时，指定使用TCP协议。需注意，MPICH 4.1.3版本下，必须使用TCP协议。

   3. 编译并安装MPICH。

        ```bash
        make && make install
        ```

        以上命令执行完成后MPICH会安装在“/usr/local/mpich”路径下。

        > [!NOTE]说明
        > 编译时可通过添加“-j ” 选项启用多线程编译，从而提升编译效率，例如：
        > make -j 32 && make install

2. 配置网络节点信息。

    将运行环境的IP地址加入到“/etc/hosts”文件中，格式为“IP地址 主机名”，示例如下：

    ```text
    172.16.0.100 node3
    ```

    其中“node3”为主机名，可通过执行“ hostname”命令获取。

    注意如果是Euler OS操作系统，需要执行如下命令使更新后的“/etc/hosts”文件生效：

    ```text
    nmcli c reload
    ```

3. 配置当前操作节点到集群通信节点的SSH信任关系，以支持集群通信节点远程SSH登录。

    以下仅为操作示例：

    1. 在当前操作节点生成密钥信息（如若环境中存在，可不重复执行）：

        ```bash
        ssh-keygen -t rsa
        ```

        例如密钥信息生成后，存储在“$HOME/.ssh/id_rsa.pub”文件中。

    2. 将操作节点的公钥文件复制到集群通信其他节点，实现SSH密钥登录远程主机。

        示例如下，其中$\{node_X__ip_address\}是需要与操作节点通信的节点IP地址。

        ```bash
        ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node3_ip_address}
        ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node4_ip_address}
        ```

    3. SSH登录上文中已设置好信任关系的节点，确认是否可以直接登录。

### Open MPI安装配置

1. 下载并解压Open MPI软件包。

    参见[Open MPI-4.1.5](https://www.open-mpi.org/software/ompi/v4.1/)下载4.1.5版本的软件包，例如：openmpi-4.1.5.tar.gz，然后执行如下命令解压缩软件包。

    ```bash
    tar -zxvf openmpi-4.1.5.tar.gz
    ```

    解压缩后Open MPI源码存储在openmpi-4.1.5路径下。

2. 编辑Open MPI源码相关配置文件，修改Open MPI支持的最大Host数量。
    1. 进入Open MPI源码存储路径。

        ```bash
        cd openmpi-4.1.5
        ```

    2. 修改“orte/mca/routed/radix/routed_radix_component.c”配置文件。

        ```text
        vi orte/mca/routed/radix/routed_radix_component.c
        ```

        修改配置参数“mca_routed_radix_component.radix”的值为“集群中总卡数/单Server中卡数”，例如：

        ```text
        mca_routed_radix_component.radix = 1024;
        ```

        保存退出。

    3. 修改“orte/mca/plm/rsh/plm_rsh_component.c”配置文件。

        ```text
        vi orte/mca/plm/rsh/plm_rsh_component.c
        ```

        修改配置参数“mca_plm_rsh_component.num_concurrent”的值为“集群中总卡数/单Server中卡数”，例如：

        ```text
        mca_plm_rsh_component.num_concurrent = 1024;
        ```

        保存退出。

3. 配置编译选项。

    ```bash
    ./configure --disable-fortran --enable-ipv6 --prefix=/usr/local/openmpi \
        --with-zlib=/usr
    ```

    - --disable-fortran：禁用Fortran语言支持。
    - --enable-ipv6：启用IPv6支持。
    - --prefix：配置的Open MPI的安装路径，用户可自定义。
    - --with-zlib：指定zlib压缩库的头文件和库文件搜索路径。

4. 编译并安装Open MPI。

    ```bash
    make && make install
    ```

    以上命令执行完成后Open MPI会安装在“/usr/local/openmpi”路径下。

    > [!NOTE]说明
    > 编译时可通过添加“-j ” 选项启用多线程编译，从而提升编译效率，例如：
    > make -j 32 && make install

5. 配置网络节点信息。

    将运行环境的主机信息加入到“/etc/hosts”文件中，格式为“IP地址 主机名”（主机名可通过执行“ hostname”命令获取），示例如下：

    ```text
    172.16.0.100 node1
    172.16.1.200 node2
    fec0::b6ef:69dc:337d:9a12 node3
    fec0::b6ef:998f:f3eb:4617 node4
    ```

    注意如果是Euler OS操作系统，需要执行如下命令使更新后的“/etc/hosts”文件生效：

    ```text
    nmcli c reload
    ```

6. 配置当前操作节点到集群通信节点的SSH信任关系，以支持集群通信节点远程SSH登录。

    以下仅为操作示例：

    1. 在当前操作节点生成密钥信息（如若环境中存在，可不重复执行）：

        ```bash
        ssh-keygen -t rsa
        ```

        例如密钥信息生成后，存储在“$HOME/.ssh/id_rsa.pub”文件中。

    2. 将操作节点公钥复制到集群通信其他节点，实现SSH密钥登录远程主机。
        - 如果通信网卡使用IPv4地址，公钥复制命令如下：

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node1_ipv4_address}
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node2_ipv4_address}
            ```

            例如：

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub 172.16.0.100
            ```

        - 如果通信网卡使用IPv6地址，公钥复制命令如下：

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node3_ipv6_address}%网卡名
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub ${node4_ipv6_address}%网卡名
            ```

            例如：

            ```bash
            ssh-copy-id -i $HOME/.ssh/id_rsa.pub fec0::b6ef:998f:f3eb:4617%enp189s0f0
            ```

    3. SSH登录到配置信任关系的节点，确认是否可以直接登录。

7. 配置Open MPI启动参数，此步骤仅在通信网卡使用IPv6协议时进行，若使用IPv4协议，跳过即可。

    ```bash
    export HYDRA_LAUNCHER_EXTRA_ARGS="-B 本节点的IPv6网卡名"
    ```

## HCCL Test工具编译

安装完MPI软件后，需要进行HCCL Test性能测试工具的编译。

1. 配置编译依赖环境变量。

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

2. 进入HCCL性能测试工具源码存放路径。

    ```bash
    cd ${INSTALL_DIR}/tools/hccl_test
    ```

3. 编译HCCL性能测试工具。

    - 安装MPICH的场景：

        ```bash
        make MPI_HOME=/usr/local/mpich ASCEND_DIR=${INSTALL_DIR}
        ```

    - 安装Open MPI的场景：

        ```bash
        make MPI_HOME=/usr/local/openmpi ASCEND_DIR=${INSTALL_DIR}
        ```

    其中“MPI_HOME”为MPI安装路径，“ASCEND_DIR”为CANN软件安装后文件存储路径。

    编译成功后，会在$\{INSTALL_DIR\}/tools/hccl_test/bin目录下生成集合通信性能测试工具的可执行文件，例如：

    all_gather_test、all_reduce_test等，每一个可执行文件对应一个集合通信算子。
