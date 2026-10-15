# Installation Package Formats and Installation Guide

## Overview

OAM-Tools supports building installation packages in three formats: `.run` (default), `.rpm`, and `.deb`. The `.run` package does not depend on the system package manager; see [README_en.md](../../README_en.md) for the complete instructions on compiling, installing, and verifying it. This document describes OS matching, compilation, installation, running and verification, and uninstallation of the `.rpm` and `.deb` packages. The key differences between the three package formats are summarized in the table below; the applicable scenarios of the installation commands are explained in the [Installation](#installation) section:

| Package Format | Applicable OS | Installation Command | Installation Path | Path Customizable |
| --- | --- | --- | --- | --- |
| `.run` (default) | Independent of the system package manager; all operating systems (requires a matching CANN environment already installed) | `./cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}` | Follows the locally installed CANN suite directory | Yes, specified via `--install-path=<path>` |
| `.rpm` | rpm-based operating systems such as RHEL/CentOS/openEuler | CANN dependencies registered in the local rpm database:<br>`sudo rpm -ivh cann-oam-tools_<cann_version>_linux-<arch>.rpm`<br>CANN installed via the `.run` package:<br>`sudo rpm -ivh --nodeps cann-oam-tools_<cann_version>_linux-<arch>.rpm` | `/usr/local/Ascend/cann-<cann_version>` | Fixed, not customizable |
| `.deb` | deb-based operating systems such as Ubuntu/Debian | CANN dependencies registered in the local dpkg database:<br>`sudo dpkg -i cann-oam-tools_<cann_version>_linux-<arch>.deb`<br>CANN installed via the `.run` package:<br>`sudo dpkg -i --force-depends cann-oam-tools_<cann_version>_linux-<arch>.deb` | `/usr/local/Ascend/cann-<cann_version>` | Fixed, not customizable |

## OS Ecosystem Background

Mainstream Linux package management falls into two ecosystems: the Debian family (Ubuntu, Debian, etc.) uses dpkg as the underlying package manager (with various front ends such as apt), while the RHEL family (RHEL, CentOS, openEuler, openSUSE, Kylin, etc.) uses rpm as the underlying package manager (with various front ends such as yum/dnf/zypper). Choose the installation package format that matches the ecosystem of your machine.

> **Selection advice**: On Ubuntu/Debian systems, install the deb package — installing this tool from the rpm package is not supported (**building** the rpm package on Ubuntu/Debian is possible). On rpm-based systems such as RHEL/CentOS/openEuler/openSUSE/Kylin, install the rpm package; likewise, the deb package is not used on rpm-based systems. The `.run` package is independent of package managers and can be installed on all operating systems.

## Prerequisites

When building rpm/deb packages, the build environment must additionally meet the following tool version requirements (all of them are build-time dependencies):

- rpmbuild >= 4.14.0 (only required when building the rpm package; provided by the rpm-build (RHEL family) or rpm (Debian family) package, verifiable via `rpmbuild --version`; verified on 4.18.2)
- dpkg >= 1.19.0.5 (only required when building the deb package)
- cmake >= 3.18 (closed-source bundle extraction uses the `file(ARCHIVE_EXTRACT)` command; older versions block in `cmake/install_bundle.cmake` during the bundle fetch stage. This is triggered by any first build or post-`build.sh --make_clean` build regardless of package format, not only rpm/deb.)

> **Note**: The rpm version requirement is based on the gzip compression format of this tool's rpm package payload. The other build dependencies (Python, gcc, CANN toolkit/ops packages, etc.) are the same as for building the `.run` package, among which cmake must be >= 3.18; see the [Environment Deployment "Prerequisites" section](quick_install.md#prerequisites) for the complete list of the rpm/dpkg packaging tool entries above and all build dependencies.

## Compilation

The general compilation preconditions and environment preparation (loading CANN environment variables, third-party library paths, offline compilation, etc.) are the same as for building the `.run` package; see the "Source Code Compilation" section of [README_en.md](../../README_en.md) for details. This document does not repeat them. On that basis, specify the target package format with the `--pkg-type` parameter:

```bash
# Build the rpm package
bash build.sh --pkg-type=rpm

# Build the deb package
bash build.sh --pkg-type=deb
```

`--pkg-type` supports five values: `run`/`rpm`/`deb`/`deb,rpm`/`all`, with `run` as the default; `--pkg` is an alias for `--pkg-type=run`. Among them, `deb,rpm` builds both the deb and rpm packages in one go, and `all` builds all three package formats (run, rpm, and deb) in one go.

Build artifacts are located in the `build_out` directory:

| Package Format | Artifact Name |
| --- | --- |
| rpm package | `build_out/cann-oam-tools_<cann_version>_linux-<arch>.rpm` |
| deb package | `build_out/cann-oam-tools_<cann_version>_linux-<arch>.deb` |
| run package (default) | `build_out/cann-oam-tools_<cann_version>_linux-<arch>.run` |

Example artifact name from an actual build: `cann-oam-tools_9.1.0_linux-aarch64.deb`.

> **Note**: `<cann_version>` is the CANN version number and `<arch>` is the operating system architecture. The artifact name pattern has been verified in an actual build; artifact names for the x86_64 architecture are inferred from the pattern.

## Installation

The rpm/deb packages declare 16 CANN dependencies (see the complete list below) in their package manager dependency fields. The installation command varies with how the CANN suite is installed on your machine: on hosts where the CANN dependencies have been installed from deb/rpm packages and registered in the local package manager database (the dependency check passes), the package can be installed directly; on hosts where CANN is installed via the `.run` package (the common form for open-source users who build and install CANN themselves, where the CANN components are not registered in the system package manager database), you must skip the dependency check with `--force-depends`/`--nodeps` during installation.

Dependency sub-package list (the deb `Depends` field and the rpm `Requires` field are identical, with a minimum version of 9.0 for all): `npu-runtime`, `bisheng-compiler`, `ops-cv`, `ops-math`, `ops-legacy`, `metadef`, `hcomm`, `hccl`, `ge-executor`, `ge-compiler`, `tbe-tik`, `asc-devkit`, `graph-autofusion`, `opbase`, `ops-nn`, `ops-transformer`.

### Installing the deb Package

```bash
# Scenario 1: CANN dependencies installed from deb packages and registered in the local dpkg database
sudo dpkg -i cann-oam-tools_<cann_version>_linux-<arch>.deb

# Scenario 2: CANN installed via the .run package (not registered in the dpkg database)
sudo dpkg -i --force-depends cann-oam-tools_<cann_version>_linux-<arch>.deb
```

Failure mode of Scenario 2 (verified): on a host where CANN was installed via the `.run` package, running `sudo dpkg -i` directly (without `--force-depends`) unpacks the package but fails during configuration (exit code 1), leaving the package in a half-configured state (dpkg status iU): the post-installation script (postinst) does not run, and symbolic links such as `bin`/`include`/`lib64`/`conf`/`pkg_inc` are not created. At this point the tool files are already unpacked and can still be invoked via absolute paths, but the package state is abnormal and triggers the apt issue described in [Notes](#notes); simply re-running the Scenario 2 command restores the package to a properly configured state.

### Installing the rpm Package

```bash
# Scenario 1: CANN dependencies installed from rpm packages and registered in the local rpm database
sudo rpm -ivh cann-oam-tools_<cann_version>_linux-<arch>.rpm

# Scenario 2: CANN installed via the .run package (not registered in the rpm database)
sudo rpm -ivh --nodeps cann-oam-tools_<cann_version>_linux-<arch>.rpm
```

Failure mode of Scenario 2 (verified): on a host whose rpm database has no record of the CANN dependencies, running `sudo rpm -ivh` directly (without `--nodeps`) fails with a "Failed dependencies" error (17 entries observed in actual testing: the 16 CANN dependencies plus `/bin/sh`), and no files are unpacked.

> **Note**: The Scenario 1 installation (CANN dependencies registered in the local rpm database, no `--nodeps` required) has not yet been verified on real rpm-based systems; Scenario 2 has been verified in an actual test environment.
>
> **Note**: `dpkg -i` / `rpm -ivh` only verify the local package database and never automatically resolve or download missing dependencies from software repositories; to have the dependencies resolved and installed from repositories instead, use `apt install ./<deb>` (deb-based) or `dnf|yum|zypper install ./<rpm>` (choose by distribution), which requires the corresponding CANN dependency packages to be already available in the repositories.

### Installation Path

The installation path of the rpm/deb packages is fixed to `/usr/local/Ascend/cann-<cann_version>` and **cannot be customized**. After installation, the four major components (asys, msaicerr, msprof, and hccl_test) are located in the `tools/` subdirectory of that directory. The path differences from the `.run` package are as follows:

| Package Format | Installation Path | Path Customizable |
| --- | --- | --- |
| `.rpm` / `.deb` | Fixed to `/usr/local/Ascend/cann-<cann_version>` | Not customizable |
| `.run` | Follows the locally installed CANN suite directory | Yes, specified via `--install-path=<path>` |

This fixed prefix is generated at build time by the packaging configuration (CPACK_PACKAGING_INSTALL_PREFIX), in the form `/usr/local/Ascend/cann-9.1.0`; it differs from the default `.run` package installation path `/usr/local/Ascend/cann`, which is the expected behavior of the rpm/deb package formats.

## Running and Verification

The rpm/deb packages do not contain the `set_env.sh` environment script, and environment variables are not configured automatically after installation. You can run the tools in either of the following ways:

- **Invocation via absolute path (for installation verification)**: Calling the tools directly with their full paths is sufficient for installation verification such as printing help information and importing modules, without configuring environment variables.
- **Load the CANN environment before running full functionality**: Full functionality such as collection, parsing, and profiling depends on the library paths and environment variables of the locally installed CANN; before running it, load the environment variables of the locally installed CANN first (for example, `source <CANN installation path>/set_env.sh`, consistent with how the `.run` package is used).

After installation, run the following commands to verify (the installation succeeded if asys and msprof print their help information normally and the msaicerr module imports normally; all three commands passed verification in actual testing):

```bash
# Verify asys (fault information collection)
python3 /usr/local/Ascend/cann-<cann_version>/tools/ascend_system_advisor/asys/asys.py --help

# Verify msprof (performance tuning)
/usr/local/Ascend/cann-<cann_version>/tools/profiler/bin/msprof --help

# Verify that the msaicerr (AI Core Error analysis) Python module can be imported
python3 -c "import sys; sys.path.insert(0, '/usr/local/Ascend/cann-<cann_version>/tools/msaicerr'); import ms_interface"
```

hccl_test is a source-code build tool; after installation it is located in `<install_path>/tools/hccl_test/` (containing the Makefile and sources) — see the README in that directory for usage.

## Uninstallation and Reinstallation

The rpm and deb packages share the same package name, `oam-tools`, which is the target to operate on when uninstalling:

```bash
# Uninstall the deb package
sudo dpkg -r oam-tools

# Uninstall the rpm package
sudo rpm -e oam-tools
```

Uninstallation behavior (verified):

- Uninstallation cleans up this package's own files and the `bin`/`include`/`lib64`/`conf`/`pkg_inc` symbolic links created during installation; shared paths are removed as empty directories only when no other CANN package occupies them (the uninstallation script determines this via the component registration information in `var/ascend_package_db.info`, and `rmdir` removes empty directories only).
- The installation root directory `/usr/local/Ascend/cann-<cann_version>` is removed together only when this tool is installed standalone (the prefix is not shared with other CANN packages) — this scenario was verified in actual testing with zero residue; in Scenario 1, where the prefix is shared, the root directory is retained, and the content of other CANN packages under the same prefix is not affected.
- `rpm -e` prints 2 harmless warnings during uninstallation (such as `file lib64/include: remove failed`); this is caused by the uninstallation script deleting the symbolic links first and does not affect the cleanup result.
- The `/usr/lib/.build-id/` symbolic links additionally created during rpm installation are also cleaned up during uninstallation.

To reinstall the deb package, there is no need to uninstall first; simply run the command matching your installation scenario again (Scenario 2 verified in actual testing; the post-installation script is idempotent and can be re-run):

```bash
# Scenario 1: CANN dependencies installed from deb packages and registered in the local dpkg database
sudo dpkg -i cann-oam-tools_<cann_version>_linux-<arch>.deb

# Scenario 2: CANN installed via the .run package (not registered in the dpkg database)
sudo dpkg -i --force-depends cann-oam-tools_<cann_version>_linux-<arch>.deb
```

Reinstalling the same version of the rpm package requires `--replacepkgs`: for an already-installed package of the same version, simply re-running `rpm -ivh` or `rpm -Uvh` fails with `package oam-tools-... is already installed` (verified in actual testing); adding `--replacepkgs` performs an overwriting reinstall (Scenario 2 verified in actual testing; the post-installation script is idempotent and can be re-run); to upgrade to a newer version of the rpm package, use `rpm -Uvh <newer-package>`:

```bash
# Scenario 1: CANN dependencies installed from rpm packages and registered in the local rpm database
sudo rpm -ivh --replacepkgs cann-oam-tools_<cann_version>_linux-<arch>.rpm

# Scenario 2: CANN installed via the .run package (not registered in the rpm database)
sudo rpm -ivh --nodeps --replacepkgs cann-oam-tools_<cann_version>_linux-<arch>.rpm
```

## Notes

- **CANN version compatibility must be ensured by the user**: When the `.run` package is installed, version compatibility with the local CANN is checked based on the `version.info` file inside the package; the rpm/deb packages do not perform this version compatibility check, but instead declare 16 CANN dependencies in their package manager dependency fields (see the [Installation](#installation) section for the complete list). When using rpm/deb packages, make sure a version-matched CANN toolkit and ops suite is installed on your machine (the minimum version declared in the dependency fields is 9.0). The 9.0 lower bound comes from the dependency declarations of `set_cann_run_dependencies` in `version.cmake` (both build and runtime dependencies are declared as >= 9.0) and is independent of the `version.info`-based compatibility check performed when the `.run` package is installed.
- **Uninstall this package before performing apt upgrade operations**: On hosts where CANN is not installed from deb packages, once this package is installed (whether in the half-configured or fully configured state), `apt --fix-broken install` removes oam-tools, `apt upgrade` fails due to unmet dependencies, and `apt-mark hold` does not mitigate the issue. Before performing apt upgrade operations, run `sudo dpkg -r oam-tools` to uninstall this package first.
- **Use only one package format per environment**: It is recommended to install this tool with only one package format (one of `.run`/`.rpm`/`.deb`) in the same environment to avoid mixed installations.
- **Installation on openEuler real machines is not yet verified**: The rpm package `--nodeps` installation and uninstallation behavior described in this document has been verified in an actual test environment; the installation scenario on rpm-based operating systems such as openEuler, where CANN dependencies are registered in the local rpm database (no `--nodeps` required), has not yet been verified on real machines.
