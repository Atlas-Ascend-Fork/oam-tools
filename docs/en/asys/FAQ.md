# FAQs

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:43:35.278Z pushedAt=2026-10-15T09:07:53.983Z -->

## Service Rerun Error

- **Symptom**

  After pressing **Ctrl+Z** to stop the service rerun task and then starting it again, the on-screen log shows that the business rerun task has failed, as shown below.

  ```bash
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

- **Possible Causes**

  Operations such as ctrl+z cause the task to terminate abnormally, but residual task processes remain (and are still performing operations such as redirecting and writing files). These residual processes conflict with the newly started asys rerun task, causing the rerun to fail.

- **Solution**

  Before running the asys rerun, check whether there are running inference/training process IDs. Manually kill the related processes, and then run the asys rerun again.

## asys Tool Real-Time Stack Export Timeout

- **Symptom**

    When using the asys tool to export the real-time stack, an export timeout error occurs in some scenarios. The error is as follows:

    ```bash
    [ASYS] [ERROR]: Generating the stackcore bin file timeout. For details, see the related description in the document.
    ```

- **Possible Causes & Solutions**
    1. The real-time stack export function has not been initialized.

        In this case, wait until initialization is complete. You can determine that initialization is complete by checking the **attr init success** keyword in the plog log (default path: $HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log), and then try to export the real-time stack information again.

    2. The **ASCEND\_COREDUMP\_SIGNAL** environment variable is set to **none**, which disables some signal sets and makes the real-time stack export function unavailable.

        In this case, you can determine that the signal sets are disabled by checking the **close the signal capture function** keyword in the plog log (default path: **$HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log**). You need to set the **ASCEND\_COREDUMP\_SIGNAL** environment variable to enable the signal sets. For details about the ASCEND\_COREDUMP\_SIGNAL environment variable and the signal sets processed by trace, see [*Environment Variable Reference*](https://hiascend.com/document/redirect/CannCommunityEnvRef).

    3. The user service has finished executing, and the resources related to the real-time stack export function have been released.

        In this case, you can determine that the resources related to the real-time stack export function have been released by checking the **unregister all signal handlers, can not capture signal** keyword in the plog log (default path: $HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log). You need to execute the user service again before exporting the real-time stack information.

    4. The real-time stack export function is abnormal.

        In this case, search for the **ERROR** keyword in the plog log (default path: $HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log) to view the specific error information, and contact technical support. Click [Link](https://www.hiascend.com/support) to contact technical support.
