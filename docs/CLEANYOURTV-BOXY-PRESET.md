# CleanYourTV BOXY — AMOLED Anime (proposed successor to v3.1)

Target: existing `com.gathin.tvhome` CleanYourTV 3.5.0 on Skyworth HP44H,
Android TV 11. No new launcher APK is installed by this change.

## Visual design

- `#000000` AMOLED-black base with the fixed, original CC0 teal-ninja anime
  wallpaper from upstream `Gathin23/cleanyourtv` v3.5.0.
- The image is slightly dimmed (`wallpaper_dim=15`), with no coloured ambient
  glow, no app glow, no sky gradient, and no animated overshoot.
- Six columns; two visible grid rows below the first row.
- Four known favourites preserved: YouTube, VK Видео, v2rayNG and BrowseHere.
  Remaining app slots are filled normally; no packages are hidden or disabled.
- Frosted dock is OFF (`dock_glass=false`), dock bands OFF, opacity 100%.
- Wi-Fi, Settings and Inputs controls use compact icon-only variants.
- Greeting line stays hidden; clock and date stay visible.
- `glass_style=rim` remains the minimal **solid** focus outline. In the
  existing CleanYourTV 3.5.0 binary, supported focus styles are only glass,
  rim and halo. The theme system cannot turn the outline off. To remove
  it completely requires a **separately built and verified APK**, not an
  unsupported `glass_style=none` value. Keep D-pad focus discoverable.

## Asset provenance

Exactly one original, CC0-licensed upstream `weeb` image is supported:

- Repository: `Gathin23/cleanyourtv`
- Commit: `d11bd68c9ac45b2fb38480941586d17930137e9d`
- Path: `themes/weeb/wallpapers/04-teal-ninja.jpg`
- Git blob SHA-1: `f83c296c9ce3c7a7b8df3b85689a70880e13edc7`
- Source licence/credits: `themes/weeb/CREDITS.md` (CC0; AI-created artwork)

The trusted local script fetches only this exact path, requires base64 and JPEG
format, enforces size bounds, and recalculates the Git blob hash before any
TV modification. There are no user-controlled URLs, remote code downloads,
remote scripts, or unrestricted wallpaper operations.

## Applying and rollback

**Bootstrap required once for this new code path:** the previously installed
agent accepts only no-wallpaper themes. Until the local code is explicitly
updated, it will reject the new JSON and leave the existing v3.1 installed.

After local bootstrap, the same fixed `TVBRIDGE/v2 cleanyourtv_apply_theme`
operation downloads the verified theme JSON from the exact CI-successful
`main` commit and fetches the pinned CC0 JPEG. The official exported
ThemeProvider writes only `wallpaper.jpg`, `config.json` and
`theme_revision` after exact backups. A failure attempts rollback of all
three files, preserving preexisting user data and launcher settings.

No device package changes, firmware, root, network, HDMI-CEC, VPN or
accessibility remapping are involved. No automatic reboot is performed.

## Real-TV acceptance

1. CI: both named checks pass for the exact `main` SHA.
2. Successful bridge receipt includes wallpaper SHA-256 and backup path.
3. Fresh 1920×1080 screenshot: actual anime artwork on black, no dock-glass
   band, grid still visible, clock and Settings readable.
4. D-pad Right, Down, Left, Up all preserve visible focus.
5. If any issue appears, restore the preceding private theme backup.
6. Physical remote/Home-after-app/reboot remain separate verification gates.

## Reference

- [Upstream theme manual](https://github.com/Gathin23/cleanyourtv/blob/v3.5.0/themes/README.md)
- [Weeb theme image credits](https://github.com/Gathin23/cleanyourtv/blob/v3.5.0/themes/weeb/CREDITS.md)
