# 解析Dump文件

## 功能说明

将Dump文件解析成.bin或.npy文件，文件中记录算子的输入、输出、workspace等信息。

## 命令格式

```bash
python3 msaicerr.py -d path1 -out path2 
```

## 参数说明

- **-d或--data**：必选参数，解析Dump文件时用于指定Dump文件路径，包含文件名。
- **-out或--output\_path**：可选参数，指定解析结果文件的存放路径，如果不指定，则解析结果默认跟Dump文件存放在同一路径下。

## 使用示例和输出说明

```bash
python3 msaicerr.py -d /demo/extra-info/data-dump/0/exception_info.2.1.20250611171538370
```

输出示例如下：

```bash
[INFO] The dump file directory will be used to as the output directory of the parsed results.
[INFO] Parse dump file finished, result path is: /demo/dfx/data-dump/0
```

根据提示，获取解析结果文件。

在执行msaicerr.py工具后，在执行msaicerr.py工具的同级目录下，会生成debug\_info.txt文件，用于记录工具执行过程中的日志信息。若debug\_info.txt中提示Can not read with dtype  _xxx_，则表示存在工具不能识别的数据类型，需由用户自行安装第三方库文件，例如，若提示Can not read with dtype bfloat16，则需安装bfloat16ext库。
