# CleanYourTV on BOXY (SkyworthDigital HP44H, Android TV 11)

## Purpose and boundaries
Stage the original CleanYourTV v3.5.0 launcher from the pinned public
source commit `d11bd68c9ac45b2fb38480941586d17930137e9d`.
This does not replace Vitrum TV and does not affect Ventry or other VDS projects.

The private CI workflow builds the upstream Java launcher with JDK 17 / Android SDK 34.
Source: https://github.com/Gathin23/cleanyourtv

## Safe staging
Only the previously confirmed TV at the operator's private LAN ADB endpoint
and with model name `4K Android TV Box` is accepted by
`scripts/stage-cleanyourtv-boxy.sh`.

The local script:
1. Verifies that the CI run succeeded on `main` and downloads its APK artifact.
2. Checks the APK against its CI-generated SHA-256.
3. Checks TV identity, ADB authorization and minimum Android SDK 26.
4. Saves installed packages, disabled packages, properties, all three settings namespaces
   and both HOME activity queries to a private backup under `~/cleanyourtv-backups/`.
5. Installs and starts `com.gathin.tvhome/.MainActivity`.
6. Saves a screenshot in Termux Downloads when storage permission is available.

It does **not** run `pm disable-user`, uninstall apps, flash firmware,
reboot, alter DNS, change the default HOME, or turn off the stock launcher.
This is intentionally less invasive than the upstream full install script.
The original repository's `tools/disable.sh`, `tools/restore.sh` and
`launcher/build-and-install.sh` remain the reference for a later full takeover.

## After staging
Inspect the TV screenshot and test physical remote direction/OK/Back/Home,
normal TV Settings, YouTube, streaming apps and Vitrum TV. Confirm that
the stock launcher can still be opened before considering `set-home-activity`
or any package disablement. Inspect the actual package list before proposing
a BOXY-specific debloat list; **do not reuse** a list from another Skyworth model.

The staged APK is debug-key signed in CI. The signing key is ephemeral:
a future CI build may not update an installed copy without a signing mismatch.
Do not clear app data or uninstall automatically to work around this.

## Run requirement
The existing private GitHub-Issues `tv_bridge_v2.py` cannot run arbitrary
commands or install this external APK. If the local agent does not respond,
there is no direct remote installation path from ChatGPT. The owner must run
the local staging script from an authenticated Termux session on the same Wi-Fi.
Running GitHub Actions only creates an artifact; it does not install it.

Do not keep plaintext ADB TCP/5555 enabled after the local setup and verification
is finished unless the owner intentionally wants remote ADB access.
