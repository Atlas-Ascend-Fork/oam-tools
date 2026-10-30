# Specifications and Constraints

<!-- md-trans-meta sourceCommit=38db658ea4f8dfa2b0e1aaf6e53782372ffc7974 translatedAt=2026-10-10T12:10:31.142Z pushedAt=2026-10-15T10:40:35.233Z -->

The HCCL performance test tool starts devices based on the number of NPUs participating in training on a single compute node configured by the user. Assuming that the number of NPUs participating in training on a single compute node is x (that is, the value of the parameter following -p is x), the tool starts x consecutive devices starting from the device with device ID 0.

  <!-- npu="950" id5 -->
- For Ascend 950PR&950DT product series, "-p" can be set to a value from 1 to 8, and the started device IDs are: \[0, p-1\].
  <!-- end id5 -->
  <!-- npu="A3" id4 -->
- For Atlas A3 product series: "-p" can be set to a value from 1 to 16, and the started device IDs are: \[0, p-1\].
  <!-- end id4 -->
  <!-- npu="910b" id3 -->
- For Atlas A2 product series: "-p" can be set to a value from 1 to 8, and the started device IDs are: \[0, p-1\]
  <!-- end id3 -->
  <!-- npu="910" id2 -->
- For Atlas training product series: "-p" can be set to 1, 2, 4, and 8, and the started device IDs are: \[0, p-1\].
  <!-- end id2 -->
  <!-- npu="310p" id1 -->
- For Atlas inference product series, the maximum supported "-p" value varies with the test command:
  - all_gather_test: The maximum supported "-p" configuration is 32, and the started device IDs are: \[0, p-1\].
  - all_gatherv_test: The maximum supported "-p" configuration is 4, and the started device IDs are: \[0, p-1\].
  - all_reduce_test: The maximum supported "-p" configuration is 32, and the started device IDs are: \[0, p-1\].
  - alltoall_test: The maximum supported configuration of "-p" is 4, and the started device IDs are: \[0, p-1\].
  - alltoallv_test: The maximum supported configuration of "-p" is 4, and the started device IDs are: \[0, p-1\].
  - reduce_scatter_test: The maximum supported configuration of "-p" is 32, and the started device IDs are: \[0, p-1\].
  - reduce_scatterv_test: The maximum supported configuration of "-p" is 4, and the started device IDs are: \[0, p-1\].
  <!-- end id1 -->
