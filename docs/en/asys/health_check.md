# Health Check

<!-- md-trans-meta sourceCommit=2a887466d2e2283344c9f9e8c9427fce31c3c901 translatedAt=2026-10-10T09:44:57.736Z pushedAt=2026-10-15T09:21:44.054Z -->

## Description

Checks the health status of all Devices or a specified Device. If a Device is unhealthy, error information is displayed.

## Command Format

```bash
asys health -d=deviceId
```

## Description

**d**: optional parameter that specifies the deviceId whose health status is to be displayed. If no device is specified, the health status of all devices is displayed. If a device is specified and the device is abnormal, the fault codes and fault information are displayed on the terminal screen, showing only the first five groups of faults. During [fault information collection](fault_information_collection.md) and [service rerun + fault information collection](rerun_fault_information_collection.md), all fault codes and fault information are written to the health\_result.txt file.

## Usage Examples and Output Description

- When no device is specified and all devices are normal, the following uses dual cards as an example:

    ```bash
    asys health
     +------------------------+------------------------------+
     | Group of 2 Device      | Overall Health: Healthy      |
     +========================+==============================+
     | Device ID: 0           | Healthy                      |
     +------------------------+------------------------------+
     | Device ID: 1           | Healthy                      |
     +------------------------+------------------------------+
    ```

- When a device is specified and the device is normal, the following uses device 0 as an example:

    ```bash
    asys health -d=0
     +-------------------+------------------------------+
     | Device ID: 0      | Overall Health: Healthy      |
     |                   | ErrorCode Num: 0             |
     +===================+==============================+
    ```

- When a device is specified and the device is abnormal, the following uses device 0 as an example:

    ```bash
    asys health -d=0
     +-------------------+------------------------------+
     | Device ID: 0      | Overall Health: Warning      |
     |                   | ErrorCode Num: 1             |
     +===================+==============================+
     | 0xa419321c‬        | lp pmbus error               |
     +-------------------+------------------------------+
    ```

    You can click *[Black Box Error Code Information List](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743?category=troubleshooting&subcategory=fault-handling)* and *[Health Management Error Definition](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743)* to obtain the manual of the corresponding version and view the detailed description of the fault codes. The mapping between the fault levels and the health status returned by the **asys health** command is as follows: Healthy (no problem; the normal status also displays Healthy), Warning (Minor), Alarm (Major), Critical, and Unknown.
