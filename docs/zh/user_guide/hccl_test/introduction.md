# 工具介绍

## 适用场景

分布式训练场景下，开发者可以通过此工具测试HCCL（Huawei Collective Communication Library）集合通信的功能正确性以及性能。

此工具仅支持基于HCCL单算子API实现集合通信的网络性能测试。

## 环境准备

- HCCL性能测试工具的编译运行依赖CANN开发套件包（ Ascend-cann-toolkit）与算子包（Ascend-cann-ops），所以使用此工具前请确保环境中已部署好CANN相关软件包。

- HCCL性能测试工具源码存放\$\{INSTALL_DIR\}/tools/hccl_test路径下，\$\{INSTALL_DIR\}请替换为CANN软件安装后文件存储路径。以root用户安装为例，安装后文件默认存储路径为：/usr/local/Ascend/cann。

## 支持的产品

<!-- npu="950" id5 -->
Ascend 950PR&950DT系列产品
<!-- end id5 -->

<!-- npu="A3" id4 -->
Atlas A3系列产品
<!-- end id4 -->

<!-- npu="910b" id3 -->
Atlas A2系列产品
<!-- end id3 -->

<!-- npu="910" id2 -->
Atlas训练系列产品
<!-- end id2 -->

<!-- npu="310p" id1 -->
Atlas推理系列产品
<!-- end id1 -->

## 约束说明

  <!-- npu="950" id8 -->
- 针对Ascend 950PR&950DT系列产品，HCCL性能测试工具最大支持集群组网包含32K的通信rank的场景。
  <!-- end id8 -->
  <!-- npu="A3" id7 -->
- 针对Atlas A3系列产品，HCCL性能测试工具最大支持集群组网包含32K的通信rank的场景。

  针对AlltoAll、AlltoAllV算子，HCCL性能测试工具最大支持集群组网包含8K的通信rank的场景。
  <!-- end id7 -->
  <!-- npu="910b" id6 -->
- 针对Atlas A2系列产品，HCCL性能测试工具最大支持集群组网包含32K的通信rank的场景。
  <!-- end id6 -->
  <!-- npu="910" id9 -->
- 针对Atlas训练系列产品，HCCL性能测试工具最大支持集群组网包含4096的通信rank的场景。
  <!-- end id9 -->

## 背景知识

集合通信带宽指的是“算法带宽”，即“执行某集合通信操作时的数据量/耗时”。

例如单机8卡做allreduce操作，则“数据量”除以“做完allreduce的耗时”就是allreduce算子执行的算法带宽。

使用HCCL性能测试工具进行测试时，带宽数据即指的“算法带宽”。

影响算法带宽的主要因素有：通信链路物理带宽以及通信算法自身的编排实现。
