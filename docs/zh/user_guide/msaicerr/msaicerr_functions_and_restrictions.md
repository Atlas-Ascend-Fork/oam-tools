# msaicerr工具功能及约束

msaicerr工具可用于分析AI Core Error问题、解析Dump文件、检查环境。

- 该工具仅支持**本地分析使用**，即部署该工具的环境应该和日志所在环境为同一环境（运行环境）。
- 该工具依赖**python3.7.5或以上版本**，在安装该工具的环境中需提前安装python。
<!-- npu="310b" id1 -->
- 该工具**不支持**在Ascend RC形态下使用。
<!-- end id1 -->
- 该工具暂不支持分析以下算子的AI Core Error问题：
  - MatmulAllReduce类算子
  - MatmulAllReduceAddRmsNorm
  - MatmulAllReduceInplaceAddRmsNorm
  - AllGatherMatmul
  - MatmulReduceScatter
  - GroupedMatmulAllReduce
  - MemSet
  - NonMaxSuppressionBucketize
