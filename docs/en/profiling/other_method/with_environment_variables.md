# Collecting Performance Data Using Environment Variables

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:31:20.121Z pushedAt=2026-10-16T03:53:18.575Z -->

The environment variable method applies to TensorFlow framework training and online inference scenarios. Unlike the method that directly uses TensorFlow framework APIs, the environment variable method inserts PROFILING\_OPTIONS environment variable configurations for performance data collection items directly into the training or online inference script.

> [!NOTE] Note
> task_trace will be deprecated in later versions. Use the task_time switch to control the collection of related data.

## Prerequisites

- Training scenario:
  - Prepare a training model developed based on TensorFlow 1.15 and the matching dataset, and complete the migration of the original TensorFlow model to the AI processor.
  - Prepare a training model developed based on TensorFlow 2.x and the matching dataset, and complete the migration of the original TensorFlow model to the AI processor.

- Online inference scenario: Download a pretrained model and prepare an online inference script.

## Procedure

The following is an example of the configured environment variables.

```sh
export PROFILING_MODE=true
export PROFILING_OPTIONS='{"output":"/tmp/profiling","training_trace":"on","task_trace":"on","fp_point":"","bp_point":"","aic_metrics":"PipeUtilization"}'
```

For details about the **PROFILING\_OPTIONS** parameter and how to use it, see [Profiling options Parameter Description](../appendices/profiling_options_parameter.md).

> [!NOTE] Note
> When **PROFILING\_MODE** is set to **true** but **PROFILING\_OPTIONS** is not configured, Profiling collects **training\_trace**, **task\_trace**, **hccl**, **aicpu**, and **aic\_metrics** (PipeUtilization) by default and saves the collected data in the directory where the current AI task resides. When **PROFILING\_MODE** is set to **true** and any parameter of **PROFILING\_OPTIONS** is configured, for the default values of the **PROFILING\_OPTIONS** parameters, see [Profiling options Parameter Description](../appendices/profiling_options_parameter.md).

<!-- npu="950,A3,910b,910,310p,310b,IPV350" id1 -->
## Collection Result Description

After configuring the PROFILING\_OPTIONS parameter, see [Parsing, Querying, and Exporting Performance Data Using the msprof Command](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/msprof_parsing_instruct.md) to parse the raw data files and export them as visualized performance data files, which are saved in the PROF\_XXX/mindstudio\_profiler\_output directory.
<!-- end id1 -->
