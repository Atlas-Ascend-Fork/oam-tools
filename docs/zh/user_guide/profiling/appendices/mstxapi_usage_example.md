# mstx API使用示例

本节中提供的代码仅为示例，非完整代码，完整样例代码获取请参照如下步骤：

1. 请确保安装Ascend-cann-toolkit包。

   <!-- npu="950,A3,910b,910,310p,310b" id1 -->
   参见[《CANN 软件安装》](https://hiascend.com/document/redirect/CannCommunityInstSoftware)。
   <!-- end id1 -->
2. mstx API样例代码集成在Ascend-cann-toolkit包中，路径为$\{INSTALL\_DIR\}/tools/mstx/samples。

   \$\{INSTALL\_DIR\}请替换为CANN软件安装后文件存储路径。以root用户安装为例，安装后文件默认存储路径为：/usr/local/Ascend/cann。
3. 根据路径下的README文档使用样例。

使用mstx API执行采集操作示例代码如下：

```cpp
aclrtContext context_;
aclrtStream stream_;
 
// 1.AscendCL初始化
aclError ret = ACL_ERROR_NONE;
ret = aclInit(nullptr);
if (ret != ACL_SUCCESS) {
    ERROR_LOG("aclInit failed");
    return FAILED;
}
 
// 2.申请运行管理资源，包括设置用于计算的Device、创建Context、创建Stream
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
 
// 3.在想采集耗时的代码位置添加打点代码，比如在执行模型前后打点，获取模型执行耗时
mstxRangeId rangeId = mstxRangeStartA("model execute", nullptr); // 第二个入参设置nullptr，只记录host侧range耗时(适用于纯host侧代码段)；设置有效的stream，同时记录host侧和对应device侧耗时(适用于下发计算任务或通信任务)
ret = aclmdlExecute(modelId, input, output); // 执行模型样例代码
mstxRangeEnd(rangeId);

// 4.步骤3里的打点数据属于默认domain；可调用mstx domain相关接口，创建自定义domain，并指定domain进行打点
mstxDomainHandle_t selfDomain = mstxDomainCreateA("self_domain");
mstxRangeId domainRangeId = mstxDomainRangeStartA(selfDomain, "model execute", nullptr);
ret = aclmdlExecute(modelId, input, output); // 执行模型样例代码
mstxDomainRangeEnd(selfDomain, domainRangeId);
 
// 5.释放运行管理资源
 
// 6.AscendCL去初始化
```
