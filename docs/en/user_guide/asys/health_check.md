# Health Check

## Description

Check the health status of all devices or specified devices. If a device is unhealthy, an error message is displayed.

## Command Format

```bash
asys health -d=deviceId
```

## Parameters

**d**  \(optional\): It specifies the ID of the device whose health status is to be displayed. If no device is specified, the health status of all devices is displayed. When device is specified, if the device is abnormal, the error code and error information are displayed on the terminal screen. Only the first five groups of faults are displayed. All fault codes and fault information are written into the  **health\_result.txt**  file in  [Fault Information Collection](fault_information_collection.md)  and  [Service Re-run And Fault Information Collection](rerun_fault_information_collection.md).

## Examples and Output Description

- If no device is specified, all devices are normal. The following uses dual devices as an example:

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

- Specify the device. The device is normal. The following uses  **device 0**  as an example:

    ```bash
    asys health -d=0
     +-------------------+------------------------------+
     | Device ID: 0      | Overall Health: Healthy      |
     |                   | ErrorCode Num: 0             |
     +===================+==============================+
    ```

- The specified device is abnormal. The following uses  **device 0**  as an example:

    ```bash
    asys health -d=0
     +-------------------+------------------------------+
     | Device ID: 0      | Overall Health: Warning      |
     |                   | ErrorCode Num: 1             |
     +===================+==============================+
     | 0xa419321c‬        | lp pmbus error               |
     +-------------------+------------------------------+
    ```

    You can click  _[Black Box Error Codes](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743?category=troubleshooting&subcategory=fault-handling)_  and  __[Health Management Fault Definition](https://support.huawei.com/enterprise/en/ascend-computing/ascend-hdk-pid-252764743)__  to obtain the manuals of the corresponding versions and view the detailed description of the fault codes. The mapping between the fault levels and the health statuses returned by the  **asys health**  command is as follows: Healthy indicates an informational fault \(Healthy is displayed when no fault is found\), Warning indicates a minor fault, Alarm indicates a major fault, Critical indicates a critical fault, and Unknown.
