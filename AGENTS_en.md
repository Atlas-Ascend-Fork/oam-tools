# AGENTS.md

This file provides guidance for agents working in this code repository.

## Project Overview

oam-tools (Operations, Administration, and Maintenance) is the operations and maintenance toolset for CANN, providing fault diagnosis tools and performance testing and tuning tools for developers.

Main functions:

- **Fault Information Collection** (asys): Fault information collection, software and hardware information display, health check, comprehensive detection, and so on
- **AI Core Error Analysis** (msaicerr): AI Core Error problem analysis, Dump file parsing, environment checking, and so on
- **Performance Tuning** (msprof): Collect and analyze key performance indicators of AI tasks running on Ascend AI processors at various running stages
- **HCCL Performance Testing** (hccl_test): Test collective communication functionality and performance in distributed training or inference scenarios

## Build Commands

### Basic Build

```bash
# Build the project
bash build.sh

# Build with specified third-party library path
bash build.sh --cann_3rd_lib_path=${third_party_path}

# View build options
bash build.sh -h
```

### Run Tests

```bash
# Run all test cases
bash build.sh -u

# Run tests for specific component
bash build.sh -u --component msprof
```

### Install Dependencies

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Download third-party libraries and subrepositories (use only when network is unavailable)
python3 cmake/download_libs.py
```

## Directory Structure

| Directory | Purpose |
|------|------|
| `src/asys/` | asys fault information collection module |
| `src/msaicerr/` | AI Core Error analysis module |
| `src/msprof/` | Performance tuning module |
| `src/hccl_test/` | HCCL performance testing module |
| `src/third_party/` | Third-party library headers |
| `cmake/` | Build configuration |
| `scripts/` | Auxiliary build files |
| `test/` | UT/ST test cases |
| `docs/` | Project documentation |
| `bundle/` | Packaging files |
| `.clang-format` | Code formatting configuration |

## Development Guidelines

### gitcode pr/issue operations

@.claude/skills/default-skills/SKILL.md

For SKILL content, refer to [SKILL.md](.claude/skills/default-skills/SKILL_en.md)

### Code Style

- Use .clang-format to format code
- Follow the existing code style of the project
- Python code follows PEP 8 standards

### pre-commit

- The project has configured pre-commit. Refer to the CANN community pre-commit configuration guide for installation and usage

## Language

Use Chinese
