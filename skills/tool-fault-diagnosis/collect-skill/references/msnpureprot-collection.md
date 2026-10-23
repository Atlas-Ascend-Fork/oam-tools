# msnpureprot 本地日志采集与 msnpureport 导出

## 名称与范围

`msnpureport` 是导出Device系统日志和其他维测信息的工具。
`msnpureprot` 是本技能采集脚本沿用的参数和目录拼写，不代表“MindSpore NPU Protocol”或任何通信协议。

```bash
bash <skill_root>/scripts/collect.sh --msnpureprot --output <collection_root>
```

该参数只复制脚本配置的本地slog与CANN目录日志，不会执行工具导出，不能据此声称已获得完整Device现场。保留旧参数及`msnpureprot/`目录以兼容现有调用。

## 路径与设备核对

脚本历史默认检查`/var/log/npu/slog/`和`/usr/local/Ascend/cann-8.5.0/log/`；它们不是所有版本的固定日志位置。核对实际安装、运行用户、Host/Device日志分类、节点/设备/rank及轮转范围，再补齐其他路径。

设备ID范围取现场清单，不能固定为0～7；容器可见ID与物理设备ID的对应也需确认。文件内字段由实际产生日志的组件解释，不能给所有导出内容套用一套dispatch/notify协议格式。

## 导出与补采

按[全量采集流程](full-log-collection.md#3-导出-device-和综合现场)先查看实际Driver工具帮助，在新的可写目录执行该版本支持的导出命令。保留完整生成目录及stdout/stderr、退出码和设备覆盖；权限或设备不可用时记录失败。

本仓asys在独立导出目录调用`msnpureport -f`，见`src/asys/collect/asys_collect.py`；这是本仓实现的接口证据，不能推定所有Driver版本均使用同一命令。

应用类日志级别与Device系统日志配置分别核对。不要将修改`acl.json`当作通用系统日志配置，也不要为采集现有材料默认变更日志级别或重跑任务。

## 完整性

- 保留源目录层级及轮转文件，避免同名文件平铺覆盖。
- 修改时间筛选不能代替日志内事件时间；过滤时记录可能遗漏的上下文。
- 核对文件非空、故障时间覆盖和设备范围；产物目录存在不代表成功。
- 导出产物可能包括系统日志、Stackcore及其他DFX信息，内容随型号/版本/状态变化；不承诺每个目录都有全部类型。
