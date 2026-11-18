# CleanYourTV BOXY — Minimal OLED v2

This preset implements the user's approved minimal launcher concept **on the
existing CleanYourTV 3.5.0 APK**. It does not produce a new launcher or claim
pixel-perfect identity with the design render.

## Visible design

- True-black base with a subtle procedural red arc. The art is generated locally
  by `scripts/boxy_minimal_wallpaper.py` (pure Python stdlib, 1600×900).
- Large greeting, live clock and date remain at upper left. Wi-Fi and Settings
  keep visible labels at upper right.
- Four actual pinned apps in exact confirmed order:
  YouTube, VK Видео, v2rayNG, BrowseHere.
- One frosted-glass dock, no redundant full-sized app name above it.
- No permanently visible lower app rows; **all other installed apps remain
  reachable by horizontal D-pad scrolling in `single_row` mode**.
- `rows_below_dock=1` supplies vertical spacing that raises the one-row dock
  toward the center; it does not create a second row when `single_row=true`.
- `app_glow=true` retains a focused-app accent. `ambient_glow=false` and
  `sky_intensity=0` prevent the heavy burgundy full-screen wash.
- `wallpaper=true` enables only the launcher-owned static background
  `wallpaper.jpg`. No system wallpaper or `wallpapers/` collection changes.

### Runtime differences from mockup

The mockup is not an APK screenshot. Actual font rendering, app banner artwork,
focus ring, tile dimensions and top-bar controls are rendered by the installed
CleanYourTV 3.5.0 engine. Do not substitute mock thumbnails or fake content.

## Installation

The existing private BOXY agent can run fixed `cleanyourtv_apply_theme`.
From Termux the equivalent local one-shot command after pulling the current
repository is:

```bash
python ~/vitrum-tv-bridge/scripts/cleanyourtv_boxy_maintenance.py theme
```

The script validates the **exact** BOXY identity, system Home and installed dock
packages. Using the official exported ThemeProvider it backs up the current
`wallpaper.jpg`, `config.json` and `theme_revision` before overwriting only
those three launcher-owned paths. Old `wallpapers/` collections remain unchanged.
A copy of the previous disabled-package list and a pre-change screenshot is
retained in `~/cleanyourtv-backups/theme-<UTC timestamp>/`.

The script verifies actual provider readback, running Home, disabled-package
state and a new screen capture. On errors it attempts byte-exact rollback for
those three files and restarts the previous launcher configuration. No root,
generic remote shell, theme reset, system-package disable, DNS write or firmware
operation is included.

**On-device acceptance:** compare a fresh 1920×1080 capture; confirm black
background/red arc, four dock apps, no hero label or second visible grid;
test Left/Right/OK/Home, open other apps by scrolling, and access Wi-Fi/Settings.
A successful write or CI test alone is not a visual or remote-control proof.
Reboot is a separate, optional validated action, never assumed completed.
