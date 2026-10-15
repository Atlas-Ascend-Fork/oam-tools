# 组件检测

## 功能说明

组件检测，当前只支持AI Vector组件检测，不支持并行执行。

## 命令格式

```bash
asys diagnose -r=component -d=deviceId --output=path
```

## 参数说明

- **r**：必选参数，检测模式，此处设置为component，表示组件检测。

    显示检测结果时：

    - 不指定device但device只有一个时，仅显示这个device的状态。
    - 显示所有device的检测结果时，若所有device的检测结果状态一致，直接显示汇总标签（如 Pass - All 或 Fail - All）。
    - 若存在device状态不一致的情况，则依次列出每个device的具体状态，例如在4个device场景下显示为 Pass, Pass, Fail, Fail。
    - **若检测结果为Fail**，可查看debug\_info.txt日志定位问题。

- **d**：可选参数，指定待检测的deviceId。不设置该参数，默认显示所有device的检测结果。
- **output**：可选参数，其值作为检测结果文件diagnose\_result\_\{time\_stamp\}.txt的保存目录。命令行中不带output参数时，输出结果不落盘仅在终端屏幕显示；若output指定值为空、无效字符串、或指定路径目录无写权限、或创建目录失败，则asys工具退出执行并报错。

## 使用示例和输出说明

- 不指定device，所有device正常，此处以四卡为例：

    ```bash
     asys diagnose -r=component
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass - All             |
     +------------------------+------------------------+
    ```

- 不指定device，部分device正常，此处以四卡为例：

    ```bash
    asys diagnose -r=component
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass, Fail, Pass, Fail |
     +------------------------+------------------------+
    ```

- 指定device，此处以device 0为例：

    ```bash
    asys diagnose -d=0 -r=component
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass                   |
     +------------------------+------------------------+
    ```
