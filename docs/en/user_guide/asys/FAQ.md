# FAQ

## FAQs About Service Re-run Errors

- **Symptom**

    Press  **Ctrl+Z**  to stop the service re-run task, and then start the service re-run task again. The displayed log shows that an error occurs in the service re-run task, as shown below.

    ```text
    [INFO]: launch task start, running:
    [WARNING]: task occurred error, output:
    Segmentation fault (core dumped)
    Process ForkServerPoolWorker-7:
    Traceback (most recent call last):
      File "/usr/local/python3.7.5/lib/python3.7/multiprocessing/pool.py", line 127, in worker
        put((job, i, result))
    ......
    BrokenPipeError: [Errno 32] Broken pipe
    ```

- **Possible causes**

    The task is ended abnormally after executing  **Ctrl+Z**. However, residual task process exists \(and operations such as redirection and file writing are still performing\), which conflict with the newly started asys re-run task. As a result, the re-run task is abnormal.

- **Handling method**

    Before the asys re-run, check whether the ID of the running inference or training process exists. If yes, manually kill the process and start the asys re-run again.

## Timeout Occurs When the asys Tool Is Used to Export Real-Time Stack Information

- **Symptom**

    When the asys tool is used to export real-time stack information, an error is reported indicating that the export times out in some scenarios. The error information is as follows:

    ```text
    [ASYS] [ERROR]: Generating the stackcore bin file timeout. For details, see the related description in the document.
    ```

- **Possible causes and solutions**
    1. The real-time stack export function has not been initialized.

        In this case, wait until the initialization is complete. You can determine that the initialization is complete based on the  **attr init success**  keyword in the plog \(**$HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log**  by default\). Then, try to export the real-time stack information.

    2. The  **ASCEND\_COREDUMP\_SIGNAL**  environment variable is set to  **none**, and some signal sets are disabled. As a result, the real-time stack export function is unavailable.

        You can determine that the signal sets are disabled based on the  **close the signal capture function**  keyword in the plog \(**$HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log**  by default\). In this case, you need to set the  **ASCEND\_COREDUMP\_SIGNAL**  environment variable to enable the signal sets. For details about the  **ASCEND\_COREDUMP\_SIGNAL**  environment variable and the signal sets for trace processing, see  [Environment Variables](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/maintenref/envvar/envref_07_0001.html).

    3. The service execution is complete, and the resources related to the real-time stack export function have been freed.

        You can determine that the resources related to the real-time stack export function have been released based on the keyword  **unregister all signal handlers, can not capture signal**  in the plog \(**_$HOME_/ascend/log/run|debug/plog/plog-_pid_\__\*_.log**  by default\). In this case, you need to execute the user service again to export the real-time stack information.

    4. The real-time stack export function is abnormal.

        In this case, you can search for the keyword  **ERROR**  in the plog \(**_$HOME_/ascend/log/run|debug/plog/plog-_pid_\__\*_.log**  by default\) to view the error information and contact technical support.  Click  [here](https://www.hiascend.com/support)  to contact technical support.
