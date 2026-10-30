# mstx API Usage Example

<!-- md-trans-meta sourceCommit=8f95822dca0f79ee6cdfc5ef7922b93196aa30eb translatedAt=2026-10-10T12:15:36.727Z pushedAt=2026-10-15T11:03:50.965Z -->

The code provided in this section is only an example and is not complete. To obtain the complete sample code, perform the following steps:

1. Ensure that the Ascend-cann-toolkit package is installed.

   <!-- npu="950,A3,910b,910,310p,310b" id1 -->
   See [CANN Software Installation](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/920/softwareinst/instg/instg_0000.html?OS=openEuler&InstallType=netyum).
   <!-- end id1 -->
2. The mstx API sample code is integrated in the Ascend-cann-toolkit package at $\{INSTALL\_DIR\}/tools/mstx/samples.

   Replace \$\{INSTALL\_DIR\} with the file storage path after CANN software installation. If the software is installed as the root user, the default file storage path is /usr/local/Ascend/cann.
3. Use the sample according to the README file in the path.

The following is an example of using the mstx API to perform a collection operation:

```cpp
aclrtContext context_;
aclrtStream stream_;

// 1. Initialize AscendCL
aclError ret = ACL_ERROR_NONE;
ret = aclInit(nullptr);
if (ret != ACL_SUCCESS) {
    ERROR_LOG("aclInit failed");
    return FAILED;
}

// 2. Apply for runtime management resources, including setting the device for computation, creating a context, and creating a stream
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

// 3. Add instrumentation code at the code location where you want to measure the elapsed time, for example, add instrumentation before and after model execution to obtain the model execution time.
mstxRangeId rangeId = mstxRangeStartA("model execute", nullptr); // Set the second input parameter to nullptr to record only the host-side range duration (applicable to pure host-side code segments); set a valid stream to record both the host-side and the corresponding device-side duration (applicable to dispatching compute tasks or communication tasks).
ret = aclmdlExecute(modelId, input, output); // Sample code for executing the model.
mstxRangeEnd(rangeId);

// 4. The instrumentation data in step 3 belongs to the default domain. You can call the mstx domain-related APIs to create a custom domain and specify the domain for instrumentation.
mstxDomainHandle_t selfDomain = mstxDomainCreateA("self_domain");
mstxRangeId domainRangeId = mstxDomainRangeStartA(selfDomain, "model execute", nullptr);
ret = aclmdlExecute(modelId, input, output); // Sample code for executing the model.
mstxDomainRangeEnd(selfDomain, domainRangeId);

// 5. Release the runtime management resources.

// 6. Deinitialize AscendCL.
```
