# 综合检测

## 功能说明

包括压力检测、HBM硬件检测、CPU检测、AI Core STL硬件检测等功能。

## 注意事项

综合检测相关命令必须在物理机且root用户下执行。

<!-- npu="910,310p,310b" id1 -->
对于Atlas 200I/500 A2推理产品、Atlas推理系列产品、Atlas训练系列产品，不支持使用综合检测功能。
<!-- end id1 -->

## 命令格式

```bash
# AI Core压力检测，可能需要时间较长
asys diagnose -r=stress_detect -d=deviceId --output=path

# HBM检测
asys diagnose -r=hbm_detect -d=deviceId --timeout=num --output=path

# CPU检测
asys diagnose -r=cpu_detect -d=deviceId --timeout=num --output=path

# AI Core STL硬件检测
asys diagnose -r=aicore_stl_detect -d=deviceId --output=path
```

## 参数说明

- **r**：必选参数，检测模式，取值如下：
    - **stress\_detect：AI Core压力检测**

        该功能涉及执行算子，因此环境中需提前安装算子二进制包（包名为Ascend-cann-\*-ops-\*.run）。

        AI Core压力检测涉及到对device侧部分电压调整，当压力检测正常结束时，可自行恢复；但部分压力检测异常退出时，可能存在电压不能自行恢复的情况，这时用户可以根据asys环境配置功能手动恢复电压。建议在执行AI Core压力检测前、后，用户可以分别获取电压，用于判断电压是否异常、以及是否需要恢复电压。获取及恢复电压请参见[环境配置](environment_configuration.md)。

        显示检测结果时：

        - 不指定device但device只有一个时，仅显示这个device的状态。
        - 显示所有device的检测结果时，若所有device的检测结果状态一致，直接显示汇总标签（如 Pass - All 或 Warn - All）。
        - 若存在device状态不一致的情况，则依次列出每个device的具体状态，例如在4个device场景下显示为 Pass, Warn, Warn, Warn。
        - **若检测结果为Warn**，表示检测失败，可查看Host侧plog日志（默认路径为$HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log），根据关键字“\[ERROR\] AML”查看日志信息，并根据其中的错误码定位并排除问题：**1**开头的错误码表示用例执行失败、任务下发失败等；**2**开头的错误码表示精度比对失败；**3**开头的错误码表示硬件问题。
        - **若检测结果为Pass**，表示检测成功。

    - **hbm\_detect：HBM检测**

        显示检测结果时：

        - 不指定device但device只有一个时，仅显示这个device的状态。
        - 显示所有device的检测结果时，若所有device的检测结果状态一致，直接显示汇总标签（如 Pass - All 或 Warn - All）。
        - 若存在device状态不一致的情况，则依次列出每个device的具体状态，例如在4个device场景下显示为 Pass, Warn, Warn, Warn。
        - **若检测结果为Warn**，表示检测失败，可查看Host侧plog日志（默认路径为$HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log），根据关键字“\[ERROR\] AML”查看日志信息，并根据其中的错误码定位并排除问题：**1**开头的错误码表示用例执行失败、任务下发失败等；**4**开头的错误码表示硬件问题。
        - **若检测结果为Pass**，表示检测成功。针对hbm检测，若返回的数值\>0，该数值表示检测后新增ECC错误的个数，用于提前激发风险地址报错并隔离，保证后续业务正常运行。

    - **cpu\_detect：CPU检测**

        显示检测结果时：

        - 不指定device但device只有一个时，仅显示这个device的状态。
        - 显示所有device的检测结果时，若所有device的检测结果状态一致，直接显示汇总标签（如 Pass - All、Warn - All 或 Fail - All）。
        - 若存在device状态不一致的情况，则依次列出每个device的具体状态，例如在4个device场景下显示为 Pass, Warn, Warn, Fail。
        - **若检测结果为Fail**，表示检测出硬件故障，需联系技术支持。
        - **若检测结果为Warn**，表示检测过程中任务调度出现问题。可查看Host侧plog日志（默认路径为$HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log）中的详细信息定位问题，可先根据关键字“\[ERROR\] AML”筛选日志信息。
        - **若检测结果为Pass**，表示检测成功。

    - **aicore\_stl\_detect：AI Core STL硬件检测**

        <!-- npu="950" id2 -->
        仅支持在Ascend 950PR&950DT系列产品上运行。
        <!-- end id2 -->
        显示检测结果时：

        - 不指定device但device只有一个时，仅显示这个device的状态。
        - 显示所有device的检测结果时，若所有device的检测结果状态一致，直接显示汇总标签（如 Pass - All、Warn - All 或 Fail - All）。
        - 若存在device状态不一致的情况，则依次列出每个device的具体状态，例如在4个device场景下显示为 Pass, Warn, Warn, Fail。
        - **若检测结果为Fail**，表示检测出硬件故障，需联系技术支持。
        - **若检测结果为Warn**，表示检测过程中任务调度出现问题，可能是硬件故障或软件问题。可查看Host侧plog日志（默认路径为$HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log）中的详细信息定位问题，可先根据关键字“\[ERROR\] AML”筛选日志信息。
        - **若检测结果为Pass**，表示检测成功。

- **d**：可选参数，指定待检测的deviceId，不设置该参数，默认显示所有device的检测结果。
- **timeout**：可选参数，指定硬件检测时间，单位秒。不传默认检测600秒。仅HBM检测、CPU检测时生效，HBM检测时取值范围：\[0, 604800\]，设置为0时表示仅执行一轮HBM检测；CPU检测时取值范围：\[1, 604800\]。
- **output**：可选参数，其值作为检测结果文件diagnose\_result\_\{time\_stamp\}.txt的保存目录。命令行中不带output参数时，输出结果不落盘仅在终端屏幕显示；若output指定值为空、无效字符串、或指定路径目录无写权限、或创建目录失败，则asys工具退出执行并报错。

## 使用示例和输出说明

- 不指定device，所有device正常，此处以四卡为例：

    ```bash
    asys diagnose -r=stress_detect
     +------------------------+ -----------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Performance --------+ -----------------------+
     | Stress Detect          | Pass - All             |
     +------------------------+ -----------------------+
    asys diagnose -r=hbm_detect --timeout=3000
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | HBM Detect             | Pass - All             |
     |                        | (0, 9, 0, 0)           |
     +------------------------+------------------------+
    asys diagnose -r=cpu_detect --timeout=3000
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | CPU Detect             | Pass - All             |
     +------------------------+------------------------+
    asys diagnose -r=aicore_stl_detect
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+------------------------+
     | AICore STL Detect      | Pass - All             |
     +------------------------+------------------------+
    ```

- 不指定device，部分device正常，此处以四卡为例：

    ```bash
    asys diagnose -r=stress_detect
     +------------------------+ -----------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Performance --------+ -----------------------+
     | Stress Detect          | Pass, Warn, Pass, Warn |
     +------------------------+ -----------------------+
    asys diagnose -r=hbm_detect
     +------------------------+ -----------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+ -----------------------+
     | HBM Detect             | Pass, Warn, Pass, Warn |
     |                        | (9, 0, 5, 0)           |
     +------------------------+ -----------------------+
    asys diagnose -r=cpu_detect
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | CPU Detect             | Pass, Warn, Pass, Fail |
     +------------------------+------------------------+
    asys diagnose -r=aicore_stl_detect
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+------------------------+
     | AICore STL Detect      | Pass, Warn, Pass, Fail |
     +------------------------+------------------------+
    ```

- 指定device，此处以device 0为例：

    ```bash
    asys diagnose -d=0 -r=stress_detect
     +--------------------+------------------------+
     | Device ID: 0       | Diagnostic Result      |
     +====================+========================+
     +--- Performance ----+------------------------+
     | Stress Detect      | Pass                   |
     +--------------------+------------------------+
    asys diagnose -d=0 -r=hbm_detect
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | HBM Detect             | Pass(9)                |
     +------------------------+------------------------+
    asys diagnose -d=0 -r=cpu_detect
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | CPU Detect             | Pass                   |
     +------------------------+------------------------+
    asys diagnose -r=aicore_stl_detect
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+------------------------+
     | AICore STL Detect      | Pass                   |
     +------------------------+------------------------+
    ```
