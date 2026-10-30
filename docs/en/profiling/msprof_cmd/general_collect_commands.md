# msprof General Collection Command

<!-- md-trans-meta sourceCommit=c24a4651641b144028d2fefef2ccf4c9774235a4 translatedAt=2026-10-10T12:19:11.442Z pushedAt=2026-10-16T02:21:27.793Z -->

## Description

The msprof command-line tool provides the collection and parsing capabilities for performance data such as **AI task runtime performance data** and **AI processor system data**.

Among them, the msprof general collection command is the basis for performance data collection. It provides the basic information required for performance data collection, including parameter description, AI task file, data storage path, and custom environment variables.

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
## Command Format

Log in to the runtime environment and run the following command in any directory.

- Method 1 (recommended): Directly pass the user program or execution script at the end of the msprof command.

    ```sh
    msprof [options] <app>
    ```

- Method 2: Pass the user program or execution script through the --application parameter.

    ```sh
    msprof [options] --application=<app>
    ```

In the following examples, the recommended method is used to avoid redundant information.
<!-- end id1 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/general_collect_commands_res.md#id00001 -->

## app Parameters

You can pass the user program and its related parameters, for example:

- Method 1 configuration example:
  - Pass the binary executable program and its program parameters to msprof:

    ```sh
    msprof --output=/home/projects/output /home/projects/main parameter1 parameter2
    ```

  - Pass the execution script and its script parameters to msprof:

    ```sh
    msprof --output=/home/projects/output /home/projects/run.sh parameter1 parameter2
    ```

- Method 2 configuration example:
  - Use the --application parameter of msprof to pass the binary executable program and its program parameters:

    ```sh
    msprof  --application="/home/projects/main parameter1 parameter2 ..."
    ```

  - Use the --application parameter of msprof to pass the execution script and its script parameters:

    Training scenario:

    ```sh
    msprof  --application="/home/projects/run.sh parameter1 parameter2 ..."
    ```

> [!NOTE] Note
>
>- If abnormal symbols exist in the parameter, the parameter cannot be recognized. Therefore, Method 1 is recommended for passing the user program. When using Method 1, if the configured user program command contains parameter values that need to be quoted, write the command into a Shell script and add the user program command to the msprof command by executing the Shell script.
>- It is not recommended to configure AI tasks in other user directories or directories writable by other users to avoid privilege escalation risks. It is not recommended to configure high-risk operations such as deleting files or directories, changing passwords, and privilege escalation commands. Avoid using pmupload as the program name.
>- This parameter is mandatory when collecting all performance data, collecting performance data during AI task running, or collecting msproftx data. This parameter is optional when collecting AI processor system data. This parameter is optional when collecting Host-side system data.

## options Parameters

- --output=<path\>: Optional. Specifies the path for storing the collected performance data.

    This parameter has a higher priority than ASCEND\_WORK\_PATH. For details, see *[Environment Variable Reference](https://gitcode.com/cann/docs/blob/9.2.0/docs/en/env-vars/README.md)*.

    The path cannot contain special characters:

    ```sh
    "\n", "\\n", "\f", "\\f", "\r", "\\r", "\b", "\\b", "\t", "\\t", "\v", "\\v", "\u007F", "\\u007F", "\"", "\\\"", "'", "\'", "\\", "\\\\", "%", "\\%", ">", "\\>", "<", "\\<", "|", "\\|", "&", "\\&", "$", "\\$", ";", "\\;", "`", "\\`"
    ```

    When an AI task execution command is appended to the end of the msprof command to pass a user program or an execution script, the data is stored in the current directory by default.

    When the --application parameter is configured to add an AI task execution command to pass a user program or an execution script, the data is stored in the directory where the AI task file resides by default.

<!-- npu="950,A3,910b,910,310p,310b" id2 -->
- --type=<type\>: Optional. Sets the format of the performance data parsing result file, that is, the format of the result file automatically parsed after msprof command-line collection. The value can be:
  - text: Indicates that the result is parsed into .json and .csv files and a .db file (msprof\_timestamp.db). The default value is text.
  - db: Indicates that the result is parsed into only one .db file (msprof\_ timestamp.db) that summarizes all performance data, which is displayed using the MindStudio Insight tool.
    <!-- end id2 -->

- --environment=<env\>: Optional. Specifies the custom environment variables required in the runtime environment during collection.

    It is not recommended to use directories of other users to overwrite the original environment variables, to avoid the risk of privilege escalation.

    The configuration format is `--environment="${envKey}=${envValue}"` or `--environment="${envKey1}=${envValue1};${envKey2}=${envValue2}"`.

- --storage-limit=<limit-value\>: Optional. Specifies the maximum file capacity allowed in the storage directory. When the performance data files on the disk are about to occupy the maximum storage space set by this parameter, or the remaining total disk space is about to be fully occupied (remaining total space <= 20 MB), the earliest files on the disk are deleted through aging.

    The value range is \[200, 4294967295\], in MB. For example, `--storage-limit=200MB`. By default, this parameter is not configured.

    When this parameter is not configured, if the available disk space is less than 20 MB before collection, the data is not written to the disk.

- --help: Optional. Help prompt parameter.

<!-- npu="950,A3,910b,910,310p,310b" id3 -->
## Usage Example

Log in to the runtime environment and run the following command in any directory:

```sh
msprof --output=/home/projects/output /home/projects/MyApp/out/main
```

After the msprof command is executed, the performance data result files are automatically parsed and exported. For details, see [Performance Data File Reference](https://gitcode.com/Ascend/msprof/blob/26.2.0/docs/en/user_guide/profile_data_file_references.md).
<!-- end id3 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/general_collect_commands_res.md#id00002 -->
