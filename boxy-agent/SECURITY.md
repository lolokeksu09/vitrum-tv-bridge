# Security contract — BOXY on-device agent v0.1.0

- Public `vitrum-tv-bridge` = source repository only.
- Private GitHub Issues repo = control plane; owner `lolokeksu09` required.
- App never accepts plain GitHub `private=false` responses as authorization.
- Fine-grained token entered on the TV only; encrypted with Android Keystore AES-GCM.
- No embedded secrets, no arbitrary URLs, no external addresses beyond
  `https://api.github.com`.
- Android Accessibility permission is explicitly granted by device owner;
  `canRetrieveWindowContent=false`, service does not inspect app text.
- Only `ping/home/back` plus 4 fixed app launch requests.
- No ADB, root, terminal, local HTTP listener, media projection, APK installer,
  shell execution, arbitrary package paths, screenshot or device logs.
- Each request validated on trusted GitHub API fields: repo private, owner,
  author identity, issue age, three exact JSON fields and per-TV random ID.
- Local command cursor is durably persisted *before* execution for at-most-once
  button behavior. No remote retries without a new owner Issue.
- Foreground service with visible notification, UI STOP and ERASE TOKEN.
- Factory reset, app data clear or reinstall = pair again.
- Foreground service startup/boot and background launch depend on BOXY OEM.
  Never claim run on target without installation and physical verification.
- v0.1.0 is NOT an updater. APK updates require Android user consent
  and stable signing identity for upgrades.
