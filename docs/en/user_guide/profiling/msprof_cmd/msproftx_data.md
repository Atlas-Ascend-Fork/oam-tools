# Collecting msproftx Data

<!-- md-trans-meta sourceCommit=1781bfe9dfb09251472d58ba6e8806766ea3753d translatedAt=2026-11-16T09:08:59.398Z pushedAt=2026-11-17T01:19:35.474Z nl=2 -->

When you need to locate performance bottlenecks in an application or an upper-layer framework program, you can use specific APIs to record the time span of specific events during application execution and write the data to a performance data file.

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
- General scenario: It is recommended to use [mstx API](https://gitcode.com/Ascend/op-plugin/blob/master/docs/en/custom_APIs/menu_Pytorch_API.md) (or optionally [msproftx API](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/latest/API/runtimeapi/docs/zh/api_ref/19-02_msproftx_extension_apis.md)).
- PyTorch scenario: Use [TorchNPU Profiler API](https://gitcode.com/Ascend/pytorch/blob/master/docs/en/developer_notes/ascend_pytorch_profiler_user_guide.md).
<!-- end id1 -->

## Prerequisites

<!-- npu="950,A3,910b,910,310p,310b" id2 -->
Call the mstx API, msproftx API, or TorchNPU Profiler API in the user program code to record the time span during which a specific event occurs during application execution.
<!-- end id2 -->
<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/msproftx_data_res.md#id00001 -->

## Command Format

Log in to the running environment and run the following command.

```sh
msprof [options] <app>
or msprof [options] --application=&lt;app&gt;
```

To collect mstx data, you must pass in the user program.

For details about the app parameters, see [app Parameters](general_collect_commands.md#app-parameters). For details about the options parameters, see [Parameters](#parameters).

## Parameters

- --msproftx: Mandatory. Controls whether the msproftx user application and upper-layer framework output performance data. The value can be on or off, and the default value is off.
<!-- npu="950,A3,910b,910,310p,310b" id4 -->
- --mstx-domain-include: Optional. Outputs the required domain data. When the user program calls APIs prefixed with "mstxDomain" to specify a domain for instrumentation, you can choose to output only the domain data configured by this parameter.

    Set the switch content to the "name" of the mstxDomainCreateA API. You can specify multiple domains separated by commas. default indicates the default domain. --msproftx=on must be configured.

    This parameter is mutually exclusive with --mstx-domain-exclude and cannot be configured at the same time. If neither this parameter nor --mstx-domain-exclude is configured, data of all domains is collected. If a domain that does not exist in the program is configured, no data of that domain is collected.

- --mstx-domain-exclude: Optional. Filters out the domain data that is not required. When the user program calls APIs prefixed with "mstxDomain" to specify a domain for instrumentation, you can choose not to output the domain data configured by this parameter.

    Set the switch content to the "name" of the mstxDomainCreateA API. You can specify multiple domains separated by commas. default indicates the default domain. --msproftx=on must be configured.

    This parameter is mutually exclusive with --mstx-domain-include and cannot be configured together with it. If neither this parameter nor --mstx-domain-include is configured, data of all domains is collected.
<!-- end id4 -->

<!-- npu="950,A3,910b,910,310p,310b" id5 -->
## Usage Example

Log in to the runtime environment and run the following command in any directory:

```sh
msprof --msproftx=on /home/projects/MyApp/out/main
```

A PROF_XXX directory is generated in the directory specified by --output to store the automatically parsed performance data. For details about the related result files, see [Performance Data File Reference](https://gitcode.com/Ascend/msprof/blob/master/docs/en/user_guide/profile_data_file_references.md).
<!-- end id5 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/msproftx_data_res.md#id00002 -->
