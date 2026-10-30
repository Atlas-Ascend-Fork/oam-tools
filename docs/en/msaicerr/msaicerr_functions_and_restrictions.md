# msaicerr Tool Functions and Constraints

<!-- md-trans-meta sourceCommit=2a887466d2e2283344c9f9e8c9427fce31c3c901 translatedAt=2026-10-10T12:14:00.953Z pushedAt=2026-10-15T10:50:00.467Z -->

The msaicerr tool can be used to analyze AI Core Error issues, parse Dump files, and check the environment.

1. This tool supports **local analysis only**, which means that the environment where the tool is deployed must be the same as the environment where the logs are located (the runtime environment).
2. This tool depends on **Python 3.7.5 or later**. Python must be installed in advance in the environment where the tool is installed.
3. This tool **does not support** use in Ascend RC mode.
4. This tool does not currently support analyzing AI Core Error issues of the following operators:
    - MatmulAllReduce operators
    - MatmulAllReduceAddRmsNorm
    - MatmulAllReduceInplaceAddRmsNorm
    - AllGatherMatmul
    - MatmulReduceScatter
    - GroupedMatmulAllReduce
    - MemSet
    - NonMaxSuppressionBucketize
