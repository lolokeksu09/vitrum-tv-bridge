# CleanYourTV BOXY maintenance through the private TV bridge

This implements the verified 2026-11-18 BOXY completion flow using the
official `Gathin23/cleanyourtv` v3.5.0 source pinned at commit
`d11bd68c9ac45b2fb38480941586d17930137e9d`.

## Operations (fixed; no arbitrary shell)

| GitHub issue title | JSON `op` | Local opt-in | Behavior |
|---|---|---|---|
| `TVBRIDGE/v2 cleanyourtv_probe` | `cleanyourtv_probe` | `--allow-maintenance` | Reads BOXY model, HOME, display, count of disabled packages and limited OEM package information |
| `TVBRIDGE/v2 cleanyourtv_apply_theme` | `cleanyourtv_apply_theme` | `--allow-maintenance` | Backs up private theme files, applies official `tools/theme.sh` with `presets/cleanyourtv-boxy/`, verifies provider readback, Home and package states, attempts theme rollback on errors |
| `TVBRIDGE/v2 cleanyourtv_reboot_check` | `cleanyourtv_reboot_check` | `--allow-maintenance --allow-reboot` | Requires fresh verified theme receipt, reboots BOXY and checks Home and disabled packages after ADB reconnect |

All issues must be posted by the authenticated owner and be younger than one hour, with
JSON body `{"v":2,"op":"cleanyourtv_probe","args":{}}` (change `op` for the other two).
Only the owner's previously confirmed `192.168.0.160:5555` is accepted.

**Not available:** arbitrary remote shell, modifying DNS, uninstalling packages, deleting
app data, forcing root, flashing firmware, or disabling OEM/Android system services.
The owner can always terminate the bridge locally with Ctrl+C.

## Operator command in Termux

Stop any currently running old `tv_bridge_v2.py --watch` instance with Ctrl+C first.
The new Python code is loaded only when the agent restarts.

```bash
git -C ~/vitrum-tv-bridge pull --ff-only
python ~/vitrum-tv-bridge/tv_bridge_v2.py --watch --allow-control --allow-screenshots --allow-maintenance --allow-reboot
```

The theme action clones the official public repo and provisions a Python venv in
`~/.cache/cleanyourtv-official-v3.5.0` on the **phone**, not the TV. For Termux,
`python3`, `git`, `adb` and `pip` must be installed. Python packages must be
downloadable from the network on the phone. The upstream tool uses a
`TV_ADB_BINARY=adb` connection already authorized to the BOXY.

A separate local, private backup is created under
`~/cleanyourtv-backups/theme-<UTC timestamp>/`. It includes prior Android
disabled states, previous theme files if accessible and before/after captures.
The theme helper **refuses to overwrite** a theme directory it cannot back up.
It does not add, remove or disable system packages.

The selected black four-column preset includes the screenshot-confirmed dock
packages: YouTube, VK Видео, v2rayNG and BrowseHere. This is a configuration
overlay; the installed CleanYourTV package `com.gathin.tvhome` is unchanged.

The reboot action is intentionally a separate issue, so the user/assistant can inspect
the post-theme screenshot first. Network ADB may close after an Android 11 reboot;
`REBOOT_UNVERIFIED` means verification did not finish, **not** that the TV failed
to boot. Check the physical display before attempting further changes.

## What cannot be verified by ADB key injection

The physical remote's dedicated TV/source buttons, HDMI cabling and TV video
playback, real VPN TUN/DNS routing, OEM package necessity, and whether the launcher
stays usable under long-term standby require physical or app-level checks.
Reboot alone does not establish these.

## Restore / final security

On a failed theme write the helper invokes the upstream official `theme.sh`
with the backup, or `--reset` if no prior theme existed. The backup remains
available for local recovery, even if automated recovery fails.

When satisfied, turn off Network/USB/Wireless debugging on the BOXY and verify
port 5555 is closed from the phone. This necessarily disconnects the agent.
**Do not silently close ADB** before recovery and reboot checks have completed.
