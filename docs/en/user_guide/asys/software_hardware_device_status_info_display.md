# Display of Software, Hardware, and Device Status Information

## Description

Collect information such as the installation package version, device temperature, and power.

## Command Format

```bash
asys info -r="status" -d=deviceId
```

## Parameters

- **r**  \(mandatory\): It specifies the type of information to be displayed. The value range is as follows:
    - **status**: It displays device information, including the chip model, temperature, health status, CPU, and AI Core information.
    - **software**: It displays host software information, including the system and kernel versions, and CANN package versions.
    - **hardware**: It displays the hardware information of the host and device, including the CPU model and the number of cores, memory capacity, and disk capacity of the host, the number of NPUs and model of the device, and the number of AI CPUs, AI Cores, and AI Vectors.

- **d**  \(optional\): It specifies the ID of the device whose information is to be displayed. If this parameter is not specified, the information of device 0 is displayed by default. This parameter is valid only when  **-r=status**.

## Command Example and Output Description

```bash
asys info -r="status" -d=0
```

The command output varies depending on the product model.

```text
 +----------------------------------+------------------------+
 | Device ID: 0                     | INFORMATION            |
 +==================================+========================+
 | Chip Name                        | Ascend xxxxxxxxxx      |
 | Power (W)                        | 1021                   |
 | Temperature (C)                  | 55                     |
 | health                           | Healthy                |
 +--- CPU Information --------------+------------------------+
 | AI CPU Count                     | 6                      |
 | AI CPU Usage (%)                 | 0                      |
 | Control CPU Count                | 1                      |
 | Control CPU Usage (%)            | 1                      |
 | Control CPU Frequency (MHZ)      | 2000                   |
 +--- AI Core Information ----------+------------------------+
 | AI Core Count                    | 20                     |
 | AI Core Usage (%)                | 0                      |
 | AI Core Frequency (MHZ)          | 800                    |
 | AI Core Voltage (MV)             | 900                    |
 +--- Memory Information -----------+------------------------+
 | HBM Total (MB)                   | 65536                  |
 | HBM Used (MB)                    | 3382.52                |
 | HBM Bandwidth Usage (%)          | 0                      |
 | HBM Frequency (MHZ)              | 1600                   |
 +----------------------------------+------------------------+
```
