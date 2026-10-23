# 公开 AscendCL Runtime 数值返回码

先核报错组件、调用 API、返回类型、原始数值与现场版本。以下原件仅定义公开
AscendCL Runtime 返回码，不能代表全部内部 Runtime、Driver、HCCL 或业务状态。
原始头文件保留英文注释；只读取与现场数值对应的行及必要上下文。

| 公开发布来源 | 本地原件 | 固定提交 |
| --- | --- | --- |
| Runtime v8.5.0 | [rt_error_codes_v8_5_0.h](return-codes/runtime-v8.5.0/include/external/acl/error_codes/rt_error_codes_v8_5_0.h) | `c741ed4fd53c92c455545ba8f17f45bda5440942` |
| Runtime v9.0.0-beta.2 | [rt_error_codes_v9_0_0_beta_2.h](return-codes/runtime-v9.0.0-beta.2/include/external/acl/error_codes/rt_error_codes_v9_0_0_beta_2.h) | `330a3a72dd0836546e6a5d13d6ac2802f065b6ac` |

从本技能目录按精确数字 token 查询，例如：

```bash
rg -n '(^|[[:space:]])107002([[:space:]]|$)' references/return-codes/runtime-*/include/external/acl/error_codes/rt_error_codes_*.h
```

确认宏名称与原注释后，沿实际 API 和原文解释当前失败及传播。比如两份公开原件均
将 `107002` 定义为 `ACL_ERROR_RT_CONTEXT_NULL`，注释为当前 Context 为空；这支持
该命名空间的直接失败含义，不自行证明从未设置、线程切换、已销毁或最早故障原因。
资源归属、线程和创建/切换/销毁次序仍由现场记录及其版本契约确认。

现场版本不明时并列已核来源，不自动选择一个发布标签作为部署版本。两版定义相同
也不证明商用/开发分支一致；未命中仅表示这些头文件没有该定义。负值、十六进制、
位组合或跨层转换需先确认返回类型及转换规则，不机械套用十进制常量。Shell退出码、
进程信号、`HcclResult`、内部`RT_ERROR_*`或Driver数值另查各自版本；不自动生成E码。

[来源清单](return-codes/sources.json)保留原路径、Git blob、大小和SHA256，两个版本
各有原 [8.5许可证](return-codes/runtime-v8.5.0/LICENSE) 与
[9beta2许可证](return-codes/runtime-v9.0.0-beta.2/LICENSE)。原件未改为技能的Apache许可。
这些资料提供定义检索，不是错误码到现场根因或通用修复动作的规则表。
