# Software, Hardware, and Device Status Information Display

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:47:16.728Z pushedAt=2026-10-15T09:31:44.009Z -->

## Description

Collects installation package version information, Device temperature, power, and more.

## Command Format

```bash
asys info -r="status" -d=deviceId
```

## Description

- **r**: Mandatory parameter that specifies the type of information to display. The following values are supported:
    - status: Displays device information, including the chip model, temperature, health status, CPU and AI Core information, etc.
    - software: Displays Host software information, including the system and kernel versions, CANN package version, etc.
    - hardware: Displays Host and Device hardware information, including the Host CPU model and core count, memory capacity, and disk capacity, as well as the Device NPU count and model, and the number of AI CPU/AI Core/AI Vector units, etc.

- **d**: Optional parameter that specifies the deviceId of the information to display. If this parameter is not set, information about device 0 is displayed by default. This parameter is valid only when -r=status.

## Usage Examples and Output Description

```bash
asys info -r="status" -d=0
```

The output information varies by product model. Refer to the actual output information.

```bash
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
