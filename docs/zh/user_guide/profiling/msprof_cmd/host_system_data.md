# 采集Host侧系统数据

## 功能说明

msprof支持采集Host侧的系统数据（CPU利用率、CPU频率、内存利用率、磁盘I/O利用率、网络I/O利用率等）以及Host侧调度、中断事件（ftrace），并且在采集后可以自动进行性能数据解析和文件落盘；同时支持按核采集Host侧CPU PMU的硬件事件与内核软件事件计数，用于分析IPC、cache命中率、TLB压力、缺页与调度等。

## 命令格式

可以在采集AI任务运行性能数据时，采集Host侧系统数据：

```sh
msprof [options] <app>
```

也可以在采集AI处理器系统数据时，采集Host侧系统数据：

```sh
msprof --output=<path> --sys-devices=<ID> --sys-period=<period> [options]
```

## 参数说明

**表1**  参数说明

|参数|**可选/必选**| 描述                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
|--|-- |-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|--host-sys|--host-sys和--host-sys-usage二者必选其一| Host侧系统数据采集开关，取值包括cpu、mem、disk、network和osrt，可选其中的一项或多项，选多项时用英文逗号隔开。配置该项必须配置`host-sys-pid`参数或传入用户程序。<br>各项取值含义如下：<br>- cpu：进程级别的CPU利用率和CPU频率。<br>- mem：进程级别的内存利用率。<br>- disk：进程级别的磁盘I/O利用率。<br>- network：系统级别的网络I/O利用率。<br>- osrt：进程级别的syscall和pthreadcall。<br>- numa：总读带宽、本节点读带宽、跨节点（远程）读带宽和内部（自身）读带宽；跨节点读流量占总读流量的比例；本节点读流量占总读流量的比例。<br>配置示例：`--host-sys`=cpu,mem,disk,network。<br>**说明**：<br>- 采集Host侧CPU频率性能数据依赖内核cpufreq驱动，若/sys/.../scaling_cur_freq文件不存在，请安装相关驱动。<br>- Host侧disk性能数据需要安装第三方开源工具iotop，采集osrt性能数据需要安装第三方开源工具perf和ltrace，其安装方法参见[安装perf-iotop-ltrace工具](../appendices/install_perf_iotop_ltrace.md)。完成安装后须参见[配置用户权限](../appendices/config_user_permission.md)完成用户权限配置，且每次重新安装CANN软件包需要重新配置。<br>- 使用开源工具ltrace采集osrt性能数据会导致CPU占用率过高，其与应用工程的pthread加解锁相关，会影响进程运行速度。<br>- x86_64架构的KylinV10SP1操作系统支持--host-sys=osrt参数， aarch64架构的KylinV10SP1操作系统下不支持--host-sys=osrt参数。<br>- 虚拟化环境Euler2.9系统下不支持--host-sys=network参数。 |
|--host-sys-usage|--host-sys和--host-sys-usage二者必选其一| Host侧系统和所有进程的性能数据采集开关，取值包括cpu和mem，可选其中的一项或多项，选多项时用英文逗号隔开。配置该项时如果配置`host-sys-pid`参数，则采集Host侧指定进程的CPU或内存利用率。取值含义如下：<br>- cpu：系统和所有进程的CPU利用率。<br>- mem：系统和所有进程的内存利用率。<br>配置示例：`--host-sys-usage=cpu,mem`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|--host-sys-pid|可选| 指定需要采集的Host侧应用程序的pid。依赖AI任务运行时该参数无需配置，且配置无效。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|--host-sys-usage-freq|可选| CPU利用率、内存利用率的采集频率，范围[1,50]，默认值50，单位Hz。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|--ftrace|可选| Host侧ftrace事件的采集开关，取值为`子系统/事件`形式的字符串，多项时用英文逗号隔开，例如`--ftrace=sched/sched_switch,irq/irq_handler_entry`。采集结果用于将Host侧调度、中断事件与AI任务的性能数据关联分析。<br>**说明**：<br>- 依赖内核tracefs，需要root权限或免密sudo权限（`sudo -n`）执行；两者都不具备、或容器内未挂载tracefs时该参数不生效，采集日志中会给出失败原因。<br>- 同一节点同一时刻只允许一个采集器工作，多任务并发采集时，仅第一个任务能采到ftrace数据。 |
|--ftrace-period|可选| Host侧ftrace的采集窗口，单位为秒，取值范围[0, 86400]，默认值0。取值为0时表示跟随profiling的生命周期，即从采集开始持续到采集结束；取值为正整数时，从采集开始计时，达到该时长后停止ftrace采集。窗口越长数据量越大，1秒窗口在256核节点上约产生400MB原始数据，建议按需设置。 |
|--ftrace-bufsize|可选| Host侧ftrace每个CPU的ring buffer大小，单位为KB，取值范围[1024, 4194304]，默认值4096。buffer越大越不容易丢事件，但会占用更多Host侧内核内存。 |
|--event-sample|可选| CPU PMU计数采集开关，取值为`none`或`system-wide`，默认值为`none`。取值`system-wide`时对所有online CPU逐个按核计数，统计该核上所有进程的合计。配置`--cpu-core-events`或`--os-events`中的任一项即视为开启，无需再单独配置本参数。<br>**说明**：<br>- 本参数只表示“是否采集”，不改变采集范围；采集范围由online CPU集合决定，与`--host-sys-pid`无关，配置了`--host-sys-pid`也不会缩小到该进程。<br>- 按核计数需要`/proc/sys/kernel/perf_event_paranoid`为0（或具备CAP_PERFMON权限）；该值为1时每个计数器打开都会失败，采集日志会给出下调该值或授予权限的提示；各等级的取值范围与三种调整方式参见[配置用户权限](../appendices/config_user_permission.md)。<br>- 采集结果按核写入`data/pmu/host_pmu_cpu<N>.data`，数值为该核上的累计值，分析后按区间差分使用。 |
|--cpu-core-events|可选| 硬件PMU计数器事件名列表，多个事件用英文逗号分隔，例如`--cpu-core-events=cycles,instructions,l1d_cache`。取值为`help`时打印当前节点支持的事件名后退出，不启动采集。<br>**说明**：<br>- 只能填事件名：既不支持Nsight Systems那种按机型编号的数字ID（同一个ID在不同架构上含义不同，照抄会采到错误数据），也不支持`raw:0x13`这类raw编码（编码依赖具体CPU型号，同一条命令在不同节点上可能数到不同事件）。可用取值见`--cpu-core-events=help`。<br>- 事件名允许字母、数字、下划线和连字符（不含冒号），单个事件名长度不超过64。<br>- 与`--os-events`合计去重后不超过32个，两类事件落在同一文件的同一行，按来源区分（见下）。<br>- 事件名在本机不存在或本机PMU不支持时，该列保留但对应数值为空，其它事件照常采集。 |
|--os-events|可选| 内核软件事件列表，取值为以下9个之一或多项，多项时用英文逗号分隔：`page-faults`、`minor-faults`、`major-faults`、`context-switches`、`cpu-migrations`、`alignment-faults`、`emulation-faults`、`task-clock`、`cpu-clock`。取值为`help`时打印支持的取值后退出。<br>**说明**：<br>- 只能取上述固定取值，拼写错误会被拒绝并列出支持的取值。<br>- 与`--cpu-core-events`共用32个事件的上限；同名事件不会被硬件事件顶替，例如`page-faults`始终解析为内核计数器而不是某个同名PMU事件。<br>- 软件事件不依赖PMU硬件，节点无可用PMU时仍可采集。 |
|--event-sampling-interval|可选| 计数采样间隔，单位为毫秒，取值范围[1, 3600000]，默认值100。<br>**说明**：间隔越小数据量越大。以256核、4个事件、100ms间隔为例，每分钟约产生150万行样本（256 × 4 × 600），调小间隔前请确认磁盘余量。 |


## 资源与权限前提

**权限**：系统级计数需要 `perf_event_paranoid <= 0`（或给二进制 `CAP_PERFMON`），调整方法见《配置用户权限》一节。

**文件描述符**：每个 CPU 需要"每个事件一个 fd + 数据文件 + 时序旁路文件"个 fd，256 核、5 事件约占 1800 个。建议在部署侧调大上限（任选其一）：

```bash
# 当前会话
ulimit -n 8192
# systemd 服务
LimitNOFILE=8192
# 容器
docker run --ulimit nofile=8192 ...
```

如果调不动，工具**不会失败**：fd 不足时自动分批轮转，轮流覆盖全部 CPU，只是单核采样间隔变为"批数 × 间隔"；采集时长不足以跑完所有轮次时，来不及出点的核在库里表现为"有 counter、无 sample"，不会静默消失。日志会打印一条 WARN 给出需要的 fd 数、当前值以及三种调法（`ulimit -n`、systemd `LimitNOFILE`、容器 `--ulimit nofile`），同样内容也写在 `host_pmu_status.txt` 的 `#note` 行；连一个核都放不下时另有一条 WARN 说明本次缺少 PMU 数据。profiling 流程与被测应用始终不受影响。日志关键字：`RLIMIT_NOFILE`、`sampling in batches`。

## 典型事件组合

按“想分析什么”选事件，比一次把所有事件都打开更合适：事件越多，内核越可能分批轮换计数器，采样值会变成估算值，而且文件更大。下表给出常用组合，事件名可用`--cpu-core-events=help`确认本节点是否支持。

**表2**  分析目标与事件组合

|想分析的问题|建议事件|派生指标与说明|
|--|--|--|
|整体计算效率|`--cpu-core-events=cycles,instructions`|IPC = instructions / cycles；两个都取自通用别名，可直接相除|
|分支预测效率|`--cpu-core-events=branch-instructions,branch-misses`|失败率 = branch-misses / branch-instructions；也可改用本节点的PMU事件（如`br_retired`，完整名称见`--cpu-core-events=help`）|
|L1数据缓存压力|`--cpu-core-events=l1d_cache,l1d_cache_refill`|命中率 = 1 − refill / access|
|末级缓存（LLC）压力|`--cpu-core-events=ll_cache,ll_cache_miss`|命中率 = 1 − miss / access|
|TLB与页表遍历|`--cpu-core-events=l1d_tlb_refill,dtlb_walk`|`dtlb_walk / l1d_tlb_refill`越高，说明页表遍历开销越大|
|流水线停顿|`--cpu-core-events=stall_frontend,stall_backend`|停顿占比高说明取指或后端执行受限，需结合IPC判断|
|访存与跨片访问|`--cpu-core-events=mem_access,remote_access`|跨片访问占比高时，优先检查数据放置与NUMA绑定|
|缺页与内存压力|`--os-events=page-faults,minor-faults,major-faults`|major-faults持续大于0通常意味着内存不足或换页|
|调度抖动|`--os-events=context-switches,cpu-migrations`|与`cycles`同采时，可观察切换密集时段的IPC下降|
|有效计算时间|`--os-events=task-clock`|单位为**纳秒**，不是次数；与墙钟时长对比可看出线程被换出的比例|

**说明**：

- 事件名必须来自`--cpu-core-events=help`或`--os-events=help`的输出；不支持按机型编号的数字ID（如`2`），也不支持`raw:0x13`这类原始编码。
- `--cpu-core-events`与`--os-events`可以同时配置，两类事件写入同一个文件、同一行，按来源区分；两者去重后合计不超过32个。
- 比值只能在同一个来源内计算：`cycles`（通用别名）不能和某个同名的`sysfs`事件混算，`task-clock`（纳秒）不能和计数类事件相加。
- 选项需要写在应用名之前，例如`msprof --output=... --cpu-core-events=cycles,instructions /path/app`；写在应用名之后不会被解析。

## 使用示例

登录运行环境，在任意路径下执行以下命令：

```sh
msprof --output=/home/projects/output --host-sys=cpu /home/projects/MyApp/out/main
```

采集Host侧调度和中断事件（ftrace），采集窗口为5秒：

```sh
msprof --output=/home/projects/output --host-sys=cpu --ftrace=sched/sched_switch,sched/sched_wakeup,irq/irq_handler_entry --ftrace-period=5 /home/projects/MyApp/out/main
```

采集Host侧CPU PMU计数（每核cycles、instructions、L1D访问与回填，外加缺页与上下文切换），采样间隔100ms：

```sh
msprof --output=/home/projects/output --cpu-core-events=cycles,instructions,l1d_cache,l1d_cache_refill --os-events=page-faults,context-switches --event-sampling-interval=100 /home/projects/MyApp/out/main
```

查看当前节点支持的事件名与软件事件取值：

```sh
msprof --cpu-core-events=help
msprof --os-events=help
```

或者：

```sh
msprof --output=/home/projects/output --sys-devices=<ID> --sys-period=<period> --sys-hardware-mem=on --host-sys-pid=<pid> --host-sys=cpu
```

在--output指定的目录下生成PROF_XXX目录，存放自动解析后的性能数据，相关结果文件请参见表1。启用CPU PMU计数时，原始数据位于PROF_XXX/data/pmu/下（每个核一个文件），解析后在msprof_<时间>.db中生成PMU_EVENTS（事件定义）、PMU_COUNTERS（事件与核的组合）和PMU_COUNTER_SAMPLES（逐采样点数值）三张表。
