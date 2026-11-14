# Scrcpy RU

Russian localization and development staging area for the Android-to-Android client [sw3gmach1n3/Scrcpy_for_Android](https://github.com/sw3gmach1n3/Scrcpy_for_Android).

**Status (2026-11-14):** Profiles v1 and Settings v2 are implemented in feature branches and built as **test-only APKs**. The current working branch is `feature/scrcpy-settings-v2` in the temporary private staging repository `lolokeksu09/vitrum-tv-bridge` — **not** a standalone Scrcpy RU repository. Android device verification is **NOT RUN**; the TV remote and later roadmap phases are still planned.

- Android client upstream: `d4a9a8caaaf8f0ff21ca6e3a3a406224b9116dd3` (2026-10-22), pinned in `.github/workflows/build-scrcpy-ru.yml`.
- Bundled server protocol: scrcpy **3.3.4**, not the current desktop release; do not replace the server binary without porting and testing the client protocol.
- App build baseline: versionName `1.5.1-foreground-usb`, versionCode `9` in upstream `app/build.gradle`.
- Baseline RU localization: **336** Android resources; Profiles v1 adds 19 and Settings v2 adds 12, giving **367 resources per language**. Some command/reference help remains English.
- Latest verified CI build: [run 43554905418](https://github.com/lolokeksu09/vitrum-tv-bridge/actions/runs/43554905418), revision `31dd71f485858fcd571377e1c0b5dc3cfc0d2990`, at least 14 unit tests, APK packaging and signature validation passed. APK SHA-256: `d1e27cefc865f56b76938fc28eb83c27f492763fb0b743f272eb5da5fb2faa63`.
- **Device tests are not complete.** This APK installs under package `ro.sw3g.scrcpy.ru.settings`, separately from prior `.ru` and `.profiles` builds. App-private preferences and ADB identity are not transferable between separate package IDs.
- Packaging: the Settings v2 workflow creates a **debug-signed** APK with `applicationId ro.sw3g.scrcpy.ru.settings`, not a production release. Earlier branches use different test package IDs.

## Documentation

- [Русская версия / Russian overview](README.ru.md)
- [Scope and product decisions](docs/PRODUCT.md)
- [Implementation roadmap and release gates](docs/ROADMAP.md)
- [Device profile specification](docs/PROFILES.md)
- [Profiles v1 implementation](docs/PROFILES_IMPLEMENTATION.md)
- [Settings v2 implementation](docs/SETTINGS_IMPLEMENTATION.md)
- [Architecture and compatibility](docs/ARCHITECTURE.md)
- [Interface and Android TV interaction](docs/UX.md)
- [Tests and acceptance](docs/QA.md)
- [Build, signing and releases](docs/BUILD_RELEASE.md)
- [Repository separation and migration](docs/REPOSITORY.md)

## Working code

This staging branch does **not** vendor the upstream Android sources. The workflow checks out a pinned upstream commit, applies the localization, Profiles v1 and Settings v2 patch scripts, changes application identity, validates strings and the grouping contract, builds with Gradle, and uploads the APK as an Actions artifact. No code or release in this directory should be described as tested on a device unless device test evidence exists.

**Build:** [Build Scrcpy RU APK](../.github/workflows/build-scrcpy-ru.yml).

## Security and attribution

Do not commit ADB identity files, pairing codes, IP addresses of private user devices, screenshots or console logs. Profiles exported for sharing must have all secrets excluded and IPs scrubbed. Keep original project attribution, server license notices and all applicable third-party notices. Never migrate the bridge repository's historical captures or code into a public Scrcpy RU repository.
