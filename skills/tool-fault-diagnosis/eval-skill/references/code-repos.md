# CANN 相关代码仓库地址

> 本文档列出 Ascend NPU / CANN 生态相关的主要开源代码仓库，用于日志分析时溯源算子实现、查找 bug fix 或参考 API 定义。

优先使用已提供的源码和版本记录；先核对现场版本与源码的 release/tag/commit，再解释实现。离线诊断不自行下载源码或补采现场。下列克隆示例仅用于已获准的源码获取，源码版本不匹配时只作参考，不能当作现场实现证据。

离线需要实现原文时，先查[包内公开源码](offline-source-code.md)的仓库/revision范围，
使用具名符号和文件检索；包中源码不能自动代表当前实际加载二进制。

## 华为官方仓库（GitCode）

| 仓库 | 地址 | 说明 |
|------|------|------|
| CANN Community | https://gitcode.com/cann/community | CANN 社区版入口，含 roadmap 和问题追踪 |
| MindSpore | https://gitcode.com/mindspore/mindspore | MindSpore 框架主仓，含 graph engine 代码 |
| MindSpeed | https://gitcode.com/Ascend/MindSpeed | 大模型训练加速库（基于 Megatron-LM） |
| PyTorch Adapter (torch_npu) | https://gitcode.com/Ascend/pytorch | PyTorch NPU 适配层，含算子注册和前端 |
| ModelZoo | https://gitcode.com/Ascend/modelzoo | 官方模型样例（含大量算子用法参考） |
| 算子库 (op-plugin) | https://gitcode.com/Ascend/op-plugin | torch_npu 算子插件，C++/Python 实现 |

## 按组件与 API 选择入口

需要核对实现时，从日志中的完整API名、组件及源文件进入对应项目，先查接口契约，
再查匹配revision的校验和实现。以下固定提交用于追溯导航依据，不代表现场版本。

| 日志或 API 所属层 | 公开入口 | 优先核对 |
| --- | --- | --- |
| GE图编译、模型加载与执行 | [cann/ge](https://gitcode.com/cann/ge/tree/0c84d0638fbcec224db5add5a4bcd8c6be78018f) | README的文档/架构入口，再按实际组件和源文件定位；GE有独立组件仓 |
| Ascend C API、算子开发接口 | [cann/asc-devkit](https://gitcode.com/cann/asc-devkit/tree/a5e1e7815d50e62f6f1814e0928a443234ce4cf6) | README目录中的`include/`声明与`impl/`实现，按basic/adv/c_api等实际API层区分 |
| Transformer类算子的ACLNN/torch接口 | [cann/ops-transformer](https://gitcode.com/cann/ops-transformer/tree/fd659b0e14917ece0c995e7096b48b7999254b94) | README中的[ACLNN接口索引](https://gitcode.com/cann/ops-transformer/blob/fd659b0e14917ece0c995e7096b48b7999254b94/docs/zh/op_api_list.md)、[torch接口索引](https://gitcode.com/cann/ops-transformer/blob/fd659b0e14917ece0c995e7096b48b7999254b94/docs/zh/torch_api_list.md)及[目录结构](https://gitcode.com/cann/ops-transformer/blob/fd659b0e14917ece0c995e7096b48b7999254b94/docs/zh/install/dir_structure.md)；区分包装、参数检查、tiling与kernel |
| AscendCL Runtime数值返回码 | [本技能Runtime原件与来源](return-codes.md) | 完整API、返回类型、现场版本和内层错误；公开码义不指定上游原因 |
| ACLNN executor生命周期 | [opbase契约与实现出处](crash-reference.md#aclnn-executor-所有权与重复释放) | 普通/复用模式、调用次序及所有权；按该页固定版本核对 |

获准获取源码时，按项目发布说明选择与现场CANN配套的tag/commit；不能把当前
master或以上固定导航提交当作现场实现。仅有包装层返回值时，继续回溯实际失败层。
已有原文足以解释的约束可直接交付；缺源码时保留对应缺口，不以下载源码作为诊断门槛。

## GitHub 镜像 / 社区仓库

| 仓库 | 地址 | 说明 |
|------|------|------|
| torch_npu (GitHub) | https://github.com/Ascend/pytorch | PyTorch NPU 适配（GitHub 镜像） |
| apex for Ascend | https://github.com/Ascend/apex | 混合精度训练工具适配 |
| DeepSpeed for Ascend | https://github.com/Ascend/DeepSpeed | DeepSpeed NPU 适配 |

## 代码定位技巧

### 根据算子名称查找源码

```bash
# 在 op-plugin 仓库中搜索算子实现
# 例如查找 MatMulV2
git clone https://gitcode.com/Ascend/op-plugin.git
grep -r "MatMulV2" op-plugin/op_plugin/ops/ --include="*.cpp" -l

# 查找 torch_npu 中的算子注册
grep -r "matmul" pytorch/torch_npu/csrc/ --include="*.cpp" -l
```

### 根据错误码查找处理逻辑

```bash
# 在 MindSpore 中搜索错误码定义
grep -r "ACL_ERROR_RT_MEMORY_ALLOCATION" mindspore/ --include="*.h" -l

# 在已有且允许读取的 CANN 安装目录中查找；路径以现场记录为准
cann_install_path=/path/to/actual/cann
rg -l --glob '*.h' 'ACL_ERROR_' "$cann_install_path"
```

### 查找 CANN 本地头文件

```bash
# 以下路径只是示例，替换为已有材料确认的安装目录
cann_install_path=/path/to/actual/cann
ls "$cann_install_path/include/"

# ACL 错误码定义
rg -n 'ACL_ERROR_' "$cann_install_path/include/acl/acl_base.h"

# GE 相关接口
ls "$cann_install_path/include/ge/"
```

## 文档参考

| 文档 | 地址 |
|------|------|
| CANN 官方文档 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/overview |
| ACL API 参考 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/apiref/appdevgapi |
| HCCL API 参考 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/apiref/hcclapi |
| npu-smi 工具指南 | https://www.hiascend.com/document/detail/zh/canncommercial/85RC1/devtools/npusmi |

## 版本配套核对

从已有环境信息、安装记录和实际加载日志分别取得 CANN、PyTorch、torch_npu 的完整版本；保留 `.postN`、RC/补丁后缀和包类型，不能只按主次版本匹配。题面与实际加载版本冲突时分别记录，缺失项保持未知，不把本页示例当作当前环境。

按对应发布版的 [Ascend/pytorch 官方兼容表](https://github.com/Ascend/pytorch/blob/master/COMPATIBILITY.en.md) 核对配套及支持平台；历史版本看对应 release/分支的表。不要由本页推导全局升级或固定版本推荐，发现不配套也仍须与当前失败机制关联。

本次资料核验使用官方 `Ascend/pytorch` 的 [固定提交兼容表](https://github.com/Ascend/pytorch/blob/2c8682df9271e545e7f50f8c45e2395563a05483/COMPATIBILITY.en.md)，用于追溯修订依据，不代表所有现场都使用该提交或其最新配套。源码搜索及修复参考同样须核对现场版本和源码 revision。
