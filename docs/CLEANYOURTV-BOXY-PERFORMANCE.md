# BOXY / CleanYourTV: frame-time measurement

## Purpose

Measure **actual drawing latency**, not infer speed from theme changes. Current
installed design: Modern TV OS black AMOLED, six columns, two visible rows,
`reduced_motion=true`. CleanYourTV upstream v3.5.0.

This feature does not install an APK, clear app data, kill processes, alter
animation scale, change Android settings, or publish screenshots.

## Authorization and execution

Request issue: `TVBRIDGE/v2 cleanyourtv_perf_probe` with the exact body

```json
{"v":2,"op":"cleanyourtv_perf_probe","args":{}}
```

Local bridge **must** have `--allow-maintenance --allow-control`. Only the
repository owner can submit an issue, and only the preinstalled, fixed local
probe is executed. The operation is not available to old Termux agents until
the operator performs a **one-time** local `git pull --ff-only` and restarts
the bridge. Do not dynamically download executable code from GitHub Issues.

The probe verifies the fixed BOXY model, Android SDK, installed CleanYourTV
and default Home; it checks that Home is actually in the foreground. It then
resets only the `dumpsys gfxinfo com.gathin.tvhome` **statistics**, sends six
pairs of remote `RIGHT/LEFT` (without OK/SELECT, POWER or BACK), and reads
`dumpsys gfxinfo ... framestats`. It rechecks foreground before every key,
aborting if an app takes focus. Nothing is saved to GitHub except a bounded
aggregate summary.

No activity is launched and no system packages are changed. The benchmark
can briefly move which icon is highlighted. Run only when nobody is actively
navigating the TV.

## Published summary (four anonymous numbers)

```text
PERF_V1 frames=27 p50_ms=12.0 p95_ms=18.0 slow16_pct=22.2
```

*This line is an **example format, not a real device reading**.*

- `frames`: counted complete app frames. At least 8 required.
- `p50_ms`, `p95_ms`: nearest-rank median and 95th percentile of
  `FrameCompleted - IntendedVsync` across accepted Android UI frame records.
- `slow16_pct`: percentage taking **more than 16.67 ms**. The cutoff is
  a reference for 60 Hz screens, **not** an authoritative Android jank count.
- If the device returns too few records or invalid output, the operation
  fails and no performance claim is made.

The public GitHub bridge publishes **only** the exact strict numeric schema
for a successful `cleanyourtv_perf_probe`. It withholds every diagnostic
string, package/path/device info, non-perf operation result or malformed data.
No images are collected or uploaded.

## Interpretation and next optimization

Compare repeated runs under the same TV resolution, loaded apps and Home
state. A single sample is not a claim of frame stability, FPS or input latency.

`gfxinfo` captures the launcher UI's drawing path, **not the startup latency**
of YouTube/VK/etc. Launch speed depends on the target app, Android process
state, network, storage and cold/warm startup; do not change Android global
animation scales or remove packages to mask it.

After collecting a baseline, inspect the upstream app grid / launch path and
measure a named app separately **only with a separate opt-in protocol**,
keeping launch actions and results private. No new APK should be built or
installed until an actual bottleneck is identified and tested.

## Safety tests

`tests/test_cleanyourtv_perf_probe.py` exercises valid CSV, malformed data,
insufficient frames, preflight failure, foreground switch while measuring,
and the exact twelve D-pad key events. Public comment tests reject injected
paths or appended text.

After code merge, both exact-`main` CI checks must be green before any
other theme change. No requirement to run a theme update just to profile it.
