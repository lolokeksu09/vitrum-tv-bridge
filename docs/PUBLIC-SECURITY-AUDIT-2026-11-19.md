# Public repository privacy audit — 2026-11-19

## Scope

Repository: `lolokeksu09/vitrum-tv-bridge` (public). Review covered current
`main` source, presets, scripts, tests, documentation, public issue bodies
and 487 issue/PR comments. This is not a forensic guarantee about all Git
objects, GitHub caches, release attachments or copies by third parties.

## Confirmed findings

1. The old `main` contained **126 device screenshots (~39.4 MB)** in
   `captures/`. Some may depict installed applications or private screens.
   Do not assume their contents are public-safe.
2. Public issue comments held screenshot links, device diagnostics, app lists,
   activity status and local backup paths.
3. The source repository is also the owner's **live control channel**. GitHub
   issue requests and operation statuses become public when visibility is public.
   An owner-authorship check is present, but it does not make these messages
   confidential.
4. The current source/test history still includes a device's **private LAN ADB
   target**. This is not an Internet-routable credential, but it is internal
   environment metadata and should move into a local ignored configuration.
5. Git history, remaining public branches, PR refs, GitHub caches and forks may
   still expose old screenshot blobs even after deleting them from `main`.
   The former images may have been copied outside GitHub.

## Remediation applied to current main

- Removed all 126 tracked screenshot files from `main`.
- Added `.gitignore` exclusions for local captures, key files, APKs and env.
- Created the **regular file** `captures` to occupy that pathname. This
  blocks outdated capture upload code from creating `captures/issue-*.png`
  beneath a path now occupied by a file.
- Redacted 125 screenshot comments and other sensitive device-diagnostic
  result comments. Retained the bridge result markers to prevent replays.
- Removed direct LAN addresses and dead screenshot references from public
  README and selected device documents.
- Updated `tv_bridge_v2.py`: screenshot capture and full UI sweep must verify
  `private=true` through GitHub before reading screen pixels; if the repo is
  public, command results omit device-specific details before commenting.
- Added regression tests for public/private fail-closed behavior.

## Mandatory outstanding work

**Until GitHub history and all refs are purged, do not treat this repository as
safe to publish old device data.** Changing visibility back to PRIVATE is the
fastest containment measure; it does not recall files already cloned.

For lasting safe publication, choose a separate PUBLIC source repository and a
PRIVATE control repository, or carry out a fully reviewed history rewrite:
remove sensitive blobs from all branches/tags/PR refs and GitHub caches with
GitHub Support as needed. A force-push breaks clones, PR links, pinned SHAs,
and the local agent's `git pull --ff-only`; it is **not** part of this audit.
Review remaining GitHub Actions artifacts and release files before publication.

Actual GitHub API and ADB credentials were **not found as literal strings in
the current checked-in text**, but hidden secrets, media contents and prior
Git history were not comprehensively proven clean. Rotate any real keys or
credentials that could have appeared inside an old TV screenshot.

The installed Termux watcher uses its local files. The public-output
redaction and screenshot denial in the revised Python code require a deliberate
one-time local `git pull --ff-only`, then restarting the watch process.
The pathname blocker in `main` takes effect for old clients without that
restart, but does not secure old commit history.

## CI

The `strict-read-only-bridge` suite is the relevant regression gate for
these source changes. CI success demonstrates tests, **not** a complete
historic secret scan or GitHub cache purge.
