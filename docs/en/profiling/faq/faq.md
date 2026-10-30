# FAQs

<!-- md-trans-meta sourceCommit=884f75dea9caf8601927afda108db547fa775b78 translatedAt=2026-10-10T12:17:02.963Z pushedAt=2026-10-15T10:09:34.381Z -->

## Memory Cannot Be Released When msprof Is Enabled to Collect Performance Data

**Symptom**

On openEuler 24.03 LTS-SP4, when msprof is enabled to collect performance data, the host-side memory usage increases, and the host memory is not restored after data collection stops.

**Cause**

Memory fragmentation in the glibc arena prevents memory from being returned to the OS in a timely manner, causing memory usage to increase.

**Solution**

Set the `MALLOC_ARENA_MAX` environment variable to a value smaller than the system default (number of CPU cores × 8) to cap the number of arenas.

This solution may affect model performance. Use it based on the actual situation.
