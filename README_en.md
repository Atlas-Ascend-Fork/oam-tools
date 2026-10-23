<div align="center">

# OAM-Tools

English | [简体中文](./README.md)

**CANN Operations, Administration, and Maintenance Toolkit**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CANN](https://img.shields.io/badge/CANN-%E2%89%A58.5.0-green.svg)](./docs/en/quick_install.md)

</div>

## 📖 Overview

OAM-Tools (Operations, Administration, and Maintenance) is an open-source operations and maintenance toolkit for Huawei CANN, providing developers on Ascend AI processors with two core capabilities: **fault diagnosis** and **performance tuning**. The toolkit covers the complete O&M pipeline — from fault information collection and AI Core Error analysis to AI task performance profiling and analysis — helping developers quickly identify software/hardware issues and optimize AI task performance.

**Use cases**

- One-click fault information collection and AI Core Error root cause analysis when AI training/inference tasks encounter anomalies.
- AI task performance tuning: collect key performance indicators across runtime stages to identify bottlenecks.
- Testing collective communication (HCCL) functionality and performance in distributed training scenarios.

## ✨ Core Features

OAM-Tools includes four core components that collaboratively cover the full O&M scenario for Ascend AI processors:

| Component | Purpose | Key Capabilities | Documentation | Examples |
| --- | --- | --- | --- | --- |
| **asys** (Fault Information Collection) | One-click fault information collection and diagnosis | Fault information collection, business rerun with info collection, software/hardware & Device status display, health check, comprehensive detection, component detection, trace/coredump/stackcore/coretrace/UB file parsing, real-time stack export, AI Core Error fault info parsing, performance data collection | [User Guide](./docs/zh/user_guide/asys/README.md) | [Examples](./examples/README_en.md#asys-fault-information-collection-and-diagnosis) |
| **msaicerr** (AI Core Error Analysis) | AI Core Error problem localization | AI Core Error problem analysis, Dump file parsing and data type conversion, runtime environment check | [User Guide](./docs/zh/user_guide/msaicerr/README.md) | [Examples](./examples/README_en.md#msaicerr-ai-core-error-analysis) |
| **msprof** (Performance Tuning) | AI task performance collection and analysis | Collect AI task runtime performance data, AI processor system data, Host-side system data, msproftx data; support dynamic/delayed collection; provide ACL/Ascend Graph/acl.json/environment variable collection methods | [User Guide](./docs/zh/user_guide/profiling/README.md) | [Examples](./examples/README_en.md#msprof-performance-tuning) |
| **hccl_test** (HCCL Performance Test) | Collective communication functionality and performance testing | Test collective communication functionality and performance based on HCCL single-operator API in distributed training/inference scenarios | [User Guide](./docs/zh/user_guide/hccl_test/README.md) | — |

> Component user guides are currently available in Chinese only (`docs/zh/`); English translations are in progress.

## 🏗️ Project Architecture

OAM-Tools adopts a modular design where the four components are independent yet collaborative: asys and msaicerr focus on fault diagnosis, msprof on performance analysis, and hccl_test on communication testing. All components share the CANN runtime environment and are compiled and packaged into `.run` (default)/`.rpm`/`.deb` installation packages via a unified build system (CMake + build.sh). After installation, they are extracted to the `tools/` subdirectory of the CANN installation directory.

**Directory structure**:

```text
oam-tools/
├── cmake/                      # Build configuration (CMake modules, third-party library download scripts)
├── scripts/                    # Auxiliary build and check scripts (oat_check.sh, etc.)
├── src/                        # Source code
│   ├── asys/                   # asys: fault information collection tool (Python)
│   ├── msaicerr/               # msaicerr: AI Core Error analysis tool (Python)
│   ├── msprof/                 # msprof: performance tuning tool (C++ collector + Python analysis scripts)
│   ├── hccl_test/              # hccl_test: HCCL performance test tool (C++)
│   ├── operator_cmp/           # Operator comparison tool
│   └── third_party/            # Third-party library headers
├── test/                       # UT/ST test cases
├── docs/                       # Project documentation (Chinese/English)
│   ├── zh/                     # Chinese documentation (asys/msaicerr/profiling/hccl_test user guides)
│   ├── en/                     # English documentation
│   └── figures/                # Image assets
├── init_env.sh                 # Development environment one-click setup script
├── build.sh                    # Project build script
├── CMakeLists.txt              # CMake main configuration file
└── version.cmake               # Version and dependency declaration
```

## 🧩 Supported Hardware

Before setting up the environment, confirm that your hardware is within the supported scope. If you do not have Ascend devices, you can still build via Docker (see [Quick Installation](docs/en/quick_install.md#method-2-docker-deployment)).

- **CPU architecture**: `aarch64`, `x86_64`
- **Ascend AI processors**:

  | `npu-smi info` Name column | Applicable products | CANN ops package keyword |
  | --- | --- | --- |
  | `910B` | Atlas A2 training series / Atlas 800I A2 inference products | `910b` |
  | `910_93` | Atlas A3 training series / Atlas A3 inference series (the commercial name "910C" maps here) | `A3` |
  | `950` | Atlas 950 series products | `950` |

  > - `npu-smi info` may print sub-model suffixes (e.g. `910B1` / `910B2` / `910B3` / `910B4`); matching is by "Name column contains the keyword".
  > - "910C" is a commercial alias. Since CANN 8.5.0, the ops package is uniformly named `Ascend-cann-A3-ops_*`. Do not use `910c`, `910_c`, or `910_93` in the package name.
  > - Other chips are not yet supported — please open an issue. The full ops package naming convention and download instructions are in [Quick Installation](docs/en/quick_install.md#method-3-manual-installation).

## 🚀 Quick Start: From Source to a Verified Install

The shortest path from zero to a working install, using the default root installation path — complete the following four sections in order to get a usable toolkit. For third-party library customization, offline builds, debug builds and other full build options, plus per-component test verification, see the "Source Code Compilation" and "Installation and Verification" sections below.

### Install Dependencies

Follow the [Quick Installation Guide](./docs/en/quick_install.md) to install the CANN software packages and build dependencies.

### Build

```bash
# For non-root users, replace /usr/local with ${HOME}
source /usr/local/Ascend/cann/set_env.sh
bash build.sh
```

The build produces `build_out/cann-oam-tools_<cann_version>_linux-<arch>.run` (`<arch>` is `x86_64` or `aarch64`).

### Install the Package

```bash
./build_out/cann-oam-tools_<cann_version>_linux-<arch>.run --full
```

### Verify the Installation

Reload the environment variables and invoke asys — printing the help output means the installation succeeded:

```bash
source /usr/local/Ascend/cann/set_env.sh
asys -h
```

To exercise each component in a real environment, see the [usage examples](./examples/README_en.md).

## 🔧 Source Code Compilation

### Loading Environment Variables

Load the environment variables from your CANN installation path before compiling:

```bash
source <CANN_install_path>/set_env.sh
```

> Default path is `/usr/local/Ascend/cann` for root users, `${HOME}/Ascend/cann` for non-root users, and `${install_path}/cann` for custom installation paths.

### Running the Build

Run the following command to compile the project:

```bash
bash build.sh
```

To specify a third-party library path, use the `--cann_3rd_lib_path` parameter:

```bash
bash build.sh --cann_3rd_lib_path=${third_party_path}
```

To build rpm/deb format packages, specify the package format via the `--pkg-type` parameter:

- `--pkg-type=<TYPE>`: Specifies the package format. Valid values are `run`/`rpm`/`deb`/`deb,rpm`/`all` (`deb,rpm` and `all` build multiple package formats in one go); the default is `run` (`--pkg` is an alias for `--pkg-type=run`).
- Build artifacts: the run package is `cann-oam-tools_<cann_version>_linux-<arch>.run`, and the rpm/deb packages are `cann-oam-tools_<cann_version>_linux-<arch>.rpm/.deb`.
- Building rpm/deb packages additionally requires rpmbuild >= 4.14.0 / dpkg (>= 1.19.0.5), needed at build time only; for installing and uninstalling rpm/deb packages, see the [Package Installation Guide](./docs/en/package_install.md).

### Build Parameters and Dependencies

Parameters:
- `--cann_3rd_lib_path`: The directory for storing third-party libraries. The default value is `./third_party`. If third-party libraries do not exist locally, the build script automatically downloads the source code of each third-party library from the gitcode open source repository.
- The build process automatically downloads closed-source binary packages that contain the libraries and header files required for normal operation. Only release versions are provided. **Even if the build option specifies debug, only the release version tar package is downloaded**.
- Closed-source binary packages are fetched per branch. When not specified, the build script detects the release branch the current git commit belongs to (branches cut from `master` fetch the master package; branches on the 9.1.0 line fetch the 9.1.0 package), falling back to `master` when detection fails. You can also specify the branch explicitly with `--bundle_branch=<NAME>`, which is recommended when detection is inaccurate for personal branches. Branches with packages currently published on OBS are `master` and `9.1.0`; specifying any other branch fails at the configuration stage.
- The build process clones the `msprof` and `msprobe` submodules via `git clone` (used for building the msprof analysis wheel and syncing the msaccucmp tool, respectively). These submodules are hosted on gitcode and require a [gitcode personal access token](https://gitcode.com/setting/token-classic) configured for HTTPS cloning; otherwise, the clone will fail.
- If the build environment cannot access the network, refer to [Offline Build Environment Preparation](docs/en/quick_install.md#offline-build-environment-preparation) to complete the download and configuration of dependency packages in advance. Then specify the dependency package directory through the `--cann_3rd_lib_path` parameter before running the build. The offline prestaging script `cmake/download_libs.py` also supports `--bundle_branch` to select which branch's closed-source package to prestage (auto-detected by default); it must match the branch used at build time.
- Closed-source binary packages are extracted to `bundle/` in the repository root. If `bundle/` already exists and is non-empty, the build reuses it and skips downloading. To force a fresh download or recover from an incomplete `bundle/`, run `bash build.sh --make_clean` before rebuilding, or manually delete `bundle/` and run `bash build.sh` again.
- For more build parameters, run `bash build.sh -h`.

After the build completes, the `build_out` directory generates a `cann-oam-tools_<cann_version>_linux-<arch>.run` software package, where `<cann_version>` is the version number and `<arch>` is the operating system architecture (possible values: `x86_64` or `aarch64`).

## 📦 Installation and Verification

### Installation

The oam-tools package is available in three formats — `.run` (default), `.rpm`, and `.deb` — summarized below:

| Package Format | Target OS | Install Command | Install Path | Path Customization |
| --- | --- | --- | --- | --- |
| `.run` | Universal | `./build_out/cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}` | `${install_path}` | Supported (`--install-path`) |
| `.rpm` | RHEL/CentOS/openEuler and other rpm-based systems | `sudo rpm -ivh --nodeps <rpm>` (see the [Package Installation Guide](./docs/en/package_install.md)) | `/usr/local/Ascend/cann-<cann_version>` | Not supported |
| `.deb` | Ubuntu/Debian and other dpkg-based systems | `sudo dpkg -i --force-depends <deb>` (see the [Package Installation Guide](./docs/en/package_install.md)) | `/usr/local/Ascend/cann-<cann_version>` | Not supported |

rpm packages cannot be installed on Ubuntu/Debian — use the deb or run package on such systems (see the [Package Installation Guide](./docs/en/package_install.md) for background).

> **Note**: On hosts where CANN is not installed from deb/rpm packages, after installing this tool via the deb package, running `apt upgrade` or similar upgrade operations fails due to unmet dependencies (`apt --fix-broken install` removes this package); uninstall this package before performing apt upgrade operations. See the [Package Installation Guide](./docs/en/package_install.md) for details.

Run the following command to install the compiled oam-tools software package:

```bash
./build_out/cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}
```

After installation completes, the user-compiled oam-tools software package replaces the oam-tools related software in the installed CANN development kit package.

> If your environment has a `grep` version greater than 3.8.0, a warning appears during installation, for example `grep: warning: stray \ before -`. This occurs because newer grep versions have stricter validation of expressions, but does not affect installation and usage.

### Verification

After compilation, users can verify whether the project functions work properly.

> Python dependency installation is handled in [Environment Preparation](docs/en/quick_install.md). No additional operations are required.

```bash
# Run all component tests
bash build.sh -u

# Test a specific component (options: host / asys / msaicerr / msprof / install / upgrade / uninstall / all)
bash build.sh -u --component msprof
```

The `--component` options map to the test scope and setup documentation as follows:

| component | Test scope | Setup reference | Example |
| --- | --- | --- | --- |
| `host` | Pure Python Host UT (UT only) | Python and pytest; no CANN, device environment or C++ build required | `bash build.sh -u --component host --ut` |
| `asys` | asys Python UT + ST | [Environment Preparation](docs/en/quick_install.md#environment-preparation), [Environment Variable Configuration](docs/en/quick_install.md#environment-variable-configuration) | `bash build.sh -u --component asys` |
| `msaicerr` | msaicerr Python UT + ST | [Environment Preparation](docs/en/quick_install.md#environment-preparation), [Environment Variable Configuration](docs/en/quick_install.md#environment-variable-configuration) | `bash build.sh -u --component msaicerr` |
| `msprof` | msprof C++ gtest UT | [Source Code Compilation](#running-the-build), [Offline Build Environment Preparation](docs/en/quick_install.md#offline-build-environment-preparation) | `bash build.sh -u --component msprof --ut` |
| `install` | Package installation ST | [Source Code Compilation](#running-the-build), [Installation](#installation) | `bash build.sh -u --component install --st` |
| `upgrade` | Package upgrade ST | [Source Code Compilation](#running-the-build), [Installation](#installation) | `bash build.sh -u --component upgrade --st` |
| `uninstall` | Package uninstallation ST | [Source Code Compilation](#running-the-build), [Installation](#installation) | `bash build.sh -u --component uninstall --st` |
| `all` | All available UT + ST | [Environment Preparation](docs/en/quick_install.md#environment-preparation), [Source Code Compilation](#running-the-build) | `bash build.sh -u` |

> `install`, `upgrade`, and `uninstall` contain ST only and depend on `build_out/cann-oam-tools_<cann_version>_linux-<arch>.run`. Use the `build.sh -u --component ... --st` commands in the table so the package is built first. If you run `scripts/run_tests.sh` directly, make sure a usable `.run` package already exists under `build_out/`.

The UT test case compilation output directory is `build`. To clear historical build records:

```bash
rm -rf build_out/ build/
```

## 🅿️ Pre-commit

Pre-commit is a framework for managing and maintaining Git pre-commit hooks. By automatically executing code checks, formatting, and security scans before code submission, pre-commit ensures code quality and unifies team standards. This significantly reduces CI/CD pipeline failures and improves collaboration efficiency.

This repository has configured pre-commit. Users can refer to [Chapter 3 of the pre-commit configuration guide](https://gitcode.com/cann/infrastructure/blob/main/docs/SC/pre-commit/pre-commit%E9%85%8D%E7%BD%AE%E6%8C%87%E5%AF%BC%E4%B9%A6.md#3-%E7%A4%BE%E5%8C%BA%E8%B4%A1%E7%8C%AE%E8%80%85%E4%BD%BF%E7%94%A8pre-commit%E8%83%BD%E5%8A%9B) in the CANN community to install pre-commit. The OAT check tool has switched to the Python version oat-py (installed via `pip install oat-py>=1.0.0`), eliminating the need for Java/Maven environment configuration. The first run takes slightly longer as pre-commit creates isolated virtual environments for each hook.

## ℹ️ Related Information

- [Quick Installation Guide](./docs/en/quick_install.md): Installation of CANN software packages and build dependencies
- [Package Installation Guide](./docs/en/package_install.md): Installing and uninstalling rpm/deb packages
- [Environment Variable Reference](https://hiascend.com/document/redirect/CannCommunityEnvRef)
- [Contributing Guide](CONTRIBUTING_en.md): Community contribution process and standards
- [Security Statement](SECURITY_en.md)
- [License](LICENSE)
