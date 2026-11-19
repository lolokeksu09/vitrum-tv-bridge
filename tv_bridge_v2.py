#!/usr/bin/env python3
"""Opt-in TV management via private GitHub Issues and local Termux ADB.

No arbitrary remote shell. Privileged capabilities require local CLI flags.
"""
import argparse
from contextlib import contextmanager
import fcntl
import base64
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import tv_bridge as base

REPO = base.REPO
OWNER = base.OWNER
PREFIX = "TVBRIDGE/v2 "
MARKER = "<!-- tv-bridge-v2-result -->"
MAX_REQUEST_AGE = dt.timedelta(hours=1)

KEYCODES = {
    "BACK": "4", "HOME": "3", "UP": "19", "DOWN": "20",
    "LEFT": "21", "RIGHT": "22", "OK": "23", "ENTER": "66",
    "MENU": "82", "VOLUME_UP": "24", "VOLUME_DOWN": "25",
}
READ_OPS = frozenset((*base.OPERATIONS, "app_list", "app_info", "vitrum_memory"))
CONTROL_OPS = frozenset(("key", "launch_vitrum", "stop_vitrum", "launch_app"))
SENSITIVE_OPS = frozenset(("screenshot", "install_vitrum", "install_vitrum_ci",
                          "install_monolith_ci", "ui_sweep"))
MAINTENANCE_OPS = frozenset(("cleanyourtv_probe", "cleanyourtv_apply_theme",
                             "cleanyourtv_reboot_check", "cleanyourtv_perf_probe"))
ALL_OPS = READ_OPS | CONTROL_OPS | SENSITIVE_OPS | MAINTENANCE_OPS
PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", re.ASCII)
APK = re.compile(r"(?:Vitrum-TV[A-Za-z0-9._-]*|tv-debug)\.apk", re.ASCII)
SHA256 = re.compile(r"[a-f0-9]{64}", re.ASCII)

BridgeError = base.BridgeError


class ActionDenied(BridgeError):
    pass


@contextmanager
def single_agent_lock(path=None):
    """Permit only one v2 bridge worker per Termux home.

    A non-blocking kernel lock prevents duplicate ADB key events when the
    operator accidentally starts two --watch sessions. The lock is released
    automatically on process exit, including an unexpected termination.
    """
    lock_path = Path(path) if path is not None else Path.home() / ".vitrum-tv-bridge-v2.lock"
    descriptor = os.open(
        str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BridgeError(
                "Another TV bridge v2 session is already running; stop it first"
            ) from exc
        yield
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class Permissions:
    control: bool = False
    screenshot: bool = False
    install: bool = False
    maintenance: bool = False
    reboot: bool = False


def validate_args(op, args):
    if not isinstance(args, dict):
        return False
    empty = (READ_OPS - {"app_info"}) | {"launch_vitrum", "stop_vitrum", "screenshot", "ui_sweep"} | MAINTENANCE_OPS
    if op in empty:
        return args == {}
    if op == "key":
        return set(args) == {"key"} and type(args["key"]) is str and args["key"] in KEYCODES
    if op in {"app_info", "launch_app"}:
        return (set(args) == {"package"} and type(args["package"]) is str
                and len(args["package"]) <= 150
                and PACKAGE.fullmatch(args["package"]) is not None)
    if op in {"install_vitrum_ci", "install_monolith_ci"}:
        return (set(args) == {"run_id", "sha256"}
                and type(args["run_id"]) is int and 0 < args["run_id"] < 10**12
                and type(args["sha256"]) is str
                and SHA256.fullmatch(args["sha256"]) is not None)
    if op == "install_vitrum":
        return (set(args) == {"filename", "sha256"}
                and type(args["filename"]) is str
                and len(args["filename"]) <= 90
                and APK.fullmatch(args["filename"]) is not None
                and type(args["sha256"]) is str
                and SHA256.fullmatch(args["sha256"]) is not None)
    return False


def parse_issue(issue, now=None):
    if not isinstance(issue, dict) or not isinstance(issue.get("author"), dict):
        return None
    if issue["author"].get("login") != OWNER:
        return None
    if str(issue.get("title", "")).startswith(base.PREFIX):
        old = base.parse_issue(issue)
        return {"number": old[0], "op": old[1], "args": {}} if old else None
    title, body, number = issue.get("title"), issue.get("body"), issue.get("number")
    if (type(number) is not int or number < 1 or not isinstance(title, str)
            or not title.startswith(PREFIX) or not isinstance(body, str)
            or len(body) > 1024):
        return None
    try:
        request = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(request, dict) or set(request) != {"v", "op", "args"}:
        return None
    op = request.get("op")
    if type(request.get("v")) is not int or request["v"] != 2:
        return None
    if type(op) is not str or op not in ALL_OPS or title != PREFIX + op:
        return None
    if not validate_args(op, request.get("args")):
        return None
    created_at = issue.get("createdAt")
    if not isinstance(created_at, str):
        return None
    try:
        created = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if created.tzinfo is None:
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    age = now - created
    if age < dt.timedelta(seconds=-30) or age > MAX_REQUEST_AGE:
        return None
    return {"number": number, "op": op, "args": request["args"]}


def repository_is_private():
    """Public destination is untrusted for device-specific results."""
    try:
        metadata = json.loads(base.gh("api", "repos/" + REPO))
    except (ValueError, BridgeError) as exc:
        raise ActionDenied("Cannot verify repository visibility") from exc
    if not isinstance(metadata, dict) or type(metadata.get("private")) is not bool:
        raise ActionDenied("Repository visibility missing; no operation")
    return metadata["private"]


def require_private_capture_repo():
    """Never read screen pixels if destination is public or unverified."""
    if not repository_is_private():
        raise ActionDenied("Screenshot capture disabled: control repository is public")


PERF_RESULT = re.compile(
    r"PERF_V1 frames=[0-9]{1,5} p50_ms=[0-9]{1,4}\.[0-9] "
    r"p95_ms=[0-9]{1,4}\.[0-9] slow16_pct=[0-9]{1,3}\.[0-9]",
    re.ASCII,
)


def public_safe_result(result, private_repo, op=None, status=None):
    """Don't publish local paths, packages or diagnostics as public comments."""
    if private_repo:
        return result
    # Only validated, anonymous aggregate performance numbers are public-safe.
    # No paths, package IDs, app names or exception output can pass this regex.
    if (op == "cleanyourtv_perf_probe" and status == "SUCCESS"
            and type(result) is str and PERF_RESULT.fullmatch(result)):
        return result
    return "Device-specific result withheld because GitHub control repository is public."


def capture_screenshot(device, number, page=None):
    """Only an explicitly authorized PRIVATE repo can receive screenshots."""
    require_private_capture_repo()
    try:
        p = subprocess.run(
            ["adb", "-s", device, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=25
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise BridgeError("ADB screenshot unavailable") from exc
    png = p.stdout
    if p.returncode or not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BridgeError("Screenshot capture failed")
    if len(png) > 5_000_000:
        raise BridgeError("Screenshot is too large")
    target = ("captures/issue-" + str(number)
              + ("-" + page if page else "") + ".png")
    payload = {
        "message": "bridge: private TV screenshot for issue #" + str(number),
        "content": base64.b64encode(png).decode("ascii"),
    }
    fd, path = tempfile.mkstemp(prefix="vitrum-tv-capture-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
        base.gh("api", "--method", "PUT",
                "repos/" + REPO + "/contents/" + target, "--input", path)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    return ("Private screenshot: https://github.com/" + REPO + "/blob/main/"
            + target + "\nWARNING: retained in private Git history.")


def require_vitrum_foreground(device):
    """Fail closed unless Android reports Vitrum TV as the resumed Activity.

    ADB key events are global, so this guard MUST precede every automated
    navigation event and every screenshot to avoid acting on another TV app.
    """
    raw, _ = base.adb(device, "dumpsys", "activity", "activities")
    if not re.search(
        r"(?:topResumedActivity|mResumedActivity)\s*[:=][^\n]*\bapp\.rayclient\.tv/\.TvActivity\b",
        raw,
    ):
        raise BridgeError("Vitrum TV is not confirmed as the foreground Activity")


def audit_five_pages(device, number):
    """Fixed, auditable read-only screenshot sequence; no issue-supplied actions."""
    if not isinstance(number, int) or number <= 0:
        raise BridgeError("Invalid issue identifier")
    require_private_capture_repo()  # Before navigation or launching any TV app.
    names = ("home", "servers", "apps", "setup", "settings")
    base.adb(device, "am", "start", "-n", "app.rayclient.tv/.TvActivity")
    time.sleep(1.0)
    urls = []
    require_vitrum_foreground(device)
    for index, name in enumerate(names):
        if index:
            for key in ("21", "20", "23"):  # LEFT, DOWN, OK
                require_vitrum_foreground(device)
                base.adb(device, "input", "keyevent", key)
                time.sleep(0.25)
            time.sleep(0.5)
        require_vitrum_foreground(device)
        urls.append(name + ": " + capture_screenshot(device, number, page=name))
    require_vitrum_foreground(device)
    base.adb(device, "input", "keyevent", "4")  # Android BACK -> Home
    time.sleep(0.25)
    require_vitrum_foreground(device)
    return "\n".join(urls) + "\nReturned to Home"


def install_vitrum(device, args, downloads):
    downloads = Path(downloads) if downloads is not None else (
        Path.home() / "storage" / "downloads"
    )
    apk = downloads / args["filename"]
    if not apk.is_file() or apk.is_symlink():
        raise BridgeError("APK is missing or is a symbolic link")
    if not 0 < apk.stat().st_size <= 120_000_000:
        raise BridgeError("APK size is not permitted")
    digest = hashlib.sha256()
    with apk.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    if digest.hexdigest() != args["sha256"]:
        raise BridgeError("APK SHA-256 mismatch; nothing installed")
    output, _ = base.execute(
        ["adb", "-s", device, "install", "-r", str(apk)], timeout=120
    )
    if "Success" not in output:
        raise BridgeError("ADB did not report installation success")
    return "Installed SHA-256 verified APK: " + apk.name


def install_vitrum_from_ci(device, args):
    """Download from a successful, known Vitrum TV workflow only.

    The caller pins the *exact* APK SHA-256. Installation still uses adb -r
    and never uninstalls old builds or clears app data.
    """
    run_id = args["run_id"]
    metadata = json.loads(base.gh(
        "api", "repos/lolokeksu09/Vitrum/actions/runs/" + str(run_id)
    ))
    if (metadata.get("name") != "Vitrum TV developer shell verification"
            or metadata.get("head_branch") != "feature/vitrum-tv-foundation"
            or metadata.get("conclusion") != "success"):
        raise BridgeError("Workflow provenance not confirmed; refusing installation")
    with tempfile.TemporaryDirectory(prefix="vitrum-tv-trusted-build-") as folder:
        argv = [
            "gh", "run", "download", str(run_id),
            "-R", "lolokeksu09/Vitrum",
            "-n", "Vitrum-TV-0.1.0-dev-ARM32-shell",
            "-D", folder,
        ]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=120
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise BridgeError("CI artifact download unavailable") from exc
        if result.returncode:
            raise BridgeError("CI artifact download failed; not installing")
        return install_vitrum(
            device,
            {"filename": "tv-debug.apk", "sha256": args["sha256"]},
            downloads=Path(folder),
        )


def install_monolith_from_ci(device, args):
    """Install exactly one pinned MONOLITH-TV main-branch preview APK.

    No uninstall, clear data, HOME selection, shell, or arbitrary URLs.
    A mismatched debug signing certificate is reported as an install failure.
    """
    repository = "lolokeksu09/MONOLITH-TV"
    run_id = args["run_id"]
    metadata = json.loads(base.gh(
        "api", "repos/" + repository + "/actions/runs/" + str(run_id)
    ))
    if (metadata.get("name") != "Android TV CI"
            or metadata.get("head_branch") != "main"
            or metadata.get("event") != "push"
            or metadata.get("status") != "completed"
            or metadata.get("conclusion") != "success"
            or (metadata.get("repository") or {}).get("full_name") != repository):
        raise BridgeError("MONOLITH CI provenance not confirmed; refusing installation")
    with tempfile.TemporaryDirectory(prefix="monolith-tv-trusted-build-") as folder:
        argv = [
            "gh", "run", "download", str(run_id), "-R", repository,
            "-n", "MONOLITH-TV-preview-debug", "-D", folder,
        ]
        try:
            downloaded = subprocess.run(
                argv, capture_output=True, text=True, timeout=120
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise BridgeError("MONOLITH CI artifact download unavailable") from exc
        if downloaded.returncode:
            raise BridgeError("MONOLITH CI artifact download failed; not installing")

        apk = Path(folder) / "app-debug.apk"
        if not apk.is_file() or apk.is_symlink():
            raise BridgeError("Expected MONOLITH app-debug.apk is missing or a symlink")
        size = apk.stat().st_size
        if not 0 < size <= 120_000_000:
            raise BridgeError("MONOLITH APK size is not permitted")
        digest = hashlib.sha256()
        with apk.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
        if digest.hexdigest() != args["sha256"]:
            raise BridgeError("MONOLITH APK SHA-256 mismatch; nothing installed")

        output, _ = base.execute(
            ["adb", "-s", device, "install", "-r", str(apk)], timeout=120
        )
        if "Success" not in output:
            raise BridgeError("MONOLITH ADB installation did not report success")
        return "Installed verified MONOLITH TV preview from CI run " + str(run_id)


def invoke_cleanyourtv_maintenance(device, action):
    """Opt-in fixed actions only: no remote arbitrary shell and no package disable."""
    if device != "192.168.0.160:5555" or action not in {"probe", "theme", "reboot", "perf"}:
        raise BridgeError("Unexpected BOXY target or maintenance operation")
    script = Path(__file__).resolve().parent / "scripts/cleanyourtv_boxy_maintenance.py"
    if not script.is_file() or script.is_symlink():
        raise BridgeError("Pinned CleanYourTV maintenance implementation unavailable")
    command = [sys.executable, str(script), action]
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              errors="replace", timeout=960, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BridgeError("CleanYourTV maintenance command unavailable or timed out") from exc
    if proc.returncode:
        # Do not expose full environment, settings or ADB output to GitHub.
        reason = proc.stderr.strip().splitlines()
        raise BridgeError((reason[-1] if reason else "Maintenance operation failed")[:420])
    return (proc.stdout.strip() or "Maintenance finished without output")[:2500]


def run_action(device, request, permissions, downloads=None):
    op, args = request["op"], request["args"]
    if op in base.OPERATIONS:
        return base.perform(device, op)
    if op == "app_list":
        raw, _ = base.adb(device, "pm", "list", "packages", "-3")
        apps = [line.strip() for line in raw.splitlines() if line.startswith("package:")]
        return "Third-party apps (first 80):\n" + "\n".join(apps[:80])
    if op == "app_info":
        package = args["package"]
        raw, _ = base.adb(device, "dumpsys", "package", package)
        name = re.search(r"(?m)^\s*versionName=(\S+)", raw)
        code = re.search(r"(?m)^\s*versionCode=(\d+)", raw)
        return ("\n".join((
            "package: " + package,
            "version: " + (name.group(1) if name else "unknown"),
            "version_code: " + (code.group(1) if code else "unknown"),
        )))
    if op == "vitrum_memory":
        raw, _ = base.adb(device, "dumpsys", "meminfo", "app.rayclient.tv")
        rows = [line.strip()[:200] for line in raw.splitlines()
                if "TOTAL PSS:" in line or "TOTAL SWAP PSS:" in line
                or re.match(r"^\s*TOTAL\s+\d+", line)]
        return "\n".join(rows[:12]) or "Memory details unavailable"

    if op in MAINTENANCE_OPS:
        if not permissions.maintenance:
            raise ActionDenied("Requires local --allow-maintenance flag")
        if op == "cleanyourtv_reboot_check" and not permissions.reboot:
            raise ActionDenied("Reboot separately requires local --allow-reboot flag")
        if op == "cleanyourtv_perf_probe" and not permissions.control:
            raise ActionDenied("Fixed D-pad performance sampling requires --allow-control")
        action = {"cleanyourtv_probe": "probe",
                  "cleanyourtv_apply_theme": "theme",
                  "cleanyourtv_reboot_check": "reboot",
                  "cleanyourtv_perf_probe": "perf"}[op]
        return invoke_cleanyourtv_maintenance(device, action)

    if op in CONTROL_OPS and not permissions.control:
        raise ActionDenied("Requires local --allow-control flag")
    if op == "key":
        name = args["key"]
        base.adb(device, "input", "keyevent", KEYCODES[name])
        return "Remote key sent: " + name
    if op == "launch_vitrum":
        base.adb(device, "am", "start", "-n", "app.rayclient.tv/.TvActivity")
        return "Vitrum TV launch requested"
    if op == "stop_vitrum":
        base.adb(device, "am", "force-stop", "app.rayclient.tv")
        return "Vitrum TV process stopped; data preserved"
    if op == "launch_app":
        package = args["package"]
        base.adb(device, "monkey", "-p", package,
                 "-c", "android.intent.category.LEANBACK_LAUNCHER", "1")
        return "Launch requested for: " + package
    if op == "ui_sweep":
        if not permissions.control or not permissions.screenshot:
            raise ActionDenied("Requires --allow-control AND --allow-screenshots")
        return audit_five_pages(device, request["number"])
    if op == "screenshot":
        if not permissions.screenshot:
            raise ActionDenied("Requires local --allow-screenshots flag")
        return capture_screenshot(device, request["number"])
    if op == "install_vitrum_ci":
        if not permissions.install:
            raise ActionDenied("Requires local --allow-installs flag")
        return install_vitrum_from_ci(device, args)
    if op == "install_monolith_ci":
        if not permissions.install:
            raise ActionDenied("Requires local --allow-installs flag")
        return install_monolith_from_ci(device, args)
    if op == "install_vitrum":
        if not permissions.install:
            raise ActionDenied("Requires local --allow-installs flag")
        return install_vitrum(device, args, downloads)
    raise BridgeError("Operation not supported")


def already_answered(number):
    comments = json.loads(base.gh(
        "api", "repos/" + REPO + "/issues/" + str(number) + "/comments?per_page=100"
    ))
    return any((MARKER in item.get("body", "")
                or base.MARKER in item.get("body", "")) for item in comments)


def process(device, permissions):
    private_repo = repository_is_private()
    issues = json.loads(base.gh(
        "issue", "list", "-R", REPO, "--state", "open", "--limit", "100",
        "--json", "number,title,body,author,createdAt"
    ))
    requests = [valid for issue in issues if (valid := parse_issue(issue))]
    requests.sort(key=lambda item: item["number"])
    if not requests:
        print("No authorized pending requests.")
        return
    for request in requests[:10]:
        number = request["number"]
        if already_answered(number):
            base.gh("issue", "close", str(number), "-R", REPO)
            continue
        try:
            result = run_action(device, request, permissions)
            status = "SUCCESS"
        except ActionDenied as exc:
            status, result = "DENIED", str(exc)
        except BridgeError as exc:
            status, result = "ERROR", str(exc)
        result = public_safe_result(result, private_repo, request["op"], status)
        result = re.sub(
            r"(?i)\b(?:vless|vmess|trojan|ss|hysteria2)://\S+",
            "<redacted link>", result
        )
        result = result[:5000].replace(chr(96) * 3, "'''")
        code = chr(96) * 3
        body = (MARKER + "\nStatus: " + status + " / " + request["op"]
                + "\n\n" + code + "text\n" + result + "\n" + code
                + "\n\nLocal Termux/ADB. No VPN traffic guarantee.")
        base.gh("issue", "comment", str(number), "-R", REPO, "--body", body)
        base.gh("issue", "close", str(number), "-R", REPO)
        print("Completed #" + str(number) + " " + request["op"] + ": " + status)


def main():
    parser = argparse.ArgumentParser(description="Opt-in TV management bridge v2")
    parser.add_argument("--device", default="192.168.0.160:5555")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--watch", action="store_true")
    parser.add_argument("--allow-control", action="store_true",
                        help="Enable remote, app launch, Vitrum process stop")
    parser.add_argument("--allow-screenshots", action="store_true",
                        help="Enable screenshots ONLY when GitHub control repository is private")
    parser.add_argument("--allow-installs", action="store_true",
                        help="Enable SHA-256 pinned local APK installation")
    parser.add_argument("--allow-maintenance", action="store_true",
                        help="Opt in to fixed CleanYourTV audit and official theme actions")
    parser.add_argument("--allow-reboot", action="store_true",
                        help="Separately allow verified CleanYourTV restart test")
    args = parser.parse_args()
    permissions = Permissions(control=args.allow_control,
                              screenshot=args.allow_screenshots,
                              install=args.allow_installs,
                              maintenance=args.allow_maintenance,
                              reboot=args.allow_reboot)
    try:
        with single_agent_lock():
            base.verify_access(args.device)
            if args.once:
                process(args.device, permissions)
            else:
                print("Watching authorized issues every 15s. Ctrl+C to stop.")
                while True:
                    try:
                        process(args.device, permissions)
                    except BridgeError as exc:
                        print("Bridge unavailable: " + str(exc), file=sys.stderr)
                    time.sleep(15)
    except KeyboardInterrupt:
        print("\nStopped.")
    except (BridgeError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
