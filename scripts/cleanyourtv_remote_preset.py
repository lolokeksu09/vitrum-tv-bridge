"""Read only a CI-verified theme JSON from a pinned private GitHub main commit.

Does NOT git-pull or execute repository code. This deliberately scopes ongoing
remote layout changes to JSON values understood by the installed launcher.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess

REPO = "lolokeksu09/vitrum-tv-bridge"
PRESET_PATH = "presets/cleanyourtv-boxy/config.json"
CHECK_RUNS = {"verify-preset", "strict-read-only-bridge"}
SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
EXPECTED_DOCK = [
    "com.google.android.youtube.tv",
    "com.vk.tv",
    "com.v2ray.ang",
    "com.tcl.browser",
]
# Only harmless theme-layout fields. No arbitrary shell, package lists, VPN,
# input-key remapping, system/HDMI settings, or wallpaper writes.
BOOL_KEYS = {
    "dock_row", "single_row", "dock_band", "dock_band_all", "dock_glass",
    "dock_even_padding", "dock_title", "fill_dock", "always_show_names",
    "show_greeting", "icon_only_buttons", "icon_only_inputs",
    "show_network_pill", "show_inputs_pill", "wallpaper", "app_glow",
    "ambient_glow", "clock_glow", "focus_overshoot", "advanced_effects",
}
INT_RANGES = {
    "columns": (4, 8),
    "rows_below_dock": (0, 3),
    "dock_opacity": (30, 100),
    "wallpaper_dim": (0, 90),
    "sky_intensity": (0, 100),
}
STRING_KEYS = {"background_color": {"#000000"},
               "glass_style": {"rim", "glass"}}
ALLOWED = BOOL_KEYS | set(INT_RANGES) | set(STRING_KEYS) | {"dock_apps"}


class RemotePresetError(Exception):
    pass


def gh_json(path: str):
    try:
        proc = subprocess.run(["gh", "api", path], capture_output=True,
                              text=True, errors="replace", timeout=35, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RemotePresetError("GitHub API unavailable; no changes") from exc
    if proc.returncode:
        raise RemotePresetError("GitHub API declined verified preset lookup; no changes")
    if len(proc.stdout) > 128_000:
        raise RemotePresetError("GitHub response unexpectedly large")
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise RemotePresetError("GitHub API returned invalid JSON") from exc


def validate(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or len(raw) > 16_384:
        raise RemotePresetError("Preset is missing or oversized")
    try:
        cfg = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RemotePresetError("Preset must be UTF-8 JSON") from exc
    if not isinstance(cfg, dict) or set(cfg) != ALLOWED:
        raise RemotePresetError("Unexpected or missing preset fields")
    if cfg["dock_apps"] != EXPECTED_DOCK:
        raise RemotePresetError("Favorite packages changed")
    for key in BOOL_KEYS:
        if type(cfg[key]) is not bool:
            raise RemotePresetError("Non-boolean theme switch: " + key)
    for key, (minimum, maximum) in INT_RANGES.items():
        if type(cfg[key]) is not int or not minimum <= cfg[key] <= maximum:
            raise RemotePresetError("Invalid numerical theme field: " + key)
    for key, options in STRING_KEYS.items():
        if type(cfg[key]) is not str or cfg[key] not in options:
            raise RemotePresetError("Unsupported theme style field: " + key)
    if cfg["wallpaper"] is not False or cfg["sky_intensity"] != 0:
        raise RemotePresetError("Autonomous mode allows only flat-black no-wallpaper themes")
    if cfg["ambient_glow"] or cfg["app_glow"] or cfg["clock_glow"]:
        raise RemotePresetError("Autonomous mode cannot restore colored glow")
    if cfg["background_color"] != "#000000":
        raise RemotePresetError("AMOLED black background required")
    if not cfg["dock_row"] or cfg["single_row"]:
        raise RemotePresetError("Autonomous mode must show multiple app rows")
    if cfg["rows_below_dock"] < 1:
        raise RemotePresetError("AMOLED mode requires a visible app grid")
    if cfg["dock_title"] or cfg["focus_overshoot"]:
        raise RemotePresetError("Hero title / overshoot forbidden in minimal theme")
    return cfg


def fetch_verified_main() -> tuple[bytes, str]:
    """Only accept exact main SHA, successful check jobs, and its config.json.

    Does not write the user's local repo and never executes downloaded code.
    """
    commit = gh_json("repos/" + REPO + "/commits/main")
    sha = commit.get("sha") if isinstance(commit, dict) else None
    if type(sha) is not str or not SHA.fullmatch(sha):
        raise RemotePresetError("Invalid main commit SHA")
    checks = gh_json("repos/" + REPO + "/commits/" + sha + "/check-runs?per_page=100")
    runs = checks.get("check_runs", []) if isinstance(checks, dict) else []
    passed = {run.get("name") for run in runs if isinstance(run, dict)
              and run.get("status") == "completed"
              and run.get("conclusion") == "success"
              and run.get("head_sha") == sha}
    if not CHECK_RUNS.issubset(passed):
        raise RemotePresetError("Main commit has not passed both theme safety checks")
    result = gh_json("repos/" + REPO + "/contents/" + PRESET_PATH + "?ref=" + sha)
    if not isinstance(result, dict) or result.get("encoding") != "base64":
        raise RemotePresetError("GitHub returned no base64 theme file")
    data = result.get("content")
    if type(data) is not str or len(data) > 32_768:
        raise RemotePresetError("GitHub theme payload has invalid size")
    try:
        raw = base64.b64decode("".join(data.splitlines()), validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise RemotePresetError("Invalid base64 theme content") from exc
    validate(raw)
    return raw, sha
