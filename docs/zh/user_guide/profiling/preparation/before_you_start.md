# 使用前准备

## 简介

性能调优工具用于采集和分析运行在AI处理器上的AI任务在各运行阶段的关键性能指标，用户可根据输出的性能数据，快速定位软、硬件性能瓶颈，提升AI任务性能分析的效率。

## 环境准备

1. 根据实际用户场景选择CANN相关软件包安装并配置CANN环境变量。
   <!-- npu="950,A3,910b,910,310p,310b" id6 -->
   具体请参见[《CANN 软件安装》](https://hiascend.com/document/redirect/CannCommunityInstSoftware)。
   <!-- end id6 -->

    <!-- npu="950,A3,910b,910,310p,310b" id1 -->
    Ascend EP场景下msprof工具路径为：\$\{INSTALL\_DIR\}/tools/profiler/bin，\$\{INSTALL\_DIR\}请替换为CANN软件安装后文件存储路径。以root用户安装为例，安装后文件默认存储路径为：/usr/local/Ascend/cann。
    <!-- end id1 -->

    <!-- npu="310b" id2 -->
    Ascend RC场景下msprof工具路径为：/var
    <!-- end id2 -->

    <!-- @ref: oam-tools/res/docs/zh/profiling/preparation/before_you_start_res.md#id1 -->
2. 设置公共环境变量。

    安装CANN软件后，使用CANN运行用户进行编译、运行时，需要以CANN运行用户登录环境，执行`source ${INSTALL_DIR}/set_env.sh`命令设置环境变量。\$\{INSTALL\_DIR\}请替换为CANN软件安装后文件存储路径。以root用户安装为例，安装后文件默认存储路径为：/usr/local/Ascend/cann。

3. 设置Python相关环境变量。

    存在多个Python3版本时，以指定python3.7.5为例，请根据实际修改。

    ```sh
    export PATH=/usr/local/python3.7.5/bin:$PATH
    #设置python3.7.5库文件路径
    export LD_LIBRARY_PATH=/usr/local/python3.7.5/lib:$LD_LIBRARY_PATH
    ```

>[!NOTE]说明
>上述环境变量只在当前窗口生效，用户可以将上述命令写入\~/.bashrc文件，使其永久生效，操作如下：
>
>1. 以安装用户在任意目录下执行`vi ~/.bashrc`，在该文件最后添加上述内容。
>2. 执行`:wq!`命令保存文件并退出。
>3. 执行`source ~/.bashrc`使环境变量生效。

## 约束

使用该工具前，请了解相关使用约束：

- 权限约束
  - 用户须自行保证使用最小权限原则（如禁止other用户可写，常见如禁止666、777）。
  - 使用性能分析工具前请确保执行用户的umask值大于等于0027，否则会导致获取的性能数据所在目录和文件权限过大。
  - 出于安全性及权限最小化角度考虑，本工具不应使用root等高权限账户，建议使用普通用户权限执行。
  - 本工具为开发调测工具，不建议在生产环境使用。
  - 本工具依赖CANN和对应驱动软件包，使用本工具前，请先安装CANN和对应驱动软件包，并使用`source`命令执行CANN的set\_env.sh环境变量文件，为保证安全，source后请勿擅自修改set\_env.sh中涉及的环境变量。
  - 请确保性能数据保存在不含软链接的当前用户目录下，否则可能引起安全问题。

  <!-- @ref: oam-tools/res/docs/zh/profiling/preparation/before_you_start_res.md#id2 -->

- 执行约束
  - 不支持在同一个Device同时拉起多个采集任务。也不可同时开启两种及以上性能数据采集方式。举例说明：使用msprof命令行方式启动Profiling时，app中不能通过acl接口启动Profiling数据采集。
    <!-- npu="950" id7 -->
    <br>Ascend 950PR&950DT系列产品场景下，支持同一个Device同时拉起多个task-time采集任务；当aic-mode取值为task-based时，支持同一个Device同时拉起多个aic-metrics采集任务。
    <!-- end id7 -->
  - 不建议性能数据的采集功能与Dump功能同时使用。Dump操作会影响系统性能，如果同时开启采集功能与Dump功能，会造成采集的性能数据指标不准确，启动采集前请关闭数据Dump。

- 数据落盘约束
  - 性能数据采集时间建议在5min以内，并且预留至少20倍于性能原始数据大小的内存和磁盘空间。原始数据大小指采集落盘后的data目录下数据总大小。
  - 执行单个采集任务采集性能数据并落盘时，在打开所有采集项的情况下，需要保证磁盘读写速度，具体规格如下：
    - 仅使用单Device进行推理时，磁盘读写速度不低于50MB/s。
    - 仅使用单个Device进行训练时，磁盘读写速度不低于60MB/s。
    - 多个Device场景下，磁盘读写速度不低于：单个Device磁盘读写速度规格 \* Device数。

  - 采集性能数据过程中如果配置的落盘路径磁盘空间已满，会出现性能数据无法落盘情况，须保证足够的磁盘空间。落盘的性能原始数据可以通过配置--storage-limit参数来预防磁盘空间被占满。
  - 解析性能数据过程中如果配置的落盘路径磁盘或用户目录空间已满，会出现解析失败或文件无法落盘的情况，须自行清理磁盘或用户目录空间。

- 兼容性和场景约束
  - 工具要求Python 3.7.5及以上版本。
  - 调用`aclInit()`接口完成初始化和调用`aclFinalize()`接口完成去初始化，才能获取到完整的性能数据。
  <!-- npu="950,A3,910b,910,310p,310b,IPV350" id5 -->
  - 应用工程开发务必遵循[《应用开发 \(C&C++\)》](https://hiascend.com/document/redirect/cannCommunityadevguide)手册。如果应用程序已调用`aclInit()`接口完成初始化和调用`aclFinalize()`接口导致工具采集流程未正常结束，采集数据会不完整。最后1秒内已采集的数据可能因未及时落盘而丢失，但丢失的数据不大于2M，不影响已落盘的性能数据分析。
  <!-- end id5 -->
  <!-- npu="950,A3,910b,910,310p,310b" id3 -->
  - 使用pyACL API开发的应用工程在通过msprof命令行方式采集性能数据时，不支持在工程Python脚本中打开相对路径文件。Python脚本中包含打开相对路径文件的操作会导致采集性能数据报错。
  <!-- end id3 -->
  <!-- npu="910b,910,310p" id4 -->
  - 昇腾虚拟化实例场景，不支持从容器、虚拟机内发起对SoC的系统性能数据采集（NPU内存占用数据除外）。
  <!-- end id4 -->
