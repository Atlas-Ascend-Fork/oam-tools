# 采集msproftx数据

当用户需要定位应用程序或上层框架程序的性能瓶颈时，可通过特定接口，记录应用程序执行期间特定事件发生的时间跨度，写入性能数据文件。

<!-- npu="950,A3,910b,910,310p,310b" id1 -->
- 通用场景：推荐使用[mstx API](https://gitcode.com/Ascend/mstx/blob/master/docs/zh/install_guide/mstx_install_guide.md)（也可选[msproftx API](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/latest/API/runtimeapi/aclcppdevg_03_1264.html)）。
- PyTorch场景：使用[TorchNPU Profiler API](https://gitcode.com/Ascend/pytorch/blob/master/docs/zh/developer_notes/ascend_pytorch_profiler_user_guide.md#%E9%87%87%E9%9B%86%E5%B9%B6%E8%A7%A3%E6%9E%90mstx%E6%95%B0%E6%8D%AE)。
<!-- end id1 -->

## 前提条件

<!-- npu="950,A3,910b,910,310p,310b" id2 -->
在用户程序代码内调用mstx API、msproftx API或TorchNPU Profiler API，记录应用程序执行期间特定事件发生的时间跨度。
<!-- end id2 -->
<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/msproftx_data_res.md#id00001 -->

## 命令格式

登录运行环境，执行如下命令。

```sh
msprof [options] <app>
或msprof [options] --application=<app>
```

采集mstx数据必须传入用户程序。

app参数说明请参见[app参数说明](general_collect_commands.md#app参数说明)，options参数说明请参见[参数说明](#参数说明)。

## 参数说明

- --msproftx：必选，控制msproftx用户应用程序和上层框架输出性能数据的开关，可选on或off，默认值为off。
<!-- npu="950,A3,910b,910,310p,310b" id4 -->
- --mstx-domain-include：可选，输出需要的domain数据。用户程序调用前缀为“mstxDomain”的接口，指定domain进行打点时，可选择只输出本参数配置的domain数据。

    开关内容填写mstxDomainCreateA接口的“name”。可指定多个domain，使用逗号隔开，default表示默认domain。需配置--msproftx=on。

    与--mstx-domain-exclude参数互斥，不可同时配置。和--mstx-domain-exclude参数都不配置时，会采集所有domain数据。若配置了程序中不存在的domain，则采集结果无该数据。

- --mstx-domain-exclude：可选，过滤不需要的domain数据。用户程序调用前缀为“mstxDomain”的接口，指定domain进行打点时，可选择不输出本参数配置的domain数据。

    开关内容填写mstxDomainCreateA接口的“name”。可指定多个domain，使用逗号隔开，default表示默认domain。需配置--msproftx=on。

    与--mstx-domain-include参数互斥，不可同时配置。和--mstx-domain-include参数都不配置时，会采集所有domain数据。
<!-- end id4 -->

<!-- npu="950,A3,910b,910,310p,310b" id5 -->
## 使用示例

登录运行环境，在任意路径下执行以下命令：

```sh
msprof --msproftx=on /home/projects/MyApp/out/main
```

在--output指定的目录下生成PROF_XXX目录，存放自动解析后的性能数据，相关结果文件请参见[性能数据文件参考](https://gitcode.com/Ascend/msprof/blob/master/docs/zh/user_guide/profile_data_file_references.md)。
<!-- end id5 -->

<!-- @ref: oam-tools/res/docs/zh/profiling/msprof_cmd/msproftx_data_res.md#id00002 -->
