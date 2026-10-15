# 健康检查

## 功能说明

检查所有Device或指定Device的健康状态（若不健康，会展示报错信息）。

## 命令格式

```bash
asys health -d=deviceId
```

## 参数说明

**d**：可选参数，指定需要显示健康状态的deviceId。不指定device时，显示所有device的健康状态；指定device时，若device有异常，则在终端屏幕上显示故障码和故障信息，仅显示前5组故障，在[故障信息收集](fault_information_collection.md)和[业务复跑+故障信息收集](rerun_fault_information_collection.md)时会将所有故障码和故障信息写入health\_result.txt文件。

## 使用示例和输出说明

- 不指定device，所有device都正常，此处以双卡为例：

    ```bash
    asys health
     +------------------------+------------------------------+
     | Group of 2 Device      | Overall Health: Healthy      |
     +========================+==============================+
     | Device ID: 0           | Healthy                      |
     +------------------------+------------------------------+
     | Device ID: 1           | Healthy                      |
     +------------------------+------------------------------+
    ```

- 指定device，device正常，此处以device 0为例：

    ```bash
    asys health -d=0
     +-------------------+------------------------------+
     | Device ID: 0      | Overall Health: Healthy      |
     |                   | ErrorCode Num: 0             |
     +===================+==============================+
    ```

- 指定device，device异常，此处以device 0为例：

    ```bash
    asys health -d=0
     +-------------------+------------------------------+
     | Device ID: 0      | Overall Health: Warning      |
     |                   | ErrorCode Num: 1             |
     +===================+==============================+
     | 0xa419321c‬        | lp pmbus error               |
     +-------------------+------------------------------+
    ```

    您可以单击《[黑匣子异常错误码信息列表](https://support.huawei.com/enterprise/zh/ascend-computing/ascend-hdk-pid-252764743?category=troubleshooting&subcategory=fault-handling)》和《[健康管理故障定义](https://support.huawei.com/enterprise/zh/ascend-computing/ascend-hdk-pid-252764743)》获取对应版本的手册，查阅故障码的详细描述，其中故障级别与**asys health**命令返回的健康状态对应关系为：提示-Healthy（没有问题、正常状态也会显示Healthy），次要-Warning，重要-Alarm，紧急-Critical，未知-Unknown。
