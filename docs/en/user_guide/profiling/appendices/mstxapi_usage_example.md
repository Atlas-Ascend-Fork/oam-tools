# mstx API Usage Example

<!-- md-trans-meta sourceCommit=f3cf4115ddb0ce33467a62e425af1dd155a6419f translatedAt=2026-11-16T08:53:43.065Z pushedAt=2026-11-16T11:54:26.979Z nl=2 -->

The code provided in this section is only an example and is not complete. To obtain the complete sample code, perform the following steps:

1. Ensure that the Ascend-cann-toolkit package is installed.

   <!-- npu="950,A3,910b,910,310p,310b" id1 -->
   See [*CANN Software Installation*](https://hiascend.com/document/redirect/CannCommunityInstSoftware).
   <!-- end id1 -->
2. The mstx API sample code is integrated in the Ascend-cann-toolkit package at $\{INSTALL\_DIR\}/tools/mstx/samples.

   Replace \$\{INSTALL\_DIR\} with the file storage path after CANN software installation. If the software is installed as the root user, the default file storage path is /usr/local/Ascend/cann.
3. Use the sample according to the README file in the path.

The following is an example of using the mstx API to perform a collection operation:

```cpp
aclrtContext context_;
aclrtStream stream_;

// 1. Initialize AscendCL.
aclError ret = ACL_ERROR_NONE;
ret = aclInit(nullptr);
if (ret != ACL_SUCCESS) {
    ERROR_LOG("aclInit failed");
    return FAILED;
}

// 2. Apply for runtime management resources, including setting the Device used for calculation, creating a Context, and creating a Stream.
ret = aclrtSetDevice(0);
if (ret != ACL_ERROR_NONE) {
    ERROR_LOG("aclrtSetDevice failed");
    return FAILED;
}
ret = aclrtCreateContext(&context_, 0);
if (ret != ACL_ERROR_NONE) {
    ERROR_LOG("acl create context failed");
    return FAILED;
}
ret = aclrtCreateStream(&stream_);
if (ret != ACL_ERROR_NONE) {
    ERROR_LOG("acl create stream failed");
    return FAILED;
}
....

// 3. Add logging code at the code positions where time consumption is to be collected, for example, log before and after executing the model to obtain the model execution time consumption.
mstxRangeId rangeId = mstxRangeStartA("model execute", nullptr); // Set the second input parameter to nullptr to record only the host-side range time consumption (applicable to pure host-side code segments); set a valid stream to record both the host-side and the corresponding device-side time consumption (applicable to dispatching calculation tasks or communication tasks).
ret = aclmdlExecute(modelId, input, output); // Execution model sample code.
mstxRangeEnd(rangeId);

// 4. The logging data in step 3 belongs to the default domain; call the mstx domain-related APIs to create a custom domain and specify the domain for logging.
mstxDomainHandle_t selfDomain = mstxDomainCreateA("self_domain");
mstxRangeId domainRangeId = mstxDomainRangeStartA(selfDomain, "model execute", nullptr);
ret = aclmdlExecute(modelId, input, output); // Execution model sample code.
mstxDomainRangeEnd(selfDomain, domainRangeId);

// 5. Release the runtime management resources.

// 6. Deinitialize AscendCL.
```
