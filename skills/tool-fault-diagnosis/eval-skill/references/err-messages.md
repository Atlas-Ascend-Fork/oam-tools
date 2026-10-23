# CANN 错误消息文档 (errMsg)

> 本文档收录 CANN 8.5.0（商用版）/ CANN 9.0.0-beta.2（社区版）/ Ascend NPU 常见错误码及错误消息的分类解释，用于日志评估阶段的快速定位。
> 官方参考：[错误码使用说明（商用版 8.5.0）](https://www.hiascend.com/document/detail/zh/canncommercial/850/maintenref/troubleshooting/troubleshooting_0225.html) / [错误码使用说明（社区版 9.0.0-beta.2）](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/maintenref/troubleshooting/troubleshooting_0225.html)

## 错误码体系

### 格式说明

错误码以 **6 位字符**表示，例如 `E10035`：

- **第 1 位**：级别 — `E`（Error 错误）、`W`（Warning 告警）、`I`（Info 提示）
- **第 2 位**：模块字母（见下表）
- **后 4 位**：错误序号，`0000~8999` 为用户类错误，`9000~9999` 为内部错误（需提交ISSUE）

> **说明**：`E*9***` 格式表示系统内部错误码，出现时须收集日志后联系技术支持。
> 异步任务场景下（连续下发多个算子），日志中可能含有多个算子报错，需**从首报错算子开始**排查。

### 模块字母映射表

| 模块字母 | 模块名称 | 说明 |
|---------|---------|------|
| `1` | GE | Graph Engine（图编译与图优化） |
| `2` | FE | Fusion Engine（图融合编译器） |
| `3` | AI CPU | AI CPU 算子执行引擎 |
| `4` | TEFusion | TE 融合算子编译 |
| `7` | Vector算子插件 | 向量算子插件（ONNX 模型适配） |
| `8` | Vector算子 | 向量算子 |
| `B` | TBE Pass 编译工具 | TBE Pass 编译器 |
| `C` | Auto Tune | 自动调优工具 |
| `D` | RLTune | 强化学习调优工具 |
| `E` | RTS (Runtime) | 运行时系统（流/任务/设备上下文管理） |
| `F` | LxFusion & AutoDeploy | 融合与部署工具 |
| `G` | AOE | 算子/图优化引擎 |
| `H` | ACL | AscendCL 接口层 |
| `I` | HCCL | 集合通信库（多卡通信） |
| `J` | HCCP | HCCL 代理进程 |
| `K` | Profiling | 性能分析工具 |
| `L` | Driver | NPU 驱动层 |
| `M` | 队列调度 | Queue Schedule |
| `N` | DVPP | 媒体数据处理加速器 |
| `O` | AMCT | 模型压缩工具 |
| `P` | Dump | 算子 Dump 功能 |
| `Z` | 算子公共错误码 / AclNN | 公共算子错误码及 aclnn 算子 API |

---

## GE Errors（模块字母 `1`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `E10001` | Invalid_Argument | GE 参数非法（通用） | 检查调用 GE API 的参数 |
| `E10002` | Invalid_Argument_Tensor_Input_Shape | 输入 Tensor shape 非法 | 检查输入维度/大小是否符合算子要求 |
| `E10009` | Invalid_Argument_Tensor_Dynamic_Shape | 动态 shape 参数非法 | 检查 `--dynamic_batch_size` / `--dynamic_image_size` / `--dynamic_dims` 配置 |
| `E10031` | Invalid_Argument_Tensor_Input_Shape | 输入 shape 范围非法 | 检查 shape 上下界配置 |
| `E10032` | File_Operation_Error_Parse | 文件解析失败 | 检查模型文件格式（Caffe/ONNX/TF） |
| `E10041` | Invalid_Argument_Model | 模型参数非法 | 检查 OM 模型文件完整性 |
| `E10050` | Invalid_Argument_Tensor_Input_Shape_Range | 输入 shape 范围超限 | 检查动态 shape 范围配置 |
| `E10055` | Not_Supported | 特性不支持 | 升级 CANN 或更换算子实现 |
| `E10401` | Invalid_Argument_Operator_Input_Count | 算子输入数量非法 | 检查算子输入 Tensor 数量 |
| `E10402` | Invalid_Argument_Operator_Input_Buffer | 算子输入 Buffer 非法 | 检查输入 Tensor 内存地址 |
| `E10403` | Invalid_Argument_Operator_Output_Count | 算子输出数量非法 | 检查算子输出 Tensor 数量 |
| `E10404` | Invalid_Argument_Operator_Output_Buffer | 算子输出 Buffer 非法 | 检查输出 Tensor 内存地址 |
| `E10410` | File_Operation_Error_File_Not_Exist | 文件不存在 | 检查模型文件路径 |
| `E10501` | Not_Supported_Operator | 算子不支持 | 检查算子是否在当前 CANN 版本中支持 |
| `E11001~E11037` | Invalid_Argument_Caffe_Model_Data/Weight | Caffe 模型数据/权重非法 | 检查 Caffe 模型结构与权重文件 |
| `E12004` | Invalid_Argument_Operator_Input_Index | 算子输入索引非法 | 检查 TensorFlow 算子输入索引 |
| `E12009~E12029` | Invalid_Argument_TensorFlow_Model_Data | TensorFlow 模型数据非法 | 检查 TF pb 文件完整性 |
| `E13000` | File_Operation_Error_Invalid_Path | 文件路径非法 | 检查模型文件路径权限 |
| `E13001` | File_Operation_Error_Open | 文件打开失败 | 确认文件存在且有读权限 |
| `E13023` | Invalid_Argument_OM_Model_Size | OM 模型大小非法 | 检查 OM 文件完整性 |
| `E13024` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查 `ASCEND_OPP_PATH` 等环境变量设置 |
| `E13027` | Invalid_Argument_Network_Connection | 网络连接参数非法 | 检查网络配置 |
| `E13028` | Compilation_Error_Execute_Custom_Fusion_Pass | 自定义融合 Pass 执行失败 | 检查自定义融合 Pass 实现 |
| `E13029` | Compilation_Error_Load_Custom_Fusion_Pass | 加载自定义融合 Pass 失败 | 检查 Pass 动态库路径与权限 |
| `E13030` | Initialization_Error_Register_Custom_Fusion_Pass | 注册自定义融合 Pass 失败 | 检查 Pass 注册接口调用 |
| `E14001` | Invalid_Argument_Operator_Compilation_Parameter | 算子编译参数非法 | 检查 ATC 转换时的算子参数 |
| `E14002` | Invalid_Argument_Tensor_Attribute | Tensor 属性非法 | 检查 Tensor dtype/format/shape 组合 |
| `E16001~E16005` | Invalid_Argument_ONNX_Model_Data | ONNX 模型数据非法 | 检查 ONNX 模型文件与 opset 版本 |
| `E19999` | Inner_Error | GE 内部错误 | 收集完整日志后提交ISSUE |
| `W11001` | Performance_Not_Optimal_Operator | 算子性能非最优 | 可忽略或优化算子 shape/格式 |
| `W11002` | Config_Error_Weight_Configuration | 权重配置告警 | 检查权重量化配置 |
| `W11003` | Config_Error_Operator_Missing_Implementation | 算子缺少实现 | 提供自定义算子实现 |

---

## FE Errors（模块字母 `2`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `E20001` | Compilation_Error | FE 编译失败 | 查看 FE 详细日志，检查图结构 |
| `E20002` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查 `ASCEND_OPP_PATH` |
| `E20003` | Config_Error | 配置错误 | 检查 ATC 转换参数 |
| `E20007` | Compilation_Error_Execute_Fusion_Pass | 融合 Pass 执行失败 | 检查内置融合 Pass 或关闭相关融合规则 |
| `E20101` / `E20103` | Invalid_Argument | 参数非法 | 检查 FE 接口输入参数 |
| `E21001` | File_Operation_Error_Open | 文件打开失败 | 检查 OPP 包路径及权限 |
| `E21002` | File_Operation_Error_Parse | 文件解析失败 | 检查 OPP 包完整性 |
| `E22001` | Compilation_Error | FE 编译失败（通用） | 查看 FE 编译 LOG |

---

## AI CPU Errors（模块字母 `3`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `E30003` | Not_Supported_Specification | 规格不支持 | 检查 AI CPU 算子输入规格是否超限 |
| `E30004` | NN_Process_Bin_Error | NN 进程二进制错误 | 重新安装 OPP 包；检查 `nnprocess` 可执行文件 |
| `E30005` | Device_Connection_Failure | 设备连接失败 | 检查驱动状态与设备连接 |
| `E30006` | Package_Error_Verify_OPP | OPP 包校验失败 | 重新安装正确版本的 OPP 包 |
| `E30007` | Cgroup_Add_Failure | Cgroup 添加失败 | 检查系统 cgroup 配置与权限 |
| `E30008` | Execution_Error_AICPU_Operator_Timeout | AI CPU 算子执行超时 | 检查算子实现性能瓶颈；增大超时时间 |
| `E39001` | Invalid_Argument | 参数非法 | 检查 AI CPU 算子输入参数 |
| `E39002` | Inner_Error_Driver_API_Call_Failed | 驱动 API 调用失败 | 检查驱动版本兼容性 |
| `E39004` | Inner_Error_AICPU_Scheduler_Init_Failed | AI CPU 调度器初始化失败 | 重启业务进程；检查设备状态 |
| `E39005` | Inner_Error_TSDaemon_Process_Abnormal | TSDaemon 进程异常 | 检查 Device 侧系统日志 |
| `E39006` | Inner_Error_Failed_Send_OPP_To_Device | OPP 包发送到 Device 失败 | 检查 OPP 包路径；重新安装 |
| `E39007` | Inner_Error_Device_Subprocess_Startup_Timeout | Device 子进程启动超时 | 检查 Device 状态；必要时复位设备 |
| `E39008` | Inner_Error_Verify_NN_Process_Binary | NN 进程签名校验失败 | 确认 OPP 包版本匹配 |
| `E39009` | Inner_Error_Device_Status_Abnormal | Device 状态异常 | `npu-smi info` 确认设备状态；可能需要联系硬件支持 |
| `E39010` | Inner_Error_Cgroup_Add_Failed | Cgroup 添加失败（内部） | 检查系统内核 cgroup 支持 |

---

## TEFusion Errors（模块字母 `4`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `E40001` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查 Python 环境与 `PYTHONPATH` |
| `E40002` | Environment_Error_Incorrect_Python_Version | Python 版本不支持 | 确认使用 CANN 要求的 Python 版本 |
| `E40003` | File_Operation_Error_Open | 文件打开失败 | 检查 TE 相关文件路径 |
| `E40020` | Environment_Error_Import_Python_Module_Failed | Python 模块导入失败 | 检查 `te`、`tbe` 等包是否安装 |
| `E40021` | Compilation_Error | TE Fusion 编译失败 | 查看 TE 详细编译日志 |
| `E40022` | Invalid_Argument | 参数非法 | 检查算子融合配置 |
| `E40023` | File_Operation_Error_Invalid_Path | 文件路径非法 | 检查 TE 工作目录权限 |
| `E40024` | Environment_Error_Call_Python_Function_Failed | Python 函数调用失败 | 检查 Python 环境完整性 |
| `W40010` | Config_Error_Invalid_Environment_Variable | 环境变量告警 | 检查 TE 相关环境变量 |
| `W40011` | Directory_Operation_Error_Create_Failed | 目录创建失败（告警） | 检查工作目录写权限 |

---

## Vector算子插件 Errors（模块字母 `7`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `E76002` | ONNX_Model_Data_Error | ONNX 模型数据错误 | 检查 ONNX 算子插件与模型的兼容性 |

---

## Vector算子 Errors（模块字母 `8`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `E80001` | Invalid_Config_Value | 配置值非法 | 检查向量算子配置参数 |

---

## TBE Pass 编译工具 Errors（模块字母 `B`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EB0000` | Compilation_Error | TBE Pass 编译失败（通用） | 查看 TBE 详细编译日志 |
| `EB0500` | Compilation_Error | TBE Pass 编译失败 | 查看具体 Pass 信息 |
| `EB1000` | Compilation_Error_Invalid_Primitives | 原语非法 | 检查 TBE 算子 Primitive 定义 |
| `EB3000` | Compilation_Error | 编译失败 | 检查 UB 内存、data type 等约束 |
| `EB4000` | Compilation_Error_Invalid_Emit_Insn | 生成指令非法 | 检查 `emit_insn` 调用参数 |
| `EB9000` | Compilation_Error | TBE 内部编译错误 | 查看详细 TBE log；可能需要联系技术支持 |

---

## Auto Tune Errors（模块字母 `C`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EC0000` | Communication_Error | 通信错误 | 检查 AOE Server 连接 |
| `EC0001` / `EC0004` | Permission_Error | 权限错误 | 检查 Auto Tune 工作目录权限 |
| `EC0002` / `EC0006` | Directory_Operation_Error | 目录操作错误 | 检查目录权限与路径 |
| `EC0003` | File_Operation_Error_File_Not_Exist | 文件不存在 | 检查 Auto Tune 依赖文件 |
| `EC0005` | Invalid_Argument | 参数非法 | 检查 AOE 调优参数 |
| `EC0007` / `EC0008` / `EC0012` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查 `ASCEND_OPP_PATH` 等环境变量 |
| `EC0009` | Resource_Error | 资源错误 | 检查系统资源（内存/CPU）是否充足 |
| `EC0010` | Environment_Error_Import_Python_Module_Failed | Python 模块导入失败 | 检查 AOE 依赖 Python 包 |
| `EC0011` | Permission_Error_User_Denied | 用户权限拒绝 | 检查用户权限 |
| `EC0013` | File_Operation_Error | 文件操作错误 | 检查文件路径与权限 |

---

## RLTune Errors（模块字母 `D`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `ED0000` | Communication_Error | 通信错误 | 检查 RLTune 服务连接 |
| `ED0001` | Invalid_Argument | 参数非法 | 检查 RLTune 调优参数 |
| `ED0002` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查相关环境变量 |

---

## RTS (Runtime) Errors（模块字母 `E`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EE1001` | Invalid_Argument | Runtime 参数非法 | 检查 stream/context/device 参数 |
| `EE1002` | Execution_Error_Stream_Synchronize_Timeout | Stream 同步超时 | 检查算子执行是否挂起；排查是否有 AI Core Error |
| `EE1003` | Invalid_Argument | Runtime 参数非法 | 检查 API 调用参数 |
| `EE1004` | Invalid_Argument_Null_Pointer | 空指针参数 | 检查传入指针是否为 null |
| `EE1005` / `EE1006` | Not_Supported | 特性不支持 | 升级 CANN 版本 |
| `EE1007` | Resource_Error_Bind_Stream | Stream 绑定资源错误 | 检查 Context 与 Stream 创建顺序 |
| `EE1008` | Execution_Error_Load_OP_Kernel | 算子 Kernel 加载失败 | 检查 OPP 包是否正确安装 |
| `EE1009` | Execution_Error_Model | 模型执行失败 | 结合 AI Core Error / HCCL Error 综合定位 |
| `EE1010` | Execution_Error_Invalid_Context | Context 非法 | 确认 `aclrtCreateContext` 已调用 |
| `EE1011` | Invalid_Argument | Runtime 参数非法 | 检查 API 调用参数 |
| `EE2002` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查 Runtime 相关环境变量 |
| `EE4001` | Model_Binding_Errors | 模型绑定失败 | 检查 `aclmdlBindExecutor` 调用顺序 |
| `EE4002` | Model_Unbinding_Errors | 模型解绑失败 | 检查 `aclmdlUnbindExecutor` 调用顺序 |
| `EE4004` | Profiling_Enable_Errors | Profiling 启用失败 | 检查 Profiling 配置 |

---

## LxFusion & AutoDeploy Errors（模块字母 `F`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EF0000` | Directory_Operation_Error_Open_Failed | 目录打开失败 | 检查 LxFusion 工作目录 |
| `EF0001` | Invalid_Argument_SOC_Version | SOC 版本非法 | 确认模型与当前 SOC 型号匹配 |
| `EF0003` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查 CANN 环境变量 |
| `WF0000` | File_Operation_Error | 文件操作告警 | 检查导出文件路径 |
| `WF0001` | Invalid_Config_Value | 配置值非法（告警） | 检查 LxFusion 配置参数 |
| `WF0002` | Model_Performance_Not_Optimal | 模型性能非最优（告警） | 可考虑使用 AOE 进行调优 |

---

## AOE Errors（模块字母 `G`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EG0000` / `EG0004` | Invalid_Argument_Command | 命令参数非法 | 检查 AOE 命令行参数 |
| `EG0001` | Config_Error | 配置错误 | 检查 AOE 配置文件 |
| `EG0002` | Config_Error_Invalid_Environment_Variable | 环境变量配置错误 | 检查 AOE 相关环境变量 |
| `EG0010` | Directory_Operation_Error | 目录操作错误 | 检查 AOE 工作目录权限 |
| `EG0011` | File_Operation_Error | 文件操作错误 | 检查 AOE 输出文件路径权限 |
| `EG0012` | Environment_Error | 环境错误 | 检查 Python 环境与依赖包 |
| `EG0013` | Invalid_Argument_Device_ID | Device ID 非法 | 确认 `-device_id` 参数有效 |
| `EG2000` | Communication_Error | 通信错误 | 检查 AOE Server 连接 |
| `EG2001` | Permission_Error_Private_Key_Certificate_Verify_Failed | 证书校验失败 | 检查环境证书配置 |
| `WG0000` | Resource_Error_Insufficient_Host_Memory | Host 内存不足（告警） | 增大宿主机内存或减少并行调优任务 |

---

## ACL Errors（模块字母 `H`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EH0001` | Invalid_Argument | ACL 参数非法 | 检查 ACL API 调用参数 |
| `EH0002` | Invalid_Argument_Null_Pointer | 空指针参数 | 检查传入指针是否为 null |
| `EH0003` | File_Operation_Error_Invalid_Path | 文件路径非法 | 检查 `acl.json` 等配置文件路径 |
| `EH0004` | File_Operation_Error | 文件操作失败 | 检查配置文件权限与格式 |
| `EH0005` | Invalid_Argument | ACL 参数非法 | 检查 ACL 接口调用顺序 |
| `EH0006` | Not_Supported | ACL 特性不支持 | 确认当前平台支持该特性 |

> **常用 ACL 运行时返回码（acl_base.h）**可直接通过 `grep "ACL_ERROR_" /usr/local/Ascend/ascend-toolkit/latest/include/acl/acl_base.h` 查看完整定义。

---

## HCCL Errors（模块字母 `I`）

| 错误码 | 错误类型 | 版本 | 说明 | 排查方向 |
|--------|---------|------|------|---------|
| `EI0001` | Config_Error_Invalid_Environment_Variable | 通用 | HCCL 环境变量配置错误 | 检查 `HCCL_CONNECT_TIMEOUT`、`HCCL_EXEC_TIMEOUT` 等 |
| `EI0002` | Communication_Error_Timeout | 通用 | 通信超时（默认 120s） | 排查是否有 rank 崩溃；检查网络连通性 |
| `EI0003` | Invalid_Argument_Collective_Communication_Operator | 通用 | 集合通信算子参数非法 | 检查各 rank 的算子参数一致性 |
| `EI0004` | Config_Error_Ranktable_Configuration | 8.5.0 | Ranktable 配置错误 | 检查 `rank_table_file` 配置，确认 IP/端口正确 |
| `EI0004` | File_Operation_Error_Parse | 9.0-beta2 | Ranktable 文件解析失败 | 检查 Ranktable JSON 格式 |
| `EI0005` | Inconsistent_Collective_Communication_Arguments_Between_Ranks | 8.5.0 | 各 rank 集合通信参数不一致 | 确认所有 rank 使用相同的通信算子和参数 |
| `EI0005` | Invalid_Argument | 9.0-beta2 | 参数非法 | 检查 HCCL 参数 |
| `EI0006` | Communication_Error_Get_Socket | 通用 | Socket 获取失败 | 检查防火墙配置；确认端口未被占用 |
| `EI0007` | Resource_Error | 通用 | 资源错误 | 检查 HBM/系统内存是否充足 |
| `EI0008` | Package_Error_Incorrect_HCCL_Version | 通用 | HCCL 版本不匹配 | 确认各节点 CANN 版本一致 |
| `EI0009` | Communication_Error_Initialize_Transport | 9.0-beta2 | 传输初始化失败 | 检查 RDMA/ROCE 网络配置 |
| `EI0010` | Communication_Error_P2P | 通用 | P2P 通信错误 | 检查 NVLink/PCIe 连接；检查 P2P 内存访问权限 |
| `EI0011` | Resource_Error_Insufficient_Device_Memory | 通用 | Device 内存不足 | 减少 batch size 或减少 HCCL buffer 大小 |
| `EI0012` | Execution_Error_SDMA | 通用 | SDMA 执行错误 | 检查 PCIe 链路状态，查看 dmesg |
| `EI0013` | Execution_Error_ROCE_CQE | 通用 | ROCE CQE 错误 | 检查 RDMA 网卡状态与驱动 |
| `EI0014` | Ranktable_Check_Failed | 8.5.0 | Ranktable 校验失败 | 检查 Ranktable 文件各字段 |
| `EI0015` | Ranktable_Detect_Failed | 8.5.0 | Ranktable 检测失败 | 检查各 rank 的 IP 连通性 |
| `EI0016` | Config_Error | 通用 | HCCL 配置错误 | 检查 HCCL 配置参数 |
| `EI0017` | Config_Error_Ranktable | 通用 | Ranktable 配置错误 | 检查 Ranktable 文件格式 |
| `EI0018` | Execution_Error_UB_CQE | 9.0-beta2 | UB CQE 执行错误 | 检查片上互联状态 |
| `EI0019` / `EI0020` | Communication_Error_Bind_IP_Port | 9.0-beta2 | IP/端口绑定失败 | 确认端口未被占用；检查 IP 配置 |

---

## HCCP Errors（模块字母 `J`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EJ0001` | HCCP_Process_Initialization_Failure | HCCP 进程初始化失败 | 检查 HCCP 相关环境变量与依赖 |
| `EJ0002` | Environment_Error | 环境错误 | 检查 HCCP 运行环境 |
| `EJ0003` | Communication_Error_Bind_IP_Port | IP/端口绑定失败 | 确认端口未被占用 |
| `EJ0004` | Invalid_Argument_IP_Address | IP 地址非法 | 检查 Ranktable 中的 IP 配置 |

---

## Profiling Errors（模块字母 `K`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EK0001` | Invalid_Argument | Profiling 参数非法 | 检查 Profiling 配置文件 |
| `EK0002` | Invalid_Argument_API_Call_Sequence | API 调用顺序错误 | 确认 `aclprofStart` / `aclprofStop` 调用顺序 |
| `EK0003` | Config_Error | Profiling 配置错误 | 检查 Profiling JSON 配置 |
| `EK0004` | Not_Supported_API | API 不支持 | 当前平台不支持该 Profiling API |
| `EK0005` | Not_Supported | 特性不支持 | 当前版本不支持该 Profiling 特性 |
| `EK0006` | Invalid_Argument_Null_Pointer | 空指针参数 | 检查 Profiling API 参数 |
| `EK0201` | Resource_Error_Insufficient_Host_Memory | Host 内存不足 | 减少 Profiling 数据采集量 |
| `EK9999` | System_Terminated | 系统终止 | Profiling 内部异常，收集日志联系技术支持 |

---

## Driver Errors（模块字母 `L`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EL0001` | Device_Absent/Abnormal | 设备不存在或异常 | `npu-smi info` 确认设备状态；查看 dmesg |
| `EL0002` | Invalid_Device_ID | Device ID 非法 | 确认 device_id 在有效范围内 |
| `EL0003` | Invalid_Argument | 驱动参数非法 | 检查驱动 API 调用参数 |
| `EL0004` | Memory_Allocation_Failure | 内存分配失败（HBM OOM） | 减小 batch size；检查 HBM 占用 |
| `EL0005` | Resource_Busy | 资源忙 | 等待其他进程释放资源 |
| `EL0006` | Insufficient_Resources | 资源不足 | 检查 Event/Stream/Notify 资源使用量 |
| `EL0007` | No_Permission | 权限不足 | 检查进程权限；确认在规定用户下运行 |
| `EL0008` | Insufficient_Event_Resources | Event 资源不足 | 减少 Event 创建数量 |
| `EL0009` | Insufficient_Stream_Resources | Stream 资源不足 | 减少 Stream 创建数量 |
| `EL0010` | Insufficient_Notify_Resources | Notify 资源不足 | 减少 Notify 创建数量 |
| `EL0011` | Insufficient_Model_Resources | Model 资源不足 | 减少同时加载的模型数量 |
| `EL0012` | Full_Service_Queue | 服务队列已满 | 等待队列消费完成；减少并发任务量 |
| `EL0013` | Insufficient_CDQM_Resources | CDQM 资源不足 | 请提交ISSUE |
| `EL0014` | Operation_Unsupported | 操作不支持 | 确认驱动版本支持该操作 |
| `EL0015` | Invalid_Device_Access | 设备访问非法 | 检查内存地址合法性；核查是否越界 |

---

## Queue Schedule Errors（模块字母 `M`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EM9001` | Inner_Error_Group_Attach_Failed | Group 附加失败 | 内部错误，收集日志，提交ISSUE |
| `EM9002` | Inner_Error_Queue_Scheduler_Init_Failed | Queue 调度器初始化失败 | 内部错误，检查 Device 状态 |

---

## DVPP Errors（模块字母 `N`）

| 错误码 | 错误类型 | 版本 | 说明 | 排查方向 |
|--------|---------|------|------|---------|
| `EN0001` / `EN0002` | Invalid_Argument | 通用 | DVPP 参数非法 | 检查分辨率/格式等参数是否在支持范围内 |
| `EN0003` | Invalid_Argument_Null_Pointer | 通用 | 空指针参数 | 检查 DVPP API 指针参数 |
| `EN0004` | Not_Supported | 通用 | 操作不支持 | 确认当前平台支持该 DVPP 操作 |
| `EN0005` | Invalid_Argument_Channel_ID | 通用 | Channel ID 非法 | 检查 DVPP 通道创建与使用 |
| `EN0006` | Invalid_Argument_Memory_Address | 通用 | 内存地址非法 | 确认使用 `acldvppMalloc` 分配的 DVPP 内存 |
| `EN0007` | Execution_Error_DVPP_Operator_Timeout | 通用 | DVPP 算子超时 | 检查输入数据大小；考虑增大超时时间 |
| `EN0008` / `EN0009` | Not_Supported_File_Type | 通用 | 文件类型不支持 | 确认图片/视频格式在 DVPP 支持列表内 |
| `EN0010` / `EN0011` | Resource_Error_Insufficient_Host_Memory | 9.0-beta2 | Host 内存不足 | 减少并发 DVPP 任务数量 |
| `EN0012` | Resource_Error_Insufficient_Device_Memory | 9.0-beta2 | Device 内存不足 | 减少 DVPP buffer 大小 |
| `EN0013` | Resource_Error_Busy | 9.0-beta2 | 资源忙 | 等待 DVPP 任务完成 |
| `EN0014` | Resource_Error_Insufficient_Channel | 9.0-beta2 | Channel 资源不足 | 减少 DVPP 通道创建数量 |
| `EN0015` | Resource_Error | 9.0-beta2 | 资源错误 | 检查 DVPP 资源使用情况 |
| `EN0016` | File_Operation_Error_Open | 9.0-beta2 | 文件打开失败 | 检查 DVPP 输入文件路径 |
| `EN0017` | Invalid_Argument_API_Call_Sequence | 9.0-beta2 | API 调用顺序错误 | 确认 DVPP 通道创建/初始化/销毁顺序 |

---

## AMCT Errors（模块字母 `O`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EO0001` | Config_Error | 配置错误 | 检查量化配置文件 |
| `EO0002` | Invalid_Argument | 参数非法 | 检查 AMCT 工具参数 |
| `EO0003` | Invalid_Argument_Model / Invalid_Model | 模型非法 | 检查输入模型格式与版本 |
| `EO0004` | Invalid_Argument_Command / Config_Error | 命令/配置错误 | 检查 AMCT 命令行参数 |
| `EO9999` | Inner_Error | 内部错误 | 收集日志，提交ISSUE |

---

## Dump Errors（模块字母 `P`）

| 错误码 | 错误类型 | 版本 | 说明 | 排查方向 |
|--------|---------|------|------|---------|
| `EP0001` | Invalid_Argument | 通用 | Dump 参数非法 | 检查 Dump 配置（路径/模式/算子名） |
| `EP0002` | File_Operation_Error / Config_Error | 通用 | 文件操作/配置错误 | 检查 Dump 路径权限；检查磁盘空间 |
| `EP0003` | Config_Error | 9.0-beta2 | Dump 配置错误 | 检查 `acl.json` 中 Dump 相关配置 |
| `WP0001` | Config_Error_Invalid_Environment_Variable | 9.0-beta2 | 环境变量配置告警 | 检查 `ASCEND_DUMP_PATH` 等环境变量 |

---

## 算子公共错误码 / AclNN Errors（模块字母 `Z`）

| 错误码 | 错误类型 | 说明 | 排查方向 |
|--------|---------|------|---------|
| `EZ0001` | Invalid_Input_Shape | 输入 shape 非法 | 检查算子输入 Tensor 的维度和大小 |
| `EZ0002` | Invalid_Attr | 属性值非法 | 检查算子属性参数值 |
| `EZ0003` | Invalid_Attr_Size | 属性大小非法 | 检查属性参数的维度/大小 |
| `EZ0004` | Invalid_Input | 输入非法 | 检查输入 Tensor 内容 |
| `EZ0005` | Invalid_Input_ShapeSize | 输入 shape 大小非法 | 检查元素总数是否超限 |
| `EZ0006` | Invalid_Input_Format | 输入格式非法 | 检查 Tensor format（如 NCHW/NHWC） |
| `EZ0007` | Invalid_Input_Dtype | 输入 dtype 非法 | 确认算子支持当前 dtype |
| `EZ0501` | Unsupported_Operator | 算子不支持 | 检查算子版本；升级 CANN 或换算子 |
| `EZ3002` / `EZ3003` / `EZ9010` | Unsupported_Operator | 算子不支持 | 同上 |
| `EZ1001` | AclNN_Parameter_Error | AclNN 参数错误 | 检查 aclnn 算子 API 调用参数 |
| `EZ9903` | AclNN_Runtime_Error | AclNN 运行时错误 | 结合 RTS/Driver 错误综合定位 |
| `EZ9999` | AclNN_Inner_Error / **AI Core Error** | AclNN 内部错误 | **训推最常见报错**，见[故障处理参考](./fault-handling.md) |

---

## 常见错误消息关键字速查

| 错误消息关键字 | 归属模块 | 最可能原因 | 优先排查 |
|--------------|---------|----------|---------|
| `aicore error exception` / `aivec error exception` | EZ9999 (AclNN/RTS) | AI Core 执行异常 | 见 fault-handling.md §AI Core Error 专题 |
| `Aicore kernel execute failed` | EZ9999 / EE1009 | AI Core Kernel 报错 | 收集 plog 和 msnpureport 数据，使用 msaicerr 分析 |
| `Graph build failed` | GE (E1xxxx) | 图构建失败 | 检查算子节点定义，查看 GE COMPILE 日志 |
| `Shape infer failed` | GE (E10002~E10050) | shape 推导失败 | 检查输入 Tensor shape 是否合法 |
| `Memory not enough` | GE (E1xxxx) / EL0004 | HBM OOM | 减小 batch size；开启重计算 |
| `UB memory overflow` | TBE (EB3000) | 统一缓存溢出 | 减小 tiling 参数 |
| `AllReduce timeout` | HCCL (EI0002) | 多卡通信超时 | 排查rank崩溃；检查网络 |
| `Device not found` | Driver (EL0001) | 设备不存在/驱动未加载 | `npu-smi info`；`lsmod \| grep npu` |
| `rtStreamSynchronize execute failed` | RTS (EE1002) | Stream 同步失败 | 结合首报错算子定位 |
| `unbind model stream failed` | RTS (EE4002) | 进程异常退出后重启 | 确认进程完整退出后再重启 |

---

## 返回码速查

| retcode | 含义 |
|---------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 参数非法 |
| 4 | 内存不足 |
| 7 | 设备未初始化 |
| 9 | 超时 |
| -1 | 未知错误 |
