# Collecting Performance Data in Delayed Mode

<!-- md-trans-meta sourceCommit=f3cf4115ddb0ce33467a62e425af1dd155a6419f translatedAt=2026-11-16T08:57:29.133Z pushedAt=2026-11-17T01:02:25.576Z nl=2 -->

## Description

You can configure the delay time and duration of data collection by setting the `--delay` and `--duration` parameters. In the delayed collection scenario, [Dynamic Collection of Performance Data](dynamically.md) is not supported.

## Command Example

Log in to the environment where the tool is located as the running user and run the following command to collect performance data. The command example is as follows:

```sh
msprof [options] <app>
```

Delayed collection can be enabled only when collecting AI task runtime performance data. In this case, the user program must be passed in, and this parameter cannot be configured together with the `--dynamic` parameter. For details about the app parameter, see [app Parameters](general_collect_commands.md#app-parameters). For details about the options parameter, see Table 1. You can also add the parameters in [Collecting AI Task Runtime Performance Data](ai_runtime_profile_data.md).

## Parameters

**Table 1** options parameter description

|Parameter|**Optional/Required**|Description|
|--|--|--|
|--delay|Optional|Delays performance data collection by the specified time. Value range: [1, 4294967295], in seconds. Default value: 0. If the configured time exceeds the execution time of the AI task, collection will not start during the execution of the AI task.|
|--duration|Optional|Duration of performance data collection. Value range: [1, 4294967295], in seconds. By default, this parameter is not configured, meaning that collection continues from the start until the task ends and stops automatically. If the `--delay` parameter is configured, the duration starts counting from the moment the delay ends.|

## Usage Example

```sh
msprof --delay=3 --duration=3 /home/projects/MyApp/out/main
```
