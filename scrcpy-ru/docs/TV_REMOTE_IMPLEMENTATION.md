# Scrcpy RU — Android TV remote overlay v1

Status: feature branch `feature/scrcpy-tv-remote-v1`; integration and Android tests are required before considering it accepted.

## Implemented

- A small **TV** launcher in the top-right of the active mirroring player, next to the existing draggable menu.
- Entry via the session menu under "TV remote".
- Non-modal near-black overlay anchored at the bottom of the video player. Close via the × button or tap TV again.
- Ten whitelisted Android `KeyEvent` actions: `DPAD_UP`, `DPAD_DOWN`, `DPAD_LEFT`, `DPAD_RIGHT`, `DPAD_CENTER`, `BACK`, `HOME`, `VOLUME_DOWN`, `VOLUME_UP`, `VOLUME_MUTE`.
- Each tap uses existing scrcpy `Control.clickKey()`; no ADB shell execution, automation, new permissions, or scrcpy server upgrade.
- The panel is dismissed on manual disconnect, session termination, and when returning from the player.
- If control is unavailable or the device is not connected, the app displays a localized explanation and no packet is sent.
- Strings added to EN/RO/RU (`382` strings per language total).
- Existing video, touchpad modes, screenshot/recording, USB and Wi-Fi connection stay available.

## Limitations

- TV remote works **on the controller Android phone**, targeting an Android TV/TV Box through USB or Wi-Fi ADB. Do **not** install the APK on the TV.
- The overlay is intentionally small and may cover the lower part of the video; close it to use the entire frame.
- No held-button repetition, swipe-to-hide, custom button mapping or remote profile binding in this stage.
- No new reconnect backoff, log rotation, or advanced connection-stage diagnosis (separate parts of Phase 3).
- `Control` must be enabled in the selected profile; cameras configured with `control=false` cannot use the panel.
- As with prior experimental builds, the APK has a **separate package ID** `ro.sw3g.scrcpy.ru.tvremote`. It cannot read previous app IDs' ADB identity or settings and must be paired/authorized separately.
- Not a production release. Debug signing cannot guarantee automatic updates of an APK built in a different CI run.

## Quality gates

1. Patch is applied after RU localization, Profiles v1 and Settings v2 with exact anchors, without modifying the server binary.
2. Static verification: ten Android keycodes, whitelist enforcement, lifecycle, translations, and absence of shell commands.
3. JUnit: seven `TvRemoteKeysTest` checks plus prior 14 tests (at least 21 in one run).
4. Gradle `assembleDebug`, `aapt dump badging`, `apksigner verify`, SHA-256 and published APK artifact.
5. Device acceptance remains **NOT RUN** until installation, connect, video, D-pad navigation, Home/Back, volume and rotation are tested on an actual phone + TV Box.

## Follow-up

After device validation, address real button sizing/orientation based on actual screenshots and user observations; next reliability work remains connection-stage diagnostics, retry backoff and log rotation per `ROADMAP.md`.
