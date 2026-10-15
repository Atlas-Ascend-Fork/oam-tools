# 环境配置

## 功能说明

获取或恢复指定配置。

## 注意事项

环境配置相关命令必须在物理机且root用户下执行。

<!-- npu="910,310p,310b" id1 -->
对于Atlas 200I/500 A2推理产品、Atlas推理系列产品、Atlas训练系列产品，不支持使用环境配置功能。
<!-- end id1 -->

## 命令格式

```bash
# 查询压测相关配置
asys config -d=deviceId --get --stress_detect

# 恢复压测相关配置
asys config -d=deviceId --restore --stress_detect
```

## 参数说明

- **d**：可选参数，指定待操作的deviceId，不设置该参数，默认获取或恢复device 0的配置。
- **get**：获取指定配置。
- **restore**：恢复指定配置。
- **stress\_detect**：表示压测相关配置。get和stress\_detect配合使用，用于获取压测相关配置；restore和stress\_detect配合使用，用于恢复压测相关配置。

## 使用示例和输出说明

各产品型号的输出信息有所不同，请以实际输出信息为准。

```bash
# 获取压测配置
asys config -d=0 --get --stress_detect
+--------------------------------+---------------------------------+
| Device ID: 0                   | CURRENT CONFIGURATION           |
+================================+=================================+
| AI Core Voltage (MV)           | 850                             |
| Bus Voltage (MV)               | 850                             |
+--------------------------------+---------------------------------+

# 恢复压测配置
asys config -d=0 --restore --stress_detect
[ASYS] [INFO]: Configuration successfully restore, on device 0.
```
