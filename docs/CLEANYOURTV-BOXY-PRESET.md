# CleanYourTV BOXY — AMOLED v3

Implemented for the existing `com.gathin.tvhome` CleanYourTV 3.5.0 on
SkyworthDigital HP44H (Android TV 11). This replaces Minimal OLED v2 without
rebuilding an APK.

## User-facing design

- Actual pure black `#000000` background. Wallpaper playback OFF, including
  the red-arc Minimal OLED v2 image. The old wallpaper file is **not deleted**.
- Six columns instead of four; tile width automatically shrinks in the official
  CleanYourTV engine.
- Greeting line removed to reduce header clutter; clock and date remain visible.
  Wi-Fi, Settings, existing app grid and navigation are preserved.
- The existing four dock favorites remain first, in verified order: YouTube,
  VK Видео, v2rayNG, BrowseHere. `fill_dock=true` fills the remaining two
  slots in the top row from the app list.
- `single_row=false` restores the normal vertical grid below the dock.
  `rows_below_dock=2` requests **two additional visible rows**. If the device
  contains more apps than fit, D-pad Down scrolls to the remainder.
- No hero title, no glass-band border behind the entire dock and no
  red app-colour focus glow, ambient glow, sky tint or clock glow.
- `glass_style=rim` deliberately retains a **thin neutral focus outline** so
  the user can navigate by remote. The official CleanYourTV 3.5.0 theme does not
  offer a truly borderless focus state; removing this last visual cue would
  require changing/building launcher source and testing keyboard navigation.
- Wi-Fi and Settings remain available on the top bar.

## Technical implementation

`presets/cleanyourtv-boxy/config.json` is the source of truth.

The private bridge's fixed `cleanyourtv_apply_theme` operation reads this file
on the owner's phone. Unlike Minimal OLED v2, **no wallpaper image is
generated, uploaded, written or deleted**. The existing `wallpaper.jpg` file
stays in place but is not displayed because `wallpaper=false`.

On Android TV 11 the official exported CleanYourTV ThemeProvider is used for
the two changed configuration files (`config.json` and `theme_revision`).
The agent saves previous versions of all three allowlisted theme files,
including the wallpaper, for reliable rollback. It verifies the readback,
correct system HOME and unchanged disabled-package count/list. Backup:
`~/cleanyourtv-backups/theme-<UTC timestamp>/`.

The change does **not** touch system apps, the stock launcher state, Wi-Fi,
HDMI-CEC, VPN, input key bindings or firmware.

## Real-TV acceptance criteria

1. Fresh 1920×1080 screenshot: black background; no red curves, large title or
   red selection glow; six narrower tiles across the first row, with visible
   grid rows beneath.
2. D-pad focus is visible but subdued; check all four directions including
   reaching a tile below the dock.
3. Check a non-favorite app launches via OK, then Home returns to CleanYourTV.
4. Check Wi-Fi and Settings buttons remain navigable.
5. Confirm default HOME and prior system package state with the local bridge.
6. Only call the update installed after a successful live TV screenshot, not
   after GitHub Actions alone. A reboot test is a separate action.

Official reference:
[Gathin23/cleanyourtv themes/README.md](https://github.com/Gathin23/cleanyourtv/blob/v3.5.0/themes/README.md).
