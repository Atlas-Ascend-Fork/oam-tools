# PROFILING\_MODE

<!-- md-trans-meta sourceCommit=f3cf4115ddb0ce33467a62e425af1dd155a6419f translatedAt=2026-11-16T08:36:11.213Z pushedAt=2026-11-16T11:22:01.933Z nl=2 -->

## Description

Whether to enable Profiling data collection.

- **true**: enables Profiling and reads the Profiling collection options from PROFILING\_OPTIONS.
- **false** or not configured: disables Profiling.
- **dynamic**: when dynamically collecting performance data (attach mode), this parameter must be configured before the training task is executed.

## Configuration Example

```sh
export PROFILING_MODE=true
```

## Usage Constraints

- This environment variable applies only to TensorFlow training and online inference scenarios.
- Enabling Profiling through AscendCL API parameters or TF Adapter API parameters **profiling\_mode** takes precedence over this environment variable (except when PROFILING\_MODE=dynamic).

## Supported Models

<!-- npu="910" id1 -->
Atlas training products
<!-- end id1 -->

<!-- npu="310p" id2 -->
Atlas inference products
<!-- end id2 -->

<!-- npu="910b" id3 -->
Atlas A2 products
<!-- end id3 -->

<!-- npu="A3" id4 -->
Atlas A3 products
<!-- end id4 -->

<!-- npu="950" id5 -->
Ascend 950PR & 950DT products
<!-- end id5 -->
