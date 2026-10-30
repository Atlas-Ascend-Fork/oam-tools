# Environment Configuration

<!-- md-trans-meta sourceCommit=31a2705d2c5ed1a4be76b191c8ed9e0d38f741a9 translatedAt=2026-10-10T09:42:17.713Z pushedAt=2026-10-15T09:03:03.257Z -->

## Description

Obtains or restores the specified configuration.

## Precautions

Environment configuration commands must be executed on a physical machine by the root user.

<!-- npu="910,310p,310b" id1 -->
The environment configuration function is not supported on Atlas 200I/500 A2 Inference Product, Atlas Inference Series, or Atlas Training Series.
<!-- end id1 -->

## Command Format

```bash
# Query the stress test related configuration.
asys config -d=deviceId --get --stress_detect

# Restore the stress test related configuration.
asys config -d=deviceId --restore --stress_detect
```

## Description

- **d**: Optional parameter that specifies the deviceId to be operated. If this parameter is not set, the configuration of device 0 is obtained or restored by default.
- **get**: Obtains the specified configuration.
- **restore**: Restores the specified configuration.
- **stress\_detect**: Indicates the stress test related configuration. get is used together with stress\_detect to obtain the stress test related configuration; restore is used together with stress\_detect to restore the stress test related configuration.

## Usage Examples and Output Description

The output information varies by product model. Use the actual output information as the final reference.

```bash
# Obtain the stress test configuration
asys config -d=0 --get --stress_detect
+--------------------------------+---------------------------------+
| Device ID: 0                   | CURRENT CONFIGURATION           |
+================================+=================================+
| AI Core Voltage (MV)           | 850                             |
| Bus Voltage (MV)               | 850                             |
+--------------------------------+---------------------------------+

# Restore the stress test configuration
asys config -d=0 --restore --stress_detect
[ASYS] [INFO]: Configuration successfully restore, on device 0.
```
