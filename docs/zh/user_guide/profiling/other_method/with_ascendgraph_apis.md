# 使用Ascend Graph接口采集性能数据

Ascend Graph API是在构图过程中采集性能数据。

> [!NOTE]说明
>--task-trace后续版本会废弃，请使用--task-time开关控制相关数据采集。

## 支持的型号

<!-- npu="310p" id1 -->
- Atlas推理系列产品
<!-- end id1 -->
<!-- npu="910" id2 -->
- Atlas训练系列产品
<!-- end id2 -->
<!-- npu="910b" id3 -->
- Atlas A2系列产品
<!-- end id3 -->
<!-- npu="A3" id4 -->
- Atlas A3系列产品
<!-- end id4 -->
<!-- npu="950" id5 -->
- Ascend 950PR&950DT系列产品
<!-- end id5 -->

## 启动方式介绍

**表1**  Profiling性能数据采集方式

|方式|接口|
|--|--|
|GEInitialize接口传入option参数|ge.exec.profilingMode和ge.exec.profilingOptions。<br>通过GEInitialize传入option参数ge.exec.profilingOptions，可以采集迭代轨迹数据，传入字段包括training_trace/bp_point/fp_point。<br>该方式采集的性能数据将存放在ge.exec.profilingOptions的output参数所配置的路径下。|
|aclgrph接口|aclgrphProfInit、aclgrphProfFinalize、aclgrphProfCreateConfig、aclgrphProfDestroyConfig、aclgrphProfStart和aclgrphProfStop。<br>该方式采集的性能数据将存放在aclgrphProfInit的profiler_path参数所配置的路径下。|

<!-- npu="950,A3,910b,910,310p,310b,IPV350" id6 -->
> [!NOTE]说明
>接口详细说明，请参见[《图开发》](https://hiascend.com/document/redirect/CannCommunityGraphguide)。
<!-- end id6 -->

## 采集性能原始数据（GEInitialize接口传入option）

参考以下示例通过GEInitialize传入option参数：

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

## 采集性能原始数据（aclgrph接口）

参考以下示例调用接口，采集Profiling性能数据：

```cpp
  // 构造Graph，该步骤省略
  // ......

  // init ge
  std::map<std::string, std::string> ge_options = {{"ge.socVersion", "Ascendxxx"}, {"ge.graphRunMode", "1"}};
  ge::GEInitialize(ge_options);

  std::string profilerResultPath = "/home/test/prof";       //该路径需要提前创建
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
## 采集数据说明

配置Ascend Graph API方式采集后请参见[使用msprof命令解析、查询与导出性能数据](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/msprof_parsing_instruct.md)将原始数据文件解析并导出为可视化的timeline和summary文件。

<!-- end id7 -->
