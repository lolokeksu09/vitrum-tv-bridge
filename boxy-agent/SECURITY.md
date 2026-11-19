# Security contract — BOXY on-device agent v0.2.0

- Default: private GitHub Issues repository owned by `lolokeksu09`.
- Explicit PUBLIC mode: only `lolokeksu09/vitrum-tv-bridge`, after a visible opt-in checkbox on the TV.
- Public mode requires both GitHub repository ownership verification and saved user consent; it does not expose the token.
- Fine-grained token entered on the TV only; encrypted with Android Keystore AES-GCM.
- No embedded secrets, no arbitrary URLs, no external addresses beyond
  `https://api.github.com`.
- Android Accessibility permission is explicitly granted by device owner;
  `canRetrieveWindowContent=false`, service does not inspect app text.
- Only `ping/home/back` plus 4 fixed app launch requests.
- No ADB, root, terminal, local HTTP listener, media projection, APK installer,
  shell execution, arbitrary package paths, screenshot or device logs.
- Each request validated on trusted GitHub API fields: repository visibility/allowed public exception, owner,
  author identity, issue age, three exact JSON fields and per-TV random ID.
- Local command cursor is durably persisted *before* execution for at-most-once
  button behavior. No remote retries without a new owner Issue.
- Foreground service with visible notification, UI STOP and ERASE TOKEN.
- Factory reset, app data clear or reinstall = pair again.
- Foreground service startup/boot and background launch depend on BOXY OEM.
  Never claim run on target without installation and physical verification.
- v0.2.0 is NOT an updater. APK updates require Android user consent
  and stable signing identity for upgrades.

## Explicit PUBLIC GitHub mode (v0.2.0)

To avoid GitHub Actions minutes, the agent can use the existing public
`lolokeksu09/vitrum-tv-bridge` Issue tracker. Issues do not run CI.
This mode is **disabled by default**, requires user checkbox consent on TV,
and allows only the above exact repo. Private repo support is retained.
All public issue titles, request payloads and status replies are visible to
third parties: never include secrets/screenshots/logs. Only the repo owner's
GitHub-authored issues are accepted. The UI must warn the owner before enable.
The app still refuses arbitrary shell commands, APK installs, uninstalls,
network/VPN configuration changes and screenshot capture.
