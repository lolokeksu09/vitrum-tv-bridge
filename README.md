# Vitrum TV — private Termux / ADB bridge

A **locally operated, opt-in** bridge between ChatGPT's connected GitHub account and a BOXY Android TV on the owner's home Wi-Fi. GitHub Issues in this **private repository** carry narrow, typed requests. A local Termux agent checks them, runs permitted ADB commands, posts results in the same issue and closes it.

**Working v1:** `tv_bridge.py` — read-only diagnostics.
**Expanded v2:** `tv_bridge_v2.py` — additional diagnostics and separately authorized remote/app controls, screenshots and Vitrum TV debug APK installation.

Instructions in Russian: [README.ru.md](README.ru.md).

## Phone setup

The owner's phone uses local GitHub CLI and Wi-Fi ADB. Keep the TV's actual LAN address and credentials outside the public repository.

```bash
pkg install -y python gh android-tools
git -C ~/vitrum-tv-bridge pull --ff-only
python ~/vitrum-tv-bridge/test_tv_bridge.py
python ~/vitrum-tv-bridge/test_tv_bridge_v2.py
```

If this repo has not been cloned, first run `gh repo clone lolokeksu09/vitrum-tv-bridge ~/vitrum-tv-bridge`. Do not share GitHub auth tokens or ADB private keys.

### Start a session

Read-only, one pass:

```bash
python ~/vitrum-tv-bridge/tv_bridge_v2.py --once
```

Allow non-destructive TV remote operations and app launches while Termux is open:

```bash
python ~/vitrum-tv-bridge/tv_bridge_v2.py --watch --allow-control
```

Optional extra permissions; **off unless explicitly enabled in the local command**:

- `--allow-screenshots` — captures current TV screen and uploads PNG to `captures/` in **private Git history**. The image can display personal information and removing a file from a later commit does not erase history. Enable only when the current TV screen is safe to share with private-repo readers.
- `--allow-installs` — installs a local APK matching the Vitrum-TV filename restriction after matching an exact supplied SHA-256. This is **not a signing certificate / APK identity verification**; install only APKs from a trusted, verified source. Existing install may reject a different debug certificate. This command does not uninstall an app or erase data.

All three switches may be combined only if the operator wants those permissions active during the session. Stop immediately with **Ctrl+C**. The phone sleeping or disconnecting from the local network interrupts the bridge; this is not persistent background access.

## V2 protocol

Each GitHub Issue must be created by `lolokeksu09`, within the previous **1 hour**, with an exact title `TVBRIDGE/v2 <operation>` and JSON body of the following form:

```json
{"v":2,"op":"launch_vitrum","args":{}}
```

All three JSON keys are mandatory; extra keys, unknown operations, unexpected argument shapes, request authors or title/body mismatches are ignored. The agent authenticates the GitHub CLI owner before doing anything.

| Operation | Required args | Local permission | Effect |
|---|---|---|---|
| `device_summary` | `{}` | Default | Android, ABI, model, security patch |
| `vitrum_status` | `{}` | Default | Vitrum TV package, version, process |
| `display_status` | `{}` | Default | Screen size / density |
| `focus_status` | `{}` | Default | Focused system window |
| `app_list` | `{}` | Default | First 80 third-party package IDs |
| `app_info` | `{"package":"com.example.app"}` | Default | Installed package version |
| `vitrum_memory` | `{}` | Default | Current Vitrum TV memory summary |
| `launch_vitrum` | `{}` | `--allow-control` | Open Vitrum TV |
| `stop_vitrum` | `{}` | `--allow-control` | Force-stop Vitrum TV without deleting data; may interrupt future VPN sessions |
| `launch_app` | `{"package":"com.example.app"}` | `--allow-control` | Request app launch through Android TV launcher |
| `key` | `{"key":"LEFT"}` | `--allow-control` | Send validated key event |
| `screenshot` | `{}` | `--allow-screenshots` | Store PNG in private Git history |
| `install_vitrum` | `{"filename":"Vitrum-TV-BOXY-0.1.0-dev.apk","sha256":"<64 lowercase hex digits>"}` | `--allow-installs` | Install a matching local APK file after SHA-256 check |

Allowed key names: `UP`, `DOWN`, `LEFT`, `RIGHT`, `OK`, `BACK`, `HOME`, `ENTER`, `MENU`, `VOLUME_UP`, `VOLUME_DOWN`. The APK file must be inside `~/storage/downloads` and not a symlink. The request supplies **only** an allowlisted operation and validated arguments; it cannot supply Android shell syntax.

V1 owner-authored read-only requests remain compatible with v2.

## BOXY CleanYourTV maintenance (separate opt-in)

The private bridge also supports three **fixed** maintenance operations:
`cleanyourtv_probe` (read BOXY status),
`cleanyourtv_apply_theme` (local backup + official pinned upstream `tools/theme.sh`),
and `cleanyourtv_reboot_check` (guarded Home/reboot verification).

These operations require `--allow-maintenance` when starting the agent.
The reboot additionally requires `--allow-reboot`. The normal
`--allow-control` and `--allow-screenshots` permissions do not enable either.

The maintenance operation does **not** grant arbitrary remote ADB shell,
package disable/uninstall, root, network DNS changes, or firmware flashing.
See [BOXY maintenance instructions](docs/CLEANYOURTV-BOXY-MAINTENANCE.md).

For future appearance-only updates the BOXY can obtain a strictly validated,
CI-approved theme JSON directly from `main` **without another manual git pull**.
The first installation of that feature still requires a single local repository
update because the existing agent cannot change its own code remotely.
Anime artwork support similarly needs a one-time trusted-code update: only a
fixed, Git-SHA-verified CC0 image from the official upstream theme can be
installed, and previous wallpaper bytes are backed up for rollback. See
[autonomous BOXY theme deployment](docs/CLEANYOURTV-BOXY-AUTONOMOUS.md).


## Trust boundary and limitations

- **No arbitrary shell**, root, deletion, firmware flashing, accessibility services, remote arbitrary file access, VPN credential retrieval, SSH server, port forwarding or inbound Internet access.
- The **local** operator grants or withholds privileged capabilities using launch flags; merely creating a GitHub Issue is not consent to an action if its flag is disabled.
- Posting to a private GitHub repository uses HTTPS; the **local ADB TCP/5555 session should only be used on trusted LAN**. Never expose 5555 to the Internet.
- Anyone with access to the private repo could read issue results and uploaded screenshots. Screenshots remain in Git history after removal from the current branch.
- A GitHub owner credential compromise can forge requests; strict schema, TTL, limited keycodes and local flags reduce the impact. The bridge is **not** an end-to-end cryptographic command channel.
- A successful installation or Activity launch does **not** demonstrate VPN TUN/DNS/network functionality.
- Process errors are returned as bounded result comments; completed requests are closed. Responses with existing result markers are not executed twice.

Run the GitHub safety tests with `python -m unittest -v test_tv_bridge.py test_tv_bridge_v2.py`. No real ADB/network calls are made by these unit tests.
