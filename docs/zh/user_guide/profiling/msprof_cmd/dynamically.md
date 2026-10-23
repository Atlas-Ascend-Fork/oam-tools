# 动态采集性能数据

## 功能说明

在执行采集的过程中可以随时启动和停止采集进程。动态采集性能数据支持通过launch和attach两种方式执行：

- launch方式：msprof命令行启动动态采集时，同步调起AI任务并进入性能数据采集交互模式，可以通过命令随时启动和停止采集。

  若使用msprof --application命令拉起的进程即为实际用卡的业务进程（例如msprof --application=main --dynamic=on，main即为实际业务进程程序），推荐使用该方式。

- attach方式：用户先自行启动AI任务，再启动msprof动态采集并进入性能数据采集交互模式，可以通过命令随时启动和停止采集。

  若通过launch方式使用msprof --application命令拉起的进程并非实际用卡的业务进程（例如msprof --application=run.sh --dynamic=on，run.sh在脚本内部才会拉起实际的业务进程），则推荐改用attach方式。

## 注意事项

- 在执行动态采集前建议先删除之前残留的动态Profiling文件，即先执行命令`rm -rf ~/dynamic_profiling_socket_*`。
- 在launch方式下，传入的用户程序中，不能设置环境变量“PROFILING\_MODE”和“PROFILING\_OPTIONS”。
- 在attach方式下，需先设置环境变量“PROFILING\_MODE”为dynamic，然后启动AI任务，最后执行命令行操作。

  ```sh
  export PROFILING_MODE=dynamic
  ```

- 在同一AI任务中，同一时间仅允许一个用户进入交互模式。
- 进入交互模式后，若未启动数据采集，30分钟后将自动退出，执行命令可重新进入交互模式。
- 多卡（含集群）场景下，推荐使用attach方式进行动态性能数据采集。
- 本功能不支持与[延迟采集性能数据](delayed_mode.md)（--delay和--duration参数）同时配置。
- 如果用户进程被设置为后台执行，将导致launch方式失效从而无法进入交互界面，此时建议使用attach方式动态采集性能数据。
- 如果在容器中启动业务进程，则也需要在容器中执行msprof采集命令。

## 命令格式

- launch方式：

  ```sh
  msprof --dynamic=on [options] <app>
  --application=<app>
    ```

- attach方式：

  ```sh
  msprof --dynamic=on --pid=<pid> [options]
  ```

launch方式必须传入用户程序，app参数说明请参见[app参数说明](general_collect_commands.md#app参数说明)，options参数说明请参见表1，同时可叠加其他采集项，例如[采集AI任务运行性能数据](ai_runtime_profile_data.md)或[采集AI处理器系统数据](processorai_accelerator_system_data.md)中的参数。

## 参数说明

**表1**  options参数说明

|参数|**可选/必选**|描述|
|--|--|--|
|--dynamic|必选|控制动态采集性能数据的开关，可选on或off，默认值为off。|
|--pid|attach方式必选；launch方式该参数不选|指定需要采集的应用程序的PID。可同时配置一个或多个PID，配置示例：--pid=1,2,3。获取PID的方法可参考获取AI任务PID，也可执行如下命令获取当前环境可以采集的所有PID：<br> `ls ~/dynamic_profiling_socket_* 2>/dev/null \| awk -F '_' '{print $4}' \| paste -sd ',' -`|
|--output|可选|指定性能数据的存放路径。默认未配置该参数，表示将性能数据保存在当前路径。路径中不能包含特殊字符。|
|start|可选|启动采集。<br>- start 、stop命令执行次数上限为100，两条命令执行次数总和超过100次后，服务端将终止连接，即最多采集50份性能数据。重新连接服务端时，重新计算次数。<br>- 反复执行start 、stop命令时，可能因stop结束Profiling流程而终止了CANN组件的数据上报，因此打印ERROR日志，为正常现象。|
|stop|可选|停止采集。每完成一次start和stop命令，在`--output`参数指定路径下生成一个存放数据文件的PROF*_*XXX目录。|
|quit|可选|停止采集并退出交互模式。quit之后AI任务正常运行，再次执行msprof动态Profiling命令，可再次进入交互模式并开启动态Profiler采集。|

--output表示的路径中不能包含的特殊字符如下：

```sh
"\n", "\\n", "\f", "\\f", "\r", "\\r", "\b", "\\b", "\t", "\\t", "\v", "\\v", "\u007F", "\\u007F", "\"", "\\\"", "'", "\'", "\\", "\\\\", "%", "\\%", ">", "\\>", "<", "\\<", "|", "\\|", "&", "\\&", "$", "\\$", ";", "\\;", "`", "\\`"
```

## 使用示例

- launch方式：

  ```sh
  msprof --dynamic=on --output=/home/projects/output  --runtime-api=on /home/projects/MyApp/out/main
  (msprof) start
  ...
  (msprof) stop
  ...
  (msprof) quit
  ...
  ```

  动态采集性能数据必须传入用户程序。

- attach方式：

  ```sh
  msprof --dynamic=on --pid=<pid> --output=/home/projects/output
  (msprof) start
  ...
  (msprof) stop
  ...
  (msprof) quit
  ...
  ```

## 输出说明

在--output指定的目录下生成PROF_XXX目录，建议使用[解析命令](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/zh/user_guide/msprof_parsing_instruct.md)进行性能数据的解析和导出。

动态采集时，若配置多个PID，则每个PID进程会在--output指定的目录下生成自己的PROF\_XXX目录，此时建议在解析时将--output指定为PROF_\_*XXX的父目录，以便同时解析多份PROF*\__XXX目录。

## 获取AI任务PID

可先执行如下命令查看当前环境可以采集的PID，之后再根据下列操作获取具体需要采集的PID。

```sh
ls ~/dynamic_profiling_socket_* 2>/dev/null | awk -F '_' '{print $4}' | paste -sd ',' -
```

- AI任务在物理机环境直接运行

  在该环境下执行如下命令查看AI任务的PID。

  ```sh
  npu-smi info
  ```

  打印结果如下，Process id字段即为该AI任务的PID。

  ```sh
  +---------------------------+---------------+----------------------------------------------------+
  | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
  +===========================+===============+====================================================+
  | 0       0                 | 830236        | python3                  | 58                      |
  +===========================+===============+====================================================+
    ```

- AI任务在特权容器中运行

    该场景下，动态采集操作的--pid参数需要指定的PID为AI任务在特权容器中运行的PID。

    需要通过如下步骤来查看该AI任务在特权容器中运行的PID。

    1. 执行如下命令，查看该AI任务运行时在宿主机中对应的PID。

        ```sh
        npu-smi info
        ```

        > [!NOTE]说明
        >无论在特权容器中还是在特权容器的宿主机中，`npu-smi info`命令都只能显示该AI任务运行时在宿主机中对应的PID。

        打印结果如下，Process id字段即为该AI任务运行时在宿主机中对应的PID，此处以PID为837666为例。

        ```sh
        +---------------------------+---------------+----------------------------------------------------+
        | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
        +===========================+===============+====================================================+
        | 0       0                 | 837666        |                          | 58                      |
        +===========================+===============+====================================================+
        ```

    2. 在宿主机视图下执行如下命令，查看该AI任务在宿主机中与在特权容器中，PID的映射关系。

        ```sh
        cat /proc/837666/status | grep NSpid
        ```

        打印结果如下。

        ```sh
        NSpid: 837666 849
        ```

        此处的849即为该AI任务在特权容器中运行的PID，动态采集操作的--pid参数需要指定的PID为849。

- AI任务在非特权容器中运行
  - 方式一：直接在非特权容器视图下执行如下命令，查看该AI任务在非特权容器中运行的PID。

    ```sh
    npu-smi info
    ```

    打印结果如下，Process id字段即为该AI任务在非特权容器中运行的PID。

    ```sh
    +---------------------------+---------------+----------------------------------------------------+
    | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
    +===========================+===============+====================================================+
    | 0       0                 | 849       |                          | 58                      |
    +===========================+===============+====================================================+
    ```

  - 方式二：在非特权容器的宿主机视图下执行如下命令，查看该AI任务运行时在宿主机中对应的PID。

    ```sh
    npu-smi info
    ```

    打印结果如下，Process id字段即为该AI任务运行时在宿主机中对应的PID，此处以PID为837666为例。

    ```sh
    +---------------------------+---------------+----------------------------------------------------+
    | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
    +===========================+===============+====================================================+
    | 0       0                 | 837666        |                          | 58                      |
    +===========================+===============+====================================================+
    ```

    在宿主机视图下执行如下命令，查看该AI任务在宿主机中与在非特权容器中，PID的映射关系。

    ```bash
    cat /proc/837666/status | grep NSpid
    ```

    打印结果如下。

    ```bash
    NSpid: 837666 849
    ```

    此处的849即为该AI任务在非特权容器中运行的PID，动态采集操作的--pid参数需要指定的PID为849。

> [!NOTE]说明
>多Device场景下，建议每个Device逐一运行AI任务，并逐一按照上述方式获取PID；若多Device同时运行AI任务，则获取任意一个PID进行采集，当前暂不支持同时指定多PID进行动态采集。
