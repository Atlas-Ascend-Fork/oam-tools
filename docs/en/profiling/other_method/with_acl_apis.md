# Collecting Performance Data Using ACL C/C++ APIs

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:26:54.515Z pushedAt=2026-10-16T03:28:38.196Z -->

## Overview

This section describes how to collect performance data through APIs in offline inference scenarios. The following implementation methods are supported:

**Table 1** Collection methods

|Collection Method|Description|
|--|--|
|Method 1: Collect and write performance data to a file|Write the collected performance data to a file, and then use the msprof tool to parse the file and display the performance analysis data.|
|Method 2: Use the msproftx extension interface to collect and write performance data to a file|When you need to locate the performance bottleneck of an application or an upper-layer framework program, you can call msproftx within the Profiling collection process (between the acl.prof.start and acl.prof.stop APIs) to start recording the time span of specific event occurrences during application execution, write the data to a performance data file, and then use the msprof tool to parse the file and export and display the performance analysis data.|
|Method 3: Subscribe to operator information|Parse the collected performance data and write it to a pipe. The user reads it into memory and then calls an API to obtain the performance data.|

<!-- npu="950,A3,910b,910,310p,310b" id22 -->
Note: For interface details, see [Runtime API](https://gitcode.com/cann/runtime/blob/9.2.0/docs/zh/api_ref/README.md).
<!-- end id22 -->

> [!NOTE] Note
>
>- To collect performance data using APIs, you must complete application project development, compilation, and running.
>- Method 1 and Method 2 cannot be called interchangeably with Method 3.

## Collecting and Persisting Performance Data

The performance data collection function is enabled by calling APIs, so that raw performance data is automatically collected. After the raw performance data is successfully collected, you can copy the collected raw data to a development environment where the tool is installed to perform raw performance [data parsing](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/msprof_parsing_instruct.md), and visually display the parsing result of the raw performance data.

**API Overview**

**Table 1** API overview

|API|Description|
|--|--|
|aclprofCreateConfig|Creates a Profiling configuration. Used in pairs with aclprofDestroyConfig.|
|aclprofInit|Initializes Profiling. Currently used to set the path of the file for saving performance data. Used in pairs with aclprofFinalize.|
|aclprofSetConfig|An extension interface of aclprofCreateConfig, used to set collection configuration parameters.|
|aclprofStart|Delivers a Profiling request to start collecting the corresponding data. Used in pairs with aclprofStop.|
|aclprofStop|Stops Profiling data collection. Used in pairs with aclprofStart.|
|aclprofFinalize|Ends Profiling. Used in pairs with aclprofInit.|
|aclprofDestroyConfig|Destroys the data of the aclprofConfig type created through the aclprofCreateConfig API. Used in pairs with aclprofCreateConfig.|

> [!NOTE] Note
>For the persistence path of the collected performance data passed in by the aclprofInit API, ensure that the user process has read and write permissions.
<!-- npu="950,A3,910b,910,310p,310b,IPV350" id23 -->
>For interface details, see also [Runtime API](https://gitcode.com/cann/runtime/blob/9.2.0/docs/zh/api_ref/README.md).
<!-- end id23 -->

**API Call Example**

The API call example is as follows:

```cpp
// 1. Call aclInit for initialization

// 2. Apply for runtime management resources, including setting the Device for computation, creating a Context, and creating a Stream.

// 3. Initialize Profiling.
// Set the data write-to-disk path. If aclprofInit is not called to set the data write-to-disk path, aclprofSetConfig can be called to set it.
const char *aclProfPath = "./output";
aclprofInit(aclProfPath, strlen(aclProfPath));

// 4. Configure Profiling.
uint32_t deviceIdList[1] = {0};    // Configure based on the Device ID of the actual environment.
// Create the configuration structure.
aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
    nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME);
const char *memFreq = "15";
ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
// ret = aclprofSetConfig(ACL_PROF_PATH, aclProfPath, strlen(aclProfPath));
aclprofStart(config);

// 5. Load the model. After successful loading, the modelId identifying the model is returned.

// 6. Create data of the aclmdlDataset type to describe the input data and output data of the model.

// 7. Execute the model.
ret = aclmdlExecute(modelId, input, output);

// 8. Process the model inference result.

// 9. Release the resources such as model input/output information and memory, and unload the model.

// 10. Disable the Profiling configuration, release the configuration resources, and release the Profiling component resources.
aclprofStop(config);
aclprofDestroyConfig(config);
aclprofFinalize();

// 11. Release the runtime management resources.

// 12. Call aclFinalize to deinitialize.
//......
```

## Collecting and Persisting Performance Data Using the msproftx Extension Interface

To obtain performance data of user and upper-layer framework programs, before Profiling enables the msproftx function, you need to call msproftx-related APIs in the program to instrument the user program so that the corresponding performance data is output.

**API Overview**

**Table 1** API overview

|API|Description|
|--|--|
|aclprofCreateStamp|Creates an msproftx event marker to describe an instantaneous event.|
|aclprofSetStampTraceMessage|Attaches description information to an msproftx event marker, which is displayed in the msprof_tx summary data in the Profiling parsing result.|
|aclprofMark|Marks an instantaneous event with msproftx.|
|aclprofMarkEx|Instrumentation API of aclprofMarkEx.|
|aclprofPush|Used by msproftx to record the start time of the time span of an event occurrence. It is used in pairs with aclprofPop and can be used only within a single thread.|
|aclprofPop|Used by msproftx to record the end time of the time span of an event occurrence. It is used in pairs with aclprofPush and can be used only within a single thread.|
|aclprofRangeStart|Used by msproftx to record the start time of the time span of an event occurrence. It is used in pairs with aclprofRangeStop and can be used across threads.|
|aclprofRangeStop|Used by msproftx to record the end time of the time span of an event occurrence. It is used in pairs with aclprofRangeStart and can be used across threads.|
|aclprofDestroyStamp|Releases an msproftx event marker.|

> [!NOTE] Note
> When only the msproftx function is enabled, set the deviceIdList parameter of the aclprofCreateConfig API to empty and the deviceNums parameter to 0.
<!-- npu="950,A3,910b,910,310p,310b,IPV350" id24 -->
> For interface details, see also [Runtime API](https://gitcode.com/cann/runtime/blob/9.2.0/docs/zh/api_ref/README.md).
<!-- end id24 -->

**API Call Example**

- Example 1 (aclprofMark example)

    ```cpp
    // 1. Call aclInit for initialization.

    // 2. Apply for runtime management resources, including setting the Device for computation, creating a Context, and creating a Stream.

    // 3. Initialize Profiling.
    // Set the data dump path.
    const char *aclProfPath = "./output";
    aclprofInit(aclProfPath, strlen(aclProfPath));

    // 4. Configure Profiling.
    uint32_t deviceIdList[1] = {0};    // Must be configured based on the actual Device ID in the environment.
    // Create the configuration structure.
    aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
        nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME | ACL_PROF_MSPROFTX);
    const char *memFreq = "15";
    ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
    aclprofStart(config);

    aclprofStepInfo *stepInfo = aclprofCreateStepInfo();
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_START, stream_);

    // 5. Load the model. After successful loading, the modelId identifying the model is returned.
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "model_load_mark", strlen("model_load_mark"));
    aclprofMark(stamp);    // Mark the model loading event.
    aclprofDestroyStamp(stamp);

    // 6. Create data of the aclmdlDataset type to describe the model's input data and output data.

    // 7. Execute the model.
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "model_exec_mark", strlen("model_exec_mark"));
    aclprofMark(stamp);    // Mark the model execution event.
    aclprofDestroyStamp(stamp);
    ret = aclmdlExecute(modelId, input, output);

    // 8. Process the model inference result.

    // 9. Release resources such as model input/output information and memory, and unload the model.
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_END, stream_);
    aclprofDestroyStepInfo(stepInfo);

    // 10. Disable the Profiling configuration, release the configuration resources, and release the Profiling component resources.
    aclprofStop(config);
    aclprofDestroyConfig(config);
    aclprofFinalize();

    // 11. Release the runtime management resources.

    // 12. Call aclFinalize to deinitialize.
    //......
    ```

- Example 2 (aclprofMarkEx example, marking the user funcA API)

    ```cpp
    aclrtStream stream;
    aclrtCreateStream(&stream);
    aclError markRet;
    markRet = aclprofMarkEx("funcA", strlen("funcA"), stream);
    if (markRet != ACL_ERROR_NONE) {
        printf("mark execute start failed");
    }
    // User service API
    funcA();
    ```

- Example 3 (aclprofPush/aclprofPop example, applicable to a single thread)

    ```cpp
    // 1. Call aclInit for initialization.

    // 2. Apply for runtime management resources, including setting the Device for computation, creating a Context, and creating a Stream.

    // 3. Initialize Profiling.
    // Set the data dump path.
    const char *aclProfPath = "./output";
    aclprofInit(aclProfPath, strlen(aclProfPath));

    // 4. Configure Profiling.
    uint32_t deviceIdList[1] = {0};    // Configure the Device ID based on the actual environment.
    // Create the configuration structure.
    aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
        nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME | ACL_PROF_MSPROFTX);
    const char *memFreq = "15";
    ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
    aclprofStart(config);

    aclprofStepInfo *stepInfo = aclprofCreateStepInfo();
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_START, stream_);

    // 5. Load the model. After the model is loaded successfully, modelId identifying the model is returned.

    // 6. Create data of the aclmdlDataset type to describe the input and output of the model.

    // 7. Execute the model (the model is executed only in a single thread).
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "aclmdlExecute_duration", strlen("aclmdlExecute_duration"));
    aclprofPush(stamp);
    ret = aclmdlExecute(modelId, input, output);
    aclprofPop();
    aclprofDestroyStamp(stamp);

    // 8. Process the model inference result.

    // 9. Release the resources such as model input/output description information and memory, and unload the model.
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_END, stream_);
    aclprofDestroyStepInfo(stepInfo);

    // 10. Disable the Profiling configuration, release the configuration resources, and release the Profiling component resources.
    aclprofStop(config);
    aclprofDestroyConfig(config);
    aclprofFinalize();

    // 11. Release the runtime management resources.

    // 12. Call aclFinalize to deinitialize.
    //......
    ```

- Example 4 (aclprofRangeStart/aclprofRangeStop example, applicable to single-thread or cross-thread scenarios)

    ```cpp
    // 1. Call aclInit for initialization.

    // 2. Apply for runtime management resources, including setting the Device for computation, creating a Context, and creating a Stream.

    // 3. Initialize Profiling.
    // Set the data dump path.
    const char *aclProfPath = "./output";
    aclprofInit(aclProfPath, strlen(aclProfPath));

    // 4. Configure Profiling.
    uint32_t deviceIdList[1] = {0};    // Configure the Device ID based on the actual environment.
    // Create the configuration structure.
    aclprofConfig *config = aclprofCreateConfig(deviceIdList, 1, ACL_AICORE_ARITHMETIC_UTILIZATION,
        nullptr,ACL_PROF_ACL_API | ACL_PROF_TASK_TIME | ACL_PROF_MSPROFTX);
    const char *memFreq = "15";
    ret = aclprofSetConfig(ACL_PROF_SYS_HARDWARE_MEM_FREQ, memFreq, strlen(memFreq));
    aclprofStart(config);

    aclprofStepInfo *stepInfo = aclprofCreateStepInfo();
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_START, stream_);

    // 5. Load the model. After the model is loaded successfully, modelId identifying the model is returned.

    // 6. Create data of the aclmdlDataset type to describe the input and output of the model.

    // 7. Execute the model (the model is executed across threads).
    stamp = aclprofCreateStamp();
    aclprofSetStampTraceMessage(stamp, "aclmdlExecute_duration", strlen("aclmdlExecute_duration"));
    aclprofRangeStart(stamp, &rangeId);
    ret = aclmdlExecute(modelId, input, output);
    aclprofRangeStop(rangeId);
    aclprofDestroyStamp(stamp);

    // 8. Process the model inference result.

    // 9. Release resources such as the model input/output description and memory, and unload the model.
    int ret = aclprofGetStepTimestamp(stepInfo, ACL_STEP_END, stream_);
    aclprofDestroyStepInfo(stepInfo);

    // 10. Disable the Profiling configuration, release the configuration resources, and release the Profiling component resources.
    aclprofStop(config);
    aclprofDestroyConfig(config);
    aclprofFinalize();

    // 11. Release the runtime management resources.

    // 12. Call aclFinalize to deinitialize.
    //......
    ```

> [!NOTE] Note
> The msproftx extension interface is called in the main function.

## Subscribing to Operator Information

By calling the message subscription API, the collected Profiling data is parsed and written to a pipe, read into memory by the user, and then obtained by the user through API calls. Currently, the performance data of operators in a network model can be obtained, including the operator name, operator type name, and operator execution time.

**API Overview**

**Table 1** API overview

|API|Description|
|--|--|
|aclprofCreateSubscribeConfig|Creates data of the aclprofSubscribeConfig type, indicating the creation of subscription configuration information.|
|aclprofModelSubscribe|Subscribes to the basic information of operators, including the operator name, operator type, and operator execution duration. This is a synchronous interface.<br>It is used in pairs with aclprofModelUnSubscribe.|
|aclprofGet*|Obtains the basic information of operators. "*" includes:<br>OpDescSize: size of the operator data structure.<br>OpNum: number of operators.<br>OpTypeLen: string length of the operator type.<br>OpType: operator type.<br>OpNameLen: string length of the operator name.<br>OpName: operator name.<br>OpStart: start time of operator execution.<br>OpEnd: end time of operator execution.<br>OpDuration: duration of operator execution.<br>ModelId: ID of the model to which the operator belongs.<br>The preceding information is displayed on the screen through the INFO_LOG API.|
|aclprofModelUnSubscribe|In the network scenario, unsubscribes from the basic information of operators, including the operator name, operator type, and operator execution duration. This is a synchronous interface.<br>It must be used in pairs with the aclprofModelSubscribe API.|
|aclprofDestroySubscribeConfig|Destroys the data of the aclprofSubscribeConfig type created through the aclprofCreateSubscribeConfig API. This is a synchronous interface.|

> [!NOTE] Note
> For details about the APIs, see [Runtime API](https://gitcode.com/cann/runtime/blob/9.2.0/docs/zh/api_ref/README.md).

## Collected Data Description

After performance data is collected, parse the raw data files and export them as visualized performance data files, which are saved in the PROF\_XXX/mindstudio\_profiler\_output directory.
<!-- npu="950,A3,910b,910,310p,310b" id1 -->
For details about parsing, see [Using the msprof Command to Parse, Query, and Export Performance Data](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/msprof_parsing_instruct.md).
<!-- end id1 -->

<!-- npu="950,A3,910b,910,310p,310b" id21 -->
The performance data files corresponding to each parameter are as follows:

- ACL_PROF_TASK_TIME/ACL_PROF_TASK_TIME_L0:
  - The CANN hierarchy in msprof_*.json and the api_statistic_*.csv file
  - The Ascend Hardware hierarchy in msprof_*.json and the task_time_*.csv file
  - The Communication hierarchy in msprof_*.json and the communication_statistic_*.csv file
  - step_trace (iteration trace data)
  - op_summary_*.csv
  - op_statistic_*.csv
  - fusion_op_*.csv
- The CANN_AscendCL hierarchy and api_statistic_*.csv file in ACL_PROF_ACL_API:msprof_\*.json
- The CANN_Runtime hierarchy and api_statistic_*.csv file in ACL_PROF_RUNTIME_API:msprof_\*.json
- The Communication hierarchy and communication_statistic_*.csv file in ACL_PROF_HCCL_TRACE:msprof_\*.json
<!-- npu="950,A3,910b,910,310p,310b" id2 -->
- ACL_PROF_AICPU:aicpu_\*.csv
- ACL_PROF_L2CACHE:l2_cache_\*.csv
<!-- end id2 -->
- ACL_PROF_AICORE_METRICS:op_summary_\*.csv
- ACL_PROF_TASK_MEMORY:
  - memory_record_*.csv
  - operator_memory_*.csv
  - static_op_mem_*.csv
- ACL_PROF_MSPROFTX: msproftx data
- ACL_PROF_SYS_HARDWARE_MEM_FREQ:
  - On-chip memory read/write rate file
  - LLC hierarchy and llc_read_write_*.csv file in msprof_\*.json
  <!-- npu="950,A3,910b,310b" id4 -->
  - acc_pmu hierarchy in msprof_\*.json
  <!-- end id4 -->
  <!-- npu="950,A3,910b,310b" id5 -->
  - Stars Soc Info hierarchy in msprof_*.json
  <!-- end id5 -->
  <!-- npu="950,A3,910b,910,310p,310b" id6 -->
  - NPU MEM hierarchy and npu_mem_*.csv file in msprof_\*.json
  <!-- end id6 -->
  - npu_module_mem_\*.csv
<!-- npu="A3,910b,910,310b" id13 -->
- ACL_PROF_SYS_IO_FREQ: the NIC hierarchy and nic_*.csv files in msprof_\*.json, and the RoCE hierarchy and roce_*.csv files in msprof_*.json
<!-- end id13 -->
<!-- npu="950,A3,910b,910,310p" id14 -->
- ACL_PROF_SYS_INTERCONNECTION_FREQ:
<!-- end id14 -->
  <!-- npu="950,A3,910b,910,310p" id15 -->
  - The PCIe hierarchy and pcie_*.csv files in msprof_\*.json
  <!-- end id15 -->
  <!-- npu="950,A3,910b" id16 -->
  - The HCCS hierarchy and hccs_*.csv files in msprof_\*.json
  <!-- end id16 -->
  <!-- npu="950,A3,910b" id17 -->
  - The Stars Chip Trans hierarchy in msprof_\*.json
  <!-- end id17 -->
<!-- npu="950,A3,910b,910,310b" id18 -->
- ACL_PROF_DVPP_FREQ: dvpp_*.csv
<!-- end id18 -->
<!-- npu="950,A3,910b,910,310p,310b" id3 -->
- ACL_PROF_HOST_SYS:
  - The CPU Usage hierarchy and host_cpu_usage_\*.csv file in msprof_\*.json
  - The Memory Usage hierarchy and host_mem_usage_\*.csv file in msprof_\*.json
<!-- end id3 -->
<!-- npu="950,A3,910b,910,310p,310b" id19 -->
- ACL_PROF_HOST_SYS_USAGE/ACL_PROF_HOST_SYS_USAGE_FREQ: Host-side process CPU utilization data and Host-side process memory utilization data
<!-- end id19 -->

<!-- npu="950,A3,910b,910,310p,310b" id20 -->
For detailed performance data information, see also [Performance Data File Reference](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/profile_data_file_references.md).
<!-- end id20 -->

<!-- end id21 -->
