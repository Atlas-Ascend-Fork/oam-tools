# Usage Examples

English | [简体中文](./README.md)

This directory provides ready-to-run examples for each OAM-Tools component. After completing the [build](../README_en.md#running-the-build) and [installation](../README_en.md#installation), follow this document to run the examples in a real environment and quickly verify tool functionality.

## Table of Contents

- [Environment Preparation](#environment-preparation)
- [One-Click Scripts](#one-click-scripts)
- [asys (Fault Information Collection and Diagnosis)](#asys-fault-information-collection-and-diagnosis)
- [msaicerr (AI Core Error Analysis)](#msaicerr-ai-core-error-analysis)
- [msprof (Performance Tuning)](#msprof-performance-tuning)

## Environment Preparation

After installation, the tools are extracted to the `tools/` subdirectory under the CANN installation directory (root user default: `/usr/local/Ascend/cann/tools/`). Load the environment variables before running any example:

```bash
# Root user default path; for non-root users, replace /usr/local with ${HOME}
source /usr/local/Ascend/cann/set_env.sh
# For a custom install path: source ${install_path}/cann/set_env.sh
```

> After running the command above, `${ASCEND_HOME_PATH}` points to the CANN installation directory:
>
> - Root user default: `/usr/local/Ascend/cann`
> - Non-root user default: `${HOME}/Ascend/cann`
> - Custom install path: `${install_path}/cann`

In addition, run `pip3 install -r ../requirements.txt` in the examples directory before running the examples. This installs the Python dependencies declared in [requirements.txt](../requirements.txt) at the repository root, including the seven third-party libraries such as sympy and scipy required for compiling the golden_op operator of the msaicerr example.

## One-Click Scripts

This directory ships ready-to-execute scripts for each scenario. Run them once the environment variables are loaded:

| Script | Description |
| --- | --- |
| [`asys/run.sh`](./asys/run.sh) | Check device health status with basic asys commands — the recommended starting point |
| [`msaicerr/run.sh`](./msaicerr/run.sh) | Run the built-in sample operator to check whether the software/hardware environment meets msaicerr requirements; runs right after installation |
| [`msprof/run.sh`](./msprof/run.sh) | Collect 5 seconds of system-level CPU/memory performance data; runs right after installation |
| [`deploy.sh`](./deploy.sh) | Run the three scripts above in sequence to exercise all examples at once |

```bash
# Run all examples at once
bash deploy.sh

# Or run the example for a single component
bash asys/run.sh
```

The sections below expand on the command examples for each component.

## asys (Fault Information Collection and Diagnosis)

The `src/asys/` directory contains both `asys.py` and a symlink `asys` pointing to it (`src/asys/asys -> ./asys.py`). CMake copies the whole directory verbatim via `install(DIRECTORY ${ASYS_DIR} ...)`, preserving the symlink. Both invocation forms therefore work after installation:

```bash
# Form 1: explicit python3 call
python3 ${ASCEND_HOME_PATH}/tools/ascend_system_advisor/asys/asys.py -h

# Form 2: call the symlink directly (asys.py has a #!/usr/bin/env python3 shebang)
${ASCEND_HOME_PATH}/tools/ascend_system_advisor/asys/asys -h
```

The asys subcommands are defined in the `Command` enum in `src/asys/cmdline/cmd_parser.py`: `info / health / collect / launch / diagnose / analyze / config / profiling`. Once the environment variables take effect, you can invoke `asys` directly:

```bash
# Collect host and device software/hardware info (independent of any task under diagnosis; typically an environment self-check)
asys info -r="status" -d=0

# Check device health status
asys health

# Collect existing O&M information and package it to the specified output directory
asys collect --output <output_dir>
```

For more usage, see the [asys Tool User Guide](../docs/zh/user_guide/asys/README.md).

## msaicerr (AI Core Error Analysis)

The msaicerr entry point is `src/msaicerr/msaicerr.py`, installed at `${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py`.

```bash
# 1) Parse an existing AI Core Error report directory, output results to <output_dir>
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -p <report_dir> -out <output_dir> -dev 0

# 2) Parse a single dump file (for dtype values, see the -h output)
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -d <dump_file> -out <output_dir> -dtype float16

# 3) Check whether the current environment meets msaicerr requirements (only needs the device id)
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -e -dev 0

# Full parameter description
python3 ${ASCEND_HOME_PATH}/tools/msaicerr/msaicerr.py -h
```

For more usage, see the [msaicerr Tool User Guide](../docs/zh/user_guide/msaicerr/README.md).

## msprof (Performance Tuning)

msprof consists of the C++ collectors (`basic`, `dvvp`) and the `msprof` Python wheel (analysis scripts). After `bash build.sh` completes, the wheel (`msprof-0.0.1-py3-none-any.whl`) is copied to `src/msprof/collector/dvvp/msprofbin/` and packaged into the `.run` installer; it is unpacked to `${ASCEND_HOME_PATH}/tools/profiler/profiler_tool/` at install time, so no manual `pip install` is needed.

The analysis scripts are invoked internally by the msprof collector pipeline (entry point `profiler_tool/analysis/msprof/msprof.py`) and do not register a standalone command in `PATH`. To run an analysis script manually, call the installed entry point with python3:

```bash
python3 ${ASCEND_HOME_PATH}/tools/profiler/profiler_tool/analysis/msprof/msprof.py -h
```

The C++ collectors are normally invoked as built-in components of the CANN profiler pipeline and developers do not need to run them directly; regression is covered by `bash build.sh -u --component msprof`, which runs the gtest cases (artifact `build/test/ut/msprof/msprofbin/msprof_bin_utest`).

For more usage, see the [Performance Tuning Tool User Guide](../docs/zh/user_guide/profiling/README.md).
