# BOXY CleanYourTV: autonomous theme-only deployment

## Purpose

The owner does not want to run `git pull` for every CleanYourTV appearance change.

Once the installed Termux maintenance script is updated, the existing authorized
`TVBRIDGE/v2 cleanyourtv_apply_theme` request directly downloads the
**configuration JSON** from the current private GitHub `main` commit.
For the anime preset, the installed trusted script additionally retrieves one
**hard-coded SHA-verified CC0 JPEG** from the pinned upstream CleanYourTV v3.5.0
commit. The URL/path cannot be influenced by theme JSON or remote requests.
It does **not** pull, checkout, update or execute remote source code.

A new design release is deployed by: updating and merging the theme configuration,
waiting for CI, creating a private owner-authored theme request, inspecting
its result and verifying a live screenshot and D-pad navigation through the agent.

## Mandatory safeguards

- The exact branch SHA is resolved first and used to fetch `config.json`.
- Both named GitHub check jobs, `verify-preset` and
  `strict-read-only-bridge`, must report completed/success for that commit.
- A strict allowlist limits which theme keys may change. BOXY must keep a flat
  black base, no colored glow, visible vertical app grid. Wallpaper is enabled
  only with a separately SHA-pinned upstream anime JPEG; no unverified image or
  arbitrary path may be supplied,
  and the existing four known pinned app packages. Values and types are bounded.
  Unknown fields are rejected, including package removal, remote shell,
  accessibility/input remapping, network or VPN settings.
- The trusted local maintenance code performs the same device/Home checks,
  private backup, official ThemeProvider readback, foreground verification
  and rollback as before. A no-wallpaper theme writes only `config.json` and
  `theme_revision`; the anime theme writes only the three allowlisted launcher
  files, including `wallpaper.jpg` after backing up its exact previous bytes.
- If GitHub API/CI/ADB is unavailable, the operation **fails closed**. Never
  silently fall back to applying an out-of-date local config.
- The exact applied JSON and prior wallpaper bytes are saved in the local private backup, allowing
  reboot verification even if `main` changes later.
- No automatic package disable, data deletion, firmware flash, TV power action,
  root, screenshot posting or reboot is introduced.

## One-time local bootstrap

The running v2 agent currently executes scripts from the local Termux filesystem;
GitHub Issues cannot replace its own code. The first installation of this
limited automatic config-fetch feature therefore still needs one explicit
bootstrap on the phone **in a second Termux session**:

```bash
git -C ~/vitrum-tv-bridge pull --ff-only
```

No agent restart is needed: the existing v2 bridge launches
`scripts/cleanyourtv_boxy_maintenance.py` fresh for each approved request.

**After installing the updated theme script once, no further `git pull` is necessary for
changes confined to the permitted CleanYourTV theme JSON and the one fixed,
SHA-verified anime wallpaper. This **new anime feature requires an additional
one-time bootstrap** because the previously installed script rejects wallpaper.** Updates to agent
code, expanded permissions or new operations still require explicit local
installation; the agent is deliberately not a remote arbitrary-code executor.

The Termux agent must be running with `--watch --allow-maintenance` to
process remote requests. Its launch flags control whether commands can run;
a GitHub Issue alone cannot override these permissions.

## Verification and rollback

Results are posted to the specific private request. A successful theme write is
not equivalent to successful visual acceptance. Obtain fresh TV screenshots,
test focus and all visible rows, and verify Home after launching an app.

To restore an earlier theme, use the retained local private backup under
`~/cleanyourtv-backups/theme-<UTC timestamp>/`. Errors attempt an automatic
byte-exact rollback of the previous config and revision.

The local Home/ADB connection is not a cloud service. If the phone sleeps, Termux
stops or Wi-Fi/ADB disconnects, autonomous application pauses until the
locally authorized agent runs again.
