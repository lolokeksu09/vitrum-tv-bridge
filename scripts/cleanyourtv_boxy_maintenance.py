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
import re
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

if __package__:
    from .cleanyourtv_provider_files import ProviderTheme, ProviderError
    from .boxy_minimal_wallpaper import generate as make_wallpaper
else:
    from cleanyourtv_provider_files import ProviderTheme, ProviderError
    from boxy_minimal_wallpaper import generate as make_wallpaper

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
    if (cfg.get("dock_apps") != DOCK or cfg.get("columns") != 6
            or cfg.get("rows_below_dock") != 2
            or cfg.get("background_color") != "#000000"
            or cfg.get("wallpaper") is not False
            or cfg.get("single_row") is not False
            or cfg.get("dock_row") is not True
            or cfg.get("dock_band") is not False
            or cfg.get("dock_title") is not False
            or cfg.get("glass_style") != "rim"
            or cfg.get("app_glow") is not False
            or cfg.get("ambient_glow") is not False
            or cfg.get("clock_glow") is not False
            or cfg.get("sky_intensity") != 0):
        raise MaintenanceError("Unexpected BOXY AMOLED v3 preset; refusing to apply")
    return cfg, hashlib.sha256(raw).hexdigest()


def home_focus():
    """Verify Home using the same WindowManager query as bridge focus_status.

    On BOXY Android TV 11 `dumpsys window windows` omits mCurrentFocus,
    while `dumpsys window` reports it. When the current window is absent,
    require both WindowManager's focused app AND ActivityManager's resumed
    activity to agree; never accept a different foreground window.
    """
    raw = adb("shell", "dumpsys", "window", timeout=30)
    current = next((x for x in raw.splitlines() if "mCurrentFocus=" in x), None)
    if current and "null" not in current.split("mCurrentFocus=", 1)[1].strip().lower():
        return PKG + "/" in current
    focused = next((x for x in raw.splitlines() if "mFocusedApp=" in x), "")
    if PKG + "/" not in focused:
        return False
    activity = adb("shell", "dumpsys", "activity", "activities", timeout=30)
    resumed = next((x for x in activity.splitlines()
                    if "topResumedActivity" in x or "mResumedActivity" in x), "")
    return PKG + "/" in resumed


def verify_home_after_theme(*, pause=time.sleep, tries=8):
    """Wait for a real foreground Home after Android TV activity restart.

    ADB reports app start before WindowManager necessarily reports focused
    activity. Reassert Home between checks if a dream/transition is foreground.
    Never accept a wrong default HOME and never disable the stock launcher.
    """
    if tries < 1 or tries > 12:
        raise MaintenanceError("Invalid Home verification retry limit")
    if home_resolver() != HOME:
        raise MaintenanceError("CleanYourTV is no longer default HOME")
    for attempt in range(tries):
        if home_focus():
            if home_resolver() == HOME:
                return
            raise MaintenanceError("CleanYourTV default HOME changed while verifying")
        if attempt == tries - 1:
            break
        if home_resolver() != HOME:
            raise MaintenanceError("CleanYourTV is no longer default HOME")
        if attempt == 4:
            # On some Android TV ROMs, KEYCODE_HOME alone cannot recover
            # a just-restarted Home activity. Restart its explicit component
            # ONCE without changing the resolver or disabling any package.
            result = adb("shell", "am", "start", "-W", "--user", "0",
                         "-n", HOME, okay=True)
            if "Status: ok" not in result and "Warning: Activity not started" not in result:
                # Keep probing; the final focus check must still be real.
                pass
        elif attempt % 2 == 0:
            adb("shell", "input", "keyevent", "3")
        pause(2)
    raise MaintenanceError(
        "CleanYourTV foreground HOME not confirmed after repeated checks"
    )


def capture_theme_failure_state(folder: Path) -> str:
    """Record transient foreground failure BEFORE rollback; report only package IDs.

    Full dumps and screen stay in local Termux backup, not in GitHub issue.
    No system settings or packages are altered.
    """
    import re as _re
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        raw_win = adb("shell", "dumpsys", "window",
                      timeout=22, okay=True)
        raw_activity = adb("shell", "dumpsys", "activity", "activities",
                           timeout=22, okay=True)
        pid = adb("shell", "pidof", PKG, timeout=12, okay=True).strip()
        focus = next((line for line in raw_win.splitlines()
                      if "mCurrentFocus=" in line), "")
        resumed = next((line for line in raw_activity.splitlines()
                        if "topResumedActivity" in line
                        or "mResumedActivity" in line), "")
        component = r"([A-Za-z_][A-Za-z0-9_.]*/[A-Za-z0-9_.$]+)"
        match_focus = _re.search(component, focus)
        match_resumed = _re.search(component, resumed)
        foreground = match_focus.group(1) if match_focus else "unknown"
        resumed_pkg = match_resumed.group(1) if match_resumed else "unknown"
        (folder / "focus-failed-before-rollback.txt").write_text(
            "foreground=" + foreground + "\nresumed=" + resumed_pkg +
            "\nprocess=" + ("running" if _re.fullmatch(r"\d+(?:\s+\d+)*", pid) else "missing") +
            "\n", encoding="utf-8")
        shot = adb("exec-out", "screencap", "-p", timeout=25, binary=True)
        if isinstance(shot, bytes) and shot:
            (folder / "screen-failed-before-rollback.png").write_bytes(shot)
        return ("foreground=" + foreground + ", resumed=" + resumed_pkg +
                ", process=" + ("running" if _re.fullmatch(r"\d+(?:\s+\d+)*", pid) else "missing"))
    except (MaintenanceError, OSError, ValueError):
        return "foreground diagnostics unavailable"


CEC_GLOBAL_KEYS = (
    "hdmi_control_enabled",
    "hdmi_control_auto_device_off_enabled",
    "hdmi_control_auto_wakeup_enabled",
    "hdmi_control_one_touch_play_enabled",
    "hdmi_control_volume_control_enabled",
    "hdmi_control_power_control_mode",
)


def cec_power_probe():
    """Read only: confirm whether BOXY/TV power are coupled by HDMI-CEC.

    Manufacturer HDMI-CEC implementations vary. Do not infer that a missing
    Android global setting means a feature is on or off; never write sysfs.
    """
    lines = ["HDMI-CEC power diagnostics (READ ONLY):"]
    for key in CEC_GLOBAL_KEYS:
        raw = adb("shell", "settings", "get", "global", key,
                  okay=True, timeout=14).strip()
        value = raw if raw in ("0", "1", "null", "to_tv", "none",
                               "to_tv_and_audio_system", "broadcast") else "unknown"
        lines.append("  " + key + "=" + value)

    device_type = adb("shell", "getprop", "ro.hdmi.device_type",
                      okay=True).strip()
    lines.append("  ro.hdmi.device_type=" +
                 (device_type if device_type in ("0", "4", "5") else "unknown"))

    # Amlogic's cec_config mask is OEM-specific; bit 0x04 is often the
    # "one-key standby" option. Observing it does NOT authorize a sysfs write.
    cec_cfg = adb("shell", "cat", "/sys/class/amhdmitx/amhdmitx0/cec_config",
                  okay=True, timeout=14).strip()
    raw = cec_cfg.splitlines()[0] if cec_cfg else ""
    if re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{1,4}", raw):
        value = int(raw, 16)
        lines.append("  amlogic_cec_config=0x" + format(value, "x"))
        lines.append("  amlogic_standby_bit_0x04=" +
                     ("set" if value & 0x04 else "clear") +
                     " (firmware-dependent interpretation)")
    else:
        lines.append("  amlogic_cec_config=unavailable")

    # HDMI control service can be absent or vendor replaced; only selected
    # coarse flags are surfaced. No neighbor TV identification/EDID/addresses.
    report = adb("shell", "dumpsys", "hdmi_control", okay=True, timeout=22)
    interesting = ("mHdmiControlEnabled", "mAutoDeviceOff", "mAutoWakeup",
                   "mPowerControlMode", "mIsActiveSource", "mStandbyMessageReceived")
    matches = []
    for line in report.splitlines():
        stripped = line.strip()
        for tag in interesting:
            if tag in stripped:
                match = re.search(r"\b" + re.escape(tag) +
                                  r"\s*[:=]\s*([A-Za-z0-9_.-]+)", stripped)
                if match:
                    matches.append("  " + tag + "=" + match.group(1)[:30])
                break
    lines.extend(matches[:12])
    if not matches:
        lines.append("  hdmi_control_service_details=unavailable")
    lines.append("  NOTE: No CEC or power setting was changed.")
    return "\n".join(lines)


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
        "Theme directory access: " + remote_directory_state(),
        "Unknown OEM candidates (READ ONLY):",
        *vendor_notes,
        cec_power_probe(),
        "No package, settings or firmware changes.",
    ])


def remote_directory_state():
    """Distinguish a missing theme directory from Android 11 permission denial.

    ADB shell accepts ONE remote command string, not a separated sh -c script.
    This read-only probe reports a dedicated marker after the ls exit status.
    """
    command = ("LC_ALL=C ls -ld '" + REMOTE +
               "' 2>&1; printf '\\nCYT_LS_EXIT:%s\\n' \"$?\"")
    output = adb("shell", command, okay=True).strip()
    match = re.search(r"CYT_LS_EXIT:(\d+)\b", output)
    if match is None:
        return "unknown"
    if match.group(1) == "0":
        return "exists"
    if "No such file or directory" in output:
        return "absent"
    return "unknown"


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
    # This design uses a fixed launcher-owned wallpaper. Even if Android/data
    # happens to be accessible, use the safer official ThemeProvider so every
    # overwritten file is first backed up byte-for-byte. Never clear a
    # wallpaper collection or run the full-theme helper's reset operation.
    provider = ProviderTheme(TV, folder)
    try:
        provider.backup_files()
    except ProviderError as exc:
        raise MaintenanceError("ThemeProvider backup failed; no changes: " +
                               str(exc)) from exc
    (folder / "mode.txt").write_text("provider-only", encoding="utf-8")

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


def restart_official_theme_home():
    """Use the upstream Home restart and accessibility-rebind helper."""
    exe = OFFICIAL / "tools/venv/bin/python"
    helper = OFFICIAL / "tools/theme_restart.py"
    if not exe.is_file() or not helper.is_file():
        raise MaintenanceError("Pinned official restart helper unavailable")
    env = os.environ.copy()
    env["TV_HOST"] = "192.168.0.160"
    env["TV_ADB_BINARY"] = shutil.which("adb") or "adb"
    run([str(exe), "-I", str(helper)], env=env, timeout=195)


def ensure_safe_adb_restart():
    """No-op safety gate: refuse a simplified restart if launcher key helpers are enabled.

    The pinned upstream helper rebinds accessibility services. When none of its
    accessibility components is enabled, ADB can restart only the app, without
    editing global settings or requiring Python cryptography on Termux.
    """
    raw = adb("shell", "settings", "--user", "0", "get", "secure",
              "enabled_accessibility_services").strip()
    state = adb("shell", "settings", "--user", "0", "get", "secure",
                "accessibility_enabled").strip()
    if state not in ("0", "1", "null"):
        raise MaintenanceError("Could not verify Android accessibility state; no changes")
    entries = () if raw in ("", "null") else raw.split(":")
    if any(entry.startswith(PKG + "/") for entry in entries):
        raise MaintenanceError(
            "CleanYourTV accessibility key helpers are enabled; "
            "the full official service-rebinding helper is required"
        )


def restart_home_simple():
    """Restart only CleanYourTV via native ADB, never touch other settings."""
    ensure_safe_adb_restart()
    if home_resolver() != HOME:
        raise MaintenanceError("Default HOME changed; refusing launcher restart")
    adb("shell", "am", "force-stop", "--user", "0", PKG)
    output = adb("shell", "am", "start", "-W", "--user", "0", "-n", HOME)
    if "Status: ok" not in output and "Warning: Activity not started" not in output:
        raise MaintenanceError("CleanYourTV did not report successful activity launch")


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
    # AMOLED v3 draws only the launcher base #000000. Do not generate, write,
    # remove or replace the user's existing wallpaper.jpg backup/asset.
    wallpaper = None
    wallpaper_sha256 = None
    before = disabled_packages()
    folder = backup_theme()
    mode_path = folder / "mode.txt"
    mode = mode_path.read_text(encoding="utf-8").strip() if mode_path.exists() else "full"
    if mode not in ("full", "provider-only"):
        raise MaintenanceError("Invalid theme backup mode")
    provider = ProviderTheme(TV, folder) if mode == "provider-only" else None
    # A scoped-storage backup is config-only, so applying it through the
    # upstream ThemeProvider requires no adb_shell/rsa/cryptography dependencies.
    # Verify the native restart is safe BEFORE any provider bytes are changed.
    if provider is not None:
        ensure_safe_adb_restart()
        script = None
    else:
        script = prepare_upstream()
    applied = False
    try:
        # Mark before invoking a write: a partial ADB write still needs rollback.
        applied = True
        if provider is not None:
            provider.apply(PRESET.read_bytes(), wallpaper=wallpaper)
            restart_home_simple()
            current = provider.read("config.json")
            if current != PRESET.read_bytes():
                raise MaintenanceError("Provider-only config readback differs")
            if wallpaper is not None and (
                    hashlib.sha256(provider.read("wallpaper.jpg") or b"").hexdigest()
                    != wallpaper_sha256):
                raise MaintenanceError("Provider-only wallpaper readback differs")
        else:
            theme_command(script, str(PRESET.parent))
            current = adb("exec-out", "content", "read", "--uri", THEME_URI,
                          binary=True, timeout=35)
        if json.loads(current.decode("utf-8")) != expected:
            raise MaintenanceError("ThemeProvider readback did not match requested preset")
        adb("shell", "input", "keyevent", "3")
        try:
            verify_home_after_theme()
        except MaintenanceError as failure:
            details = capture_theme_failure_state(folder)
            raise MaintenanceError(str(failure) + "; " + details) from failure
        if disabled_packages() != before:
            raise MaintenanceError("Unexpected change in disabled packages")
        after = adb("exec-out", "screencap", "-p", binary=True)
        if not after.startswith(b"\x89PNG\r\n\x1a\n"):
            raise MaintenanceError("Screen verification capture missing")
        (folder / "screen-after.png").write_bytes(after)
    except (MaintenanceError, ProviderError, UnicodeDecodeError, ValueError) as exc:
        if applied:
            try:
                if provider is not None:
                    provider.restore()
                    restart_home_simple()
                else:
                    restore_theme(script, folder)
            except (MaintenanceError, ProviderError) as recovery:
                raise MaintenanceError(str(exc) + "; RESTORE FAILED: " +
                                       str(recovery) + "; backup: " + str(folder)) from exc
        raise MaintenanceError(str(exc) + "; previous theme restored if it was changed") from exc

    receipt = {"method": mode, "time": dt.datetime.now(dt.timezone.utc).isoformat(),
               "theme_sha256": digest, "wallpaper_sha256": wallpaper_sha256,
               "backup": str(folder),
               "disabled_before": before, "home": HOME}
    RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    RECEIPT.chmod(0o600)
    return ("CLEAN_YOUR_TV_THEME_OK\n"
            "Pinned official theme mechanism applied; mode: " + mode + ".\n"
            "AMOLED v3 six-column grid and no-wallpaper config verified by ThemeProvider readback.\n"
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
    if receipt.get("wallpaper_sha256"):
        actual_wallpaper = adb("exec-out", "content", "read", "--uri",
                               "content://" + PKG + ".theme/wallpaper.jpg", binary=True)
        if hashlib.sha256(actual_wallpaper).hexdigest() != receipt["wallpaper_sha256"]:
            raise MaintenanceError("Wallpaper changed before reboot; no reboot")
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
