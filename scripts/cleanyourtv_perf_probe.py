"""Bounded BOXY launcher frame probe. No screenshots, app launch or arbitrary shell.

Runs only after maintenance.device_guard() confirms the known BOXY and Home.
Only fixed D-pad Left/Right focus moves; no key presses that open an app.
The *only* permitted public result is four anonymous aggregate numbers.
"""
from __future__ import annotations

import math
import re
import time

PKG = "com.gathin.tvhome"
MARKER = "---PROFILEDATA---"
PUBLIC_SUMMARY = re.compile(
    r"PERF_V1 frames=[0-9]{1,5} p50_ms=[0-9]{1,4}\.[0-9] "
    r"p95_ms=[0-9]{1,4}\.[0-9] slow16_pct=[0-9]{1,3}\.[0-9]",
    re.ASCII,
)


class FrameProbeError(ValueError):
    pass


def parse_framestats(raw: str) -> list[float]:
    """Return only completed UI frame durations (ms) from Android gfxinfo CSV.

    FrameCompleted-IntendedVsync is the app's full latency (not pure GPU time).
    Only Flags=0 rows with nonzero, ordered timestamps are accepted.
    """
    if not isinstance(raw, str):
        raise FrameProbeError("Missing Android gfxinfo text")
    pieces = raw.split(MARKER)
    if len(pieces) < 3:
        raise FrameProbeError("Android did not provide framestats CSV")
    values = []
    # Android surrounds each PROFILEDATA block with a start/end marker.
    for block in pieces[1::2]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        header = [cell.strip() for cell in lines[0].split(",")]
        if not {"Flags", "IntendedVsync", "FrameCompleted"}.issubset(header):
            continue
        flag, start, stop = [header.index(field) for field in
                             ("Flags", "IntendedVsync", "FrameCompleted")]
        for line in lines[1:]:
            columns = [cell.strip() for cell in line.split(",")]
            if len(columns) != len(header):
                continue
            try:
                if columns[flag] != "0":
                    continue
                vsync = int(columns[start])
                complete = int(columns[stop])
            except (ValueError, IndexError):
                continue
            if 0 < vsync < complete:
                ms = (complete - vsync) / 1_000_000.0
                if 0 < ms < 2000:
                    values.append(ms)
    return values


def percentile(values: list[float], percentage: int) -> float:
    if not values or not 0 < percentage <= 100:
        raise FrameProbeError("Insufficient frames or invalid percentile")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percentage / 100) - 1)]


def summarize(values: list[float]) -> str:
    if len(values) < 8:
        raise FrameProbeError("Too few recorded Home frames; no latency claim")
    report = ("PERF_V1 frames=" + str(len(values)) +
              " p50_ms=" + f"{percentile(values, 50):.1f}" +
              " p95_ms=" + f"{percentile(values, 95):.1f}" +
              " slow16_pct=" + f"{sum(x > 16.67 for x in values) * 100 / len(values):.1f}")
    if not PUBLIC_SUMMARY.fullmatch(report):
        raise FrameProbeError("Out-of-range anonymous performance summary")
    return report


def measure(adb, device_guard, home_focus, pause=time.sleep) -> str:
    """Profile twelve fixed focus moves, without starting or stopping an app."""
    device_guard()
    if not home_focus():
        raise FrameProbeError("CleanYourTV must be in the foreground")
    adb("shell", "dumpsys", "gfxinfo", PKG, "reset", timeout=30)
    for _ in range(6):
        for key in ("22", "21"):  # RIGHT, LEFT; no SELECT/BACK/POWER.
            if not home_focus():
                raise FrameProbeError("Foreground changed; abort input immediately")
            adb("shell", "input", "keyevent", key, timeout=18)
        pause(0.12)
    if not home_focus():
        raise FrameProbeError("CleanYourTV lost focus during probe")
    pause(0.25)
    raw = adb("shell", "dumpsys", "gfxinfo", PKG, "framestats", timeout=30)
    return summarize(parse_framestats(raw))
