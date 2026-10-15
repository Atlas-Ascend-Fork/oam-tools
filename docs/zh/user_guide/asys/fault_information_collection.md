# 故障信息收集

## 功能说明

不复跑业务，仅收集故障信息，例如软硬件信息、日志等。

## 命令格式

```bash
asys collect --task_dir=path1 --tar="True" --output=path2
```

## 参数说明

- **task\_dir**：可选参数，用于指定收集算子编译文件（包括.o、.json等文件）和dump文件（包括GE dump图、TF Adapter dump图、exception dump等文件）的目录。如果没有指定task\_dir参数或从task\_dir参数指定的目录下没有收集到，则asys工具会从环境上自动收集。

    自动收集会受环境变量影响，因此执行asys命令收集时，环境变量值需与业务运行时的值保持一致，否则可能收集到的信息不准确。涉及的环境变量如下：ASCEND\_PROCESS\_LOG\_PATH、NPU\_COLLECT\_PATH、DUMP\_GRAPH\_PATH、ASCEND\_WORK\_PATH、ASCEND\_CACHE\_PATH、ASCEND\_CUSTOM\_OPP\_PATH，各环境变量的详细说明及约束，请参见[《环境变量参考》](https://hiascend.com/document/redirect/CannCommunityEnvRef)。

- **tar：**可选参数，是否将asys工具的结果输出目录压缩为\*.tar.gz文件，默认不压缩，该参数值为T或True时，压缩为\*.tar.gz文件且不保留原目录；参数值为F或False时，不压缩为\*.tar.gz文件。参数值不区分大小写。
- **output**：可选参数，其值作为asys工具的结果输出目录的路径前缀，即最终输出目录为\{output\}/asys\_output\_timestamp。命令行中不带output参数时，输出结果存放在命令行执行目录下；若output指定值为空、无效字符串、或指定路径目录无写权限、或创建目录失败，则asys工具退出执行并报错。

## 使用示例和输出说明

```bash
asys collect --task_dir=$HOME/cache_path --tar="True" --output=$HOME/dfx_info
```

执行完命令后，在\{output\}/asys\_output\_timestamp路径下的故障信息文件目录如下所示：

```bash
├── asys_output_timestamp         
   ├── software_info.txt            // 安装包版本、环境变量、依赖软件、系统信息
   ├── hardware_info.txt            // 收集了host和device侧硬件信息，host信息包括内核版本信息、CPU型号、内存和硬盘使用情况等， device信息包括设备个数、aicpu个数等
   ├── status_info.txt              // 收集device的信息，包含芯片型号、CPU和AI Core利用率等
   ├── health_result.txt            // 收集device健康信息，包括故障码和故障信息
   └── dfx              
       ├── bbox                     // Device侧的黑匣子信息       
       ├── data-dump                // L0发生AI Core Error时，生成L0 exception dump文件
       ├── graph                    // dump图信息，包含GE与TF Adapter的dump图，L0 exception dump不收集该信息
       ├── ops                      // 算子编译信息，包括算子编译*.o和*.json文件、自定义算子配置信息等                    
       ├── stackcore                // 报错触发coredump时的core文件信息
       ├── atrace                   // trace落盘信息，包括trace二进制文件解析的明文文件
       └── log          
           ├── device       
           │     ├──dev-os-{id}
           │           ├── firmware      // 固件生成的日志
           │           ├── slogd         // 日志相关进程的维测日志
           │           ├── application   // 业务进程产生的非EVENT级别应用日志
           │           └── system        // 常驻进程生成的日志
           └── host     
                ├── message         // message/syslog日志
                ├── install         // 包历史安装情况的日志
                ├── cann            // 应用类日志
                └── driver          // Host侧驱动日志
```

**其中，用户可根据需求自行定义software\_info.txt文件中收集的第三方依赖软件的版本信息**。在asys工具目录下的“ascend\_system\_advisor/conf/dependent\_package.csv”文件中，增加或删除配置项，每行对应一个配置项，逗号分割依赖项名字和查询指令，逗号后无空格。示例片段如下：

```bash
make,make --version
cmake,cmake --version
unzip,unzip -v
zlib1g,dpkg -l zlib1g| grep zlib1g| grep ii
zlib1g-dev,dpkg -l zlib1g-dev| grep zlib1g-dev| grep ii
libsqlite3-dev,dpkg -l libsqlite3-dev| grep libsqlite3-dev| grep ii
openssl,dpkg -l openssl| grep openssl| grep ii
libssl-dev,dpkg -l libssl-dev| grep libssl-dev| grep ii
libffi-dev,dpkg -l libffi-dev| grep libffi-dev| grep ii
```
