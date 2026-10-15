# UB文件解析

## 功能说明

解析UB维测信息文件。

若需获取UB（Unified Bus）文件，请参见[《msnpureport工具》](https://support.huawei.com/enterprise/zh/ascend-computing/ascend-hdk-pid-252764743?category=reference-guides&subcategory=command-reference)中的“导出Device侧系统类日志和其他维测信息 \> 单次导出Device侧系统类日志和其他维测信息”章节导出UB文件。

## 命令格式

```bash
asys analyze -r=ub --path=directory --output=path
```

## 参数说明

- **r**：必选参数，解析模式，此处设置为ub，用于解析二进制格式的UB维测信息采集文件，供后续定位使用。
- **path**：指定目录，用于解析指定目录下的二进制文件，ub模式下必选。asys会读取path路径下的以下二进制文件并解析为同名的txt文件。
    - ubnl\_dfx\_config\_item.bin：UB网络层配置表项
    - ubnl\_dfx\_statistic.bin：UB网络层统计信息
    - ubnl\_dfx\_ssu\_schedule.bin：UB网络层SSU（System Scheduling Unit）调度队列统计和队列丢包统计
    - ubmem\_daw.bin：UB memory各配置表项
    - ubtpl\_acl\_src.bin：UB Transport层关键表项和配置
    - sl\_to\_vl.bin：UB QOS（Quality of Service）配置&表项

- **output**：可选参数，其值作为asys工具的结果输出目录的路径前缀，即最终输出目录为\{output\}/asys\_output\_timestamp。命令行中不带output参数时，输出结果存放在命令行执行目录下；若output指定值为空、无效字符串、或指定路径目录无写权限、或创建目录失败，则asys工具退出执行并报错。

## 使用示例和输出说明

```bash
asys analyze -r=ub --path=/home/test/msnpureport/device-0/ub
```

执行命令后，用户可根据终端界面提示的路径获取解析后的txt文件，示例如下：

```bash
2026-02-12 14:23:10,020 [ASYS] [INFO]: asys start.
2026-02-12 14:23:10,021 [ASYS] [INFO]: asys output directory: /home/test/asys_output_20260212142310021
2026-02-12 14:23:10,032 [ASYS] [INFO]: Conversion successful! /home/test/msnpureport/device-0/ub/ubnl_dfx_statistic.bin has been converted to text file /home/test/asys_output_20260212142310021/ubnl_dfx_statistic.txt
......
2026-02-12 14:23:10,049 [ASYS] [INFO]: analyze task execute finish.
2026-02-12 14:23:10,049 [ASYS] [INFO]: asys finish.
```
