# 规格约束

HCCL性能测试工具会按照用户配置的单个计算节点参与训练的NPU个数来启动Device，假设单个计算节点上参与训练的NPU个数为x（即-p后的参数取值为x），则会从Device ID为0的设备开始，连续启动x个Device。

  <!-- npu="950" id5 -->
- 针对Ascend 950PR&950DT系列产品，“-p”支持配置为1\~8，启动的Device ID为：\[0, p-1\]。
  <!-- end id5 -->
  <!-- npu="A3" id4 -->
- 针对Atlas A3系列产品：“-p”支持配置为1\~16，启动的Device ID为：\[0, p-1\]。
  <!-- end id4 -->
  <!-- npu="910b" id3 -->
- 针对Atlas A2系列产品：“-p”支持配置为1\~8，启动的Device ID为：\[0, p-1\]
  <!-- end id3 -->
  <!-- npu="910" id2 -->
- 针对Atlas训练系列产品：“-p”支持配置为1、2、4、8，启动的Device ID为：\[0, p-1\]。
  <!-- end id2 -->
  <!-- npu="310p" id1 -->
- 针对Atlas推理系列产品，不同的测试命令支持的最大“-p”值不同：
  - all_gather_test：“-p”最大支持配置为32，启动的Device ID为：\[0, p-1\]。
  - all_gatherv_test：“-p”最大支持配置为4，启动的Device ID为：\[0, p-1\]。
  - all_reduce_test：“-p”最大支持配置为32，启动的Device ID为：\[0, p-1\]。
  - alltoall_test：“-p”最大支持配置为4，启动的Device ID为：\[0, p-1\]。
  - alltoallv_test：“-p”最大支持配置为4，启动的Device ID为：\[0, p-1\]。
  - reduce_scatter_test：“-p”最大支持配置为32，启动的Device ID为：\[0, p-1\]。
  - reduce_scatterv_test：“-p”最大支持配置为4，启动的Device ID为：\[0, p-1\]。
  <!-- end id1 -->
