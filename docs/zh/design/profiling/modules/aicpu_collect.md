# AICPU 数据采集（Device 侧）模块架构

## 1. 模块概述

- **功能介绍**：本模块负责 Device 侧 AICPU（含自定义 AICPU、以及经 AICPU 驱动通道上报的 MC2/HCCL）Profiling 数据的采集与上报。核心是 Device 侧 `libprofimpl.so` 中的 `DevprofDrvAicpu` 单例：向驱动注册采样算子（`halProfSampleRegister`）、管理采集生命周期、启动上报线程，并把 AICPU 附加信息（`MsprofAdditionalInfo`）经 host-move 环形缓冲区或 device-move 驱动通道搬运回 Host。
- **设计目标**：
  - 通过 `MsprofDrvApi` 延迟加载驱动 HAL API；驱动库或符号缺失时按不支持/错误路径降级，不影响通用服务器上的 Host 侧启动。
  - 以单例 + 后台上报线程模型统一管理 AICPU 通道生命周期（注册 / 启动 / 暂停 / 释放）。
  - 兼容两种数据回传路径：host-move「环形缓冲区直搬」（`RunHostMoveMode`）与 device-move「驱动缓冲区上报」（`RunNormalMode`）。
  - 在驱动提供 host-move 能力时，将 AICPU 数据写入共享环形缓冲区，由配套的 Host CPU 消费端继续处理和上报，减少 Ctrl CPU 侧搬运开销；不支持时自动回退到 device-move 路径（原始 device-move mode 为老流程，后续版本可能日落）。

## 2. 使用场景、架构与对外接口

### 2.1 使用场景

本模块面向用户提供一种 Device 侧 AICPU Profiling 数据采集使用场景：用户启动或停止 Profiling 采集，Device 侧采集器完成组件联动和驱动适配后，将数据通过 host-move 或 device-move 路径回传 Host。该使用场景由以下三个协同环节组成：

1. **AICPU 采集启停**：Profiling 启动时通过 `MsprofInit`（`devprof_msprof_api.cpp`）驱动 `DevprofDrvAicpu::AdprofInit` → `Init` → 向驱动注册采样算子；驱动回调 `ProfStartAicpu` 根据能力优先选择 host-move，能力不可用时选择 device-move 驱动通道路径。
2. **组件回调联动**：MC2、HCCL 等组件通过 `MsprofRegisterCallback` 注册命令回调，采集器在 START/STOP 状态切换时统一广播 `MsprofCommandHandle`。
3. **驱动 API 适配**：AICPU 采集器通过 `MsprofDrvApi` 间接调用 `libascend_hal.so` 中的驱动/Profiling 符号；缺库或缺符号时返回不支持/错误码。

## 2.2 架构与组件交互

### 2.2.1 整体设计思路

上层请求经 `DevprofApi` 的 C 导出层进入 `DevprofDrvAicpu`，由 `MsprofDrvApi` 间接调用驱动 HAL API。AICPU 通道由 `DevprofDrvAicpu` 单例负责注册和生命周期管理。驱动支持 host-move 时，设备侧将数据写入共享环形缓冲区，由配套的 Host CPU 消费端继续处理；否则使用 device-move 的设备侧后台上报线程通过驱动通道回传 Host。

### 2.2.2 架构分层图

```mermaid
graph TB
    subgraph HostControl["Host 侧控制方"]
        HC["libprofimpl.so(host) / msprof<br/>Profiling 启停与通道开关"]
    end

    subgraph AicpuCaller["Device 侧数据上报方"]
        DC["aicpu<br/>MC2 / HCCL / AICPU 组件"]
    end

    subgraph Devprof["Device 侧 AICPU 驱动采集器 (dvvp C++)"]
        DAPI["Device libprofimpl.so<br/>devprof_msprof_api.cpp<br/>Msprof* C 导出"]
        DRV["DevprofDrvAicpu 单例<br/>devprof_drv_aicpu.cpp"]
        COMMON["devprof_common.cpp<br/>ProfSendEvent"]
        THREAD["Prof_Reporter 上报线程<br/>host-move / device-move"]
    end

    ADAPTER["MsprofDrvApi<br/>驱动动态加载适配层"]

    subgraph Driver["驱动 / HAL"]
        HAL["libascend_hal.so / Driver<br/>halProfSampleRegister(Ex)<br/>halProfSampleDataReport / halProfQueryAvailBufLen<br/>halEschedQueryInfo / halEschedSubmitEvent"]
    end

    RING["host-move 共享环形缓冲区"]
    CONSUMER["Host CPU 消费端"]

    DC --> DAPI --> DRV
    HC -. "TSD 配置 / 驱动启停与通道开关" .-> DRV
    DRV --> THREAD
    DRV --> COMMON --> ADAPTER
    DRV --> ADAPTER --> HAL
    HAL -. "采集启停回调" .-> DRV
    THREAD -->|"host-move"| RING --> CONSUMER
    THREAD -->|"device-move"| ADAPTER
```

### 2.2.3 核心模块交互图

- **场景一（Host-Move Mode）**

```mermaid
sequenceDiagram
    participant R as runtime
    participant P as libprofimpl.so(host)
    participant D as driver
    participant C as aicpu channel 插件
    participant A as aicpu
    participant DP as libprofimpl.so(device)

    D->>D: halProfInit
    C->>D: 注册 AICPU channel 插件钩子函数

    opt setDevice
        R->>A: TSD open
        A->>D: bind pid
        R->>P: MsprofNotifySetDevice
    end

    opt 启动事件监听线程
        P->>D: halEschedAttachDevice
        P->>D: halEschedCreateGrpEx
        D-->>P: grpId
        P->>D: halEschedSubscribeEvent
        P->>D: halEschedWaitEvent
        P->>R: callback(profSwitch, Hi)
    end

    R->>A: 通过 TSD 发送 profConfig
    A->>DP: MsprofInit(para)
    DP->>D: halProfSampleRegister 注册驱动通道
    DP->>D: halEschedQueryInfo
    D-->>DP: grpId
    DP->>D: halEschedSubmitEvent
    D-->>P: 发送事件
    P->>D: prof_start打开aicpu prof channel
    D->>C: prof start阶段一
    C->>C: 调用halMemAlloc申请内存
    C-->>D: 把地址信息返回给driver
    D-->>DP: prof start(入参新增标记是否支持host搬运，host注册过的通道此参数为true)把地址信息传给device的采集组件
    DP-->>DP: device侧记录地址信息
    DP-->>D: 返回
    D-->>DP: prof start阶段二(不做任何事情)
    DP->>A: 回调通知profiling打开

    loop Str2Id
        A->>DP: MsprofStr2Id
        DP->>DP: 缓存Str2Id信息
        A->>DP: reportdata
        DP->>DP: 写数据到device内存，刷header
    end

    loop sample
        D->>C: sample采集
        C->>C: D2H读出写指针、D2H拷贝数据、H2D写读指针都是同步拷贝(drvMemcpy)
        D->>P: 上报数据
        P->>P: 此阶段不解析数据，直接落盘
    end

    opt resetDevice
        R->>P: notify
        P->>D: prof_stop
        D->>DP: stop(operation flag置pause标记)
        DP->>DP: 上报缓存的str2Id数据
        D->>C: sample
        D->>DP: stop(operation flag置release标记)
        DP->>DP: 清除地址信息，不用释放内存
        D->>C: stop
        C->>C: 清除内存地址信息
        D-->>P: 上报数据
        P-->>P: 从关闭aicpu prof channel后，收到数据后，要解析数据内容，将str2Id信息单独过滤过来，和host的str2Id落到一个文件
    end
```

- **场景二（Device-Move Mode）**

```mermaid
sequenceDiagram
    participant R as runtime
    participant P as libprofimpl.so(host)
    participant D as driver
    participant A as aicpu
    participant DP as libprofimpl.so(device)

    opt setDevice
        R->>A: TSD open
        A->>D: bind pid
        R->>P: MsprofNotifySetDevice
    end

    opt 启动事件监听线程
        P->>D: halEschedAttachDevice
        P->>D: halEschedCreateGrpEx
        D-->>P: grpId
        P->>D: halEschedSubscribeEvent
        P->>D: halEschedWaitEvent
        P->>R: callback(profSwitch, Hi)
    end

    R->>A: 通过 TSD 发送 profConfig
    A->>DP: MsprofInit(para)
    DP->>D: halProfSampleRegister 注册驱动通道
    DP->>D: halEschedQueryInfo
    D-->>DP: grpId
    DP->>D: halEschedSubmitEvent
    D-->>P: 发送事件
    P->>D: prof_start
    D->>DP: start callback
    A->>DP: data

    loop sample
        D->>DP: sample callback
        DP-->>D: data
    end

    opt resetDevice
        R->>P: notify
        P->>D: prof_stop
        D->>DP: stop callback
        DP->>D: halProfSampleDataReport
        DP-->>D: 发送完所有数据
        P-->>R: 返回停止结果
        R->>A: kill aicpu
    end
```

### 2.3 对外接口

本节列出的接口均为 Profiling 在 Device 侧提供的接口。在通用 Device 构建中，这些接口由 `devprof_msprof_api.cpp` 编入 `libprofimpl.so`（CMake 目标 `profimpl_share_device`）对外提供；部分特定产品构建还会编入 `libascend_devprof.so`。Host 侧 `libprofapi.so` 存在部分同名接口，但其实现入口、调用链和功能职责与 Device 侧接口不同；本文仅描述 Device 侧接口，不将 Host 侧同名接口作为本模块对外接口。

| 接口 | 文件位置 | 说明 |
| ---- | -------- | ---- |
| `MsprofInit` | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` | 初始化 AICPU 采集模块，传入 `AicpuStartPara` |
| `MsprofRegisterCallback` | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` | 注册组件命令回调 |
| `MsprofFinalize` | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` | 停止 Device 侧上报并完成模块收尾 |
| `MsprofStr2Id` | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` | 生成字符串对应的 Profiling ID |
| `MsprofReportAdditionalInfo` | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` | 上报单批次 AICPU 附加信息 |
| `MsprofReportBatchAdditionalInfo` | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` | 批量上报 AICPU 附加信息 |
| `MsprofGetBatchReportMaxSize` | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` | 查询批量上报最大字节数 |

## 3. 详细设计

### 3.1 核心流程

#### AICPU 注册与启动流程

```mermaid
flowchart TD
    A["MsprofInit<br/>(devprof_msprof_api.cpp)"] --> B["DevprofDrvAicpu::AdprofInit"]
    B --> C["SetProfConfig(profConfig)"]
    C --> D{"CheckProfilingIsOn?<br/>校验 AICPU_SWITCH / channel_switch"}
    D -- 否 --> E["若已 START 则切 STOP<br/>返回 SUCCESS"]
    D -- 是 --> F{"IsRegister()?"}
    F -- 是 --> G["CommandHandleLaunch 广播<br/>返回 SUCCESS"]
    F -- 否 --> H["Init(para)"]
    H --> I["RegisterDrvChannel<br/>halProfSampleRegister + Ex"]
    I --> J["ProfSendEvent<br/>halEschedSubmitEvent"]
    J --> K["HashData::Init"]
    K --> L["返回 PROFILING_CONTINUE"]
    L -.驱动回调.-> M["ProfStartAicpu"]
    M --> N{"is_support_host_move?"}
    N -- 是 --> O["ProfStartHostMove<br/>RecordHostMoveBufferAddresses"]
    N -- 否 --> P["SetSupportHostMove(false)"]
    O --> Q["DeviceReportStart + Start"]
    P --> Q
    Q --> R["Prof_Reporter 线程运行 Run()"]
```

**流程步骤说明**：

1. `AdprofInit` 无条件先 `SetProfConfig`，再用 `CheckProfilingIsOn` 校验开关（`AICPU_SWITCH=2` 或 `AICPU_CHANNEL_SWITCH_MASK=0x10000`；MC2/HCCL 数据经 aicpu 驱动通道上报，故需校验 channel switch），并在此初始化 `aicpuAdditionalBuffer_`。
2. 已注册时只需 `CommandHandleLaunch` 广播当前命令；未注册时执行 `Init`：按 `channelId`（`PROF_CHANNEL_AICPU` 或 `PROF_CHANNEL_CUS_AICPU`）选择事件组名，调 `RegisterDrvChannel` 注册采样算子，再 `ProfSendEvent` 通过 `halEschedSubmitEvent` 向 Device 发事件。
3. `RegisterDrvChannel` 先调 `halProfSampleRegister`，再调 `halProfSampleRegisterEx`；后者返回 `DRV_ERROR_NOT_SUPPORT` 时兼容老流程（仍标记 `isRegister_=true`）。
4. 驱动回调 `ProfStartAicpu` 中，若支持 host-move 则记录共享环形缓冲区地址，随后切换 START 状态并拉起 `Prof_Reporter` 上报线程。
5. host-move 是当前数据直搬路径。能力不可用时回退到 device-move 驱动通道路径。AICPU 侧批量写入共享 ring buffer，Host CPU 消费端读取后继续处理、上报。

**关键代码**（标注来源文件）：

```cpp
// 文件位置：collector/dvvp/msprof/devprof/src/devprof_drv_aicpu.cpp
int32_t DevprofDrvAicpu::RegisterDrvChannel(uint32_t devId, uint32_t channelId)
{
    ProfSampleRegisterPara registerPara = {1, {ProfStartAicpu, ProfSampleAicpu, nullptr, ProfStopAicpu}};
    int32_t ret = halProfSampleRegister(devId, channelId, &registerPara);
    ...
    ret = halProfSampleRegisterEx(devId, channelId, &registerPara);
    if (ret == DRV_ERROR_NOT_SUPPORT) { isRegister_ = true; return PROFILING_SUCCESS; }  // 兼容老驱动
    ...
}
```

#### 数据上报流程（Run）

数据流为“采集回调 → Device 侧缓冲 → 搬运/驱动上报 → Host 消费与落盘”。host-move 路径先计算共享环形缓冲区空闲槽位，再完成批量搬运并更新写指针，最后由 Host 消费；device-move 路径再查询驱动可接收空间，批量取出附加信息并提交给驱动。

```mermaid
flowchart LR
    A["aicpu 调用<br/>MsprofReportAdditionalInfo / MsprofReportBatchAdditionalInfo<br/>提交附加信息"] --> B["ReportAdditionalInfo<br/>校验参数并调用 BatchPush"]
    B --> C["Device 侧附加信息缓冲<br/>aicpuAdditionalBuffer_"]
    C --> D{"isSupportHostMove_?"}
    D -- 是 --> E["RunHostMoveMode<br/>host-move 路径"]
    E --> F["DrainBufferToHostMove<br/>循环搬运待上报数据"]
    F --> G["WriteBatchToHostMoveBuffer<br/>写共享环形缓冲并更新写指针"]
    G --> H["Host CPU 消费并继续上报"]
    D -- 否 --> I["RunNormalMode<br/>device-move 路径"]
    I --> J["halProfQueryAvailBufLen + BatchPop<br/>查询驱动空间并取数据"]
    J --> K["halProfSampleDataReport<br/>提交驱动通道"]
    K --> H
```

```mermaid
flowchart TD
    A["Run(errorContext)<br/>Prof_Reporter 线程入口"] --> B{"isSupportHostMove_?"}

    subgraph HostMove["host-move：RunHostMoveMode"]
        direction TB
        H0["校验 hostMoveBuffer_、rptr、wptr"] --> H1["DrainBufferToHostMove<br/>循环直到停止且数据排空"]
        H1 --> H2["AcquireHostMoveFreeSlots<br/>校验 rptr/wptr 并计算空闲槽"]
        H2 --> H2R{"环形区状态?"}
        H2R -- 满，重试 --> H2S["OsalSleep(WAIT_DATA_TIME)<br/>等待 Host CPU 消费"] --> H2
        H2R -- 指针异常，失败 --> H9["返回 PROFILING_FAILED"]
        H2R -- 有空闲槽 --> H3["MoveOneBatchToHostMove<br/>计算批量大小并调用 BatchPop"]
        H3 --> H4["WriteBatchToHostMoveBuffer<br/>memcpy_s 写入共享环形缓冲"]
        H4 --> H5["更新 hostMoveWriteIndex_<br/>发布共享 *hostMoveWptr_"]
        H5 --> H6{"停止且缓冲区空?"}
        H6 -- 否 --> H1
        H6 -- 是 --> H7["HashData::GetHashKeys + FillStr2IdIntoBuffer<br/>封装 str2id 并写入源缓冲"]
        H7 --> H8["再次调用 DrainBufferToHostMove<br/>将 str2id 写入共享环形缓冲"]
    end

    subgraph DeviceMove["device-move：RunNormalMode"]
        direction TB
        N0["检查 stopped_ 和<br/>aicpuAdditionalBuffer_ 状态"]
        N0 -- 缓冲区为空且未停止 --> NS["OsalSleep(WAIT_DATA_TIME)<br/>等待新数据"] --> N0
        N0 -- 有数据 --> N1["MsprofDrvApi::halProfQueryAvailBufLen<br/>查询驱动可接收长度"]
        N1 --> N2["aicpuAdditionalBuffer_.BatchPop<br/>按对齐后的批量大小取数据"]
        N2 --> N3["MsprofDrvApi::halProfSampleDataReport<br/>提交 prof_data_report_para"]
        N3 --> N4["BatchPopBufferIndexShift<br/>推进源缓冲区读索引"]
        N4 --> N5{"停止且缓冲区空?"}
        N5 -- 否 --> N0
        N5 -- 是 --> N6["HashData::GetHashKeys<br/>获取 str2id 键值"]
        N6 --> N7["ReportStr2IdInfoToHost<br/>调用 FillStr2IdIntoBuffer + SendAdditionalInfo"]
        N7 --> N8["SendAdditionalInfo<br/>查询驱动空间并调用 halProfSampleDataReport"]
    end

    B -- 是 --> H0
    B -- 否 --> N0
```

**流程步骤说明**：

1. **公共入口 `Run`**：`DevprofDrvAicpu::Start` 启动 `Prof_Reporter` 线程后进入 `Run`。`Run` 根据 `isSupportHostMove_` 分流：为 true 调用 `RunHostMoveMode`（host-move），为 false 调用 `RunNormalMode`（device-move）。该标志在 `ProfStartAicpu` 中根据驱动回调传入的 `is_support_host_move` 设置。
2. **采集数据进入缓冲**：AICPU 侧调用 `MsprofReportAdditionalInfo` 或 `MsprofReportBatchAdditionalInfo`，最终进入 `DevprofDrvAicpu::ReportAdditionalInfo`；该函数校验数据指针、长度和批量上限后，通过 `aicpuAdditionalBuffer_.BatchPush` 写入 Device 侧 `BlockBuffer<MsprofAdditionalInfo>`。`Prof_Reporter` 从该缓冲区取出数据进行后续上报。

**host-move 路径（`RunHostMoveMode`）**：

1. `RunHostMoveMode` 先检查 `hostMoveBuffer_`、读写指针和缓冲区大小，然后调用 `DrainBufferToHostMove`，持续处理 Device 侧缓冲区，直到停止且数据排空。
2. `DrainBufferToHostMove` 在有数据时调用 `AcquireHostMoveFreeSlots`。该函数读取本地写索引 `hostMoveWriteIndex_` 和 Host CPU 更新的 `*hostMoveRptr_`，校验索引范围并计算可用槽位；保留一个空槽区分“空”和“满”，环形区满时返回重试，指针非法时返回失败。
3. `DrainBufferToHostMove` 调用 `MoveOneBatchToHostMove`，按源缓冲区数据量、环形区空闲槽位和 `MAX_DRV_REPORT_SIZE` 计算本批大小，并通过 `aicpuAdditionalBuffer_.BatchPop` 取得连续数据。
4. `MoveOneBatchToHostMove` 调用 `WriteBatchToHostMoveBuffer`。该函数使用一次或两次 `memcpy_s` 将批量记录写入共享环形缓冲区（跨环回绕时拆成两段），然后更新本地写索引，并以 release 顺序发布共享 `*hostMoveWptr_`，供 Host CPU 消费端读取。
5. 当主数据排空后，`RunHostMoveMode` 从 `HashData::GetHashKeys` 获取 str2id 键值，经 `FillStr2IdIntoBuffer` 切分并写入 `aicpuAdditionalBuffer_`，再调用 `DrainBufferToHostMove` 通过同一 host-move 环形缓冲区发送。

**device-move 路径（`RunNormalMode`）**：

1. `RunNormalMode` 循环检查 `stopped_` 和 `aicpuAdditionalBuffer_` 是否为空；有数据时调用 `MsprofDrvApi::halProfQueryAvailBufLen` 查询驱动通道可接收的字节数。
2. 根据驱动可用长度、`MAX_DRV_REPORT_SIZE` 和 `sizeof(MsprofAdditionalInfo)` 对齐本批大小，再用 `aicpuAdditionalBuffer_.BatchPop` 取得待上报数据；没有可取数据时短暂休眠后重试。
3. 构造 `prof_data_report_para`，调用 `MsprofDrvApi::halProfSampleDataReport` 将数据提交给驱动通道；无论成功或失败，都调用 `aicpuAdditionalBuffer_.BatchPopBufferIndexShift` 推进源缓冲区读索引。
4. 线程停止且附加信息缓冲区排空后，调用 `HashData::GetHashKeys` 获取 str2id；非空时通过 `ReportStr2IdInfoToHost` 处理。该函数调用 `FillStr2IdIntoBuffer` 将键值封装为 `MsprofAdditionalInfo`，再调用 `SendAdditionalInfo`，后者循环查询驱动可用空间并通过 `halProfSampleDataReport` 上报。

**关键函数与用途**：

| 函数 | 用途 |
| --- | --- |
| `Run` | 上报线程入口，根据 host-move 能力选择数据路径 |
| `RunHostMoveMode` | 校验 host-move 共享区并完成主数据、str2id 数据排空 |
| `RunNormalMode` | 通过 device-move 驱动通道循环上报附加信息 |
| `RecordHostMoveBufferAddresses` | 保存驱动传入的共享缓冲区、读指针和写指针地址，并初始化指针 |
| `DrainBufferToHostMove` | 循环从 Device 缓冲搬运数据到共享环形缓冲区 |
| `AcquireHostMoveFreeSlots` | 校验环形区读写索引并计算可写槽位 |
| `MoveOneBatchToHostMove` | 从源缓冲取一批数据并调用批量写入函数 |
| `WriteBatchToHostMoveBuffer` | 处理环形回绕、拷贝记录并发布共享写指针 |
| `ReportAdditionalInfo` | 校验附加信息并写入 `aicpuAdditionalBuffer_` |
| `BatchPush` | 将生产侧附加信息写入 Device 侧缓冲区 |
| `BatchPop` | 从 `aicpuAdditionalBuffer_` 获取连续待上报数据 |
| `BatchPopBufferIndexShift` | 数据提交后推进源缓冲区读索引 |
| `halProfQueryAvailBufLen` | 查询 device-move 驱动通道可接收空间 |
| `halProfSampleDataReport` | 向 device-move 驱动通道提交一批数据 |
| `FillStr2IdIntoBuffer` | 将 str2id 键值切分并封装为附加信息记录 |
| `ReportStr2IdInfoToHost` / `SendAdditionalInfo` | 封装并发送停止阶段缓存的 str2id 信息 |

### 3.2 核心机制详解

本节同时说明数据上报、线程协作和性能优化机制；批量上报与 host-move 直搬优先用于降低小包调用和设备侧拷贝开销。

#### 类职责与线程

```mermaid
classDiagram
    class DevprofDrvAicpu {
        <<singleton + thread>>
        -devId_ uint32_t
        -channelId_ uint32_t
        -isSupportHostMove_ bool
        -aicpuAdditionalBuffer_ BlockBuffer~MsprofAdditionalInfo~
        +Init(para) int32_t
        +Start() int32_t
        +Stop() int32_t
        +Run(context) void
        +ReportAdditionalInfo(flag, data, length) int32_t
        +RunHostMoveMode() void
        +RunNormalMode() void
    }

    class Singleton~DevprofDrvAicpu~ {
        <<基类>>
        +instance() DevprofDrvAicpu
    }

    class Thread {
        <<基类>>
        +Start() int32_t
        +Stop() int32_t
        #Run(context) void
    }

    class MsprofDrvApi {
        <<singleton>>
        +halProfSampleRegister()
        +halProfSampleRegisterEx()
        +halProfQueryAvailBufLen()
        +halProfSampleDataReport()
        +halEschedQueryInfo()
        +halEschedSubmitEvent()
    }

    class BlockBuffer~MsprofAdditionalInfo~ {
        <<Device侧缓冲>>
        +BatchPush(data, length)
        +BatchPop(size, stopped)
        +BatchPopBufferIndexShift(ptr, size)
    }

    class DevprofMsprofApi {
        <<devprof_msprof_api.cpp C导出>>
        +MsprofInit()
        +MsprofRegisterCallback()
        +MsprofReportAdditionalInfo()
        +MsprofReportBatchAdditionalInfo()
        +MsprofFinalize()
        +MsprofStr2Id()
    }

    class DevprofCommon {
        <<devprof_common.cpp 公共函数>>
        +ProfSendEvent()
    }

    class AicpuUserProfileBufferInfo {
        <<共享缓冲区描述>>
        +buffer_base_user_va
        +buffer_size
        +buffer_write_ptr_user_va
        +buffer_read_ptr_user_va
    }

    DevprofDrvAicpu --|> Singleton~DevprofDrvAicpu~
    DevprofDrvAicpu --|> Thread
    DevprofDrvAicpu *-- BlockBuffer~MsprofAdditionalInfo~ : 持有
    DevprofMsprofApi ..> DevprofDrvAicpu : 转发 API 调用
    DevprofDrvAicpu ..> MsprofDrvApi : 调用驱动适配接口
    DevprofDrvAicpu ..> DevprofCommon : 调用 ProfSendEvent
    DevprofDrvAicpu ..> AicpuUserProfileBufferInfo : 记录 host-move 地址
```

| 类/线程 | 职责 |
| --- | --- |
| `DevprofMsprofApi` | 表示 `devprof_msprof_api.cpp` 中的 Device 侧 C 导出层，将初始化、回调注册和数据上报请求转发给 `DevprofDrvAicpu`。 |
| `DevprofDrvAicpu` | AICPU 采集核心单例，管理驱动通道注册、采集生命周期、组件回调和 `Prof_Reporter` 线程，并选择 host-move/device-move 上报路径。 |
| `Thread` / `Prof_Reporter` | `Thread` 提供启动、停止和 `Run` 执行框架；`DevprofDrvAicpu` 继承该类后以 `Prof_Reporter` 线程执行两种数据上报路径。 |
| `BlockBuffer<MsprofAdditionalInfo>` | 暂存 AICPU 产生的附加信息，支持生产侧批量入队以及上报线程批量取数和推进读索引。 |
| `MsprofDrvApi` | 延迟加载 `libascend_hal.so`，封装驱动 Profiling/HAL 符号并提供统一调用入口。 |
| `DevprofCommon` / `AicpuUserProfileBufferInfo` | `DevprofCommon` 提供 `ProfSendEvent`；`AicpuUserProfileBufferInfo` 描述 host-move 共享缓冲区及读写指针地址。 |

##### 线程构成与启动关系

本架构涉及的线程及执行上下文如下。表中“启动组件”表示实际创建或启动该线程的组件，而不是数据流中调用该线程处理结果的组件。

| 线程/执行上下文 | 所属侧 | 启动组件及入口 | 主要作用 | 适用场景 |
| --- | --- | --- | --- | --- |
| 驱动事件监听线程 | Host | Host 侧 `libprofimpl.so` 中的 `ProfAicpuJob::Init` 调用 `ProfDrvEvent::SubscribeEventThreadInit`，由 `OsalCreateTaskWithThreadAttr` 创建，入口为 `EventThreadHandle` | 查询 Device PID，attach Device，创建/查询事件组，订阅并通过 `halEschedWaitEvent` 等待 Device 侧 AICPU 通道就绪事件；收到事件后触发 `CollectionJobRun` 启动采集任务 | host-move、device-move 共用 |
| `ChannelPoll` 驱动通道轮询线程 | Host | Host 侧 `libprofimpl.so` 中的 `ProfChannelManager::Init` 创建 `ChannelPoll` 并调用 `ChannelPoll::Start`，最终调用基类 `Thread::Start` | 调用 `DrvChannelPoll` 轮询已就绪的 Profiling 驱动通道，并把对应通道分发给 `ChannelReader` | host-move、device-move 共用 |
| Channel 读取工作线程池 | Host | `ChannelPoll::Start` 创建并启动 `ThreadPool`；`ProfAicpuJob::Process` 通过 `AddReader` 注册 AICPU 通道对应的 `ChannelReader` 任务 | 并发执行 `ChannelReader::Execute`，从驱动通道读取 AICPU 数据并交给后续上传/落盘流程 | host-move、device-move 共用 |
| `ChannelBuffer` 缓冲线程 | Host | `ChannelPoll::Start` 创建 `ChannelBuffer` 并调用 `ChannelBuffer::Start` | 为通道读取任务准备和周转数据缓冲，解耦驱动通道读取与后续处理 | host-move、device-move 共用 |
| `Prof_Reporter` 数据上报线程 | Device | Device 侧 `libprofimpl.so` 中，驱动执行 `ProfStartAicpu` 回调后调用 `DevprofDrvAicpu::Start`，由基类 `Thread::Start` 启动 | 进入 `DevprofDrvAicpu::Run`；host-move 时执行 `RunHostMoveMode` 写共享环形缓冲区，device-move 时执行 `RunNormalMode` 调用驱动上报接口 | host-move、device-move 共用，但运行时二选一 |
| AICPU channel 插件采样/消费执行上下文 | Host CPU/driver | 由 driver 的 Profiling sample 调度机制触发 AICPU channel 插件；具体线程创建实现在 driver/插件侧，不在 runtime 仓中 | host-move 时读取共享写指针和环形缓冲区数据，更新读指针，并将数据继续送入 Host 侧 Profiling 通道 | 仅 host-move |

AICPU、MC2、HCCL 等组件在各自已有的业务线程或回调执行上下文中调用 `MsprofReportAdditionalInfo`、`MsprofReportBatchAdditionalInfo` 等接口生产数据；这些线程由对应业务组件管理，不是本 Profiling 模块新建的线程，因此不计入本模块线程数量。

#### 性能优化机制

- 批量上报：附加信息按固定上限批量弹出并提交，减少驱动调用次数。
- host-move 直搬：通过共享环形缓冲区批量写入 Host 内存，减少设备侧中间拷贝，同时减少 Ctrl CPU 侧的数据搬运开销，降低 Ctrl CPU 负载。
- 驱动 API 弱依赖：采用延迟加载和符号解析，避免对驱动库形成链接期硬依赖。
- 回调补发：组件晚注册时仅补发当前启动状态，避免遗漏和重复广播。

#### 命令回调广播（ModuleRegisterCallback / CommandHandleLaunch）

**设计思想**：采集器集中管理组件回调，在采集状态切换时向已注册组件广播命令；组件在采集已启动后注册时补发当前启动状态，避免状态丢失和重复广播。

#### 附加信息缓冲与批量上报（aicpuAdditionalBuffer_）

**设计思想**：附加信息先进入有界环形缓冲区，由生产侧批量写入、上报线程批量取出并提交，降低频繁小包上报的开销；字符串标识信息采用同一缓冲和批处理机制。

### 3.3 模块职责划分

| 子模块 | 职责 | 位置 |
| ------ | ---- | ---- |
| Msprof C 导出接口 | 对外暴露 `Msprof*` 接口（Init/Finalize/Report/Register） | `collector/dvvp/msprof/devprof/src/devprof_msprof_api.cpp` |
| DevprofDrvAicpu | AICPU 采集核心：驱动注册、上报线程、host-move、命令回调 | `collector/dvvp/msprof/devprof/src/devprof_drv_aicpu.{cpp,h}` |
| 驱动 API 适配 | 延迟加载 `libascend_hal.so`，解析驱动/Profiling 符号并在缺失时降级 | `collector/dvvp/driver/devmgmt/msprof_drv_api.cpp` / `.h` |
| devprof 公共 | `ProfSendEvent`（`halEschedSubmitEvent`）、`AicpuUserProfileBufferInfo` 结构 | `collector/dvvp/msprof/devprof/src/devprof_common.cpp` / `include/devprof_common.h` |

### 3.4 核心数据结构

```mermaid
classDiagram
    class Singleton~DevprofDrvAicpu~
    class Thread
    class DevprofDrvAicpu {
        -volatile bool stopped_
        -uint32_t devId_, channelId_
        -volatile uint64_t profConfig_
        -bool isRegister_, isSupportHostMove_
        -uint8_t* hostMoveBuffer_
        -volatile uint32_t* hostMoveWptr_/hostMoveRptr_
        -atomic~uint32_t~ hostMoveWriteIndex_
        -BlockBuffer~MsprofAdditionalInfo~ aicpuAdditionalBuffer_
        -MsprofCommandHandle command_
        -map~uint32_t,set~ProfCommandHandle~~ moduleCallbacks_
        +Init(AicpuStartPara*) int32
        +Start()/Stop() int32
        +AdprofInit(AicpuStartPara*) int32
        +ModuleRegisterCallback(id, handle) int32
        +CommandHandleLaunch() void
        +DeviceReportStart()/DeviceReportStop() void
        +ReportAdditionalInfo(flag, data, len) int32
        +SendAdditionalInfo() int32
        #Run(Context&) void
        -RunHostMoveMode()/RunNormalMode() void
    }
    Singleton~DevprofDrvAicpu~ <|-- DevprofDrvAicpu
    Thread <|-- DevprofDrvAicpu

    class AicpuUserProfileBufferInfo {
        +uint32_t buffer_size
        +uint64_t buffer_base_user_va
        +uint64_t buffer_read_ptr_user_va
        +uint64_t buffer_write_ptr_user_va
    }
    DevprofDrvAicpu ..> AicpuUserProfileBufferInfo : host-move
```
