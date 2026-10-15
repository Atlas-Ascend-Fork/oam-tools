# msprof采集通用命令

## 功能说明

msprof命令行工具提供了**AI任务运行性能数据**、**AI处理器系统数据**等性能数据的采集和解析能力。

其中，msprof采集通用命令是性能数据采集的基础，用于提供性能数据采集时的基本信息，包括参数说明、AI任务文件、数据存放路径、自定义环境变量等。

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
## 命令格式

登录运行环境，可在任意目录下执行以下命令。

- 方式一（推荐）：在msprof命令末尾，直接传入用户程序或执行脚本。

    ```sh
    msprof [options] <app>
    ```

- 方式二：通过--application参数传入用户程序或执行脚本。

    ```sh
    msprof [options] --application=<app>
    ```

在下文举例时，为避免信息冗余，均采用推荐方式进行示例。
<!-- end id1 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/general_collect_commands_res.md#id00001 -->

## app参数说明

支持传入用户执行程序及相关参数，例如：

- 方式一配置示例：
  - 在msprof传入二进制执行程序和程序参数：

    ```sh
    msprof --output=/home/projects/output /home/projects/main parameter1 parameter2
    ```

  - msprof传入执行脚本和脚本参数：

    ```sh
    msprof --output=/home/projects/output /home/projects/run.sh parameter1 parameter2
    ```

- 方式二配置示例：
  - 使用msprof的--application参数传入二进制执行程序和程序参数：

    ```sh
    msprof  --application="/home/projects/main parameter1 parameter2 ..."
    ```

  - 使用msprof的--application参数传入执行脚本和脚本参数：

    训练场景：

    ```sh
    msprof  --application="/home/projects/run.sh parameter1 parameter2 ..."
    ```

> [!NOTE]说明
>
>- 若parameter中存在异常符号时将无法识别参数，因此推荐使用方式一传入用户程序。使用方式一时，若配置的用户程序命令中，存在配置参数值需要加引号的情况，请将命令写入Shell脚本后，通过执行Shell脚本的方式在msprof命令上添加用户程序命令。
>- 不建议配置其他用户目录或其他用户可写目录下的AI任务，避免提权风险；不建议配置删除文件或目录、修改密码、提权命令等有安全风险的高危操作；应避免使用pmupload作为程序名称。
>- 采集全部性能数据、采集AI任务运行时性能数据或采集msproftx数据时，本参数必选。采集AI处理器系统数据时，本参数可选。采集Host侧系统数据时，本参数可选。

## options参数说明

- --output=<path\>：可选，收集到的性能数据的存放路径。

    该参数优先级高于ASCEND\_WORK\_PATH，具体请参见[《环境变量参考》](https://hiascend.com/document/redirect/CannCommunityEnvRef)。

    路径中不能包含特殊字符：

    ```sh
    "\n", "\\n", "\f", "\\f", "\r", "\\r", "\b", "\\b", "\t", "\\t", "\v", "\\v", "\u007F", "\\u007F", "\"", "\\\"", "'", "\'", "\\", "\\\\", "%", "\\%", ">", "\\>", "<", "\\<", "|", "\\|", "&", "\\&", "$", "\\$", ";", "\\;", "`", "\\`"
    ```

    在msprof命令末尾添加AI任务执行命令来传入用户程序或执行脚本时，默认落盘在当前目录。

    配置--application参数添加AI任务执行命令来传入用户程序或执行脚本时，默认落盘在AI任务文件所在目录。

<!-- npu="950,A3,910b,910,310p,310b" id2 -->
- --type=<type\>：可选，设置性能数据解析结果文件格式，即可以选择msprof命令行执行采集后自动解析的结果文件格式，取值为：
  - text：表示解析为.json、.csv格式的文件和.db格式文件（msprof\_时间戳.db）。默认为text。
  - db：仅解析为一个汇总所有性能数据的.db格式文件（msprof\_时间戳.db），使用MindStudio Insight工具展示。
    <!-- end id2 -->

- --environment=<env\>：可选，执行采集时运行环境上需要的自定义环境变量。

    不建议使用其他用户的目录覆盖原有环境变量，避免提权风险。

    配置格式为`--environment="${envKey}=${envValue}"`或`--environment="${envKey1}=${envValue1};${envKey2}=${envValue2}"`。

- --storage-limit=<limit-value\>：可选，指定落盘目录允许存放的最大文件容量。当性能数据文件在磁盘中即将占满本参数设置的最大存储空间或剩余磁盘总空间即将被占满时（总空间剩余<=20MB），则将磁盘内最早的文件进行老化删除处理。

    范围\[200, 4294967295\]，单位为MB，例如`--storage-limit=200MB`，默认未配置本参数。

    未配置本参数时，采集前，如果磁盘可用空间小于20MB时，则不落盘数据。

- --help：可选，帮助提示参数。

<!-- npu="950,A3,910b,910,310p,310b" id3 -->
## 使用示例

登录运行环境，在任意路径下执行以下命令：

```sh
msprof --output=/home/projects/output /home/projects/MyApp/out/main
```

msprof命令执行完成后，会自动解析并导出性能数据结果文件，详细内容请参见[性能数据文件参考](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/profile_data_file_references.md)。
<!-- end id3 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/general_collect_commands_res.md#id00002 -->
