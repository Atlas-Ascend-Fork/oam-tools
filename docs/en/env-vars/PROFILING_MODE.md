# PROFILING\_MODE

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:00:14.660Z pushedAt=2026-10-15T09:50:53.744Z -->

## Description

Whether to enable Profiling data collection.

- **true**: enables Profiling and reads the Profiling collection options from PROFILING\_OPTIONS.
- **false** or not configured: disables Profiling.
- **dynamic**: when dynamically collecting performance data (attach mode), this parameter must be configured before the training task is executed.

## Configuration Example

```sh
export PROFILING_MODE=true
```

## Constraints

- This environment variable applies only to TensorFlow training and online inference scenarios.
- Enabling Profiling through AscendCL API parameters or TF Adapter API parameters “profiling\_mode” takes precedence over this environment variable (except when PROFILING\_MODE=dynamic).

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
Ascend 950PR&950DT products
<!-- end id5 -->
