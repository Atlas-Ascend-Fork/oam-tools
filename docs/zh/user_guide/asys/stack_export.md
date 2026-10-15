# 实时堆栈导出

## 功能说明

该功能适用于训练、推理业务进程卡住场景，以便导出堆栈信息定位问题。在业务未卡死时，执行实时堆栈导出，可能有：信号发送失败、bin文件生成超时、bin文件解析失败等异常，无法正常导出堆栈信息。另外，不支持对同一个卡住进程并行导出堆栈信息，否则可能执行命令失败。

## 注意事项

导出实时堆栈信息时，asys工具会检索trace日志所在的目录，若trace日志文件过多，可能会导致asys工具执行时间长，因此建议先清理trace日志（trace日志默认存放路径为$HOME/ascend/atrace/），再执行asys工具导出实时堆栈信息。关于trace日志的详细介绍请参见[《日志参考》](https://hiascend.com/document/redirect/CannCommunitylogref)中的“查看trace日志”。

## 命令格式

```bash
asys collect -r=stacktrace --remote=pid --all --quiet --timeout=num --output=path
```

## 参数说明

- **r**：必选参数，此处设置为stacktrace，用于实时导出堆栈信息，供后续定位使用。若不设置本参数，则表示执行故障信息收集功能，但此时不能与--remote、--all、--quiet参数混用。

    命令执行成功后，根据终端屏幕提示获取导出的文件。

- **remote**：指定卡住进程的进程ID，在-r=stacktrace时必选。ID取值要求大于或等于2，若此处传入的进程ID不存在，asys命令报错退出。
- **all**：设置该参数表示导出卡住进程中所有线程的堆栈信息，在-r=stacktrace时必选。
- **quiet**：可选参数，导出堆栈信息过程中，设置该参数关闭与用户交互的开关，不设置该参数则默认开启交互，需用户确认当前服务器上是否打开trace处理的信号集（ASCEND\_COREDUMP\_SIGNAL环境变量未设置或设置为非none的值时，表示信号集已打开）。在-r=stacktrace时可选择使用本参数。

    由于导出实时堆栈信息时，需要向指定进程发送信号35，如果关闭trace处理的信号集，则会终止卡住进程，无法导出堆栈信息。

    关于ASCEND\_COREDUMP\_SIGNAL环境变量及trace处理的信号集的详细说明请参见[《环境变量参考》](https://hiascend.com/document/redirect/CannCommunityEnvRef)。

- **timeout**：可选参数，指定导出实时堆栈的超时时间，取值范围：\[1, 60\]，单位秒。不设置该参数，默认10秒。

    **output**：可选参数，其值作为asys工具的结果输出目录的路径前缀，即最终输出目录为\{output\}/asys\_output\_timestamp。命令行中不带output参数时，输出结果存放在命令行执行目录下；若output指定值为空、无效字符串、或指定路径目录无写权限、或创建目录失败，则asys工具退出执行并报错。

## 使用示例和输出说明

```bash
asys collect -r=stacktrace --remote=892839 --all --quiet --timeout=10 --output=./
```

输出示例如下：

```bash
2026-06-26 03:12:35,573 [ASYS] [INFO]: asys start.
2026-06-26 03:12:35,615 [ASYS] [WARNING]: This command sends signal 35 to the process:892839. If the process is executed to disable signal receiving through the environment variable ASCEND_COREDUMP_SIGNAL=none, the process:892839 will be killed.
2026-06-26 03:12:35,615 [ASYS] [INFO]: bin file generate path is /root/ascend/atrace, get from default path.
2026-06-26 03:12:36,236 [ASYS] [INFO]: bin file generated, awaiting stack trace completion.
2026-06-26 03:12:36,988 [ASYS] [INFO]: start parse bin file
2026-06-26 03:12:36,997 [ASYS] [INFO]: stackcore file path: /root/ascend/atrace/trace_892633_892633_20260626030851615735/stackcore_event_892839_20260626031235677855/stackcore_tracer_35_892839_aoe_20260626031235677902.txt
2026-06-26 03:12:36,998 [ASYS] [INFO]: Stacktrace output directory: /root/asys_output_20260626031235573
2026-06-26 03:12:36,998 [ASYS] [INFO]: collect task execute finish.
2026-06-26 03:12:36,998 [ASYS] [INFO]: asys finish.
```
