# Environment Configuration

## Description

Obtain or restore the specified configuration.

## Notes

You must run the commands related to environment configuration as the  **root**  user on a physical machine.

<!-- npu="910,310p,310b" id1 -->
Atlas 200I/500 A2 inference products,  Atlas inference products, and  Atlas training products  do not support environment configuration.
<!-- end id1 -->

## Command Format

```
# Query the stress test configuration.
asys config -d=deviceId --get --stress_detect

# Restore the stress test configuration.
asys config -d=deviceId --restore --stress_detect
```

## Parameters

-   **d**: This parameter is optional. It specifies the ID of the device to be operated. If this parameter is not set, the configuration of device 0 is obtained or restored by default.
-   **get**: It is used to obtain the specified configuration.
-   **restore**: It is used to restore the specified configuration.
-   **stress\_detect**: it indicates the stress test configuration.  **get**  and  **stress\_detect**  are used together to obtain stress test configuration.  **restore**  and  **stress\_detect**  are used together to restore the stress test configuration.

## Command Example and Output Description

The command output varies depending on the product model.

```
# Obtain the stress test configuration.
asys config -d=0 --get --stress_detect
+--------------------------------+---------------------------------+
| Device ID: 0                   | CURRENT CONFIGURATION           |
+================================+=================================+
| AI Core Voltage (MV)           | 850                             |
| Bus Voltage (MV)               | 850                             |
+--------------------------------+---------------------------------+

# Restore the stress test configuration.
asys config -d=0 --restore --stress_detect
[ASYS] [INFO]: Configuration successfully restore, on device 0.
```
