# Contributing Guide

This project welcomes developers to experience and contribute. Before participating in community contributions, please refer to [cann-community](https://gitcode.com/cann/community) to learn the [code of conduct](https://gitcode.com/cann/community/blob/master/contributor/code-of-conduct.md), complete the [CLA agreement signing](https://gitcode.com/cann/infrastructure/blob/master/docs/cla/cla_user_guide.en.md), and understand the contribution process of source repositories. Beyond code contributions, the community also welcomes contributions in various forms such as meetings, emails, and testing. For details, see the community [contribution overview](https://gitcode.com/cann/community#参与贡献).

If you wish to make advanced contributions to the community beyond this repository (such as creating a new SIG, becoming a core contributor, creating a new repository, or introducing open-source third-party components), please refer to the [CANN Community Contribution Guide](https://gitcode.com/cann/community#进阶贡献).

## Contribution Scenarios

Developer contribution scenarios mainly include:

- [Contributing New Features](#1-contributing-new-features)
- [Bug Fix](#2-bug-fix)
- [Documentation Correction](#3-documentation-correction)
- [Experience Feedback](#4-experience-feedback)
- [Help Solve Others' Issues](#5-help-solve-others-issues)

---

## 1. Contributing New Features

Thank you for participating in OAM-Tools development and bringing more value to Ascend O&M tooling! The complete contribution process is as follows:

> **Create an Issue** → **Solution Review** → **Development Environment Setup** → **PR Submission** → **CI Gate** → **Committer Review and Maintainer Merge**

### 1. Create an Issue (Solution Discussion)

If your contribution is not a simple bug fix but involves new features, new interfaces, new configuration parameters, or modifications to the code flow, please discuss the solution through an Issue first to avoid your code being rejected. If you are unsure whether your modification can be classified as a "simple bug fix," you can also discuss it by submitting an Issue.

Please create a `Requirement` type Issue to propose your idea. The Issue should include at least the following:

- **Background and motivation of the feature**: for example, what scenario requirements this feature addresses.
- **Core design solution**: briefly describe the technical approach for implementing this feature and the design of key modules.
- **Expected functional and performance goals**: for example, the core functions this feature must implement, and the expected performance improvement or locating accuracy gain.
- **Estimated completion time**: this helps the community understand development progress and facilitates subsequent collaborative support.

For specific steps, refer to the [Issue Operation Guide](https://gitcode.com/cann/community/blob/master/contributor/issue-operation.md).

### 2. Solution Review

After creating a requirement Issue, you need to submit a SIG topic and attend the [Tools SIG](https://gitcode.com/cann/community/blob/master/CANN/sigs/tools/README.md) review. For meeting arrangements, topic application methods, and Maintainer contact information, see the [Tools SIG description](https://gitcode.com/cann/community/blob/master/CANN/sigs/tools/README.md).

**Urgent requirements**: If your requirement is urgent, contact the Maintainer according to the Tools SIG description to request a temporary SIG review.

**Requirement acceptance**: If the requirement is accepted, [SIG members](https://gitcode.com/cann/community/blob/master/CANN/sigs/tools/sig-info.yaml) will assign you an appropriate integration path (such as the `experiment/` directory). Please submit the feature code to the corresponding directory.

### 3. Development Environment Setup

OAM-Tools depends on the Ascend CANN software stack. Please complete environment setup and source code building first to ensure that results can be reproduced and verified locally:

**Basic dependencies** (for complete environment deployment, see the [Quick Installation Guide](docs/en/quick_install.md)):

| Dependency | Version Requirement |
| ---------- | ------------------- |
| Python | >= 3.10.0 |
| GCC / CMake / patch | >= 7.3.0 / >= 3.18.0 / >= 2.7.6 |
| ccache | No version requirement (build acceleration) |
| CANN (Toolkit & Ops) | >= 8.5.0 (NPU driver / firmware must be installed in advance) |

Building the C++ components (msprof collector, hccl_test) additionally requires protobuf >= 25.1, abseil >= 20230802.1, and json >= 3.11.3 (fetched and linked automatically by `cmake/`). Running UTs also requires pytest / pytest-mock / coverage / googletest / mockcpp; for recommended versions, see the [Quick Installation Guide](docs/en/quick_install.md).

**Source code build and installation verification**:

```bash
# 1. Install Python dependencies and enable local code checks (see Appendix B)
pip3 install -r requirements.txt
pip3 install pre-commit
pre-commit install

# 2. Load CANN environment variables and build
#    The default path is /usr/local/Ascend/cann for the root user,
#    ${HOME}/Ascend/cann for non-root users, or ${install_path}/cann for
#    installation at a specified path
source <CANN installation path>/set_env.sh
bash build.sh

# 3. Install the built package and verify
#    ${cann_version} and ${arch} are obtained from the file name in the build_out/
#    directory, e.g. cann-oam-tools_9.1.0_linux-aarch64.run (arch is x86_64 or aarch64)
./build_out/cann-oam-tools_${cann_version}_linux-${arch}.run --full
source <CANN installation path>/set_env.sh
asys -h    # Printing the help information properly indicates a successful installation
```

> **Note**:
>
> - The build process pulls the `msprobe` sub-repository (used to sync the msaccucmp tool) via `git clone`. Before cloning over HTTPS, you need to [configure a GitCode personal access token](https://gitcode.com/setting/token-classic) to replace the login password; otherwise the clone fails. The msprof analysis wheel is downloaded from the OBS profiler run package at build time, so cloning the `msprof` source is not required; only offline build preparation (`cmake/download_libs.py`) additionally pulls `msprof`.
> - If the build environment has no network access, complete dependency package download in advance as described in [Offline Build Environment Preparation](docs/en/quick_install.md#offline-build-environment-preparation), and specify the dependency directory via `--cann_3rd_lib_path`.
> - Developers without Ascend hardware can build via Docker or the CANNLab cloud environment; see the [Quick Installation Guide](docs/en/quick_install.md).

**Unit tests** (recommended to run locally before submitting a PR):

```bash
bash build.sh -u                     # Build and run all tests
bash build.sh -u --component asys    # Run only the specified component (options: host / asys / msaicerr / msprof / install / upgrade / uninstall / all)
```

### 4. PR Submission

#### Delivery Requirements

| Scenario | Delivery Requirements | Reference |
| -------- | --------------------- | --------- |
| New asys / msaicerr tool capabilities (new commands, subcommands, parameters, or parsing capabilities) | Feature code + UT / ST cases + user guide updates in both Chinese and English (`docs/zh/user_guide/`, `docs/en/user_guide/`) | [asys User Guide](docs/en/user_guide/asys/README.md), [msaicerr User Guide](docs/en/user_guide/msaicerr/README.md) |
| msprof / hccl_test component features (C++ collector, collective communication tests) | Feature code + gtest UT cases + user guide updates in both Chinese and English (`docs/zh/user_guide/`, `docs/en/user_guide/`) | [msprof User Guide](docs/en/user_guide/profiling/README.md), [hccl_test User Guide](docs/en/user_guide/hccl_test/README.md) |
| Experimental features (`experiment/`) | Feature code + README documentation | [experiment/](experiment/) |
| Running examples (`examples/`) | Example scripts + example documentation | [examples/README.md](examples/README.md) |

If your feature has not undergone strong generalization testing, it is recommended to merge the feature code into the `experiment/` directory. For directory organization, refer to existing features (such as [msprof_experience_demo](experiment/task-book/msprof_experience_demo/)). For the complete structure, see [Appendix A](#appendix-a-delivery-directory-structure).

#### Compliance Checklist

Before submitting, please perform a self-check on each item:

- [ ] Does the code comply with the [C++ Coding Standards](https://gitcode.com/cann/community/blob/master/contributor/coding-standards/C++%20Coding%20standards.md) or the Python standards (for the tool matrix of this repository, see [Appendix B](#appendix-b-coding-standards-and-local-checks))?
- [ ] Does the code compile successfully (`bash build.sh`), and do the UTs / STs pass (`bash build.sh -u`)?
- [ ] Does the Markdown documentation syntax comply with the specifications?
- [ ] Is the LICENSE used compliant? Licenses such as Apache 2.0 are recommended, with copyright information marked according to actual conditions.
- [ ] The merged code contains no binary files (except for images needed in README or documentation).
- [ ] If third-party datasets are involved, only describe the download and usage methods in the documentation; there is no need to provide the datasets directly.
- [ ] If the modification involves public code (not code internal to the feature), it can pass CI validation.

#### Submission Conventions

- **Target branch**: Submit PRs to the `master` branch.
- **PR title**: Follow the Conventional Commits specification (`feat:` / `fix:` / `docs:` / `perf:` / `refactor:` etc.). It is recommended to associate the Issue number, such as `feat(asys): add XX parsing capability(#123)`.
- **PR description**: Please carefully fill in the business background, purpose, solution, and other information of this PR according to the PR template, and link the preceding requirement Issue.

For specific operations such as forking, cloning, synchronization, and conflict handling, refer to the [PR Operation Guide](https://gitcode.com/cann/community/blob/master/contributor/pull_request_operation.md) and the [GitCode Workflow description](https://gitcode.com/cann/community/blob/master/contributor/gitcode-workflow.md).

### 5. CI Gate

Trigger the open-source repository gate by entering the `/compile` command in the PR comment box, and make modifications according to the CI results. Currently, the CI gate mainly includes the following checks:

- Code compilation (x86 / aarch64)
- Static checks (for codecheck false positives, please submit them to SIG members for suppression)
- UT tests
- Smoke tests

After the gate passes, please @ the Committer in the PR comment box to remind them to review.

### 6. Committer Review and Maintainer Merge

After the Committer review, review comments will be provided. Please make modifications based on the comments, and @ the Committer when the modifications are complete.

After the Committer review passes, the `/lgtm` label will be added. The Maintainer then performs the final review and, after confirming that there are no problems, adds the `/approve` label to merge the PR.

---

## 2. Bug Fix

If you discover bugs in this project and wish to fix them, you are welcome to create an Issue for feedback and tracking.

You can follow the [Submit Issue/Process Issue Task](https://gitcode.com/cann/community#提交Issue处理Issue任务) guide to create a `Bug-Report` type Issue to describe the bug. For simple bug fixes, you can also submit a PR directly (please still describe the background and verification method according to the PR template).

## 3. Documentation Correction

If you discover documentation description errors in this project, you are welcome to create an Issue for feedback and correction. For documentation writing specifications, refer to the [Documentation Contribution Guide](https://gitcode.com/cann/community/blob/master/contributor/docs/document_writing_specs.md).

You can follow the [Submit Issue/Process Issue Task](https://gitcode.com/cann/community#提交Issue处理Issue任务) guide to create a `Documentation` type Issue to point out the problems in the corresponding documentation. Then enter "/assign" or "/assign @yourself" in the comment box to assign the Issue to yourself to correct the documentation description.

## 4. Experience Feedback

If you find usability problems during the use of OAM-Tools in areas such as documentation, command lines and configuration, running examples, the build toolchain, or runtime feedback (such as being hard to learn, hard to use, or unclear error messages), you are welcome to create an Issue for feedback to help us continuously improve usability.

You can follow the [Submit Issue/Process issue Task](https://gitcode.com/cann/community#提交Issue处理Issue任务) guide to create an `Experience Request` type Issue, describing the tool and functional chain the problem belongs to (asys / msaicerr / msprof / hccl_test), the problem you actually encountered, and the improvement you expect. If you would like to work on the improvement yourself, you can also enter "/assign" or "/assign @yourself" in the comment box to assign the Issue to yourself for processing.

## 5. Help Solve Others' Issues

If you have suitable solutions for problems encountered by others in the community, you are welcome to publish comments in the Issue to communicate, helping others solve problems and pain points and jointly improving usability.

If the corresponding Issue requires code modification, you can enter "/assign" or "/assign @yourself" in the Issue comment box to assign the Issue to yourself, and track the assistance in solving the problem.

---

## Appendix A: Delivery Directory Structure

This repository organizes deliverables as "component sources + experimental features + running examples + tests + documentation". When adding new features, please follow the structure below:

```text
├── src/                                      # Component sources
│   ├── asys/                                 # asys: fault information collection (Python)
│   │   ├── <module>/                         # Functional modules (analyze / collect / diagnose / cmdline, etc.)
│   │   └── ...
│   ├── msaicerr/                             # msaicerr: AI Core Error analysis (Python)
│   ├── msprof/                               # msprof: performance profiling (C++ collector + Python analysis)
│   └── hccl_test/                            # hccl_test: HCCL collective communication tests (C++)
├── experiment/                               # Experimental features (not yet strongly generalized)
│   └── task-book/
│       └── <feature_name>/                   # Feature name (such as msprof_experience_demo)
│           ├── README.md                     # Feature documentation
│           ├── 01_cmdline/                   # Feature code and notes organized by integration method
│           └── ...
├── examples/                                 # Running examples
│   ├── <component>/                          # Component directory (asys / msaicerr / msprof)
│   │   ├── run.sh                            # One-click run script
│   │   └── ...
│   └── README.md                             # Example overview
├── test/
│   ├── ut/                                   # Unit tests (test/ut/{asys,msaicerr,msprof}/)
│   └── st/                                   # System tests (test/st/{asys,msaicerr,install,upgrade,uninstall}/)
└── docs/
    ├── zh/                                   # Chinese documentation (user guides: docs/zh/user_guide/<component>/)
    └── en/                                   # English documentation (docs/en/user_guide/<component>/)
```

## Appendix B: Coding Standards and Local Checks

This repository uses `pre-commit` to automatically run code checks on commits. The main checks include:

| Check | Description |
| ----- | ----------- |
| clang-format | C/C++ code formatting (follows `.clang-format` in the repository root) |
| ruff | Python code checking and formatting (follows PEP 8) |
| bandit | Python security checks (medium severity and above) |
| codespell / typos | Spelling checks (the Ascend-specific word whitelist is configured in `.typos.toml` and `.pre-commit-config.yaml`) |
| OAT | Open-source compliance check (remote Python hook, installed and run automatically by pre-commit; no manual configuration required) |
| Text / security checks | Trailing whitespace, end-of-file newline, YAML / JSON syntax, large files (>1 MB), private key detection, etc. |

```bash
pip install pre-commit
pre-commit install
```

For more standards, refer to the community documentation:

- [C++ Coding Standards](https://gitcode.com/cann/community/blob/master/contributor/coding-standards/C++%20Coding%20standards.md)
- [Secure Coding Standards](https://gitcode.com/cann/community/blob/master/contributor/coding-standards/SecureCoding.md)
- [Experimental Feature Conventions](https://gitcode.com/cann/community/blob/master/contributor/experimental-feature-conventions.md)
- [Open-Source Code Snippet Reference Guideline](https://gitcode.com/cann/community/blob/master/contributor/third_party/snippet-reference-guideline.md)

If you have any questions during the contribution process, feel free to communicate in the community at any time. Thank you again for your support, and we look forward to your wonderful contributions!
