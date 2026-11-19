# FAQs

<!-- md-trans-meta sourceCommit=32702b5a8035e70cb3100e12f8c538ed59ef4c87 translatedAt=2026-11-16T08:56:25.776Z pushedAt=2026-11-17T01:30:02.198Z nl=2 -->

## Memory Cannot Be Released When msprof Is Enabled to Collect Performance Data

**Symptom**

On openEuler 24.03 LTS-SP4, when msprof is enabled to collect performance data, the host-side memory usage increases, and the host memory is not restored after data collection stops.

**Cause**

Memory fragmentation in the glibc arena prevents memory from being returned to the OS in a timely manner, causing memory usage to increase.

**Solution**

Set the `MALLOC_ARENA_MAX` environment variable to a value smaller than the system default (number of CPU cores × 8) to cap the number of arenas.

This solution may affect model performance. Use it based on the actual situation.

## msprof Collection Failure or Non-Zero Exit Code

**Symptom**

The msprof command returns a non-zero exit code, and the command line prompt indicates application exit, export failure, or a log path, without printing "Profiling finished".

**Cause**

- When the application exits with a non-zero code, msprof records a warning and continues export and analysis; the application's own exit code does not directly determine the msprof exit code.
- When the application calls aclprofInit or aclprofStart to configure API collection while msprof tool collection is in progress, error code 100042 is returned. The two Profiling configurations cannot coexist.
- When the timeline or summary export child process exits with a non-zero code, msprof returns a non-zero exit code and does not mask the failure as success.

**Solution**

1. Determine whether collection succeeds based on the msprof command exit code. When the exit code is non-zero, view the command line prompt, the output of the application under test, and the PROF_*/mindstudio_profiler_log/ logs.
2. If the application log contains aclprofInit or aclprofStart returning 100042, remove the in-application API collection configuration, or stop using msprof tool collection, keeping only one Profiling configuration.
3. If an export failure is reported, view mindstudio_profiler_log/msprof_analysis_*.log to confirm the specific error of the export child process.
4. In "An exception has occurred in process ... exit code: N", N is the child process exit code, not the system errno. It should not be diagnosed based on errno messages such as "Exec format error". If "terminated by signal: N" is prompted, N is the signal number that caused the child process to terminate.
