# Scrcpy RU

Russian localization and development staging area for the Android-to-Android client [sw3gmach1n3/Scrcpy_for_Android](https://github.com/sw3gmach1n3/Scrcpy_for_Android).

**Status (2026-11-14):** localized debug APK builds successfully; device profiles, redesigned settings and TV remote are **planned, not implemented**. This directory is in a **temporary staging branch** of `lolokeksu09/vitrum-tv-bridge`; it is **not** yet an independent Scrcpy RU repository.

- Android client upstream: `d4a9a8caaaf8f0ff21ca6e3a3a406224b9116dd3` (2026-10-22), pinned in `.github/workflows/build-scrcpy-ru.yml`.
- Bundled server protocol: scrcpy **3.3.4**, not the current desktop release; do not replace the server binary without porting and testing the client protocol.
- App build baseline: versionName `1.5.1-foreground-usb`, versionCode `9` in upstream `app/build.gradle`.
- Localization build: **336** Android string resources for RU, plus core help content; some command/reference material remains English.
- Packaging: workflow changes applicationId to `ro.sw3g.scrcpy.ru` for side-by-side installation and produces a **debug-signed** APK. This is **not** a production release.

## Documentation

- [Русская версия / Russian overview](README.ru.md)
- [Scope and product decisions](docs/PRODUCT.md)
- [Implementation roadmap and release gates](docs/ROADMAP.md)
- [Device profile specification](docs/PROFILES.md)
- [Architecture and compatibility](docs/ARCHITECTURE.md)
- [Interface and Android TV interaction](docs/UX.md)
- [Tests and acceptance](docs/QA.md)
- [Build, signing and releases](docs/BUILD_RELEASE.md)
- [Repository separation and migration](docs/REPOSITORY.md)

## Working code

This staging branch does **not** vendor the upstream Android sources. The workflow checks out a pinned upstream commit, applies `apply_to_source.py`, changes application identity, validates strings, builds with Gradle, and uploads the APK as an Actions artifact. No code or release in this directory should be described as tested on a device unless device test evidence exists.

**Build:** [Build Scrcpy RU APK](../../.github/workflows/build-scrcpy-ru.yml) (relative link from this subtree may depend on GitHub tree navigation; use the repository's Actions tab).

## Security and attribution

Do not commit ADB identity files, pairing codes, IP addresses of private user devices, screenshots or console logs. Profiles exported for sharing must have all secrets excluded and IPs scrubbed. Keep original project attribution, server license notices and all applicable third-party notices. Never migrate the bridge repository's historical captures or code into a public Scrcpy RU repository.
