# Preparation Before Use

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-23T11:15:27.758Z pushedAt=2026-10-23T11:29:27.700Z nl=2 -->

## Introduction

The performance tuning tool collects and analyzes key performance metrics of AI tasks running on AI processors at each execution stage. Based on the output performance data, you can quickly identify software and hardware performance bottlenecks and improve the efficiency of AI task performance analysis.

## Environment Preparation

1. Select and install the appropriate CANN software packages based on your actual usage scenario, and configure the CANN environment variables.
   <!-- npu="950,A3,910b,910,310p,310b" id6 -->
   For details, see [CANN Software Installation](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/920/softwareinst/instg/instg_0000.html?OS=openEuler&InstallType=netyum).
   <!-- end id6 -->

    <!-- npu="950,A3,910b,910,310p,310b" id1 -->
    In the Ascend EP scenario, the msprof tool path is \$\{INSTALL\_DIR\}/tools/profiler/bin. Replace \$\{INSTALL\_DIR\} with the storage path of the installed CANN software. For example, if the software is installed by the root user, the default storage path is /usr/local/Ascend/cann.
    <!-- end id1 -->

    <!-- npu="310b" id2 -->
    In the Ascend RC scenario, the msprof tool path is /var
    <!-- end id2 -->

    <!-- @ref: oam-tools/res/docs/zh/profiling/preparation/before_you_start_res.md#id1 -->
2. Set the common environment variables.

    After installing the CANN software, when you compile and run programs as the CANN running user, log in to the environment as the CANN running user and run the `source ${INSTALL_DIR}/set_env.sh` command to set environment variables. Replace \$\{INSTALL\_DIR\} with the storage path of the installed CANN software. For example, if the software is installed by the root user, the default storage path is /usr/local/Ascend/cann.

3. Set the Python-related environment variables.

    If multiple Python 3 versions exist, the following uses Python 3.7.5 as an example. Modify the settings based on your actual environment.

    ```sh
    export PATH=/usr/local/python3.7.5/bin:$PATH
    # Set the library file path for python3.7.5.
    export LD_LIBRARY_PATH=/usr/local/python3.7.5/lib:$LD_LIBRARY_PATH
    ```

>[!NOTE]Note
>The preceding environment variables take effect only in the current window. You can write the preceding commands to the \~/.bashrc file to make them take effect permanently. The procedure is as follows:
>
>1. As the installation user, run `vi ~/.bashrc` in any directory and add the preceding content to the end of the file.
>2. Run the `:wq!` command to save the file and exit.
>3. Run `source ~/.bashrc` to make the environment variables take effect.

## Constraint

Before using this tool, understand the related usage constraints:

- Permission constraints
  - You must ensure the principle of least privilege is applied (for example, prohibit write access for other users, such as prohibiting 666 and 777 permissions).
  - Before using the performance analysis tool, ensure that the umask value of the execution user is greater than or equal to 0027. Otherwise, the directories and files where the obtained performance data is stored will have excessive permissions.
  - For security and least-privilege considerations, do not use high-privilege accounts such as root to run this tool. It is recommended to run it with a regular user account.
  - This tool is intended for development and debugging and is not recommended for use in production environments.
  - This tool depends on CANN and the corresponding driver software package. Before using this tool, install CANN and the corresponding driver software package, and use the `source` command to run the set\_env.sh environment variable file of CANN. For security, do not modify the environment variables involved in set\_env.sh after sourcing.
  - Ensure that performance data is stored in the current user's directory without symbolic links. Otherwise, security issues may arise.

  <!-- @ref: oam-tools/res/docs/zh/profiling/preparation/before_you_start_res.md#id2 -->

- Execution constraints
  - Multiple collection tasks cannot be launched simultaneously on the same Device. Two or more performance data collection methods cannot be enabled at the same time. For example, when Profiling is started using the msprof command line, the app cannot start Profiling data collection through the acl API.
    <!-- npu="950" id7 -->
    <br>In the scenario of Ascend 950PR&950DT products, multiple task-time collection tasks can be launched simultaneously on the same Device. When aic-mode is set to task-based, multiple aic-metrics collection tasks can be launched simultaneously on the same Device.
    <!-- end id7 -->
  - It is not recommended to use the performance data collection function together with the Dump function. Dump operations affect system performance. If the collection function and the Dump function are enabled at the same time, the collected performance data metrics will be inaccurate. Disable data Dump before starting collection.

- Data persistence constraints
  - It is recommended that the performance data collection time be within 5 minutes, and that memory and disk space at least 20 times the size of the raw performance data be reserved. The raw data size refers to the total size of data in the data directory after collection and persistence.
  - When a single collection task collects performance data and persists it, with all collection items enabled, the disk read/write speed must be guaranteed. The specific specifications are as follows:
    - When inference is performed on a single Device only, the disk read/write speed is not lower than 50 MB/s.
    - When training is performed on a single Device only, the disk read/write speed is not lower than 60 MB/s.
    - In the scenario of multiple Devices, the disk read/write speed is not lower than: the disk read/write speed specification of a single Device \* the number of Devices.

  - If the configured storage path runs out of disk space during performance data collection, the performance data cannot be written to disk. Ensure sufficient disk space is available. You can configure the --storage-limit parameter to prevent the disk from being filled up by the raw performance data written to disk.
  - If the configured storage path disk or the user directory runs out of space during performance data parsing, parsing may fail or files cannot be written to disk. You must clear the disk or user directory space yourself.

- Compatibility and scenario constraints
  - The tool requires Python 3.7.5 or later.
  - You must call the `aclInit()` API to complete initialization and the `aclFinalize()` API to complete deinitialization before complete performance data can be obtained.
  <!-- npu="950,A3,910b,910,310p,310b,IPV350" id5 -->
  - Application project development must follow the *[Application Development \(C&C++\)](https://gitcode.com/cann/docs/blob/9.2.0/docs/zh/app-dev/README.md)]* manual. If the application has already called the `aclInit()` API to complete initialization and called the `aclFinalize()` API, causing the tool collection process to not end normally, the collected data will be incomplete. Data collected in the last 1 second may be lost because it was not written to disk in time, but the lost data does not exceed 2 MB and does not affect the analysis of the performance data already written to disk.
  <!-- end id5 -->
  <!-- npu="950,A3,910b,910,310p,310b" id3 -->
  - For application projects developed with the pyACL API, when collecting performance data through the msprof command line, opening files with relative paths in the project Python script is not supported. If the Python script contains operations that open files with relative paths, an error occurs during performance data collection.
  <!-- end id3 -->
  <!-- npu="910b,910,310p" id4 -->
  - In the Ascend virtualization instance scenario, initiating system performance data collection on the SoC from within a container or virtual machine is not supported (except for NPU memory usage data).
  <!-- end id4 -->
