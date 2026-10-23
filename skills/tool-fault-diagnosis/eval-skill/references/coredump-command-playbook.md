# CANN Coredump Command Playbook

本页提供命令模板，执行范围遵守 [处理流公共约定](fault-flows/common-flow.md#1-输入与证据保护)。已有日志诊断不执行本页的现场采集、附加进程或业务复跑命令；仅分析已提供的材料，缺失结果记录为证据边界。离线解析已有 core/符号前核对版本与适用参数，避免修改生产库目录。

## 1. Baseline Triage

```bash
file <core_file>
file <exe_file>
readelf -n <core_file> 2>/dev/null | sed -n '1,160p'
strings <core_file> | rg -i 'cann|ascend|runtime|driver|firmware|version|segmentation|sigsegv|sigabrt' | head -80
```

Capture environment:

```bash
uname -a
ldd <exe_file>
ulimit -c
cat /proc/sys/kernel/core_pattern
npu-smi info
```

If CANN environment variables are needed:

```bash
source <cann_install_path>/latest/bin/setenv.bash
which asys
asys --help
```

## 2. Isolated Symbol Layout

Never overwrite runtime `.so` files under live CANN install paths. Create a separate analysis root:

```bash
mkdir -p <analysis_root>/symbols/lib64
mkdir -p <analysis_root>/debug
cp -a <debug_so_or_symbol_files> <analysis_root>/symbols/lib64/
```

Record build IDs and symbol quality:

```bash
readelf -n <analysis_root>/symbols/lib64/<libname>.so | rg -A4 'Build ID'
file <analysis_root>/symbols/lib64/<libname>.so
nm -an <analysis_root>/symbols/lib64/<libname>.so | head
```

If `.debug` files are split from `.so`, point gdb at the debug directory:

```gdb
set debug-file-directory <analysis_root>/debug
set solib-search-path <analysis_root>/symbols/lib64:<cann_install_path>/latest/lib64:<other_lib_dirs>
```

## 3. Host Core With gdb

Batch collection:

```bash
gdb -q <exe_file> <core_file> \
  -ex 'set pagination off' \
  -ex 'set print frame-arguments all' \
  -ex 'set solib-search-path <analysis_root>/symbols/lib64:<cann_install_path>/latest/lib64:<other_lib_dirs>' \
  -ex 'set debug-file-directory <analysis_root>/debug' \
  -ex 'info files' \
  -ex 'info sharedlibrary' \
  -ex 'info threads' \
  -ex 'thread apply all bt full' \
  -ex 'info registers' \
  -ex 'quit' \
  2>&1 | tee <analysis_root>/gdb_core_analysis.txt
```

Interactive checks:

```gdb
info proc mappings
info sharedlibrary
thread <crash_thread_id>
bt full
frame <frame_no>
info args
info locals
x/16gx $sp
x/16i $pc
```

Useful interpretation:

- `??` frames usually mean missing symbols, unloaded shared libraries, stripped binaries, wrong executable/core pair, or corrupted stack.
- A top frame in `raise`, `abort`, or assertion code often means the real cause is in the caller frames or logs immediately before abort.
- A crash address near `0x0` suggests null dereference; an address in unmapped/high random memory suggests use-after-free, wild pointer, ABI mismatch, or memory corruption.

## 4. CANN asys Coredump

Official command shape:

```bash
asys analyze -r=coredump --exe_file=<exe_file> --core_file=<core_file> --reg=<0|1|2> --symbol=<0|1> --output=<output_dir>
```

Recommended first pass:

```bash
asys analyze -r=coredump \
  --exe_file=<exe_file> \
  --core_file=<core_file> \
  --reg=1 \
  --symbol=1 \
  --output=<analysis_root>/asys
```

Notes:

- `--reg=0` omits registers; `--reg=1` adds one register record per thread; `--reg=2` is more complete but can be slower and consume more Host resources.
- `--symbol=1` keeps original gdb stack lines except `in ?? ()` lines, which helps preserve useful gdb detail.
- The generated Stackcore-style text can be passed into stackcore analysis when needed.

## 5. msnpureport Collection

Run from a writable collection directory on the Host. The tool is installed under the Driver path and can export Device logs/files, commonly including `slog`, `message`, `hisi_logs`, `stackcore`, and version-dependent folders such as `event_sched` or `module_info`.

```bash
mkdir -p <collection_root>
cd <collection_root>
<driver_install_path>/driver/tools/msnpureport report
```

For broader collection, use all/force modes when justified:

```bash
<driver_install_path>/driver/tools/msnpureport report -a
<driver_install_path>/driver/tools/msnpureport report -f
```

If the installed version supports typed export, collect Stackcore only or all logs by type:

```bash
<driver_install_path>/driver/tools/msnpureport report -t 3
<driver_install_path>/driver/tools/msnpureport report -t 0
```

Record the resulting timestamped directory:

```bash
find <collection_root> -maxdepth 2 -type d | sort
find <collection_root>/<timestamp_dir> -maxdepth 3 -type f | sort | tee <analysis_root>/msnpureport_files.txt
```

Constraints to remember:

- Some versions require root or specific deployment modes.
- Do not run from locked directories.
- Avoid mixing old and new exports; start with an empty collection directory when possible.
- Some documentation states the tool is for Ascend EP scenarios; capture deployment form in the report.

## 6. asys Active Collection

Collect CANN toolkit, Host, Device, health, dfx, log, and Stackcore-related evidence without rerunning the workload:

```bash
source <cann_install_path>/latest/bin/setenv.bash
asys collect --tar=True --output=<collection_root>
```

If reproducing the workload is acceptable, wrap the task with `asys launch`:

```bash
source <cann_install_path>/latest/bin/setenv.bash
asys launch --task="<full_reproduction_command>" --tar=True --output=<collection_root>
```

Notes:

- Run as the CANN installation/runtime user unless the environment requires root.
- Use a foreground task command; some versions cannot observe scripts that immediately start the real workload in the background.
- Preserve the generated `software_info.txt`, `hardware_info.txt`, `status_info.txt`, `health_result.txt`, and `dfx/` directories.

## 7. Stackcore Analysis

Single Stackcore file:

```bash
asys analyze -r=stackcore \
  --file=<stackcore_file> \
  --symbol_path=<analysis_root>/symbols/lib64,<cann_install_path>/latest/lib64,<other_symbol_dirs> \
  --output=<analysis_root>/asys_stackcore
```

Directory of Stackcore files:

```bash
asys analyze -r=stackcore \
  --path=<stackcore_dir> \
  --symbol_path=<analysis_root>/symbols/lib64,<cann_install_path>/latest/lib64,<other_symbol_dirs> \
  --output=<analysis_root>/asys_stackcore
```

If `asys` cannot resolve frames, try direct address translation after obtaining module base and offset:

```bash
addr2line -Cfipe <symbolized_so> <relative_pc_or_offset>
readelf -Ws <symbolized_so> | rg '<function_or_near_symbol>'
```

## 8. Log Correlation

Search around the crash time:

```bash
rg -n -i 'error|failed|exception|fault|panic|segmentation|sigsegv|sigabrt|aicore|runtime|acl|driver|device|task|stream' \
  <msnpureport_timestamp_dir> <app_log_dir> | tee <analysis_root>/log_hits.txt
```

Build a timeline:

```bash
rg -n '<yyyy-mm-dd|hh:mm:ss|pid|tid|device_id|stream_id|task_id>' <logs...>
```

Correlate:

- Crash PID/TID and process name.
- Device ID, stream ID, task ID, model/operator name.
- First error before the crash, not just repeated cleanup errors after the crash.
- Version mismatch or symbol mismatch warnings.

## 9. Remote Source Correlation

Prefer remote repository plus exact ref:

```bash
git clone <cann_related_git_url> <source_root>
cd <source_root>
git fetch --all --tags
git checkout <branch_or_tag_or_commit>
git rev-parse HEAD
rg -n '<function_name>|<class_name>|<log_keyword>|<error_code>' .
```

If only local source is available:

```bash
cd <source_root>
git rev-parse HEAD
git status --short
rg -n '<function_name>|<class_name>|<log_keyword>|<error_code>' .
```

When reporting, label each source mapping as:

- Confirmed by symbols and matching source ref.
- Inferred from stack/module/function names.
- Unconfirmed due to missing symbols, missing source, or version mismatch.

## 10. Fix Recommendation Checklist

Map evidence to likely fix class:

- Null pointer: add ownership/validity checks at boundary and identify why null reached the crashing function.
- Use-after-free/lifetime: audit async callback, stream/task lifetime, model unload, shared object unload, and thread handoff.
- Buffer/offset issue: check tensor shape, workspace size, kernel arguments, device/host memory boundary, and alignment.
- Version/ABI mismatch: align CANN runtime, driver, firmware, debug symbols, executable build, and third-party libraries.
- Concurrency/race: inspect locks, stream synchronization, callback ordering, reference counts, and shutdown paths.
- Device-side fault: correlate Stackcore with slog/black box first error, then map to CANN operator/runtime/driver code.

## 11. Official Documentation Anchors

- `asys analyze -r=coredump`: https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/maintenref/troubleshooting/troubleshooting_0510.html
- `asys analyze -r=stackcore` and `asys collect/launch`: https://www.hiascend.com/document/detail/zh/canncommercial/80RC22/developmentguide/maintenref/troubleshooting/troubleshooting_0095.html
- `msnpureport report`: https://www.hiascend.com/document/detail/zh/canncommercial/80RC22/developmentguide/maintenref/logreference/logreference_0016.html
