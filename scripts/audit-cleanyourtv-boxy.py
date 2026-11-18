#!/usr/bin/env python3
"""Read-only BOXY/CleanYourTV audit. No package, HOME or DNS mutations.

Output:
  ~/cleanyourtv-backups/<UTC>/  (private complete snapshot)
  ~/storage/downloads/BOXY-CleanYourTV-audit.txt (shareable package summary)
  ~/storage/downloads/BOXY-CleanYourTV-screen.png (optional local screenshot)
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import re
import subprocess
import sys

TV = "192.168.0.160:5555"
EXPECTED_MODEL = "4K Android TV Box"
NEW_HOME = "com.gathin.tvhome/.MainActivity"

# These are REVIEW flags only: regex matching can yield false positives.
REVIEW_PATTERNS = {
    "possible_telemetry": r"analyt|telemetr|metrics|tracking|crash|bugly|feedback|reporting",
    "possible_ad_content": r"advert|recommend|promot|sponsor|patchwall|suggest|discover",
    "vendor_services": r"skyworth|coocaa|tcl|amlogic|hisi|oem",
    "preserve_cast": r"cast|miracast|airplay|dlna",
    "preserve_voice": r"voice|speech|assistant|search",
    "preserve_updates": r"updat|ota|firmware|fota",
}

PROTECT_PREFIXES = (
    "android", "com.android.", "com.google.android.", "com.mediatek.",
    "com.amlogic.", "com.skyworth.", "com.tcl.", "com.cltv.",
)


def execute(*args: str, timeout: int = 25, binary: bool = False) -> str | bytes:
    cmd = ["adb", "-s", TV, *args]
    result = subprocess.run(cmd, capture_output=True, timeout=timeout,
                            text=not binary, check=False)
    if result.returncode != 0:
        err = result.stderr
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        raise RuntimeError(f"ADB {' '.join(args)} failed: {str(err).strip()[:300]}")
    return result.stdout


def package_ids(text: str) -> set[str]:
    return {
        line.removeprefix("package:").strip()
        for line in text.splitlines()
        if line.startswith("package:") and
        re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", line[8:].strip())
    }


def review_groups(names: set[str]) -> dict[str, list[str]]:
    return {
        label: sorted(pkg for pkg in names if re.search(pattern, pkg, re.I))
        for label, pattern in REVIEW_PATTERNS.items()
    }


def is_protected(pkg: str) -> bool:
    return pkg == "android" or pkg.startswith(PROTECT_PREFIXES)


def save_text(directory: Path, name: str, content: str) -> None:
    target = directory / name
    target.write_text(content, encoding="utf-8")
    target.chmod(0o600)


def get_adb_summary() -> dict[str, str]:
    return {
        "model": str(execute("shell", "getprop", "ro.product.model")).strip(),
        "manufacturer": str(execute("shell", "getprop", "ro.product.manufacturer")).strip(),
        "sdk": str(execute("shell", "getprop", "ro.build.version.sdk")).strip(),
        "platform": str(execute("shell", "getprop", "ro.board.platform")).strip(),
    }


def main() -> int:
    os.umask(0o077)
    if len(sys.argv) != 1:
        print("Usage: python3 scripts/audit-cleanyourtv-boxy.py", file=sys.stderr)
        return 2
    subprocess.run(["adb", "connect", TV], capture_output=True, timeout=12, check=False)
    state = str(execute("get-state")).strip()
    if state != "device":
        raise RuntimeError("TV is not authorized on ADB. No changes made.")
    device = get_adb_summary()
    if device["model"] != EXPECTED_MODEL or "skyworth" not in device["manufacturer"].lower():
        raise RuntimeError(f"Unrecognized TV model/manufacturer: {device}. No changes made.")
    if not device["sdk"].isdigit() or int(device["sdk"]) < 26:
        raise RuntimeError("CleanYourTV requires SDK >=26. No changes made.")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path.home() / "cleanyourtv-backups"
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    backup = root / f"audit-{stamp}"
    backup.mkdir(mode=0o700)

    snapshot: dict[str, str] = {}
    commands = {
        "packages-all.txt": ("shell", "pm", "list", "packages"),
        "packages-system.txt": ("shell", "pm", "list", "packages", "-s"),
        "packages-user.txt": ("shell", "pm", "list", "packages", "-3"),
        "packages-disabled.txt": ("shell", "pm", "list", "packages", "-d"),
        "properties.txt": ("shell", "getprop"),
        "settings-global.txt": ("shell", "settings", "list", "global"),
        "settings-secure.txt": ("shell", "settings", "list", "secure"),
        "settings-system.txt": ("shell", "settings", "list", "system"),
        "home-before.txt": ("shell", "cmd", "package", "resolve-activity", "--brief",
                            "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"),
        "home-claimants.txt": ("shell", "cmd", "package", "query-activities", "--brief",
                              "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"),
        "focus.txt": ("shell", "dumpsys", "activity", "activities"),
        "window.txt": ("shell", "dumpsys", "window", "windows"),
        "display-size.txt": ("shell", "wm", "size"),
        "display-density.txt": ("shell", "wm", "density"),
        "usb.txt": ("shell", "dumpsys", "usb"),
        "connectivity.txt": ("shell", "dumpsys", "connectivity"),
        "tv-inputs.txt": ("shell", "dumpsys", "tv_input"),
        "cleanyourtv-package.txt": ("shell", "dumpsys", "package", "com.gathin.tvhome"),
    }
    failures = []
    for name, cmd in commands.items():
        try:
            response = str(execute(*cmd, timeout=35))
            snapshot[name] = response
            save_text(backup, name, response)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            failures.append(f"{name}: {str(exc)[:160]}")

    all_packages = package_ids(snapshot.get("packages-all.txt", ""))
    system_packages = package_ids(snapshot.get("packages-system.txt", ""))
    user_packages = package_ids(snapshot.get("packages-user.txt", ""))
    disabled = package_ids(snapshot.get("packages-disabled.txt", ""))
    home = snapshot.get("home-before.txt", "").strip().splitlines()
    home_component = home[-1] if home else "unknown"
    groups = review_groups(system_packages)

    # Nothing from settings/getprop/dumpsys is copied into the shareable report.
    report = [
        "BOXY / CleanYourTV — READ-ONLY AUDIT",
        f"Timestamp (UTC): {stamp}",
        f"TV: {device['model']} / {device['manufacturer']}",
        f"Android SDK: {device['sdk']} / Platform: {device['platform']}",
        f"Resolved HOME: {home_component}",
        f"CleanYourTV appears installed: {'yes' if 'com.gathin.tvhome' in all_packages else 'no'}",
        f"Packages: all={len(all_packages)} system={len(system_packages)} "
        f"user={len(user_packages)} disabled={len(disabled)}",
        f"Snapshot folder (private): {backup}",
        "",
        "CURRENT DISABLED PACKAGES (preserved as found):",
        *(f"  {pkg}" for pkg in sorted(disabled)),
        "",
        "POSSIBLE REVIEW GROUPS (NOT APPROVED TO DISABLE):",
    ]
    for group, names in groups.items():
        report.append(f"{group} ({len(names)}):")
        report.extend(f"  {pkg} {'[CORE/OEM - KEEP PENDING REVIEW]' if is_protected(pkg) else ''}"
                      for pkg in names)
    report += [
        "",
        "ALL SYSTEM PACKAGES (to classify after reading package roles):",
        *(f"  {pkg}" for pkg in sorted(system_packages)),
        "",
        "ALL USER PACKAGES:",
        *(f"  {pkg}" for pkg in sorted(user_packages)),
        "",
        "SNAPSHOT WARNINGS:",
        *(f"  {item}" for item in failures) if failures else ["  none"],
        "",
        "IMPORTANT: The audit has NOT disabled, removed, or reconfigured any package.",
        "Do not copy a debloat list for another Skyworth model.",
        "Complete settings and system dumps are PRIVATE in Termux; do not post them publicly.",
    ]

    download = Path.home() / "storage" / "downloads"
    if not download.is_dir():
        download = Path("/storage/emulated/0/Download")
    if not download.is_dir() or not os.access(download, os.W_OK):
        download = backup
        print("Download folder unavailable; report saved inside private backup.")
    report_path = download / "BOXY-CleanYourTV-audit.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    shot_path = download / "BOXY-CleanYourTV-screen.png"
    try:
        shot = execute("exec-out", "screencap", "-p", timeout=25, binary=True)
        if isinstance(shot, bytes) and shot.startswith(b"\x89PNG\r\n\x1a\n") and len(shot) > 1024:
            shot_path.write_bytes(shot)
        else:
            print("Screenshot unavailable; other backups are retained.")
    except (RuntimeError, subprocess.TimeoutExpired):
        print("Screenshot unavailable; other backups are retained.")

    save_text(backup, "RESTORE-INSTRUCTIONS.txt",
              "No packages were changed by this audit.\n"
              "The Home handover backup and explicit rollback command remain in "
              "~/cleanyourtv-backups/home-*/RESTORE-STOCK.sh.\n"
              "For future debloat, use upstream tools/disable.sh and matching "
              "tools/restore.sh with exactly the approved list.\n"
              "Do not enable every entry in packages-disabled.txt blindly; "
              "some were already disabled before the snapshot.\n")
    print(f"AUDIT_OK: {report_path}")
    print(f"BACKUP: {backup}")
    print(f"PACKAGES: {len(all_packages)} total / {len(system_packages)} system / "
          f"{len(user_packages)} user / {len(disabled)} disabled")
    print(f"HOME: {home_component}")
    print(f"SCREEN: {shot_path if shot_path.is_file() else 'unavailable'}")
    print("NO TV CHANGES MADE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"AUDIT_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
