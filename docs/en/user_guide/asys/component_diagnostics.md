# Component Detection

## Description

Component detection: Currently, only the AI Vector component detection is supported; parallel execution is not supported.

## Command Format

```
asys diagnose -r=component -d=deviceId --output=path
```

## Parameters

-   **r**: \(mandatory\) detection mode. Set this parameter to  **component**, indicating component detection.

    Display of the detection result:

    -   If no device is specified but there is only one device, only the status of this device is displayed.
    -   When the detection results of all devices are displayed, if the detection result status of all devices is the same, the summary label (such as  **Pass - All**  or  **Fail - All**) is directly displayed.
    -   If the status of devices is inconsistent, the status of each device is displayed in sequence. For example, if there are four devices,  **Pass**,  **Pass**,  **Fail**, and  **Fail**  are displayed.
    -   If the detection result is  **Fail**, view the debug\_info.txt log to locate the fault.

-   **d**  \(optional\): It specifies the ID of the device to be detected. If this parameter is not specified, the detection results of all devices are displayed by default.
-   **output**  \(optional\): It specifies the directory for storing the detection result file  **diagnose\_result\__\{time\_stamp\}_.txt**. If the command does not contain the  **output**  parameter, the command output is only printed on the terminal screen but not flushed. If the value of  **output**  is empty or invalid, the specified directory does not have the write permission, or the directory fails to be created, the asys tool exits and reports an error.

## Examples and Output Description

-   No device is specified, and all devices are normal. The following uses four devices as an example:

    ```
    asys diagnose -r=component
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass - All             |
     +------------------------+------------------------+
    ```

-   No device is specified, and some devices are normal. The following uses four devices as an example:

    ```
    asys diagnose -r=component
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass, Fail, Pass, Fail |
     +------------------------+------------------------+
    ```

-   A device is specified. The following uses  **device 0**  as an example:

    ```
    asys diagnose -d=0 -r=component
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass                   |
     +------------------------+------------------------+
    ```
