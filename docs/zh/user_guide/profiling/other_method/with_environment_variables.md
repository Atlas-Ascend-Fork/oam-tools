# 使用环境变量采集性能数据

环境变量方式采集适用于TensorFlow框架训练/在线推理场景。与直接使用TensorFlow框架接口采集方式不同的是，环境变量方式是在训练/在线推理脚本中直接插入PROFILING\_OPTIONS环境变量配置性能数据采集项。

> [!NOTE]说明
> task_trace后续版本会废弃，请使用task_time开关控制相关数据采集。

## 前提条件

- 训练场景：
  - 准备好基于TensorFlow 1.15开发的训练模型以及配套的数据集，并完成TensorFlow原始模型向AI处理器的迁移。
  - 准备好基于TensorFlow 2.x开发的训练模型以及配套的数据集，并完成TensorFlow原始模型向AI处理器的迁移。

- 在线推理场景：下载预训练模型并准备在线推理脚本。

## 操作步骤

配置的环境变量内容示例如下。

```sh
export PROFILING_MODE=true
export PROFILING_OPTIONS='{"output":"/tmp/profiling","training_trace":"on","task_trace":"on","fp_point":"","bp_point":"","aic_metrics":"PipeUtilization"}'
```

**PROFILING\_OPTIONS**参数解释及使用方法，请参见[Profiling options参数解释](../appendices/profiling_options_parameter.md)。

> [!NOTE]说明
>配置**PROFILING\_MODE**为**true**但未配置**PROFILING\_OPTIONS**情况下Profiling默认会执行**training\_trace**、**task\_trace**、**hccl**、**aicpu**和**aic\_metrics**（PipeUtilization）采集并将采集到的数据保存在当前AI任务所在目录；当配置**PROFILING\_MODE**为**true**且配置**PROFILING\_OPTIONS**任意参数后，**PROFILING\_OPTIONS**参数默认情况请参见[Profiling options参数解释](../appendices/profiling_options_parameter.md)。

<!-- npu="950,A3,910b,910,310p,310b,IPV350" id1 -->
## 采集结果说明

配置PROFILING\_OPTIONS参数后请参见[使用msprof命令解析、查询与导出性能数据](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/msprof_parsing_instruct.md)将原始数据文件解析并导出为可视化的性能数据文件，保存在PROF\_XXX/mindstudio\_profiler\_output目录下。
<!-- end id1 -->
