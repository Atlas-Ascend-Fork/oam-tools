# Comprehensive Detection

## Description

Involve the stress test, HBM hardware detection, CPU detection and AI Core STL hardware detection.

## Notes

You must run the commands related to comprehensive detection as the  **root**  user on a physical machine.

<!-- npu="910,310p,310b" id1 -->
For  Atlas 200I/500 A2 inference products,  Atlas inference products, and  Atlas training products, the comprehensive detection function is not supported.
<!-- end id1 -->

## Command Format

```
# AI Core stress test, which may take a long time
asys diagnose -r=stress_detect -d=deviceId --output=path

# HBM detection
asys diagnose -r=hbm_detect -d=deviceId --timeout=num --output=path

# CPU detection
asys diagnose -r=cpu_detect -d=deviceId --timeout=num --output=path

# AI Core STL hardware detection
asys diagnose -r=aicore_stl_detect -d=deviceId --output=path
```

## Parameters

-   **r**  \(mandatory\): It indicates the detection mode. The values are as follows:
    -   **stress\_detect**: AI Core stress test

        Executing this function involves operator execution. Therefore, you need to install the operator binary package \(**Ascend-cann-\*-ops-\*.run**\) in the environment in advance.

        AI Core stress test involves voltage adjustment on the device. When the stress test is complete, the voltage can be automatically restored. However, when the stress test exits abnormally, the voltage cannot be automatically restored. In this case, you can manually restore the voltage based on the asys environment configuration. You are advised to obtain the voltage before and after the AI Core stress test to check whether the voltage is abnormal and whether the voltage needs to be restored. For details about how to obtain and restore the voltage, see  [Environment Configuration](environment_configuration.md).

        Display of the detection result:

        -   If no device is specified but there is only one device, only the status of this device is displayed.
        -   When the detection results of all devices are displayed, if the detection result status of all devices is the same, the summary label (such as **Pass - All** or **Warn - All**) is directly displayed.
        -   If the status of devices is inconsistent, the status of each device is displayed in sequence. For example, if there are four devices,  **Pass**,  **Warn**,  **Warn**, and  **Warn**  are displayed.
        -   If the detection result is  **Warn**, the detection fails. You can view the plog on the host \(default path: $HOME/ascend/log/run|debug/plog/plog-_pid_  \_\*.log\), view the log information based on the keyword "\[ERROR\] AML", and locate and rectify the fault based on the error code. Error codes starting with  **1**  indicate that the test case fails to be executed or the task fails to be delivered. Error codes starting with  **2**  indicate that the accuracy comparison fails. Error codes starting with  **3**  indicate hardware problems.
        -   If the detection result is  **Pass**, the detection is successful.

    -   **hbm\_detect**: HBM detection

        Display of the detection result:

        -   If no device is specified but there is only one device, only the status of this device is displayed.
        -   When the detection results of all devices are displayed, if the detection result status of all devices is the same, the summary label (such as **Pass - All** or **Warn - All**) is directly displayed.
        -   If the status of devices is inconsistent, the status of each device is displayed in sequence. For example, if there are four devices,  **Pass**,  **Warn**,  **Warn**, and  **Warn**  are displayed.
        -   If the detection result is  **Warn**, the detection fails. You can view the plog on the host \(default path: $HOME/ascend/log/run|debug/plog/plog-_pid_  \_\*.log\), view the log information based on the keyword "\[ERROR\] AML", and locate and rectify the fault based on the error code. Error codes starting with  **1**  indicate that the test case fails to be executed or the task fails to be delivered. Error codes starting with  **4**  indicate hardware problems.
        -   If the detection result is  **Pass**, the detection is successful. For HBM detection, if the returned value is greater than 0, the value indicates the number of new ECC errors after the detection. This value is used to trigger the reporting and isolation of risk addresses in advance, ensuring normal running of subsequent services.

    -   **cpu\_detect**: CPU detection

        Display of the detection result:

        -   If no device is specified but there is only one device, only the status of this device is displayed.
        -   When the detection results of all devices are displayed, if the detection result status of all devices is the same, the summary label (such as **Pass - All** or **Warn - All**) is directly displayed.
        -   If the status of devices is inconsistent, the status of each device is displayed in sequence. For example, if there are four devices,  **Pass**,  **Warn**,  **Warn**, and  **Warn**  are displayed.
        -   If the detection result is  **Fail**, the hardware faults occur. In this case, contact technical support.
        -   If the detection result is  **Warn**, task scheduling problems occur during the detection. You can view the detailed information in the plog on the host \(default path: $HOME/ascend/log/run|debug/plog/plog-_pid_  \_\*.log\) to locate the fault. You can filter the log information based on the keyword "\[ERROR\] AML".
        -   If the detection result is  **Pass**, the detection is successful.

    -   **aicore\_stl\_detect**: AI Core STL (Software Test Library) hardware detection

        <!-- npu="950" id2 -->
        It can run only on the Ascend 950PR/Ascend 950DT.
        <!-- end id2 -->

        Display of the detection result:

        -   If no device is specified but there is only one device, only the status of this device is displayed.
        -   When the detection results of all devices are displayed, if the detection result status of all devices is the same, the summary label (such as **Pass - All** or **Warn - All**) is directly displayed.
        -   If the status of devices is inconsistent, the status of each device is displayed in sequence. For example, if there are four devices,  **Pass**,  **Warn**,  **Warn**, and  **Warn**  are displayed.
        -   If the detection result is  **Fail**, the hardware faults occur. In this case, contact technical support.
        -   If the detection result is  **Warn**, task scheduling problems occur during the detection. You can view the detailed information in the plog on the host \(default path: $HOME/ascend/log/run|debug/plog/plog-_pid_  \_\*.log\) to locate the fault. You can filter the log information based on the keyword "\[ERROR\] AML".
        -   If the detection result is  **Pass**, the detection is successful.

-   **d**  \(optional\): It specifies the ID of the device to be detected. If this parameter is not specified, the detection results of all devices are displayed by default.
-   **timeout**  \(optional\): It specifies the hardware detection time, in seconds. If this parameter is not specified, the detection time is 600s by default. This parameter is valid only for HBM detection and CPU detection. For HBM detection, the value range is \[0, 604800\] \(**0**  indicates that only one round of HBM detection is performed\); for CPU detection, the value range is \[1, 604800\].
-   **output**  \(optional\): It specifies the directory for storing the detection result file  **diagnose\_result\__\{time\_stamp\}_.txt**. If the command does not contain the  **output**  parameter, the command output is only printed on the terminal screen but not flushed. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and reports an error.

## Examples and Output Description

-   No device is specified, and all devices are normal. The following uses four devices as an example:

    ```
    asys diagnose -r=stress_detect
     +------------------------+ -----------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Performance --------+ -----------------------+
     | Stress Detect          | Pass - All             |
     +------------------------+ -----------------------+
    asys diagnose -r=hbm_detect --timeout=3000
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | HBM Detect             | Pass - All             |
     |                        | (0, 9, 0, 0)           |
     +------------------------+------------------------+
    asys diagnose -r=cpu_detect --timeout=3000
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | CPU Detect             | Pass - All             |
     +------------------------+------------------------+
    ```

-   No device is specified, and some devices are normal. The following uses four devices as an example:

    ```
    asys diagnose -r=stress_detect
     +------------------------+ -----------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Performance --------+ -----------------------+
     | Stress Detect          | Pass, Warn, Pass, Warn |
     +------------------------+ -----------------------+
    asys diagnose -r=hbm_detect
     +------------------------+ -----------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+ -----------------------+
     | HBM Detect             | Pass, Warn, Pass, Warn |
     |                        | (9, 0, 5, 0)           |
     +------------------------+ -----------------------+
    asys diagnose -r=cpu_detect
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | CPU Detect             | Pass, Warn, Pass, Fail |
     +------------------------+------------------------+
    ```

-   A device is specified. The following uses  **device 0**  as an example:

    ```
    asys diagnose -d=0 -r=stress_detect
     +--------------------+------------------------+
     | Device ID: 0       | Diagnostic Result      |
     +====================+========================+
     +--- Performance ----+------------------------+
     | Stress Detect      | Pass                   |
     +--------------------+------------------------+
    asys diagnose -d=0 -r=hbm_detect
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | HBM Detect             | Pass(9)                |
     +------------------------+------------------------+
    asys diagnose -d=0 -r=cpu_detect
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+========================+
     +--- Hardware -----------+------------------------+
     | CPU Detect             | Pass                   |
     +------------------------+------------------------+
    ```
