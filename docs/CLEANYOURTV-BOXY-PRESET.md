# CleanYourTV BOXY — Modern TV OS (AMOLED)

Device: Skyworth BOXY HP44H / Android TV 11, existing `com.gathin.tvhome`
CleanYourTV v3.5.0. This is a **theme-only update** (no new APK).

## Goal

Practical modern TV home rather than illustration-led or frosted-glass design:
apps visible immediately, visually quiet chrome, deep black on OLED, and clear
remote focus.

## Installed theme target

- **True black** `#000000`, `wallpaper=false`, `wallpaper_dim=0`: the previous
  anime image is **not displayed**. The existing `wallpaper.jpg` is **not
  deleted or rewritten**, so it remains recoverable from the prior theme.
- **6 columns**, `rows_below_dock=2`: the current nine installed tile icons
  fit in the existing screenshot viewport without scrolling.
- **Four fixed favourites** remain at the beginning: YouTube, VK Видео,
  v2rayNG, BrowseHere. `fill_dock=true` fills unused first-row slots from
  the installed app list. No apps are hidden, disabled, removed or renamed.
- **No glass**: `dock_glass=false`, `dock_band=false`,
  `dock_band_all=false`, fully opaque dock, no coloured app or ambient glow.
- **Compact header**: clock/date on the left, icon-only Wi-Fi/Settings on the
  right; greeting/title omitted. Wi-Fi and other existing actions are kept.
- **No redundant names** beneath every banner (`always_show_names=false`).
  The selected app may still show its name for remote clarity.
- **Focus navigation**: `glass_style=rim` keeps the thinnest solid non-glass
  outline; overshoot and advanced effects stay off.
- **Performance preset**: `reduced_motion=true` uses the upstream low-motion
  implementation: no tile entrance/replay, no long fades and UI transitions
  at most 90 ms. Scrolling may jump between positions rather than gliding.
  This improves perceived responsiveness and reduces animation work; actual
  frame times and CPU usage on BOXY remain unmeasured. The launcher v3.5.0 accepts
  only `glass`, `rim`, `halo`, not `none`. Removing all focus indication
  is not compatible with reliable D-pad control.

## Trusted deployment

The same current local Termux agent uses
`TVBRIDGE/v2 cleanyourtv_apply_theme`. It fetches the JSON from the exact
successful `main` CI SHA, strictly validates allowed fields and takes a
private launcher ThemeProvider backup before changing `config.json` and
`theme_revision`. No wallpaper bytes are written in this mode. A failed write
attempts byte-exact rollback; system packages, CEC, VPN, network settings and
remote mappings are not changed.

**One-time agent update is required for the performance switch.** The
previously installed script only allows 28 theme keys and rejects the new
`reduced_motion` key. Install the updated trusted local script via a normal
`git pull --ff-only` and restart the bridge once; no arbitrary remote code
updates are permitted. Any screenshot commit advances `main`;
both required CI checks must be successful for the **current exact** SHA
before the agent accepts an apply request.

## Real TV acceptance

1. CI `verify-preset` and `strict-read-only-bridge` pass on merged `main`.
2. Bridge receipt confirms provider readback, HOME focus and unchanged disabled
   packages; backup path is recorded.
3. On-device ThemeProvider readback confirms `reduced_motion=true`; HOME
   remains the foreground launcher and the installed/disabled app sets do not
   change. As the control repository is public, do not upload screenshots.
   Visual inspection must be local or via a separately private channel.
4. D-pad Right/Down navigate to adjacent tile and second row; focus remains
   visible and no app gets launched inadvertently. Real frame times require
   local `dumpsys gfxinfo` measurements outside the public issue tracker.
5. Return to HOME and inspect result. Reboot is deliberately separate.

## Revert

Restore previous launcher theme using the private backup created at apply
time. Do not clear application data or disable the stock TV launcher.

## Upstream references

- [CleanYourTV v3.5.0 theme format](https://github.com/Gathin23/cleanyourtv/blob/v3.5.0/themes/README.md)
- [CleanYourTV focus-style implementation](https://github.com/Gathin23/cleanyourtv/blob/v3.5.0/launcher/app/src/main/java/com/gathin/tvhome/GlassView.java)
