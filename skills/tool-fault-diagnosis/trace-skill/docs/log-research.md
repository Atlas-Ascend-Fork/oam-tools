# CANN Log Sources and Local Sample Assessment

This note records the official log-source reference and the read-only assessment of the local sample at `C:/Users/ad/Downloads/log_159052`. It is intended to define what evidence is available for the fault-chain view and what is still missing for a complete Host/Device call trace.

## Primary Reference

- Huawei Ascend official log reference: <https://www.hiascend.com/document/detail/zh/canncommercial/latest/maintenref/logreference/logreference_0001.html>
- Repository log model and examples: [`skills/tool-fault-diagnosis/eval-skill/references/log-spec.md`](../skills/tool-fault-diagnosis/eval-skill/references/log-spec.md)

## Official Classification

The Huawei Ascend CANN 9.0.0 log introduction classifies logs by producer and purpose:

- **System logs** are produced on the Device. Control CPU system logs include kernel logs and user-space system-process logs and reflect the overall AI processor state. Non-Control CPU system logs cover areas such as low power, Task Scheduler, and ISP.
- **Application logs** are produced while an AI application runs. Host-side records include AscendCL, GE, Runtime, and HCCL output; Device-side application records include AI CPU process output.
- **Trace logs** are a separate mechanism. Software-stack maintenance information is retained in memory and written to a file when a program errors or exits, reducing runtime file-write overhead.

The official common record format is `[Level] ModuleName(PID,PName):DateTimeMS [FileName:LineNumber]LogContent`, where `DateTimeMS` is `yyyy-mm-dd-hh:mm:ss.fff.zzz` and includes millisecond and microsecond fields. This format describes a record timestamp; it does not by itself prove that independently generated Host and Device records share a calibrated clock.

## Local Sample Inventory

The sample contains 54 files under the failure package, including:

- Host application `plog` files under `log/run/plog` and `log/debug/plog`.
- Device runtime logs under `slog/dev-os-0/run/device-os`.
- Device event logs under `slog/dev-os-0/run/event`.
- Device debug logs under `slog/dev-os-0/debug/device-0`.
- Host kernel logs under `slog/host/host_kernel.log`.
- Device messages, `slogd` logs, device information, and `system_info/event_sched` snapshots.

The transmitted sample does not include the original Host `syslog` because it was removed for size reasons. Treat that file as an optional supplementary source, not as a prerequisite for the first trace parser.

## Evidence Found

### Host application evidence

The `plog` sample contains full timestamps with microsecond precision, process IDs, thread IDs in some records, component names such as `RUNTIME`, `OP`, `DRV`, and concrete error messages. It contains a clear error cluster around `RUNTIME` context validation and `MemCopySync`, including `EE1018` and device error information.

This is sufficient to produce Host-side error events and a component-level failure timeline.

### Device and driver evidence

The Device runtime and event logs contain `devid/device_id`, event IDs, node types, severity, assertion state, event descriptions, and host-notification records. The Host kernel log contains device lifecycle and driver events with `dev_id`, `host_pid`, `dev_pid`, queue identifiers such as `sq_id/cq_id`, and both wall-clock and monotonic timestamps.

The `event_sched` snapshots expose microsecond-oriented fields and task-related columns, but the inspected sample is primarily a point-in-time diagnostic snapshot. Several tables are empty or contain only headers/abnormal records, so they cannot by themselves reconstruct every task span.

### Clock-domain evidence

The sample demonstrates that Device location does not imply one timestamp convention. The Host `plog`, Host Kernel log, and Device OS runtime log contain 2026 wall-clock values, while the Device debug and some Device event records use `1970-01-01` with boot-relative-looking values. Other Device event records in the same file use 2026 wall-clock values. A parser must therefore classify clock source per record or source file and must not discard the date or merge records solely by their rendered time-of-day.

## Requirements Assessment

| Requirement | Assessment |
| --- | --- |
| Device logs are present | Yes |
| Host/Device fault propagation can be shown | Yes, for observed events and driver/message propagation |
| Microsecond timestamps are available | Yes, but clock domains and timestamp formats differ |
| Component call chain can be fully reconstructed | Not yet proven for this sample |
| Host/Device concurrency can be shown | Partially; event points and driver activity are available, matched execution spans are incomplete |
| `task_id`/`stream_id`-based correlation | `task_id`-like fields appear in diagnostic snapshots, but the inspected `plog` sample has no usable `stream_id` and no complete matched task lifecycle |
| Host `syslog` evidence | Not assessed; the file was omitted from the transmitted sample |

## Implication for the First Implementation

This sample is suitable for the first parser and fault-chain prototype if the output is explicitly labelled as an evidence-backed fault timeline. It is not sufficient as the sole acceptance fixture for a full component call-sequence diagram with duration bars and reliable Host/Device concurrency.

The implementation should therefore preserve:

1. the original timestamp and clock source;
2. wall-clock and monotonic/boot-relative timestamps separately;
3. evidence provenance at event and edge level;
4. an explicit distinction between an observed event, a correlated call span, and an inferred relationship.

A stronger call-trace acceptance fixture should additionally include a normal or failed operator execution with matched Host and Device records carrying `task_id`, `stream_id`, `device_id`, and start/end or equivalent duration information.

## Whether `syslog` Is Needed

Request the omitted `syslog` when the diagnosis needs to verify Host-level OOM, process termination, kernel/driver reset, PCIe faults, or an OS-level crash boundary. It is lower priority when the goal is only to correlate application `plog` with Device execution, because the current package already contains Host Kernel, Device runtime, Device event, and message logs.
