# Collecting Performance Data Using the Ascend Graph API

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:27:23.641Z pushedAt=2026-10-16T03:49:47.103Z -->

The Ascend Graph API collects performance data during graph construction.

> [!NOTE] Note
> --task-trace will be deprecated in later versions. Use the --task-time switch to control the collection of related data.

## Supported Models

<!-- npu="310p" id1 -->
- Atlas inference products
<!-- end id1 -->
<!-- npu="910" id2 -->
- Atlas training products
<!-- end id2 -->
<!-- npu="910b" id3 -->
- Atlas A2 products
<!-- end id3 -->
<!-- npu="A3" id4 -->
- Atlas A3 products
<!-- end id4 -->
<!-- npu="950" id5 -->
- Ascend 950PR & 950DT products
<!-- end id5 -->

## Startup Methods

**Table 1** Profiling performance data collection methods

|Method|API|
|--|--|
|Passing the option parameter through the GEInitialize API|ge.exec.profilingMode and ge.exec.profilingOptions.<br>By passing the option parameter ge.exec.profilingOptions through GEInitialize, you can collect iteration trace data. The fields to be passed include training_trace/bp_point/fp_point.<br>The performance data collected in this method is stored in the path configured by the output parameter of ge.exec.profilingOptions.|
|aclgrph API|aclgrphProfInit, aclgrphProfFinalize, aclgrphProfCreateConfig, aclgrphProfDestroyConfig, aclgrphProfStart, and aclgrphProfStop.<br>The performance data collected in this method is stored in the path configured by the profiler_path parameter of aclgrphProfInit.|

<!-- npu="950,A3,910b,910,310p,310b,IPV350" id6 -->
> [!NOTE] Note
> For details about the APIs, see [Graph Development](https://gitcode.com/cann/ge/blob/9.2.0/docs/zh/user_guides/graph_dev/README.md).
<!-- end id6 -->

## Collect Performance Raw Data (Passing option Through GEInitialize)

Refer to the following example to pass the option parameter through GEInitialize:

```cpp
// 0. System init
std::map<AscendString, AscendString> config = {{"ge.exec.deviceId", "0"},
                        {"ge.graphRunMode", "1"},
                        {"ge.exec.precision_mode", "allow_fp32_to_fp16"},
                        {"ge.exec.profilingMode", "1"},
                        {"ge.exec.profilingOptions",  R"({"output":"/tmp/profiling","training_trace":"on","fp_point":"","bp_point":""})"}};
    Status ret = ge::GEInitialize(config);
    if (ret != SUCCESS) {
        return FAILED;
    }
```

## Collect Performance Raw Data (aclgrph API)

Call the APIs as shown in the following example to collect Profiling performance data:

```cpp
  // Construct the graph. This step is omitted.
  // ......

  // init ge
  std::map<std::string, std::string> ge_options = {{"ge.socVersion", "Ascendxxx"}, {"ge.graphRunMode", "1"}};
  ge::GEInitialize(ge_options);

  std::string profilerResultPath = "/home/test/prof";       // Create this path in advance.
  uint32_t length = strlen("/home/test/prof");
  ret = ge::aclgrphProfInit(profilerResultPath.c_str(), length);

  std::map<string, string> options = {{"a", "b"}, {"c", "d"}};
  uint32_t graphId = 0;

  ge::Session *session = new Session(options);
  ret = session->AddGraph(graphId, graph);

  uint32_t deviceid_list[1] = {0};
  uint32_t device_nums = 1;
  uint64_t data_type_config = ProfDataTypeConfig::kProfTaskTime | ProfDataTypeConfig::kProfAiCoreMetrics | ProfDataTypeConfig::kProfAicpu | ProfDataTypeConfig::kProfTrainingTrace;
  ProfAicoreEvents *aicore_events = NULL;
  ProfilingAicoreMetrics aicore_metrics = ProfilingAicoreMetrics::kAicoreArithmeticUtilization;
  ge::aclgrphProfConfig *pro_config = ge::aclgrphProfCreateConfig(deviceid_list, device_nums, aicore_metrics, aicore_events, data_type_config);

  ge::aclgrphProfStart(pro_config);

  session->RunGraph(graphId, inputs_r, outputs_r);

  ge::aclgrphProfStop(pro_config);

  ge::aclgrphProfDestroyConfig(pro_config);

  ge::aclgrphProfFinalize();

  delete session;
  ge::GEFinalize();
```

<!-- npu="950,A3,910b,910,310p,310b,IPV350" id7 -->
## Data Collection Description

After configuring Ascend Graph API-based collection, see [Parsing, Querying, and Exporting Performance Data Using the msprof Command](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/msprof_parsing_instruct.md) to parse the raw data files and export them as visualized timeline and summary files.

<!-- end id7 -->
