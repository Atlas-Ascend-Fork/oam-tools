# Checking the Environment

## Description

Run a built-in operator sample to check the software and hardware environments.

## Command Format

```
python3 msaicerr.py -e -dev 0
```

## Parameters

-   **-e**  or  **--env**: The parameter is mandatory. It indicates checking the environment.
-   **-dev**  or  **--device\_id**: The parameter is optional. It specifies the ID of the device where the built-in operator sample runs. If this parameter is not set, the default device ID is  **0**. The msaicerr tool runs a built-in operator sample to check whether the software and hardware environments are normal.

## Command Example and Output Description

```
python3 msaicerr.py -e
```

Output example:

```
[INFO] Total device count: 1
[INFO] Valid device_id 0
[INFO] Get soc_version: xxxxxxx
[INFO] Start to test env with golden op.
[INFO] The built-in sample operator runs successfully, The environment is normal.
```

After the msaicerr.py tool is executed, the  **debug\_info.txt**  file is generated in the same directory as the msaicerr.py tool to record the log information generated during the tool execution.
