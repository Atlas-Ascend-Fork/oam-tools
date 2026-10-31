# FAQ

## 开启msprof采集性能数据，内存无法释放

**故障现象**

在openeuler 24.03 LTS-SP4系统，开启msprof采集性能数据，host侧内存出现上涨，停止采集后host内存没有恢复。

**故障原因**

环境glibc arena内存碎片化，导致内存未及时归还至OS，内存占用上涨。

**故障处理**

可尝试设置环境变量`MALLOC_ARENA_MAX`为小于系统默认值（CPU核心数 × 8）的数字，设定arena个数上限。

该方案可能对模型性能有影响，请根据实际情况使用。

## msprof采集失败或退出码非0

**故障现象**

msprof命令返回非0退出码，命令行提示应用退出、导出失败或日志路径，未打印“Profiling finished”。

**故障原因**

- 应用以非0退出，msprof会中止后续导出并返回非0退出码。
- 应用在msprof工具采集的同时调用aclprofInit或aclprofStart配置API采集，返回错误码100042，两种Profiling配置不能并存。
- timeline或summary导出子进程以非0退出，msprof会返回非0退出码，不会把失败掩盖为成功。

**故障处理**

1. 以msprof命令退出码判断采集是否成功；退出码非0时，再查看命令行提示、被测应用输出和PROF_*/mindstudio_profiler_log/日志。
2. 若应用日志包含aclprofInit或aclprofStart返回100042，移除应用内API采集配置，或停止使用msprof工具采集，只保留一种Profiling配置。
3. 若提示导出失败，查看mindstudio_profiler_log/msprof_analysis_*.log，确认导出子进程具体错误。
4. “An exception has occurred in process ... exit code: N”中的N是子进程退出码，不是系统errno，不应按“Exec format error”等errno文案排查；若提示“terminated by signal: N”，N是导致子进程终止的信号号。
