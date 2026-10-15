# asys工具功能及约束

## 功能介绍

为提高系统故障维测效率，提供**故障信息收集工具asys**一键式收集信息。**该工具仅支持在Ascend EP形态下使用。**

工具支持以下功能：

- **[故障信息收集](fault_information_collection.md)**：不复跑业务，仅收集故障信息，例如软硬件信息、日志等。
- **[业务复跑+故障信息收集](rerun_fault_information_collection.md)**：复跑业务后再收集故障信息，例如软硬件信息、日志等。
- **[软硬件、Device状态信息展示](software_hardware_device_status_info_display.md)**：收集安装包版本信息、Device温度、功率等。
- **[健康检查](health_check.md)**：检查所有Device或指定Device的健康状态（若不健康，会展示报错信息）。
- **[综合检测](comprehensive_detection.md)**：涉及压力检测、HBM硬件检测、CPU检测、AI Core STL硬件检测等功能。
- **[组件检测](component_diagnostics.md)**：当前只支持AI Vector组件检测，不支持并行执行。
- **[trace文件解析](trace_files_parsing.md)/[coredump文件解析](coredump_files_parsing.md)/[stackcore文件解析](stackcore_files_parsing.md)/[coretrace文件解析](coretrace_files_parsing.md)/[UB文件解析](UB_files_parsing.md)**：解析各类文件，以便后续定位问题。
- **[实时堆栈导出](stack_export.md)**：该功能适用于业务进程卡住场景，以便导出堆栈信息定位问题。
- **[环境配置](environment_configuration.md)**：获取或恢复指定配置。
- **[AI Core Error故障信息解析](AI_Core_error_analysis.md)**：执行业务时，若日志文件或屏幕打印信息中包含AI Core Error报错（例如“there is an aivec error exception”或“there is an aicore error exception”），可使用AI Core Error故障信息解析功能，快速定位AI Core Error问题的原因，提高排查效率。
- **[性能数据采集](profiling_collection.md)**：采集关键性能数据，辅助用户分析性能问题。

**表 1** **asys工具支持收集的信息列表**

| 分类 | 描述 |
| --- | --- |
| 软件信息 | 涉及软件包版本，环境变量，软件依赖，系统信息。 |
| 日志信息 | 包括以下信息：<br><br>  - Host侧CANN软件栈日志。<br>  - Host侧message日志。<br>  - Device侧固件日志：device-*日志（需root权限）。<br>  - Device侧系统日志：message日志，device-os日志（需root权限）。<br>  - 黑匣子、stackcore文件、coretrace文件（需root权限）。<br>  - 任务打印日志。<br>  - run包安装日志（需run包安装用户与应用程序执行用户一致才可收集）。 |
| dump信息 | 包括以下信息：<br><br>  - GE dump图。<br>  - TF Adapter dump图。<br>  - 发生AI Core Error时生成的dump文件。 |
| 算子编译*.o、*.json文件 | - |
| 算子编译过程信息文件 | 仅支持在业务复跑时收集算子编译过程信息文件，文件内容包括编译成功失败、编译结果是复用的缓存/在线编译/二进制等。<br>asys工具是否能收集到算子编译过程信息，取决于用户是否设置NPU_COLLECT_PATH环境变量（用于设置故障信息的保存路径），若设置，则系统会在该环境变量设置的目录下新建子目录/extra-info/ops/，在子目录下新建op_compile_stats.log，将算子编译过程信息写入log文件，此时asys工具则可以收集到算子编译过程信息文件；若不设置，则系统不会生成对应的log文件，因此asys工具也不会收集该文件。 |
| 自定义算子配置信息（*.json文件） | asys工具是否能收集到自定义算子配置信息，取决于用户是否设置以下环境变量：<br><br>  - 若用户设置ASCEND_OPP_PATH环境变量（用于设置算子库的安装路径），则asys工具会根据\${ASCEND_OPP_PATH}/vendors/config.ini文件load_priority字段，收集\${ASCEND_OPP_PATH}/vendors目录下的自定义算子配置信息（即config/*.json文件）；否则，asys工具不收集。<br>  - 若用户设置ASCEND_CUSTOM_OPP_PATH环境变量（用于设置自定义算子包安装路径），则收集${ASCEND_CUSTOM_OPP_PATH}目录下的自定义算子配置信息（即config/*.json文件）；否则，asys工具不收集。 |
| 用户用例执行的命令信息 | - |
| 调试版本的二进制信息 | 即${ASCEND_OPP_PATH}/debug_kernel目录下的信息，但需提前配置环境变量ASCEND_OPP_PATH（用于设置算子库的安装路径）。若未配置ASCEND_OPP_PATH环境变量或该环境变量配置不正确，则默认不收集调试版本的二进制信息。 |

>**说明：**
>环境变量的详细配置说明请参见[《环境变量参考》](https://hiascend.com/document/redirect/CannCommunityEnvRef)。

## 使用约束

1. 不支持在Ascend RC形态下使用。
2. 相同用户、相同时间段内，同机器同时作业时，收集到的数据会有交叉。
3. 非root用户，获取到的数据范围会受限，具体限制参考上表中的权限要求。
4. 集群、容器、虚拟机、云场景不支持一键式工具收集故障信息。
5. asys工具涉及大量维测信息的收集，因此涉及内存占用，不建议多进程并行执行，否则可能导致asys工具执行出错或环境异常。
6. asys工具会检索trace日志所在的目录，若trace日志文件过多，可能会导致asys工具执行时间长。

    trace日志默认存放路径为$HOME/ascend/atrace/，关于trace日志的详细介绍请参见[《日志参考》](https://hiascend.com/document/redirect/CannCommunitylogref)中的“查看trace日志”。
