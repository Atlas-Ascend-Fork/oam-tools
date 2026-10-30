# Comprehensive Detection

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:39:48.614Z pushedAt=2026-10-15T08:14:17.633Z -->

## Description

It includes stress detection, HBM hardware detection, CPU detection, and AI Core STL hardware detection.

## Precautions

Commands related to comprehensive detection must be executed on a physical machine and by the root user.

<!-- npu="910,310p,310b" id1 -->
Comprehensive detection is not supported for Atlas 200I/500 A2 inference products, Atlas inference products, and Atlas training products.
<!-- end id1 -->

## Command Format

```bash
# AI Core stress detection, which may take a long time
asys diagnose -r=stress_detect -d=deviceId --output=path

# HBM detection
asys diagnose -r=hbm_detect -d=deviceId --timeout=num --output=path

# CPU detection
asys diagnose -r=cpu_detect -d=deviceId --timeout=num --output=path

# AI Core STL hardware detection
asys diagnose -r=aicore_stl_detect -d=deviceId --output=path
```

## Description

- **r**: Required parameter, detection mode. The value can be:
    - **stress\_detect: AI Core stress detection**

        This function involves executing operators. Therefore, install the operator binary package (named Ascend-cann-\*-ops-\*.run) in the environment in advance.

        AI Core stress detection involves adjusting some voltages on the device side. When the stress detection ends normally, the voltages are restored automatically. However, when some stress detection exits abnormally, the voltages may not be restored automatically. In this case, you can manually restore the voltages by using the asys environment configuration function. It is recommended that you obtain the voltages before and after AI Core stress detection to determine whether the voltages are abnormal and whether they need to be restored. For details about how to obtain and restore voltages, see [Environment Configuration](environment_configuration.md).

        When displaying the detection result:

        - If device is not specified but there is only one device, only the status of this device is displayed.
        - When the detection results of all devices are displayed, if the statuses of all devices are consistent, the summary tab (for example, Pass - All or Warn - All) is displayed directly.
        - If the device statuses are inconsistent, the specific status of each device is listed in sequence. For example, in a scenario with four devices, the statuses are displayed as Pass, Warn, Warn, Warn.
        - **If the detection result is Warn**, the detection fails. You can view the plog log on the host side (the default path is $HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log), and view the log information by using the keyword “\[ERROR\] AML". Then locate and resolve the problem based on the error code in the log: an error code starting with **1** indicates that the test case execution failed or task delivery failed; an error code starting with **2** indicates that the precision comparison failed; an error code starting with **3** indicates a hardware problem.
        - **If the detection result is Pass**, the detection succeeds.

    - **hbm\_detect: HBM detection**

        When the detection results are displayed:

        - If device is not specified but there is only one device, only the status of this device is displayed.
        - When the detection results of all devices are displayed, if the statuses of all devices are consistent, the summary tab (for example, Pass - All or Warn - All) is displayed directly.
        - If the device statuses are inconsistent, the specific status of each device is listed in sequence. For example, in a scenario with four devices, the statuses are displayed as Pass, Warn, Warn, Warn.
        - **If the detection result is Warn**, the detection fails. You can view the Host-side plog log (default path: $HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log), search for the log information by the keyword “\[ERROR\] AML", and locate and resolve the issue based on the error code: error codes starting with **1** indicate test case execution failure, task delivery failure, and so on; error codes starting with **4** indicate hardware issues.
        - **If the detection result is Pass**, the detection succeeds. For HBM detection, if the returned value \>0, this value indicates the number of ECC errors newly added after detection, which is used to trigger error reporting and isolation of risky addresses in advance to ensure normal running of subsequent services.

    - **cpu\_detect: CPU detection**

        When displaying the detection result:

        - If no device is specified and there is only one device, only the status of this device is displayed.
        - When displaying the detection results of all devices, if the detection result status of all devices is consistent, the summary tab is directly displayed (for example, Pass - All, Warn - All, or Fail - All).
        - If the device statuses are inconsistent, the specific status of each device is listed in sequence. For example, in a scenario with four devices, the display is Pass, Warn, Warn, Fail.
        - **If the detection result is Fail**, a hardware fault is detected. Contact technical support.
        - **If the detection result is Warn**, a task scheduling problem occurs during detection. You can view the detailed information in the Host-side plog log (default path: $HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log) to locate the problem. You can first filter the log information by the keyword “\[ERROR\] AML".
        - **If the detection result is Pass**, the detection succeeds.

    - **aicore\_stl\_detect: AI Core STL hardware detection**

        <!-- npu="950" id2 -->
        It can run only on Ascend 950PR&950DT products.
        <!-- end id2 -->
        When displaying the detection results:

        - If device is not specified but there is only one device, only the status of this device is displayed.
        - When displaying the detection results for all devices, if the detection result status of all devices is consistent, the summary tab is directly displayed (for example, Pass - All, Warn - All, or Fail - All).
        - If the device statuses are inconsistent, the specific status of each device is listed in sequence. For example, in a scenario with four devices, the result is displayed as Pass, Warn, Warn, Fail.
        - **If the detection result is Fail**, it indicates that a hardware fault is detected. Contact technical support.
        - **If the detection result is Warn**, it indicates that a task scheduling problem occurs during the detection, which may be caused by a hardware fault or a software issue. You can view the detailed information in the Host-side plog log (default path: $HOME/ascend/log/run|debug/plog/plog-_pid_\_\*.log) to locate the problem. You can first filter the log information by the keyword **\[ERROR\] AML**.
        - **If the detection result is Pass**, it indicates that the detection is successful.

- **d**: optional parameter that specifies the deviceId to be detected. If this parameter is not set, the detection results of all devices are displayed by default.
- **timeout**: optional parameter that specifies the hardware detection duration in seconds. If not passed, the default detection duration is 600 seconds. It takes effect only for HBM detection and CPU detection. For HBM detection, the value range is \[0, 604800\]. When set to 0, only one round of HBM detection is executed. For CPU detection, the value range is \[1, 604800\].
- **output**: optional parameter whose value is used as the directory for saving the detection result file diagnose\_result\_\{time\_stamp\}.txt. When the output parameter is not specified in the command line, the output result is not written to disk and is only displayed on the terminal screen. If the value specified for output is empty, an invalid string, or the specified path directory has no write permission, or directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

- When no device is specified and all devices are normal, the following uses four cards as an example:

    ```bash
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
    asys diagnose -r=aicore_stl_detect
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+------------------------+
     | AICore STL Detect      | Pass - All             |
     +------------------------+------------------------+
    ```

- When no device is specified and some devices are normal, the following uses four cards as an example:

    ```bash
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
    asys diagnose -r=aicore_stl_detect
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+------------------------+
     | AICore STL Detect      | Pass, Warn, Pass, Fail |
     +------------------------+------------------------+
    ```

- When a device is specified, the following uses device 0 as an example:

    ```bash
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
    asys diagnose -r=aicore_stl_detect
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+ =======================+
     +--- Hardware -----------+------------------------+
     | AICore STL Detect      | Pass                   |
     +------------------------+------------------------+
    ```
