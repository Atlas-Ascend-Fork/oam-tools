# AI Core Error故障信息解析

## 功能说明

执行业务时，若日志文件或屏幕打印信息中包含AI Core Error报错（例如“there is an aivec error exception”或“there is an aicore error exception”），可使用AI Core Error故障信息解析功能，快速定位AI Core Error问题的原因，提高排查效率。

## 注意事项

1. 为保证解析数据的准确性，在复现AI Core Error问题前，建议先清理业务运行日志和plog日志。
2. 避免循环拷贝，--output目录不能为--path目录或者其子目录。

## 命令格式

```bash
# 以下命令中aic_err_info_timestamp为存放AI Core Error问题信息的目录，请根据实际情况替换
asys analyze -r=aicore_error -d=deviceId --path=${HOME}/aic_err_info_timestamp
```

## 参数说明

- **r**：必选参数，解析模式，此处设置为aicore\_error。
- **d**：可选参数，指定待操作的deviceId，不设置该参数，默认解析device 0的故障信息。
- **path**：可选参数，存放日志和dump文件等故障信息的目录。

    如果不配置该参数，asys工具会自动收集这些故障信息。自动收集会受环境变量影响，因此执行asys命令时，环境变量值需与业务运行时的值保持一致，否则可能收集到的信息不准确。涉及的环境变量如下：ASCEND\_PROCESS\_LOG\_PATH、NPU\_COLLECT\_PATH、DUMP\_GRAPH\_PATH、ASCEND\_WORK\_PATH、ASCEND\_CACHE\_PATH、ASCEND\_CUSTOM\_OPP\_PATH，各环境变量的详细说明及约束，请参见[《环境变量参考》](https://hiascend.com/document/redirect/CannCommunityEnvRef)。如果这些环境变量都不存在，会从执行asys命令的当前目录下收集故障信息。

- **output**：可选参数，其值作为asys工具的结果输出目录。命令行中不带output参数时，输出结果存放在命令行执行目录下；若output指定值为空、无效字符串、或指定路径目录无写权限、或创建目录失败，则asys工具退出执行并报错。

## 使用示例和输出说明

```bash
# 以下命令中aic_err_info_timestamp为存放AI Core Error问题信息的目录，请根据实际情况替换
asys analyze -r=aicore_error --path=${HOME}/aic_err_info_timestamp
```

执行命令后，用户根据终端界面提示的info.txt文件所在的路径，通过info.txt文件中的提示信息进行问题分析和定位。若收集的信息中存在多个AI Core Error问题，则本工具按日志时间解析第一次出现的AI Core Error问题。
