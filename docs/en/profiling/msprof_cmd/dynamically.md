# Collecting Performance Data Dynamically

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:18:36.809Z pushedAt=2026-10-16T02:45:17.325Z -->

## Description

During collection, you can start and stop the collection process at any time. Dynamic collection of performance data supports two modes: launch and attach.

- launch mode: When msprof starts dynamic collection from the command line, it simultaneously starts the AI task and enters the interactive mode for performance data collection. You can start and stop collection at any time using commands.

  If the process started by the msprof --application command is the actual business process that uses the device (for example, msprof --application=main --dynamic=on, where main is the actual business process program), this mode is recommended.

- attach mode: You first start the AI task on your own, then start msprof dynamic collection and enter the interactive mode for performance data collection. You can start and stop collection at any time using commands.

  If the process started by the msprof --application command in launch mode is not the actual business process that uses the device (for example, msprof --application=run.sh --dynamic=on, where run.sh starts the actual business process inside the script), attach mode is recommended instead.

## Precautions

- Before performing dynamic collection, you are advised to delete the residual dynamic Profiling files by running the command `rm -rf ~/dynamic_profiling_socket_*`.
- In launch mode, the environment variables “PROFILING\_MODE” and “PROFILING\_OPTIONS” cannot be set in the user program that is passed in.
- In attach mode, set the environment variable “PROFILING\_MODE” to dynamic first, then start the AI task, and finally run the command line operation.

  ```sh
  export PROFILING_MODE=dynamic
  ```

- For the same AI task, only one user is allowed to enter the interactive mode at a time.
- After entering the interactive mode, if data collection is not started, the system automatically exits after 30 minutes. You can run the command to re-enter the interactive mode.
- In multi-card (including cluster) scenarios, you are advised to use attach mode for dynamic performance data collection.
- This function cannot be configured together with [Delayed Performance Data Collection](delayed_mode.md) (the --delay and --duration parameters).
- If the user process is set to run in the background, launch mode becomes invalid and the interactive interface cannot be entered. In this case, you are advised to use attach mode for dynamic performance data collection.
- If the business process is started in a container, the msprof collection command must also be executed in the container.

## Command Format

- launch mode:

  ```sh
  msprof --dynamic=on [options] <app>
  --application=<app>
    ```

- attach mode:

  ```sh
  msprof --dynamic=on --pid=<pid> [options]
  ```

In launch mode, the user program must be passed in. For details about the app parameter, see [app Parameters](general_collect_commands.md#app-parameters). For details about the options parameter, see Table 1. You can also add other collection items, such as the parameters in [Collecting AI Task Execution Performance Data](ai_runtime_profile_data.md) or [Collecting AI Processor System Data](processorai_accelerator_system_data.md).

## Parameters

**Table 1** options parameter description

|Parameter|**Optional/Required**|Description|
|--|--|--|
|--dynamic|Required|Controls the switch for dynamic collection of performance data. The value can be on or off, and the default value is off.|
|--pid|Required in attach mode; not selected in launch mode|Specifies the PID of the application to be collected. You can configure one or more PIDs at a time. Example: --pid=1,2,3. For details about how to obtain the PID, see Obtaining the AI Task PID. You can also run the following command to obtain all PIDs that can be collected in the current environment:<br> `ls ~/dynamic_profiling_socket_* 2>/dev/null \| awk -F '_' '{print $4}' \| paste -sd ',' -`|
|--output|Optional|Specifies the storage path of the performance data. If this parameter is not configured, the performance data is saved in the current path by default. The path cannot contain special characters.|
|start|Optional|Starts collection.<br>- The start and stop commands can be executed up to 100 times in total. After the total number of executions of the two commands exceeds 100, the server terminates the connection, that is, a maximum of 50 performance data files can be collected. When the server is reconnected, the count is recalculated.<br>- When the start and stop commands are executed repeatedly, the stop command may end the Profiling process and terminate the data reporting of the CANN component, causing ERROR logs to be printed. This is normal.|
|stop|Optional|Stops collection. Each time a start command and a stop command are completed, a PROF*_*XXX directory for storing data files is generated in the path specified by the `--output` parameter.|
|quit|Optional|Stops collection and exits the interactive mode. After quit, the AI task continues to run normally. Run the msprof dynamic Profiling command again to re-enter the interactive mode and start dynamic Profiler collection.|

The special characters that cannot be included in the path specified by --output are as follows:

```sh
"\n", "\\n", "\f", "\\f", "\r", "\\r", "\b", "\\b", "\t", "\\t", "\v", "\\v", "\u007F", "\\u007F", "\"", "\\\"", "'", "\'", "\\", "\\\\", "%", "\\%", ">", "\\>", "<", "\\<", "|", "\\|", "&", "\\&", "$", "\\$", ";", "\\;", "`", "\\`"
```

## Usage Example

- launch mode:

  ```sh
  msprof --dynamic=on --output=/home/projects/output  --runtime-api=on /home/projects/MyApp/out/main
  (msprof) start
  ...
  (msprof) stop
  ...
  (msprof) quit
  ...
  ```

  Dynamic collection of performance data requires passing in the user program.

- attach mode:

  ```sh
  msprof --dynamic=on --pid=<pid> --output=/home/projects/output
  (msprof) start
  ...
  (msprof) stop
  ...
  (msprof) quit
  ...
  ```

## Output Description

A PROF_XXX directory is generated in the directory specified by --output. You are advised to use the [parsing command](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/msprof_parsing_instruct.md) to parse and export the performance data.

During dynamic collection, if multiple PIDs are configured, each PID process generates its own PROF\_XXX directory in the directory specified by --output. In this case, you are advised to set --output to the parent directory of PROF_\_*XXX during parsing so that multiple PROF*\__XXX directories can be parsed at the same time.

## Obtaining the PID of an AI Task

You can first run the following command to view the PIDs that can be collected in the current environment, and then obtain the specific PID to be collected by following the operations below.

```sh
ls ~/dynamic_profiling_socket_* 2>/dev/null | awk -F '_' '{print $4}' | paste -sd ',' -
```

- The AI task runs directly in a physical machine environment.

  In this environment, run the following command to view the PID of the AI task.

  ```sh
  npu-smi info
  ```

  The result is printed as follows. The Process id field is the PID of the AI task.

  ```sh
  +---------------------------+---------------+----------------------------------------------------+
  | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
  +===========================+===============+====================================================+
  | 0       0                 | 830236        | python3                  | 58                      |
  +===========================+===============+====================================================+
    ```

- The AI task runs in a privileged container.

    In this scenario, the PID to be specified for the --pid parameter of the dynamic collection operation is the PID of the AI task running in the privileged container.

    Perform the following steps to view the PID of the AI task running in the privileged container.

    1. Run the following command to view the PID corresponding to the AI task on the host during task execution.

        ```sh
        npu-smi info
        ```

        > [!NOTE] Note
        > Whether in the privileged container or on the host of the privileged container, the `npu-smi info` command can only display the PID corresponding to the AI task on the host during task execution.

        The output is as follows. The Process id field is the PID corresponding to the AI task on the host during task execution. In this example, the PID is 837666.

        ```sh
        +---------------------------+---------------+----------------------------------------------------+
        | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
        +===========================+===============+====================================================+
        | 0       0                 | 837666        |                          | 58                      |
        +===========================+===============+====================================================+
        ```

    2. In the host view, run the following command to view the PID mapping relationship of the AI task between the host and the privileged container.

        ```sh
        cat /proc/837666/status | grep NSpid
        ```

        The output is as follows.

        ```sh
        NSpid: 837666 849
        ```

        Here, 849 is the PID of the AI task running in the privileged container. The PID to be specified for the --pid parameter of the dynamic collection operation is 849.

- The AI task runs in a non-privileged container.
  - Method 1: Directly run the following command in the non-privileged container view to view the PID of the AI task running in the non-privileged container.

    ```sh
    npu-smi info
    ```

    The output is as follows. The Process id field is the PID of the AI task running in the non-privileged container.

    ```sh
    +---------------------------+---------------+----------------------------------------------------+
    | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
    +===========================+===============+====================================================+
    | 0       0                 | 849       |                          | 58                      |
    +===========================+===============+====================================================+
    ```

  - Method 2: In the host view of the non-privileged container, run the following command to view the PID corresponding to the AI task on the host during task execution.

    ```sh
    npu-smi info
    ```

    The output is as follows. The Process id field is the PID corresponding to the AI task on the host during task execution. In this example, the PID is 837666.

    ```sh
    +---------------------------+---------------+----------------------------------------------------+
    | NPU     Chip              | Process id    | Process name             | Process memory(MB)      |
    +===========================+===============+====================================================+
    | 0       0                 | 837666        |                          | 58                      |
    +===========================+===============+====================================================+
    ```

    In the host view, run the following command to view the PID mapping relationship of the AI task between the host and the non-privileged container.

    ```bash
    cat /proc/837666/status | grep NSpid
    ```

    The print result is as follows.

    ```bash
    NSpid: 837666 849
    ```

    Here, 849 is the PID of the AI task running in the non-privileged container. The --pid parameter of the dynamic collection operation must be set to 849.

> [!NOTE] Note
> In a multi-device scenario, it is recommended that you run the AI task on each device one by one and obtain the PID for each device in the preceding manner. If AI tasks run on multiple devices simultaneously, obtain any one PID for collection. Currently, specifying multiple PIDs for dynamic collection at the same time is not supported.
