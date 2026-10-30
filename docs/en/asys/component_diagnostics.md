# Component Diagnostics

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:38:51.914Z pushedAt=2026-10-15T08:12:23.568Z -->

## Description

Component diagnostics currently supports only AI Vector component diagnostics and does not support parallel execution.

## Command Format

```bash
asys diagnose -r=component -d=deviceId --output=path
```

## Description

- **r**: Required parameter that specifies the diagnostics mode. Set this parameter to component to indicate component diagnostics.

    When displaying the diagnostic results:

    - If no device is specified but there is only one device, only the status of this device is displayed.
    - When displaying the diagnostic results of all devices, if the diagnostic result status of all devices is consistent, a summary label (such as Pass - All or Fail - All) is directly displayed.
    - If the device statuses are inconsistent, the specific status of each device is listed in sequence. For example, in a scenario with four devices, the result is displayed as Pass, Pass, Fail, Fail.
    - **If the diagnostic result is Fail**, you can check the debug\_info.txt log to locate the issue.

- **d**: Optional parameter that specifies the device ID to be diagnosed. If this parameter is not set, the diagnostic results of all devices are displayed by default.
- **output**: Optional parameter whose value is used as the directory for saving the diagnostic result file diagnose\_result\_\{time\_stamp\}.txt. If the output parameter is not included in the command line, the output result is not written to disk and is only displayed on the terminal screen. If the value specified for output is empty, an invalid string, or a path whose directory has no write permission, or if directory creation fails, the asys tool exits and reports an error.

## Usage Examples and Output Description

- When device is not specified and all devices are normal, using four cards as an example:

    ```bash
     asys diagnose -r=component
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass - All             |
     +------------------------+------------------------+
    ```

- When device is not specified and some devices are normal, using four cards as an example:

    ```bash
    asys diagnose -r=component
     +------------------------+------------------------+
     | Group of 4 Device      | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass, Fail, Pass, Fail |
     +------------------------+------------------------+
    ```

- When device is specified, using device 0 as an example:

    ```bash
    asys diagnose -d=0 -r=component
     +------------------------+------------------------+
     | Device ID: 0           | Diagnostic Result      |
     +========================+========================+
     +--- Component ----------+------------------------+
     | AI Vector              | Pass                   |
     +------------------------+------------------------+
    ```
