# Checking the Environment

<!-- md-trans-meta sourceCommit=2a887466d2e2283344c9f9e8c9427fce31c3c901 translatedAt=2026-10-10T12:13:20.057Z pushedAt=2026-10-16T02:09:47.512Z -->

## Description

Run the built-in operator sample to check the software and hardware environment.

## Command Format

```bash
python3 msaicerr.py -e -dev 0
```

## Parameters

- **-e or --env**: Mandatory parameter, indicating environment check.
- **-dev or --device\_id**: Optional parameter, specifying the Device ID for running the built-in operator sample. If this parameter is not set, the default Device ID is 0. The msaicerr tool runs a built-in operator sample to check whether the software and hardware environment is normal.

## Usage Examples and Output Description

```bash
python3 msaicerr.py -e
```

The following shows an example of the output:

```bash
[INFO] Total device count: 1
[INFO] Valid device_id 0
[INFO] Get soc_version: xxxxxxx
[INFO] Start to test env with golden op.
[INFO] The built-in sample operator runs successfully, The environment is normal.
```

After the msaicerr.py tool is executed, a debug\_info.txt file is generated in the same directory as the msaicerr.py tool to record the log information generated during tool execution.
