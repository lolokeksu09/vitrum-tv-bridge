# Vitrum TV — private diagnostic bridge

Read-only relay from **private GitHub Issues** to BOXY via **Termux + ADB** on the phone. ChatGPT can submit a request through the connected GitHub integration; the phone executes it locally only when the owner starts this script, then writes a reply in the private issue.

## Security contract

- No SSH server, public TCP port, ADB port forwarding, root, unrestricted shell, app installation or system changes.
- The agent accepts **only** requests authored by `lolokeksu09` with exact title/JSON shape and one of four hard-coded operations.
- No issue text becomes an ADB argument or shell command.
- Private GitHub Issues contain the returned **non-secret** device metadata; anybody with read access to this private repo can view that data.
- `--once` makes one pass and exits. `--watch` polls every 15 seconds while Termux is running; stop with Ctrl+C. Phone sleep can interrupt it.
- Keep ADB TCP/5555 confined to a trusted home Wi-Fi network. Do **not** forward this port to the Internet. Unlike GitHub HTTPS, TCP/5555 ADB should not be assumed safe on an untrusted LAN.

## Install on the phone

You already confirmed `adb connect 192.168.0.160:5555` works and `gh auth login` is configured.

```bash
pkg install -y python gh android-tools
gh repo clone lolokeksu09/vitrum-tv-bridge ~/vitrum-tv-bridge
python ~/vitrum-tv-bridge/test_tv_bridge.py
python ~/vitrum-tv-bridge/tv_bridge.py --once
```

The last command processes any requests created in the private repository. It writes a comment to the request and closes it. GitHub credentials remain within Termux. If the repo was already cloned, use `git -C ~/vitrum-tv-bridge pull --ff-only` instead.

### Operations

| Operation | Request title | Exact issue body |
|---|---|---|
| Device model, OS, ABI and patch | `TVBRIDGE/v1 device_summary` | `{"v":1,"op":"device_summary"}` |
| Vitrum TV install/version/running | `TVBRIDGE/v1 vitrum_status` | `{"v":1,"op":"vitrum_status"}` |
| Screen size and density | `TVBRIDGE/v1 display_status` | `{"v":1,"op":"display_status"}` |
| Focused window | `TVBRIDGE/v1 focus_status` | `{"v":1,"op":"focus_status"}` |

Other requests are ignored. A comment marked `tv-bridge-v1-result` prevents duplicate execution if the process stops between posting its result and closing the issue.

## Limitations

This version is **diagnostic only**, not remote control. It cannot install APKs, press remote buttons, obtain screenshots, read credentials or inspect VPN traffic. Each operation uses an allowlisted set of read-only ADB calls. For write operations, any later revision needs a separate user approval mechanism — simply posting an issue would not constitute consent.

No persistent unattended access is established by cloning or running `--once`. Stop the agent and disable wireless debugging when finished.
