#!/usr/bin/env python3
"""Read-only private GitHub Issues -> Termux ADB bridge for Vitrum TV."""
import argparse
import json
import re
import subprocess
import sys
import time

REPO = "lolokeksu09/vitrum-tv-bridge"
OWNER = "lolokeksu09"
PREFIX = "TVBRIDGE/v1 "
MARKER = "<!-- tv-bridge-v1-result -->"
OPERATIONS = frozenset(("device_summary", "vitrum_status", "display_status", "focus_status"))


class BridgeError(Exception):
    pass


def execute(argv, timeout=25, allow_failure=False):
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                errors="replace", timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise BridgeError("Command unavailable or timed out: " + argv[0]) from exc
    if result.returncode and not allow_failure:
        raise BridgeError(argv[0] + " failed (exit " + str(result.returncode) + ")")
    return result.stdout.strip(), result.returncode


def gh(*args):
    return execute(["gh", *args], timeout=25)[0]


def adb(device, *args, allow_failure=False):
    return execute(["adb", "-s", device, "shell", *args],
                   timeout=20, allow_failure=allow_failure)


def verify_access(device):
    login = gh("api", "user", "--jq", ".login").strip()
    if login != OWNER:
        raise BridgeError("GitHub login is not the repository owner")
    state, code = execute(["adb", "-s", device, "get-state"],
                          timeout=8, allow_failure=True)
    if code or state.strip() != "device":
        # ADB's selected TCP device is often forgotten when Termux/adb restarts.
        # Try one ordinary connection; never change adbd mode or open port 5555.
        if re.fullmatch(r"[A-Za-z0-9.-]+:[0-9]{2,5}", device):
            answer, _ = execute(["adb", "connect", device],
                                timeout=12, allow_failure=True)
            state, code = execute(["adb", "-s", device, "get-state"],
                                  timeout=8, allow_failure=True)
            if code or state.strip() != "device":
                detail = (answer.strip() or state.strip() or "no response")[:180]
                raise BridgeError(
                    "ADB still offline after adb connect " + device + ": " + detail +
                    ". Check BOXY power/Wi-Fi, network debugging, and ADB authorization. "
                    "Do not disable the stock Home while ADB is offline."
                )
        else:
            raise BridgeError(
                "ADB device " + device +
                " is offline. Reconnect or authorize it before starting the bridge."
            )
    print("Ready: GitHub owner authenticated; local ADB device connected.")


def parse_issue(issue):
    if not isinstance(issue, dict):
        return None
    if not isinstance(issue.get("author"), dict):
        return None
    if issue["author"].get("login") != OWNER:
        return None
    title = issue.get("title")
    body = issue.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        return None
    if len(body) > 150 or not title.startswith(PREFIX):
        return None
    try:
        request = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(request, dict) or set(request) != {"v", "op"}:
        return None
    operation = request.get("op")
    if type(request.get("v")) is not int or request["v"] != 1:
        return None
    if type(operation) is not str or operation not in OPERATIONS:
        return None
    if title != PREFIX + operation:
        return None
    number = issue.get("number")
    if type(number) is not int or number < 1:
        return None
    return number, operation


def perform(device, operation):
    if operation == "device_summary":
        props = (
            ("model", "ro.product.model"),
            ("android", "ro.build.version.release"),
            ("sdk", "ro.build.version.sdk"),
            ("abi", "ro.product.cpu.abilist"),
            ("security_patch", "ro.build.version.security_patch"),
        )
        lines = []
        for key, prop in props:
            value, _ = adb(device, "getprop", prop)
            lines.append(key + ": " + (value[:200] or "(empty)"))
        return "\n".join(lines)

    if operation == "vitrum_status":
        pkg, rc = adb(device, "pm", "path", "app.rayclient.tv",
                      allow_failure=True)
        if rc or not pkg.startswith("package:"):
            return "installed: no\nprocess_running: no"
        details, _ = adb(device, "dumpsys", "package", "app.rayclient.tv")
        version = re.search(r"(?m)^\s*versionName=(\S+)", details)
        code = re.search(r"(?m)^\s*versionCode=(\d+)", details)
        pid, status = adb(device, "pidof", "app.rayclient.tv",
                          allow_failure=True)
        return "\n".join((
            "installed: yes",
            "version: " + (version.group(1) if version else "unknown"),
            "version_code: " + (code.group(1) if code else "unknown"),
            "process_running: " + ("yes" if status == 0 and pid else "no"),
        ))

    if operation == "display_status":
        size, _ = adb(device, "wm", "size")
        density, _ = adb(device, "wm", "density")
        return "display: " + size[:200] + "\ndensity: " + density[:200]

    if operation == "focus_status":
        # Some Android TV 11 builds omit focus data from "window windows".
        # Use the full window service, then the resumed-activity fallback.
        window, _ = adb(device, "dumpsys", "window")
        lines = [line.strip()[:260] for line in window.splitlines()
                 if "mCurrentFocus=" in line or "mFocusedApp=" in line]
        if lines:
            return "\n".join(lines[:4])
        activity, _ = adb(device, "dumpsys", "activity", "activities")
        resumed = [line.strip()[:260] for line in activity.splitlines()
                   if "topResumedActivity" in line or "mResumedActivity" in line]
        return "\n".join(resumed[:4]) if resumed else "focus: not reported"

    raise BridgeError("Unknown operation")


def already_answered(number):
    comments = json.loads(gh("api", "repos/" + REPO + "/issues/"
                             + str(number) + "/comments?per_page=100"))
    return any(MARKER in item.get("body", "") for item in comments)


def process(device):
    issues = json.loads(gh("issue", "list", "-R", REPO, "--state", "open",
                           "--limit", "100",
                           "--json", "number,title,body,author"))
    requests = [parsed for item in issues if (parsed := parse_issue(item))]
    requests.sort()
    if not requests:
        print("No pending authorized diagnostic requests.")
        return
    for number, operation in requests[:10]:
        if already_answered(number):
            gh("issue", "close", str(number), "-R", REPO)
            print("Already answered request #" + str(number))
            continue
        result = perform(device, operation)
        body = (
            MARKER + "\n**Read-only operation:** " + operation + "\n\n"
            + chr(96) * 3 + "text\n"
            + result[:5000].replace(chr(96) * 3, "'''")
            + "\n" + chr(96) * 3
            + "\n\nReported by local Termux/ADB. Not a VPN traffic test."
        )
        gh("issue", "comment", str(number), "-R", REPO, "--body", body)
        gh("issue", "close", str(number), "-R", REPO)
        print("Completed #" + str(number) + ": " + operation)


def main():
    parser = argparse.ArgumentParser(description="Read-only Vitrum TV bridge")
    parser.add_argument("--device", default="192.168.0.160:5555")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    try:
        verify_access(args.device)
        if args.once:
            process(args.device)
        else:
            print("Watching every 15 seconds. Ctrl+C stops the bridge.")
            while True:
                try:
                    process(args.device)
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
