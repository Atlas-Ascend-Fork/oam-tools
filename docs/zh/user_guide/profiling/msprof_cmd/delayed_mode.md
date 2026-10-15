# 延迟采集性能数据

## 功能说明

用户可以通过设置`--delay`和`--duration`参数来配置数据采集的延迟时间和持续时间。延迟采集场景下不支持[动态采集性能数据](dynamically.md)。

## 命令示例

以运行用户登录工具所在环境，执行以下命令采集性能数据。命令示例如下：

```sh
msprof [options] <app>
```

仅当采集AI任务运行性能数据时支持启用延迟采集能力，必须传入用户程序，与`--dynamic`参数不能同时配置。app参数说明请参见[app参数说明](general_collect_commands.md#app参数说明)，options参数说明请参见表1，同时可叠加[采集AI任务运行性能数据](ai_runtime_profile_data.md)中的参数。

## 参数说明

**表1**  options参数说明

|参数|**可选/必选**|描述|
|--|--|--|
|--delay|可选|按设定时间延迟采集性能数据，范围[1, 4294967295]，单位s，默认值0。若配置的时间超过了AI任务的执行时间，在AI任务执行期间不会启动采集。|
|--duration|可选|性能数据采集的持续时间，范围[1, 4294967295]，单位s，默认未配置，即随采集开始持续到任务结束，自动停止采集。若配置了`--delay`参数，则duration从delay结束的时刻开始计时。|

## 使用示例

```sh
msprof --delay=3 --duration=3 /home/projects/MyApp/out/main
```
