# 分析AI Core Error问题

## 功能说明

分析AI Core Error问题的故障信息，辅助定位AI Core Error问题。

执行业务时，若日志文件或屏幕打印信息中包含如下AI Core Error报错，此时，需要先获取AI Core Error问题相关的故障信息，再配合使用msaicerr分析AI Core Error问题的故障信息，辅助定位AI Core Error问题。

```bash
# 报错示例
there is an xx aicore error

# 或报错示例
there is an xx aivec error
```

## 注意事项

在收集到的故障信息中，请提前检查dfx/data-dump目录下是否存在dump文件、是否存在异常算子编译信息（算子编译\*.o和\*.json文件），检查dfx/log/host/cann目录下是否存在日志文件，若不存在，则无法使用msaicerr工具提取AI Core Error信息。

## 命令格式

```bash
python3 msaicerr.py -p path1 -out path2 -dev 0
```

## 参数说明

- **-p或--report\_path**：必选参数，分析AI Core Error问题时用于指定AI Core Error故障信息所在的目录。不能进入-p参数指定的目录或子目录下执行msaicerr工具，否则，会出现工具解析卡住或失败的情况。
- **-out或--output\_path**：可选参数，指定解析结果文件的存放路径，如果不指定，则解析结果默认存放在执行命令的当前路径下。-out参数指定的目录不能为-p参数指定的目录或子目录，否则，会出现工具解析卡住或失败的情况。若-out参数指定值为空或无效字符串、或指定目录无写权限、或创建目录失败，则msaicerr工具退出并报错。
- **-dev或--device\_id**：可选参数，指定运行内置算子样例的Device ID，不设置该参数时，默认Device ID为0。在分析AI Core Error问题时，msaicerr工具会运行一个内置算子样例，用于检查软硬件环境是否正常。

## 使用示例和输出说明

```bash
python3 msaicerr.py -p $HOME/aic_err_info -out $HOME/result
```

执行命令后，用户根据终端界面提示的info.txt文件所在的路径，通过info.txt文件中的提示信息进行问题分析和定位。若故障信息中存在多个AI Core Error问题，则msaicerr工具按日志时间解析第一次出现的AI Core Error问题。

在执行msaicerr.py工具后，在执行msaicerr.py工具的同级目录下，会生成“debug\_info.txt”或“info\_\{时间戳\}/debug\_info.txt”文件，用于记录工具执行过程中的日志信息。
