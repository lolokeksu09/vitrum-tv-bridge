# BOXY CleanYourTV visual preset

`presets/cleanyourtv-boxy/config.json` is a **non-installed candidate**
configuration in the exact JSON format documented by upstream
[Gathin23/cleanyourtv themes](https://github.com/Gathin23/cleanyourtv/blob/main/themes/README.md).

The preset:
- retains the currently configured `dock_apps` (it deliberately omits the
  `dock_apps` key, as actual app packages/order must come from the BOXY);
- uses the upstream four-column default, black background, glass dock,
  visible Inputs/Network controls, and no animated wallpaper;
- does not require a new APK and does not change system HOME or packages.

**Do not apply until package inventory and dock choices are reviewed.**

For application, use the upstream `tools/theme.sh` from a clone of the
official repository (with its documented Python virtual environment),
with `TV_HOST=192.168.0.160` and the absolute path to this folder.
The upstream tool sends `config.json` and restarts CleanYourTV to pick it up.

Rollback is the upstream `TV_HOST=192.168.0.160 tools/theme.sh --reset`
(which clears overlay settings) or the previously saved theme configuration.

After application, capture the TV screen and check four-way D-pad navigation,
application launch, Input menu, Wi-Fi pill, physical Home button and
availability of the original Settings. Verify the live behavior before calling
the preset accepted.
