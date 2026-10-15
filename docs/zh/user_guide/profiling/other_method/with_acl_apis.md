# 使用acl C&C++接口采集性能数据

## 总体介绍

本章节提供离线推理场景下，如何通过API方式采集性能数据，支持以下实现方式：

**表1**  采集方式

|采集方式|说明|
|--|--|
|方式一：采集并落盘性能数据|将采集到的性能数据写入文件，再使用msprof工具解析该文件，并展示性能分析数据。|
|方式二：使用msproftx扩展接口采集并落盘性能数据|当用户需要定位应用程序或上层框架程序的性能瓶颈时，可在Profiling采集进程内（acl.prof.start接口、acl.prof.stop接口之间）调用msproftx，开启记录应用程序执行期间特定事件发生的时间跨度，并将数据写入性能数据文件，再使用msprof工具解析该文件，并导出展示性能分析数据。|
|方式三：订阅算子信息|将采集到的性能数据解析后写入管道，由用户读入内存，再由用户调用API获取性能数据。|

<!-- npu="950,A3,910b,910,310p,310b" id22 -->
注：接口详细说明，请参见《[Runtime运行时API](https://gitcode.com/cann/runtime/blob/master/docs/zh/api_ref/README.md)》。
<!-- end id22 -->

> [!NOTE]说明
>
>- 使用接口进行性能数据采集，须完成应用工程开发、编译和运行。
>- 方式一和方式二不能与方式三交叉调用。

## 采集并落盘性能数据

通过调用API方式开启性能数据采集功能，从而自动采集性能原始数据。采集性能原始数据成功后，可将采集的原始数据拷贝到装有工具的开发环境上进行原始性能[数据解析](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/msprof_parsing_instruct.md)，可视化展示原始性能数据解析结果。

**API简介**

**表1**  API简介

|接口|说明|
|--|--|
|aclprofCreateConfig|创建Profiling配置。与aclprofDestroyConfig成对使用。|
|aclprofInit|初始化Profiling，目前用于设置保存性能数据的文件的路径。与aclprofFinalize成对使用。|
|aclprofSetConfig|aclprofCreateConfig的扩展接口，用于设置采集配置参数。|
|aclprofStart|下发Profiling请求，开启对应数据的采集。与aclprofStop成对使用。|
|aclprofStop|停止Profiling数据采集。与aclprofStart成对使用。|
|aclprofFinalize|结束Profiling。与aclprofInit成对使用。|
|aclprofDestroyConfig|销毁通过aclprofCreateConfig接口创建的aclprofConfig类型的数据。与aclprofCreateConfig成对使用。|

> [!NOTE]说明
>aclprofInit接口传入的性能采集数据的落盘路径，需要确保用户进程具有读写权限。
<!-- npu="950,A3,910b,910,310p,310b,IPV350" id23 -->
>接口详细说明，请参见《[Runtime运行时API](https://gitcode.com/cann/runtime/blob/master/docs/zh/api_ref/README.md)》。
<!-- end id23 -->

**API调用示例**

API调用示例如下：

```cpp
// 1.调用aclInit初始化

// 2.申请运行管理资源，包括设置用于计算的Device、创建Context、创建Stream

// 3.Profiling初始化
// 设置数据落盘路径，如果不调用aclprofInit设置数据落盘路径，可以调用aclprofSetConfig设置
const char *aclProfPath = "./output";
aclprofInit(aclProfPath, strlen(aclProfPath));

// 4.进行Profiling配置
uint32_t deviceIdList[1] = {0};    // 须根据实际环境的Device ID配置
// 创建配置结构体
aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
    nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME);
const char *memFreq = "15";
ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
// ret = aclprofSetConfig(ACL_PROF_PATH, aclProfPath, strlen(aclProfPath));
aclprofStart(config);

// 5.模型加载，加载成功后，返回标识模型的modelId

// 6.创建aclmdlDataset类型的数据，用于描述模型的输入数据input、输出数据output

// 7.执行模型
ret = aclmdlExecute(modelId, input, output);

// 8.处理模型推理结果

// 9.释放描述模型输入/输出信息、内存等资源，卸载模型

// 10.关闭Profiling配置,释放配置资源,释放Profiling组件资源
aclprofStop(config);
aclprofDestroyConfig(config);
aclprofFinalize();

// 11.释放运行管理资源

// 12.调用aclFinalize去初始化
//......
```

## 使用msproftx扩展接口采集并落盘性能数据

为了获取用户和上层框架程序的性能数据，Profiling开启msproftx功能之前，需要在程序内调用msproftx相关接口来对用户程序进行打点以输出对应的性能数据。

**API简介**

**表1**  API简介

|接口|说明|
|--|--|
|aclprofCreateStamp|创建msproftx事件标记，用于描述瞬时事件。|
|aclprofSetStampTraceMessage|为msproftx事件标记携带描述信息，在Profiling解析结果中msprof_tx summary数据展示。|
|aclprofMark|msproftx标记瞬时事件。|
|aclprofMarkEx|aclprofMarkEx打点接口。|
|aclprofPush|msproftx用于记录事件发生的时间跨度的开始时间。与aclprofPop成对使用，仅能在单线程内使用。|
|aclprofPop|msproftx用于记录事件发生的时间跨度的结束时间。与aclprofPush成对使用，仅能在单线程内使用。|
|aclprofRangeStart|msproftx用于记录事件发生的时间跨度的开始时间。与aclprofRangeStop成对使用，可跨线程使用。|
|aclprofRangeStop|msproftx用于记录事件发生的时间跨度的结束时间。与aclprofRangeStart成对使用，可跨线程使用。|
|aclprofDestroyStamp|释放msproftx事件标记。|

> [!NOTE]说明
>当只开启msproftx功能时，aclprofCreateConfig接口的deviceIdList参数值需设为空，deviceNums参数值设为0。
<!-- npu="950,A3,910b,910,310p,310b,IPV350" id24 -->
>接口详细说明，请参见《[Runtime运行时API](https://gitcode.com/cann/runtime/blob/master/docs/zh/api_ref/README.md)》。
<!-- end id24 -->

**API调用示例**

- 示例一（aclprofMark示例）

    ```cpp
    // 1.调用aclInit初始化

    // 2.申请运行管理资源，包括设置用于计算的Device、创建Context、创建Stream

    // 3.Profiling初始化
    // 设置数据落盘路径
    const char *aclProfPath = "./output";
    aclprofInit(aclProfPath, strlen(aclProfPath));

    // 4.进行Profiling配置
    uint32_t deviceIdList[1] = {0};    // 须根据实际环境的Device ID配置
    // 创建配置结构体
    aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
        nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME | ACL_PROF_MSPROFTX);
    const char *memFreq = "15";
    ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
    aclprofStart(config);

    aclprofStepInfo *stepInfo = aclprofCreateStepInfo();
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_START, stream_);

    // 5.模型加载，加载成功后，返回标识模型的modelId
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "model_load_mark", strlen("model_load_mark"));
    aclprofMark(stamp);    // 标记模型加载事件
    aclprofDestroyStamp(stamp);

    // 6.创建aclmdlDataset类型的数据，用于描述模型的输入数据input、输出数据output

    // 7.执行模型
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "model_exec_mark", strlen("model_exec_mark"));
    aclprofMark(stamp);    // 标记模型执行事件
    aclprofDestroyStamp(stamp);
    ret = aclmdlExecute(modelId, input, output);

    // 8.处理模型推理结果

    // 9.释放描述模型输入/输出信息、内存等资源，卸载模型
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_END, stream_);
    aclprofDestroyStepInfo(stepInfo);

    // 10.关闭Profiling配置,释放配置资源,释放Profiling组件资源
    aclprofStop(config);
    aclprofDestroyConfig(config);
    aclprofFinalize();

    // 11.释放运行管理资源

    // 12.调用aclFinalize去初始化
    //......
    ```

- 示例二（aclprofMarkEx示例，标识用户funcA接口）

    ```cpp
    aclrtStream stream;
    aclrtCreateStream(&stream);
    aclError markRet;
    markRet = aclprofMarkEx("funcA", strlen("funcA"), stream);
    if (markRet != ACL_ERROR_NONE) {
        printf("mark execute start failed");
    }
    // 用户业务接口
    funcA();
    ```

- 示例三（aclprofPush/aclprofPop示例，适用于单线程）

    ```cpp
    // 1.调用aclInit初始化

    // 2.申请运行管理资源，包括设置用于计算的Device、创建Context、创建Stream

    // 3.Profiling初始化
    // 设置数据落盘路径
    const char *aclProfPath = "./output";
    aclprofInit(aclProfPath, strlen(aclProfPath));

    // 4.进行Profiling配置
    uint32_t deviceIdList[1] = {0};    // 须根据实际环境的Device ID配置
    // 创建配置结构体
    aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
        nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME | ACL_PROF_MSPROFTX);
    const char *memFreq = "15";
    ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
    aclprofStart(config);

    aclprofStepInfo *stepInfo = aclprofCreateStepInfo();
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_START, stream_);

    // 5.模型加载，加载成功后，返回标识模型的modelId

    // 6.创建aclmdlDataset类型的数据，用于描述模型的输入数据input、输出数据output

    // 7.执行模型（模型仅在单线程执行）
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "aclmdlExecute_duration", strlen("aclmdlExecute_duration"));
    aclprofPush(stamp);
    ret = aclmdlExecute(modelId, input, output);
    aclprofPop();
    aclprofDestroyStamp(stamp);

    // 8.处理模型推理结果

    // 9.释放描述模型输入/输出信息、内存等资源，卸载模型
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_END, stream_);
    aclprofDestroyStepInfo(stepInfo);

    // 10.关闭Profiling配置,释放配置资源,释放Profiling组件资源
    aclprofStop(config);
    aclprofDestroyConfig(config);
    aclprofFinalize();

    // 11.释放运行管理资源

    // 12.调用aclFinalize去初始化
    //......
    ```

- 示例四（aclprofRangeStart/aclprofRangeStop示例，适用于单线程或跨线程）

    ```cpp
    // 1.调用aclInit初始化

    // 2.申请运行管理资源，包括设置用于计算的Device、创建Context、创建Stream

    // 3.Profiling初始化
    // 设置数据落盘路径
    const char *aclProfPath = "./output";
    aclprofInit(aclProfPath, strlen(aclProfPath));

    // 4.进行Profiling配置
    uint32_t deviceIdList[1] = {0};    // 须根据实际环境的Device ID配置
    // 创建配置结构体
    aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
        nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME | ACL_PROF_MSPROFTX);
    const char *memFreq = "15";
    ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
    aclprofStart(config);

    aclprofStepInfo *stepInfo = aclprofCreateStepInfo();
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_START, stream_);

    // 5.模型加载，加载成功后，返回标识模型的modelId

    // 6.创建aclmdlDataset类型的数据，用于描述模型的输入数据input、输出数据output

    // 7.执行模型（模型在跨线程执行）
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "aclmdlExecute_duration", strlen("aclmdlExecute_duration"));
    aclprofRangeStart(stamp, &rangeId);
    ret = aclmdlExecute(modelId, input, output);
    aclprofRangeStop(rangeId);
    aclprofDestroyStamp(stamp);

    // 8.处理模型推理结果

    // 9.释放描述模型输入/输出信息、内存等资源，卸载模型
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_END, stream_);
    aclprofDestroyStepInfo(stepInfo);

    // 10.关闭Profiling配置,释放配置资源,释放Profiling组件资源
    aclprofStop(config);
    aclprofDestroyConfig(config);
    aclprofFinalize();

    // 11.释放运行管理资源

    // 12.调用aclFinalize去初始化
    //......
    ```

> [!NOTE]说明
>msproftx扩展接口在main函数内调用。

## 订阅算子信息

通过调用消息订阅接口实现将采集到的Profiling数据解析后写入管道，由用户读入内存，再由用户调用API获取性能数据。当前支持获取网络模型中算子的性能数据，包括算子名称、算子类型名称、算子执行时间等。

**API简介**

**表1**  API简介

|接口|说明|
|--|--|
|aclprofCreateSubscribeConfig|创建aclprofSubscribeConfig类型的数据，表示创建订阅配置信息。|
|aclprofModelSubscribe|订阅算子的基本信息，包括算子名称、算子类型、算子执行耗时等。同步接口。<br>与aclprofModelUnSubscribe成对使用。|
|aclprofGet*|获取算子的基本信息。“*”包括：<br>OpDescSize：算子数据结构大小。<br>OpNum：算子个数。<br>OpTypeLen：算子类型的字符串长度。<br>OpType：算子类型。<br>OpNameLen：算子名称的字符串长度。<br>OpName：算子名称。<br>OpStart：算子执行开始时间。<br>OpEnd：算子执行结束时间。<br>OpDuration：算子执行耗时。<br>ModelId：算子所在模型ID。<br>以上信息通过INFO_LOG接口将Profiling结果显示在屏幕上。|
|aclprofModelUnSubscribe|网络场景下，取消订阅算子的基本信息，包括算子名称、算子类型、算子执行耗时等。同步接口。<br>需要与aclprofModelSubscribe接口配对使用。|
|aclprofDestroySubscribeConfig|销毁通过aclprofCreateSubscribeConfig接口创建的aclprofSubscribeConfig类型的数据。同步接口。|

> [!NOTE]说明
>接口详细说明，请参见《[Runtime运行时API](https://gitcode.com/cann/runtime/blob/master/docs/zh/api_ref/README.md)》。

## 采集数据说明

采集性能数据后请将原始数据文件解析并导出为可视化的性能数据文件，保存在PROF\_XXX/mindstudio\_profiler\_output目录下。
<!-- npu="950,A3,910b,910,310p,310b" id1 -->
解析详细操作请参见[使用msprof命令解析、查询与导出性能数据](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/msprof_parsing_instruct.md)。
<!-- end id1 -->

<!-- npu="950,A3,910b,910,310p,310b" id21 -->
各参数对应的性能数据文件如下：

- ACL_PROF_TASK_TIME/ACL_PROF_TASK_TIME_L0:
  - msprof_*.json中的CANN层级和api_statistic_*.csv文件
  - msprof_*.json中的Ascend Hardware层级和task_time_*.csv文件
  - msprof_*.json中的Communication层级和communication_statistic_*.csv文件
  - step_trace（迭代轨迹数据）
  - op_summary_*.csv
  - op_statistic_*.csv
  - fusion_op_*.csv
- ACL_PROF_ACL_API:msprof_\*.json中的CANN_AscendCL层级和api_statistic_*.csv文件
- ACL_PROF_RUNTIME_API:msprof_\*.json中的CANN_Runtime层级和api_statistic_*.csv文件
- ACL_PROF_HCCL_TRACE:msprof_\*.json中的Communication层级和communication_statistic_*.csv文件
<!-- npu="950,A3,910b,910,310p,310b" id2 -->
- ACL_PROF_AICPU:aicpu_\*.csv
- ACL_PROF_L2CACHE:l2_cache_\*.csv
<!-- end id2 -->
- ACL_PROF_AICORE_METRICS:op_summary_\*.csv
- ACL_PROF_TASK_MEMORY:
  - memory_record_*.csv
  - operator_memory_*.csv
  - static_op_mem_*.csv
- ACL_PROF_MSPROFTX：msproftx数据
- ACL_PROF_SYS_HARDWARE_MEM_FREQ：
  - 片上内存读写速率文件
  - msprof_\*.json中的LLC层级和llc_read_write_*.csv文件
  <!-- npu="950,A3,910b,310b" id4 -->
  - msprof_\*.json中的acc_pmu层级
  <!-- end id4 -->
  <!-- npu="950,A3,910b,310b" id5 -->
  - msprof_*.json中的Stars Soc Info层级
  <!-- end id5 -->
  <!-- npu="950,A3,910b,910,310p,310b" id6 -->
  - msprof_\*.json中的NPU MEM层级和npu_mem_*.csv文件
  <!-- end id6 -->
  - npu_module_mem_\*.csv
<!-- npu="A3,910b,910,310b" id13 -->
- ACL_PROF_SYS_IO_FREQ：msprof_\*.json中的NIC层级和nic_*.csv文件和msprof_*.json中的RoCE层级和roce_*.csv文件
<!-- end id13 -->
<!-- npu="950,A3,910b,910,310p" id14 -->
- ACL_PROF_SYS_INTERCONNECTION_FREQ：
<!-- end id14 -->
  <!-- npu="950,A3,910b,910,310p" id15 -->
  - msprof_\*.json中的PCIe层级和pcie_*.csv文件
  <!-- end id15 -->
  <!-- npu="950,A3,910b" id16 -->
  - msprof_\*.json中的HCCS层级和hccs_*.csv文件
  <!-- end id16 -->
  <!-- npu="950,A3,910b" id17 -->
  - msprof_\*.json中的Stars Chip Trans层级
  <!-- end id17 -->
<!-- npu="950,A3,910b,910,310b" id18 -->
- ACL_PROF_DVPP_FREQ：dvpp_*.csv
<!-- end id18 -->
<!-- npu="950,A3,910b,910,310p,310b" id3 -->
- ACL_PROF_HOST_SYS:
  - msprof_\*.json中的CPU Usage层级和host_cpu_usage_\*.csv文件
  - msprof_\*.json中的Memory Usage层级和host_mem_usage_\*.csv文件
<!-- end id3 -->
<!-- npu="950,A3,910b,910,310p,310b" id19 -->
- ACL_PROF_HOST_SYS_USAGE/ACL_PROF_HOST_SYS_USAGE_FREQ:Host侧进程CPU利用率数据和Host侧进程内存利用率数据
<!-- end id19 -->

<!-- npu="950,A3,910b,910,310p,310b" id20 -->
详细的性能数据信息如请参考[性能数据文件参考](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/profile_data_file_references.md)。
<!-- end id20 -->

<!-- end id21 -->
