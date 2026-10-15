# 检查环境

## 功能说明

运行内置算子样例检查软硬件环境。

## 命令格式

```bash
python3 msaicerr.py -e -dev 0
```

## 参数说明

- **-e或--env**：必选参数，表示检查环境。
- **-dev或--device\_id**：可选参数，指定运行内置算子样例的Device ID，不设置该参数，默认Device ID为0。msaicerr工具会运行一个内置算子样例，用于检查软硬件环境是否正常。

## 使用示例和输出说明

```bash
python3 msaicerr.py -e
```

输出示例如下：

```bash
[INFO] Total device count: 1
[INFO] Valid device_id 0
[INFO] Get soc_version: xxxxxxx
[INFO] Start to test env with golden op.
[INFO] The build-in sample operator runs successfully, The environment is normal.
```

在执行msaicerr.py工具后，在执行msaicerr.py工具的同级目录下，会生成debug\_info.txt文件，用于记录工具执行过程中的日志信息。
