#!/usr/bin/env python3
"""Fixed, opt-in CleanYourTV maintenance actions on the owner's Skyworth BOXY.

This module deliberately has NO arbitrary shell or package disable/uninstall path.
Theme writes use the pinned official upstream tools/theme.sh only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

MODEL = "4K Android TV Box"
TV = "192.168.0.160:5555"
PKG = "com.gathin.tvhome"
HOME = "com.gathin.tvhome/.MainActivity"
SHA = "d11bd68c9ac45b2fb38480941586d17930137e9d"
ROOT = Path(__file__).resolve().parent.parent
PRESET = ROOT / "presets/cleanyourtv-boxy/config.json"
OFFICIAL = Path.home() / ".cache/cleanyourtv-official-v3.5.0"
BACKUPS = Path.home() / "cleanyourtv-backups"
RECEIPT = BACKUPS / "latest-theme-receipt.json"
REMOTE = "/sdcard/Android/data/com.gathin.tvhome/files"
THEME_URI = "content://com.gathin.tvhome.theme/config.json"
DOCK = ["com.google.android.youtube.tv", "com.vk.tv",
        "com.v2ray.ang", "com.tcl.browser"]


class MaintenanceError(Exception):
    pass


def run(argv: list[str], timeout: int = 30, env=None, binary=False, okay=False):
    try:
        proc = subprocess.run(argv, capture_output=True, text=not binary,
                              env=env, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MaintenanceError("Command failed or timed out: " + argv[0]) from exc
    if proc.returncode and not okay:
        stderr = proc.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise MaintenanceError(argv[0] + " returned " + str(proc.returncode)
                               + ": " + stderr.strip()[-240:])
    return proc.stdout


def adb(*args, timeout=30, binary=False, okay=False):
    return run(["adb", "-s", TV, *args], timeout=timeout,
               binary=binary, okay=okay)


def home_resolver():
    raw = adb("shell", "cmd", "package", "resolve-activity", "--brief",
              "-a", "android.intent.action.MAIN",
              "-c", "android.intent.category.HOME")
    return raw.strip().splitlines()[-1].strip() if raw.strip() else ""


def disabled_packages():
    return sorted(x.strip() for x in adb("shell", "pm", "list",
                                         "packages", "-d").splitlines()
                  if x.strip().startswith("package:"))


def device_guard():
    state = adb("get-state").strip()
    model = adb("shell", "getprop", "ro.product.model").strip()
    maker = adb("shell", "getprop", "ro.product.manufacturer").strip().lower()
    sdk = adb("shell", "getprop", "ro.build.version.sdk").strip()
    if (state != "device" or model != MODEL or "skyworth" not in maker
            or sdk != "30"):
        raise MaintenanceError("Target mismatch or unauthorized BOXY; no changes")
    if not adb("shell", "pm", "path", PKG).strip().startswith("package:"):
        raise MaintenanceError("CleanYourTV APK absent; no changes")
    if home_resolver() != HOME:
        raise MaintenanceError("CleanYourTV not current HOME; no changes")
    return {"model": model, "manufacturer": maker, "sdk": sdk}


def check_preset():
    try:
        raw = PRESET.read_bytes()
        cfg = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise MaintenanceError("Official-format BOXY preset missing or invalid") from exc
    if (cfg.get("dock_apps") != DOCK or cfg.get("columns") != 4
            or cfg.get("background_color") != "#000000"
            or cfg.get("wallpaper") is not False):
        raise MaintenanceError("Unexpected BOXY preset changes; refusing to apply")
    return cfg, hashlib.sha256(raw).hexdigest()


def home_focus():
    raw = adb("shell", "dumpsys", "window", "windows", timeout=30)
    return any(PKG + "/" in line for line in raw.splitlines()
               if "mCurrentFocus=" in line)


def probe():
    state = device_guard()
    disabled = disabled_packages()
    resolution = adb("shell", "wm", "size").strip()
    density = adb("shell", "wm", "density").strip()
    vendor_notes = []
    for package in ("com.oem.qa", "com.oemservice",
                    "com.sdt.rcuotaActivity", "com.sdt.remotecontrolota"):
        pkg = adb("shell", "dumpsys", "package", package, timeout=30, okay=True)
        labels = [x.strip()[:140] for x in pkg.splitlines()
                  if any(term in x for term in
                         ("Service Resolver Table:", "Activity Resolver Table:",
                          "Receiver Resolver Table:", "versionName=", "versionCode="))]
        vendor_notes.append(package + ": " +
                            (", ".join(labels[:4]) or "component roles unconfirmed"))
    return "\n".join([
        "BOXY_PROBE_OK",
        "Model: " + state["model"],
        "Android SDK: " + state["sdk"],
        "HOME: " + home_resolver(),
        "HOME focused: " + str(home_focus()),
        "Display: " + resolution + " / " + density,
        "Disabled packages: " + str(len(disabled)),
        "Unknown OEM candidates (READ ONLY):",
        *vendor_notes,
        "No package, settings or firmware changes.",
    ])


def backup_theme():
    os.umask(0o077)
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    BACKUPS.chmod(0o700)
    folder = BACKUPS / ("theme-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    folder.mkdir(mode=0o700)
    (folder / "disabled-before.txt").write_text(
        "\n".join(disabled_packages()) + "\n", encoding="utf-8")
    (folder / "home-before.txt").write_text(home_resolver() + "\n", encoding="utf-8")
    (folder / "screen-before.png").write_bytes(
        adb("exec-out", "screencap", "-p", binary=True))
    try:
        # A directory may not exist if no theme has previously been applied.
        existing = adb("shell", "ls", "-d", REMOTE, okay=True).strip()
        if existing == REMOTE:
            dest = folder / "existing"
            dest.mkdir()
            run(["adb", "-s", TV, "pull", REMOTE, str(dest)], timeout=80)
            files = list(dest.rglob("*"))
            if not files or not any(x.is_file() for x in files):
                raise MaintenanceError("Theme directory exists but backup is empty")
        else:
            # Verify it is absent, rather than merely inaccessible.
            output = adb("shell", "test", "-e", REMOTE, okay=True)
            if output.strip():
                raise MaintenanceError("Cannot establish current theme state")
    except MaintenanceError:
        raise
    return folder


def prepare_upstream():
    if not OFFICIAL.is_dir():
        OFFICIAL.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--branch", "v3.5.0",
             "https://github.com/Gathin23/cleanyourtv.git",
             str(OFFICIAL)], timeout=120)
    commit = run(["git", "-C", str(OFFICIAL), "rev-parse", "HEAD"]).strip()
    if commit != SHA:
        raise MaintenanceError("Upstream official v3.5.0 pin mismatch; refusing theme")
    # A pristine commit hash is not enough if someone edited local tracked files.
    dirty = run(["git", "-C", str(OFFICIAL), "diff", "--name-only",
                 "HEAD", "--", "tools/theme.sh"]).strip()
    official_script = OFFICIAL / "tools/theme.sh"
    if dirty or official_script.is_symlink() or not official_script.is_file():
        raise MaintenanceError("Local official theme.sh is modified or unavailable")
    exe = OFFICIAL / "tools/venv/bin/python"
    if not exe.is_file():
        run([sys.executable, "-m", "venv", str(OFFICIAL / "tools/venv")], timeout=80)
    run([str(exe), "-m", "pip", "install", "-r",
         str(OFFICIAL / "tools/requirements.txt"),
         "--disable-pip-version-check"], timeout=180)
    return official_script


def theme_command(script: Path, action: str, timeout=210):
    env = os.environ.copy()
    env["TV_HOST"] = "192.168.0.160"
    env["TV_ADB_BINARY"] = shutil.which("adb") or "adb"
    return run(["bash", str(script), action], env=env, timeout=timeout)


def restore_theme(script: Path, folder: Path):
    configs = list((folder / "existing").rglob("config.json"))
    if configs:
        restore = folder / "restore"
        restore.mkdir(exist_ok=True)
        source = configs[0].parent
        shutil.copy2(configs[0], restore / "config.json")
        for name in ("wallpaper.jpg", "wallpapers"):
            path = source / name
            if path.is_file():
                shutil.copy2(path, restore / name)
            elif path.is_dir():
                shutil.copytree(path, restore / name)
        theme_command(script, str(restore))
    else:
        theme_command(script, "--reset")


def theme():
    device_guard()
    expected, digest = check_preset()
    before = disabled_packages()
    folder = backup_theme()
    script = prepare_upstream()
    applied = False
    try:
        # Official theme.sh may write an overlay before reporting a later failure.
        applied = True
        theme_command(script, str(PRESET.parent))
        current = adb("exec-out", "content", "read", "--uri", THEME_URI,
                      binary=True, timeout=35)
        if json.loads(current.decode("utf-8")) != expected:
            raise MaintenanceError("ThemeProvider readback did not match requested preset")
        adb("shell", "input", "keyevent", "3")
        time.sleep(2)
        if home_resolver() != HOME or not home_focus():
            raise MaintenanceError("CleanYourTV no longer active HOME")
        if disabled_packages() != before:
            raise MaintenanceError("Unexpected change in disabled packages")
        after = adb("exec-out", "screencap", "-p", binary=True)
        if not after.startswith(b"\x89PNG\r\n\x1a\n"):
            raise MaintenanceError("Screen verification capture missing")
        (folder / "screen-after.png").write_bytes(after)
    except (MaintenanceError, UnicodeDecodeError, ValueError) as exc:
        if applied:
            try:
                restore_theme(script, folder)
            except MaintenanceError as recovery:
                raise MaintenanceError(str(exc) + "; RESTORE FAILED: " +
                                       str(recovery) + "; backup: " + str(folder)) from exc
        raise MaintenanceError(str(exc) + "; previous theme restored if it was changed") from exc

    receipt = {"time": dt.datetime.now(dt.timezone.utc).isoformat(),
               "theme_sha256": digest, "backup": str(folder),
               "disabled_before": before, "home": HOME}
    RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    RECEIPT.chmod(0o600)
    return ("CLEAN_YOUR_TV_THEME_OK\n"
            "Pinned official Gathin23 v3.5.0 theme.sh applied.\n"
            "Black four-column dock config verified by ThemeProvider readback.\n"
            "HOME focused; system package states unchanged.\n"
            "Private backup: " + str(folder) + "\n"
            "Reboot not yet performed; use separate reboot_check.")


def reboot_check():
    device_guard()
    if not RECEIPT.is_file():
        raise MaintenanceError("No completed local theme receipt; no reboot")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    created = dt.datetime.fromisoformat(receipt["time"])
    now = dt.datetime.now(dt.timezone.utc)
    if not dt.timedelta() <= now - created <= dt.timedelta(hours=3):
        raise MaintenanceError("Theme receipt expired; no reboot")
    cfg, digest = check_preset()
    if receipt["theme_sha256"] != digest or receipt["home"] != HOME:
        raise MaintenanceError("Theme provenance changed; no reboot")
    if disabled_packages() != receipt["disabled_before"]:
        raise MaintenanceError("Package state changed; no reboot")

    # Confirm theme still readable before deliberate reboot.
    themed = adb("exec-out", "content", "read", "--uri", THEME_URI, binary=True)
    if json.loads(themed.decode("utf-8")) != cfg:
        raise MaintenanceError("Theme disappeared; no reboot")
    adb("reboot", timeout=15, okay=True)
    time.sleep(12)
    online = False
    for _ in range(42):
        run(["adb", "connect", TV], timeout=8, okay=True)
        if run(["adb", "-s", TV, "get-state"], timeout=8, okay=True).strip() == "device":
            online = True
            break
        time.sleep(3)
    if not online:
        raise MaintenanceError("REBOOT_UNVERIFIED: ADB did not return; "
                               "check physical TV and re-enable network debugging if needed")
    device_guard()
    adb("shell", "input", "keyevent", "3")
    time.sleep(2)
    if not home_focus():
        raise MaintenanceError("REBOOT_WARNING: Home window not confirmed")
    if disabled_packages() != receipt["disabled_before"]:
        raise MaintenanceError("REBOOT_WARNING: package disabled-state differs")
    return ("REBOOT_VERIFIED\nCleanYourTV remains default HOME and focused.\n"
            "Disabled-package state is unchanged.\n"
            "Backup: " + receipt["backup"] + "\n"
            "ADB remains on for recovery. Physical remote and HDMI require on-device testing.")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("probe", "theme", "reboot"):
        raise MaintenanceError("Fixed operations only: probe, theme, reboot")
    operation = sys.argv[1]
    if operation == "probe":
        print(probe())
    elif operation == "theme":
        print(theme())
    else:
        print(reboot_check())


if __name__ == "__main__":
    try:
        main()
    except (MaintenanceError, OSError, ValueError, KeyError) as exc:
        print("MAINTENANCE_ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
