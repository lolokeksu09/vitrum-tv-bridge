# CleanYourTV — BOXY HP44H completion procedure

Source of truth: [Gathin23/cleanyourtv](https://github.com/Gathin23/cleanyourtv), especially
`PROMPT.md`, `tools/disable.sh`, `tools/restore.sh`, `tools/theme.sh`, and
`launcher/build-and-install.sh`. Reuse these upstream tools for actual debloat; do **not**
turn guessed package names into `pm disable-user` commands.

## Confirmed so far
- Device: SkyworthDigital BOXY Android TV 4K, HP44H, Android TV 11; private local ADB `192.168.0.160:5555`.
- CleanYourTV `com.gathin.tvhome` installed from the pinned upstream 3.5.0 source in
  the dedicated GitHub Actions workflow.
- User reports that the launcher now replaces the stock Home.
- Prior verified screenshot shows launcher UI; current Home ownership after reboot is **not yet tested**.
- The prior handover tool has recovery data under `~/cleanyourtv-backups/home-*/`.
- Four read-only private GitHub bridge requests have been posted: #290–293. They only run when
  the owner starts the Termux agent and it is still within its 1-hour TTL.

## Next action on the BOXY — read-only inventory
On the connected phone in Termux:
```bash
git -C ~/vitrum-tv-bridge pull --ff-only
python ~/vitrum-tv-bridge/scripts/audit-cleanyourtv-boxy.py
```
This writes the **shareable** package inventory to `~/storage/downloads/BOXY-CleanYourTV-audit.txt`,
and a TV screenshot to `~/storage/downloads/BOXY-CleanYourTV-screen.png` when available.

Keep `settings-*.txt`, `properties.txt`, `usb.txt`, `connectivity.txt`, `tv-inputs.txt`
and the complete backup folder inside Termux — they may contain identifying information.
The audit makes **no** modifications. A report of successful package classification cannot
be asserted until the real inventory has been inspected.

## Required owner decisions BEFORE disabling packages
1. USB attachments: what uses the TV's USB ports (storage, audio, wireless dongles),
   and in particular whether the TV network is on a **USB Ethernet adapter**.
   Debugging may cause USB/ethernet to disconnect.
2. Which preinstalled and streaming apps should be kept, and which are unused.
3. Keep or disable **Chromecast / Miracast / DLNA**, voice assistant, automatic firmware
   updates? These are independent decisions. Retain Google Play/Play Services, input
   routing, HDMI, remote and Bluetooth under all circumstances.
4. Dock: 4/5/6/7 slots and preferred installed apps in order. The upstream default is
   four slots when there is no preference.
5. Optional ad-filtering DNS only after checking for router-level Pi-hole, AdGuard Home,
   VPN / fake-IP proxy or equivalent DNS filtering (Android Private DNS bypasses these).
   It does not block in-stream YouTube ads.

## Package approval and safe debloat
- Start with the saved list of **currently disabled** packages. Some may predate this
  session; never blanket-enable them or reinterpret them as new changes.
- Use names from the actual BOXY inventory, inspect unknown ones with
  `adb shell dumpsys package <exact package>` without launching factory menus.
- Split into vendor telemetry, vendor recommendations/advertising, background extras,
  optional preloaded apps and streaming apps. A name-match is only a REVIEW flag,
  not authorization to disable.
- Exclude all core Android, TV input/source, remote, Bluetooth, keyboard, Google Play
  and Play Services packages.
- Create the approved BOXY-specific file `debloat.txt` only after review. Keep
  an explicit list of packages left alone and reasons.
- On a PC with the upstream repo and its `tools/venv`:
```bash
TV_HOST=192.168.0.160 tools/disable.sh /path/to/approved/debloat.txt
```
  The matching restore is:
```bash
TV_HOST=192.168.0.160 tools/restore.sh /path/to/approved/debloat.txt
```
  Those are the official upstream, safety-guarded scripts. Do not copy a list for
  a different Skyworth or Android release.
- Change packages in small groups, checking a screenshot, actual Home, HDMI, Internet,
  voice/casting controls (if retained), app launch and ADB after each group.
  Before reboot, wait at least 15 seconds for package state to be persisted.
- Reboot once and check Home, disabled-package list, physical remote navigation,
  settings/inputs, ADB, streaming and media playback. Restore immediately if the
  Home or TV input handler is broken.

## Launcher cosmetics and usability
- Keep upstream `com.gathin.tvhome`, rather than introducing a separate launcher.
- Prefer a theme overlay via `tools/theme.sh` / `config.json`, not invasive source edits.
  Layout keys: `columns`, `dock_apps`, `rows_below_dock`, `dock_title`,
  `dock_row`, `icon_only_buttons`; see `themes/README.md`.
- Confirm dock order/app IDs from the **real** installed package inventory.
- Test DPAD Up/Down/Left/Right/OK/Back, physical remote Home and
  Input/Settings/volume and direct app buttons, not just injected ADB keys.
- Preserve current source build until a new theme has been observed working.
  Theme may be reset with upstream `tools/theme.sh --reset`.

## Security and final handoff
- Record file names and SHA of backups, exact modified package IDs, before/after screenshots,
  the launcher Home result, reboot test and a restoration command.
- At the end, close plaintext network ADB access / Wireless debugging and revoke debugging
  authorisations unless the owner explicitly wants to retain them for ongoing work.
  Confirm port 5555 is closed. Keep backups until the owner has tested the TV.
- The bridge is an opt-in agent; a GitHub issue alone does not provide access to the
  TV. Never claim changes or screenshots were observed unless an actual issue result,
  local report or live command verifies them.

## Status matrix
| Stage | Status |
|---|---|
| Pinned CleanYourTV APK build | PASS (CI) |
| Home works after handover | Reported by owner, actual reboot test pending |
| Private pre-change backup | Exists from prior staging/handover; fresh inventory pending |
| Full inventory | NOT RUN on real BOXY until Termux command executes |
| Debloat package approvals | BLOCKED on inventory and owner's keep/disable choices |
| New theme | NOT APPLIED |
| Physical remote / HDMI / reboot acceptance | NOT RUN in this phase |
| Close ADB and final restore handoff | NOT DONE |
