# Functions and Restrictions of the msaicerr Tool

The msaicerr tool can be used to analyze AI Core errors, parse dump files, and check the environment.

- This tool can be used only for  **local analysis**. So the environment where the tool is deployed must be the same as the environment where logs are stored \(operating environment\).
- This tool depends on  **python 3.7.5 or later versions**. You need to pre-install python in the environment where this tool is installed.
<!-- npu="310b" id1 -->
- This tool  **cannot be used**  in  Ascend RC  mode.
<!-- end id1 -->
- This tool cannot analyze AI Core errors of the following operators:
    - MatmulAllReduce operators
    - MatmulAllReduceAddRmsNorm
    - MatmulAllReduceInplaceAddRmsNorm
    - AllGatherMatmul
    - MatmulReduceScatter
    - GroupedMatmulAllReduce
    - MemSet
    - NonMaxSuppressionBucketize
