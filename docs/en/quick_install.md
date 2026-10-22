# Environment Deployment

This document is the basic environment setup for Oam-tools tools. The main purpose is to complete NPU driver, firmware, and CANN software (`Ascend-cann-toolkit` and `Ascend-cann-ops`) installation and complete Oam-Tools source code download in the running environment. Complete the basic environment setup and source code download by following the steps below.

## Environment Preparation

This project provides multiple ways to set up the Ascend environment. Choose according to your needs.

> **Note**: The meanings of build mode and runtime mode mentioned in this document are as follows. Choose according to your actual situation.
>
> - Build mode: For scenarios where you only compile this project without running, you only need to install the CANN toolkit package.
> - Runtime mode: For scenarios where you run this project (compile and run or pure run), you need to install driver and firmware, CANN toolkit package, and CANN ops package.

| Installation Method | Usage Instructions | Usage Scenario |
| ----- | ------ | ------ |
| WebIDE | CANNLab is an out-of-the-box cloud development environment for CANN community developers. It comes pre-installed with the full suite of development tools including CANN software, NPU computing power and WebIDE. It supports access via both web browser and local IDE client, facilitating community developers in three major development areas: operator development, model training and tuning, as well as AI application development.| Suitable for developers without Ascend devices.|
| Docker | Docker image is an efficient deployment method that pre-integrates CANN packages and necessary dependencies. Currently only applicable to Atlas A2 series products, OS only supports Ubuntu operating system. **Installs the latest commercial release CANN package by default**. |Suitable for developers who need to quickly set up the environment, with or without Ascend devices.|
| Manual Installation | Follow [Method 3: Manual Installation](#section_manual_install) in this document for environment preparation |Suitable for developers with Ascend devices who want to experience manual CANN package installation or experience the latest master branch capabilities.|

### Method 1: WebIDE Environment

For developers without Ascend devices, you can directly use the CANNLab cloud development environment, namely the **CANN One-Stop Development Platform**. This platform provides an online Ascend environment ready for immediate use. The required driver firmware, software packages and dependencies are pre-installed in the environment with no manual installation needed.

> **Note**:The environment comes with the latest commercial release of the CANN package by default. Please ensure version compatibility with the software when downloading source code. For more information about the development platform, refer to [CANNLab Guide](https://gitcode.com/org/cann/cannlab/docs).

1. Go to the open-source project and click the `CANNLab` button. If you have not registered or authenticated, complete registration and authentication following the on-screen prompts.

2. Create the environment and configure specifications according to the on-screen instructions. After starting the cloud development environment, click **Connect** to access the one-stop development platform.

After environment deployment completes, continue with the following steps:

1. **Install Python Dependencies**

   The WebIDE environment has pre-installed core dependencies. If other libraries are missing when running UT, execute the following command to supplement:

   ```bash
   pip3 install -r requirements.txt
   ```

2. **Verify Environment**

   Refer to the [Environment Verification](#environment-verification) section to confirm that the environment and driver are normal.

### Method 2: Docker Deployment

If you want to quickly set up an Ascend environment, you can use Docker image deployment.

> **Note**: The image file is relatively large and requires some time to download. Please wait patiently. For docker command option descriptions, query through `docker --help`.

1.**Download Image**

- Step 1: Log in to the host machine as root user. Ensure the host machine has installed Docker engine (version 1.11.2 or higher).
- Step 2: Pull the image that pre-integrates CANN software packages and development dependencies from the [Ascend Image Repository](https://www.hiascend.com/developer/ascendhub/detail/17da20d1c2b6493cb38765adeba85884). The command is as follows. Choose according to the actual architecture:

    ```bash
    # Example: Pull ARM architecture CANN development image
    docker pull --platform=arm64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    # Example: Pull X86 architecture CANN development image
    docker pull --platform=amd64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    ```

2.**Run Docker**
After pulling the image, start the container with specific parameters. Choose the corresponding scenario below based on whether you need to run samples (access NPU devices) in the container:

**Scenario 1: Need to Run Samples (Requires NPU Device Access)**

If you need to run samples or tests, the container needs to access the host's NPU devices. Taking Atlas A2 series products as an example:

```bash
docker run \
    --name  oam-tools \
    --device /dev/davinci0 \
    --device /dev/davinci_manager \
    --device /dev/devmm_svm \
    --device /dev/hisi_hdc \
    -v /usr/local/dcmi:/usr/local/dcmi \
    -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
    -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
    -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info \
    -v /etc/ascend_install.info:/etc/ascend_install.info \
    -it swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10 bash
```

| Parameter | Description | Notes |
| :--- | :--- | :--- |
| `--name oam-tools` | Specify a name for the container for easy management. | Can be customized. |
| `--device=/dev/davinci0` | Mount the 0th NPU device node. | If there are multiple cards, add them one by one (e.g., `--device=/dev/davinci1`). |
| `--device=/dev/davinci_manager` | Mount the device management interface. | Must be mounted. |
| `--device=/dev/devmm_svm` | Mount the device memory management module. | Must be mounted. |
| `--device=/dev/hisi_hdc` | Mount the HDC communication channel. | Must be mounted. |
| `-v /usr/local/dcmi:/usr/local/dcmi` | Mount the DCMI (Device Communication Management Interface) directory. | Required (when running samples). |
| `-v /usr/local/bin/npu-smi:...` | Mount the NPU monitoring tool for viewing NPU status. | Required (when running samples). |
| `-v /usr/local/Ascend/driver/...` | Mount the NPU driver library and version information. | Required (when running samples). |
| `-v /etc/ascend_install.info:...` | Mount the Ascend software installation information. | Required (when running samples). |
| `-it` | Combination of `-i` (interactive) and `-t` (allocate pseudo-terminal). | - |
| `swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10` | Specify the Docker image to run. |Ensure that this image name and tag match exactly with the image you pulled through `docker pull`. |
| `bash` | Command to execute immediately after container starts. | - |

**Scenario 2: Only Compile and Build (No Need to Run Samples)**

If you only need to compile and build the code without accessing NPU devices, use the following simplified command:

```bash
docker run --name oam-tools -it swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10 bash
```

| Parameter | Description | Notes |
| :--- | :--- | :--- |
| `--name oam-tools` | Specify a name for the container for easy management. | Can be customized. |
| `-it` | Combination of `-i` (interactive) and `-t` (allocate pseudo-terminal). | - |
| `swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10` | Specify the Docker image to run. |Ensure that this image name and tag match exactly with the image you pulled through `docker pull`. |
| `bash` | Command to execute immediately after container starts. | - |

3.**Initialize Environment**
After entering the container, execute the following command to initialize the environment:

```bash
curl -fsSL https://raw.gitcode.com/cann/oam-tools/raw/master/init_env.sh | bash
```

`init_env.sh` automatically installs the Python dependencies declared in the repository root `requirements.txt`. After environment deployment completes, continue with the following steps:

1. **Verify Environment**

   Refer to the [Environment Verification](#environment-verification) section to confirm that the environment and driver are normal.

<a id="section_manual_install"></a>

### Method 3: Manual Installation

For developers with Ascend devices, if you want to manually set up an Ascend environment, refer to the following steps.

#### Prerequisites

    The dependencies used for compiling this project source code are as follows. Note the version requirements.

    - python >= 3.10.0
    - gcc >= 7.3.0
    - cmake >= 3.18.0
    - ccache
    - CANN toolkit package: `Ascend-cann-toolkit_${cann_version}_linux-${arch}.run`
    - CANN ops package: `Ascend-cann-${chip_type}-ops_${cann_version}_linux-${arch}.run`
    - protobuf >= 25.1 (C++ build dependency fetched/linked by cmake, used to generate .pb.cc)
    - abseil >= 20230802.1
    - json >= 3.11.3
    - patch >= 2.7.6
    - dpkg >= 1.19.0.5 (only required when building the deb package)
    - rpmbuild >= 4.14.0 (only required when building the rpm package; provided by the rpm-build/rpm package)
    - coverage (only required when running UT, recommended version 7.13.2)
    - googletest (only required when running UT, recommended version 1.14.0)
    - mockcpp (only required when running UT, recommended version 2.7)
    - pytest (only required when running UT, recommended version 9.0.2)
    - pytest-mock (only required when running UT, recommended version 3.15.1)

    Python runtime dependencies (required by tools such as asys / msaicerr at runtime, installed via `pip install -r requirements.txt`) are listed in `requirements.txt` at the repository root. Note that `protobuf>=6.33.4` there refers to the Python package `protobuf` on PyPI, which uses a versioning scheme independent from the C++ protobuf 25.1 above; the two version numbers do not conflict.

    Where:
    - $\{chip\_type\}: Indicates the Ascend AI processor model (equivalent to `${soc_name}` below), used to compose the CANN ops package name. Run `npu-smi info` and read the `Name` column to identify the chip on this machine, then pick the matching ops package from the table below.
    - $\{cann\_version\}: Indicates the CANN package version number. Must match the Toolkit package version number.
    - $\{arch\}: Indicates the CPU architecture, such as aarch64, x86_64.

Currently supported chip models and their CANN ops packages:

| `npu-smi info` Name column | Applicable products | `${chip_type}` / `${soc_name}` | CANN ops package |
| --- | --- | --- | --- |
| `910B` | Atlas A2 training series / Atlas 800I A2 inference products | `910b` | `Ascend-cann-910b-ops_${cann_version}_linux-${arch}.run` |
| `910_93` | Atlas A3 training series / Atlas A3 inference series (the commercial name "910C" maps here) | `910_93` | `Ascend-cann-A3-ops_${cann_version}_linux-${arch}.run` |
| `950` | Atlas 950 series products | `950` | `Ascend-cann-950-ops_${cann_version}_linux-${arch}.run` |

> **Notes**
>
> - The Name column values above are the keywords this tool recognizes. `npu-smi info` may print a string with sub-model suffixes (e.g. `910B1` / `910B2` / `910B3` / `910B4` for the `910B` family); matching is by "Name column contains the keyword".
> - "910C" is a commercial alias. Since CANN 8.5.0, the ops package is uniformly named `Ascend-cann-A3-ops_*`. Do not use `910c`, `910_c`, or `910_93` in the package name.
> - The actual ops package filename and available versions follow the [CANN download page](https://www.hiascend.com/cann/download). Only the three chip families above are supported; please open an issue for any other chip you'd like added.

#### Software Installation

1. **Install Driver and Firmware (Runtime Dependency)**

    For driver and firmware download and installation operations, refer to the "Prepare Software Packages" and "Install NPU Driver and Firmware" chapters in the [CANN Software Installation Guide](https://www.hiascend.com/document/redirect/CannCommunityInstWizard). Driver and firmware are runtime dependencies. If you only compile operators, you do not need to install them.

2. **Install CANN Packages**

    - **Scenario 1: Experience master version capabilities or develop based on master version**

        Click [Download Link](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run-mirror/software/master/) to select the latest time version. Download the corresponding package according to product model and environment architecture. The installation command is as follows. For more guidance, refer to the [CANN Software Installation Guide](https://www.hiascend.com/document/redirect/CannCommunityInstWizard).

        1. Install CANN toolkit package

            ```bash
            # Ensure the installation package has executable permissions
            chmod +x Ascend-cann-toolkit_${cann_version}_linux-${arch}.run
            # Installation command
            ./Ascend-cann-toolkit_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
            ```

        2. Install CANN ops package (runtime dependency)

            The ops package is a runtime dependency. If you only compile operators, you do not need to install this package.

            ```bash
            # Ensure the installation package has executable permissions
            chmod +x Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run
            # Installation command
            ./Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
            ```

        - $\{cann\_version\}: Indicates the CANN package version number.
        - $\{arch\}: Indicates the CPU architecture, such as aarch64, x86_64.
        - $\{soc\_name\}: Indicates the NPU model name, equivalent to `${chip_type}` above. See the "supported chip models and CANN ops packages" table in the [Prerequisites](#prerequisites) section for valid values.
        - $\{install\_path\}: Indicates the specified installation path. The ops package must be installed in the same path as the toolkit package. For root user, the default installation is in the `/usr/local/Ascend` directory.

    - **Scenario 2: Experience released version capabilities or develop based on released version**

        Visit the [CANN Official Download Center](https://www.hiascend.com/cann/download), select the release version (only supports CANN 8.5.0 and subsequent versions), and download the corresponding package according to product model and environment architecture. Finally, complete the installation following the commands provided on the webpage.

After environment deployment completes, continue with the following steps:

1. **Install Python Dependencies**

   The manual installation environment requires you to configure Python dependencies yourself. Execute the following command to install the core packages required for UT:

   ```bash
   pip3 install -r requirements.txt
   ```

2. **Verify Environment**

   Refer to the [Environment Verification](#environment-verification) section to confirm that the environment and driver are normal.

## Source Code Download

The source code download command is as follows. Replace `${branch}` with the target branch tag name. For the relationship between source code branch tags and CANN versions, refer to the [release repository](https://gitcode.com/cann/release-management).

```bash
# Download project corresponding branch source code
git clone -b ${branch} https://gitcode.com/cann/oam-tools.git
```

For WebIDE or Docker environments, the latest commercial release version project source code is provided by default. If you need to obtain source code for other versions, you also need to download the source code through the above command.

> Note
>
> - When using the HTTPS protocol on the gitcode platform, configure and use a personal access token instead of the login password for clone, push, and other operations.
> - If your build environment cannot access the network and cannot download code through git commands, first download the source code in a networked environment, then manually upload it to the target environment.

<a id="offline-build-environment-preparation"></a>

## Offline Build Environment Preparation

If your build environment cannot access the network, you need to manually download third-party libraries, closed-source binary packages, and subrepositories in a networked environment, then manually upload them to your build environment.

### Download Dependency Packages

Run the download script in a networked environment. This script directly downloads and saves the above third-party libraries, closed-source binary packages, and subrepositories in the path where the command is executed. (Downloading subrepositories requires a git environment and [configure gitcode personal access token](https://gitcode.com/setting/token-classic) to ensure git clone can execute correctly)

```bash
# Save files in the current execution path. You can execute the command in different paths (need to modify the script relative path or use absolute path) to change the save location
python cmake/download_libs.py
```

Closed-source binary packages are fetched per branch. By default the script detects the release branch the current git commit belongs to (falling back to `master` when detection fails), using the same branch resolution rules as `build.sh` / `install_bundle.cmake` at build time. To prestage a specific branch, specify it explicitly with `--bundle_branch` (currently `master` or `9.1.0`; any other value fails):

```bash
# Explicitly prestage the closed-source package for the 9.1.0 branch;
# must match the later build with bash build.sh --bundle_branch=9.1.0
python cmake/download_libs.py --bundle_branch=9.1.0
```

> Note: The prestaged bundle branch must match the branch resolved at build time in the target environment; otherwise the build fails because the package for that branch is missing locally. Detection may be inaccurate for personal branches, so specifying `--bundle_branch` explicitly for both download and build is recommended.

### Upload Dependency Packages

Create a new `third_party_path` directory in the build environment to store third-party open source software and closed-source software

```bash
mkdir -p ${third_party_path}
```

After creating the directory, upload the downloaded third-party libraries, closed-source binary packages, and subrepositories to the `third_party_path` directory.

### Dependency Package List

Third-party libraries, closed-source binary packages, and subrepositories include:

| Open Source Software | Version | Download Address |
|---|---|---|
|protobuf|v25.1|[protobuf-25.1.tar.gz](https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1/protobuf-25.1.tar.gz)|
|makeself|2.5.0|[makeself-release-2.5.0.tar.gz](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself/makeself-release-2.5.0.tar.gz)|
|makeself-patch|2.5.0|[makeself-2.5.0.patch](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/makeself/fix/makeself-2.5.0.patch)|
|abseil-cpp|20230802.1|[abseil-cpp-20230802.1.tar.gz](https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1/abseil-cpp-20230802.1.tar.gz)|
|abseil-cpp-patch|20230802.1-h0|[backport-CVE-2025-0838.patch](https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1-h0/backport-CVE-2025-0838.patch)|
|boost|v1.87.0|[boost_1_87_0.tar.gz](https://gitcode.com/cann-src-third-party/boost/releases/download/v1.87.0/boost_1_87_0.tar.gz)|
|gtest|1.14.0|[googletest-1.14.0.tar.gz](https://gitcode.com/cann-src-third-party/googletest/releases/download/v1.14.0/googletest-1.14.0.tar.gz)|
|mockcpp-patch|2.7-h5|[mockcpp-2.7-h5.patch](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h5/mockcpp-2.7-h5.patch)|
|mockcpp|2.7-h2|[mockcpp-2.7.tar.gz](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7.tar.gz)|

> Note: The addresses above are consistent with the third-party packages actually fetched by cann-cmake at build time (the protobuf / abseil-cpp / boost / googletest / mockcpp source packages on gitcode are identical to the OBS packages verified by cann-cmake). When downloading manually, the three patch files makeself-2.5.0.patch, backport-CVE-2025-0838.patch, and mockcpp-2.7-h5.patch must be placed in the patch/ subdirectory of the dependency directory, while the other files are placed directly in the root of the dependency directory; the cmake/download_libs.py script saves files in this layout automatically.

Closed-source binary packages are fetched per branch. The table below uses the default `master` branch as an example; to prestage another branch, replace `master` in the address with the corresponding branch name (for example `9.1.0`), or run `python cmake/download_libs.py --bundle_branch=<branch>` to download the package for that branch automatically.

| Closed-source Binary | Branch | Download Address |
|---|---|---|
|cann-oam-tools-release-x86_64.tar.gz|master|[Download](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cann/oam-tools-diag/master/cann-oam-tools-release-x86_64.tar.gz)|
|cann-oam-tools-release-aarch64.tar.gz|master|[Download](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cann/oam-tools-diag/master/cann-oam-tools-release-aarch64.tar.gz)|

| Subrepository | Version | Download Address |
|---|---|---|
|msprobe|master|https://gitcode.com/Ascend/msprobe|
|msprof|master|https://gitcode.com/Ascend/msprof|
|cann-cmake|master-059|[cmake-master-059.tar.gz](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cmake/cmake-master-059.tar.gz)|

<a id="environment-verification"></a>

## Environment Verification

After installing CANN packages, verify whether the environment and driver are normal.

- **Check NPU Device**

    ```bash
    # Run npu-smi. If device information displays normally, the driver is normal
    npu-smi info
    ```

    Note the `Name` column in the output and cross-reference it with the "supported chip models and CANN ops packages" table in the [Prerequisites](#prerequisites) section to confirm the chip on this machine matches the installed CANN ops package. If the `Name` column is not in the table, the chip is not yet supported by this tool — please open an issue.
- **Check CANN Installation**

    ```bash
    # View CANN toolkit package version information (default path installation). For WebIDE scenarios, replace /usr/local with /home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_toolkit_install.info
    # View CANN ops package version information (default path installation). For WebIDE scenarios, replace /usr/local with /home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_ops_install.info
    ```

- **Check Python Dependencies**

    ```bash
    # Check pytest version
    pytest --version
    # Check coverage version
    coverage --version
    ```

    > If the command execution fails, execute `pip3 install -r requirements.txt` to install dependencies.

## Environment Variable Configuration

Choose the appropriate command according to your needs to make environment variables effective.

```bash
# Default path installation, using root user as example (for non-root user, replace /usr/local with ${HOME})
source /usr/local/Ascend/cann/set_env.sh
# Specified path installation
# source ${install_path}/cann/set_env.sh
```
