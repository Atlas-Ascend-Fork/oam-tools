# Tool Introduction

<!-- md-trans-meta sourceCommit=38db658ea4f8dfa2b0e1aaf6e53782372ffc7974 translatedAt=2026-10-10T12:06:44.362Z pushedAt=2026-10-15T10:36:15.614Z -->

## Applicable Scenarios

In distributed training scenarios, developers can use this tool to test the functional correctness and performance of HCCL (Huawei Collective Communication Library) collective communication.

This tool supports only network performance tests that implement collective communication based on the HCCL single-operator API.

## Environment Preparation

- The compilation and running of the HCCL performance test tool depend on the CANN development kit package (Ascend-cann-toolkit) and the operator package (Ascend-cann-ops). Therefore, before using this tool, ensure that the relevant CANN software packages have been deployed in the environment.

- The source code of the HCCL performance test tool is stored in the \$\{INSTALL_DIR\}/tools/hccl_test path. \$\{INSTALL_DIR\} must be replaced with the file storage path after the CANN software is installed. For example, when installed as the root user, the default file storage path is /usr/local/Ascend/cann.

## Supported Products

<!-- npu="950" id5 -->
Ascend 950PR&950DT series
<!-- end id5 -->

<!-- npu="A3" id4 -->
Atlas A3 series
<!-- end id4 -->

<!-- npu="910b" id3 -->
Atlas A2 series
<!-- end id3 -->

<!-- npu="910" id2 -->
Atlas Training series
<!-- end id2 -->

<!-- npu="310p" id1 -->
Atlas Inference series
<!-- end id1 -->

## Constraints

  <!-- npu="950" id8 -->
- For the Ascend 950PR&950DT series, the HCCL performance test tool supports a cluster networking scenario with up to 32K communication ranks.
  <!-- end id8 -->
  <!-- npu="A3" id7 -->
- For the Atlas A3 series, the HCCL performance test tool supports a cluster networking scenario with up to 32K communication ranks.

  For the AlltoAll and AlltoAllV operators, the HCCL performance test tool supports a cluster networking scenario with up to 8K communication ranks.
  <!-- end id7 -->
  <!-- npu="910b" id6 -->
- For the Atlas A2 series, the HCCL performance test tool supports a cluster networking scenario with up to 32K communication ranks.
  <!-- end id6 -->
  <!-- npu="910" id9 -->
- For Atlas training products, the HCCL performance test tool supports cluster networking scenarios with a maximum of 4096 communication ranks.
  <!-- end id9 -->

## Background

Collective communication bandwidth refers to "algorithm bandwidth", that is, "the amount of data divided by the time consumed when executing a collective communication operation".

For example, when an allreduce operation is performed on 8 cards in a single server, the "amount of data" divided by the "time consumed to complete allreduce" is the algorithm bandwidth of the allreduce operator.

When testing with the HCCL performance test tool, the bandwidth data refers to the "algorithm bandwidth".

The main factors affecting algorithm bandwidth are: the physical bandwidth of the communication link and the orchestration implementation of the communication algorithm itself.
