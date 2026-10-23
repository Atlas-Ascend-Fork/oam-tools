# 公开 ACLNN 数值返回码

实际调用为ACLNN API时，按完整API名、返回类型、原始数值和现场版本核对本页。
下列公开opbase原件定义ACLNN返回码及其说明，不是AscendCL Runtime、Driver、
HCCL或进程退出码。错误码提供失败类别，具体对象和前置失败由同次原文继续定位。

| 发布 | 宏定义 | 完整官方说明 |
| --- | --- | --- |
| v8.5.0 | [op_errno_v8_5_0.h](aclnn-return-codes/opbase-v8.5.0/include/nnopbase/opdev/op_errno_v8_5_0.h) | [aclnn返回码](aclnn-return-codes/opbase-v8.5.0/docs/zh/nnopbase/opdev/aclnn返回码.md) |
| v9.0.0-beta.2 | [op_errno_v9_0_0_beta_2.h](aclnn-return-codes/opbase-v9.0.0-beta.2/include/nnopbase/opdev/op_errno_v9_0_0_beta_2.h) | [aclnn返回码](aclnn-return-codes/opbase-v9.0.0-beta.2/docs/zh/nnopbase/opdev/aclnn返回码.md) |

从本技能目录精确查数值，例如：

```bash
rg -n '(^|[[:space:]])561103([[:space:]]|$)' references/aclnn-return-codes/opbase-*/include/nnopbase/opdev/op_errno_*.h
```

再用命中的完整宏名查对应官方说明，读取完整表格行。两个发布的对应码义相同，
不证明任意现场安装版都相同；版本缺失时并列来源，未知码保留未知，不按相近数字猜测。

## 常见定义与定位入口

本表概括上述两版公开定义；完整原件还包含其他内部异常码及说明。

| 返回码 | 原宏名 | 公开说明支持的范围 |
| --- | --- | --- |
| 161001 | `ACLNN_ERR_PARAM_NULLPTR` | 参数校验发现非法nullptr；按实际API和内层消息定位具体参数 |
| 161002 | `ACLNN_ERR_PARAM_INVALID` | 参数校验错误，如输入数据类型不满足推导关系；须核明确违反的输入契约 |
| 361001 | `ACLNN_ERR_RUNTIME_ERROR` | API内部调用NPU Runtime接口异常；继续回溯Runtime内层返回和任务 |
| 561000 | `ACLNN_ERR_INNER` | API内部异常，尚未细分具体机制 |
| 561001 | `ACLNN_ERR_INNER_INFERSHAPE_ERROR` | 内部输出shape推导错误 |
| 561002 | `ACLNN_ERR_INNER_TILING_ERROR` | 内部kernel tiling异常 |
| 561003 | `ACLNN_ERR_INNER_FIND_KERNEL_ERROR` | 查找kernel异常；原说明把未安装算子二进制包列为可能原因，不是唯一原因 |
| 561101 | `ACLNN_ERR_INNER_CREATE_EXECUTOR` | 内部创建aclOpExecutor失败；原说明的操作系统异常只是可能原因 |
| 561102 | `ACLNN_ERR_INNER_NOT_TRANS_EXECUTOR` | 内部未调用uniqueExecutor ReleaseTo，不等于用户必须手工销毁普通executor |
| 561103 | `ACLNN_ERR_INNER_NULLPTR` | ACLNN API内部出现nullptr异常；区别于161001参数nullptr校验，不能单由此码认定某个输入为空、具体对象或空指针产生原因 |
| 561107 | `ACLNN_ERR_INNER_OPP_PATH_NOT_FOUND` | 未检测到所需ASCEND_OPP_PATH配置，结合实际进程环境核查 |
| 561112 | `ACLNN_ERR_INNER_OPP_KERNEL_PKG_NOT_FOUND` | 没有加载到算子二进制kernel库，结合实际搜索/加载日志定位 |

官方说明对参数及内部异常还给出`aclGetRecentErrMsg`作为取得详细错误消息的接口。
已有对应日志时沿原文分析；只有后续获准复现或修改调用方时才考虑在失败调用后记录
实际返回的详细消息，不声称本次已调用。具体接口名、阶段、版本和加载路径未知时
保留这些缺口。返回码不独立证明kernel已执行、设备异常、某个输入对象为空或某个
构建开关配置错误；修复应对应查到的具体失败对象与契约。

## 来源

[sources.json](aclnn-return-codes/sources.json)记录原路径、Git blob、大小和SHA256。
来源为`https://gitcode.com/cann/opbase.git`，8.5固定提交
`b27e949de1ce29df366a279adf3976f2660e669c`，9beta2固定提交
`ed5bab5da501bc4af61d0518b70f9b3689582a74`。原件逐字节保留，9beta2另有561105宏的
拼写纠正别名；不为统一命名改动原头文件或官方说明。
两版各附原 [8.5许可证](aclnn-return-codes/opbase-v8.5.0/LICENSE) 与
[9beta2许可证](aclnn-return-codes/opbase-v9.0.0-beta.2/LICENSE)，不改标Apache。
