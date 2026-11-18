#!/usr/bin/env bash
# Stage CleanYourTV on the already-authorized BOXY Android TV.
# Installs and starts the official launcher; never disables or removes stock software.
# Usage: bash scripts/stage-cleanyourtv-boxy.sh [successful-main-workflow-run-id]
set -euo pipefail

REPO="lolokeksu09/vitrum-tv-bridge"
TV="192.168.0.160:5555"
EXPECTED_MODEL="4K Android TV Box"
ARTIFACT="CleanYourTV-BOXY-v3.5.0"

for tool in adb gh sha256sum find awk mktemp; do
  command -v "$tool" >/dev/null || { echo "Missing command: $tool" >&2; exit 1; }
done
if (( $# > 1 )); then
  echo "Usage: bash scripts/stage-cleanyourtv-boxy.sh [successful-main-workflow-run-id]" >&2
  exit 2
fi
if (( $# == 1 )); then
  RUN_ID="$1"
else
  # Discover the most recent successful main-branch build automatically.
  RUN_ID="$(gh run list -R "$REPO" --workflow build-cleanyourtv-boxy.yml --branch main \
    --limit 20 --json databaseId,conclusion,event,status \
    --jq '[.[] | select(.status == "completed" and .conclusion == "success" and .event == "push")][0].databaseId')"
fi
[[ "$RUN_ID" =~ ^[0-9]+$ ]] || {
  echo "No verified successful main-branch CleanYourTV build yet. No TV changes." >&2; exit 1;
}

# Do not trust an arbitrary run, branch or artifact name.
OK="$(gh api "repos/$REPO/actions/runs/$RUN_ID" --jq '(.name == "Build CleanYourTV for BOXY" and .head_branch == "main" and .event == "push" and .status == "completed" and .conclusion == "success" and .repository.full_name == "lolokeksu09/vitrum-tv-bridge")')"
[[ "$OK" == "true" ]] || { echo "Refusing unverified workflow run" >&2; exit 1; }

adb connect "$TV" >/dev/null || true
STATE="$(adb -s "$TV" get-state 2>/dev/null || true)"
[[ "$STATE" == "device" ]] || { echo "BOXY is not connected over authorized ADB" >&2; exit 1; }
MODEL="$(adb -s "$TV" shell getprop ro.product.model | tr -d '\r')"
SDK="$(adb -s "$TV" shell getprop ro.build.version.sdk | tr -d '\r')"
[[ "$MODEL" == "$EXPECTED_MODEL" ]] || {
  echo "TV identity differs: expected '$EXPECTED_MODEL', got '$MODEL'. No changes." >&2; exit 1;
}
[[ "$SDK" =~ ^[0-9]+$ ]] && (( SDK >= 26 )) || {
  echo "Android SDK $SDK is below CleanYourTV minimum 26. No changes." >&2; exit 1;
}

# Backups stay in Termux private storage; some settings may contain sensitive values.
BACKUP_ROOT="$HOME/cleanyourtv-backups"
mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"
BACKUP="$BACKUP_ROOT/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$BACKUP"
adb -s "$TV" shell pm list packages > "$BACKUP/packages-all.txt"
adb -s "$TV" shell pm list packages -d > "$BACKUP/packages-disabled.txt"
adb -s "$TV" shell getprop > "$BACKUP/properties.txt"
for namespace in global secure system; do
  adb -s "$TV" shell settings list "$namespace" > "$BACKUP/settings-$namespace.txt"
done
adb -s "$TV" shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME > "$BACKUP/home-before.txt"
adb -s "$TV" shell cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.HOME > "$BACKUP/home-candidates.txt"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
gh run download "$RUN_ID" -R "$REPO" -n "$ARTIFACT" -D "$WORK"
APK="$(find "$WORK" -type f -name app-release.apk -print -quit)"
SUMS="$(find "$WORK" -type f -name cleanyourtv-boxy.sha256 -print -quit)"
[[ -n "$APK" && -s "$APK" && -n "$SUMS" && -s "$SUMS" ]] || {
  echo "APK or checksum missing from signed-source workflow artifact" >&2; exit 1;
}
EXPECTED_SHA="$(awk 'NR==1 {print $1}' "$SUMS")"
ACTUAL_SHA="$(sha256sum "$APK" | awk '{print $1}')"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{64}$ && "$EXPECTED_SHA" == "$ACTUAL_SHA" ]] || {
  echo "APK checksum mismatch; TV unchanged" >&2; exit 1;
}
printf '%s\n' "$ACTUAL_SHA" > "$BACKUP/installed-apk.sha256"

echo "Backup: $BACKUP"
echo "Verified Android SDK: $SDK; TV model: $MODEL"
echo "Stock HOME before installation:"
cat "$BACKUP/home-before.txt"

# Safe staging: install/launch only. No set-home, pm disable-user, uninstall or reboot.
adb -s "$TV" install -r "$APK"
adb -s "$TV" shell pm path com.gathin.tvhome | grep -q '^package:'
START="$(adb -s "$TV" shell am start -W -n com.gathin.tvhome/.MainActivity)"
printf '%s\n' "$START"
printf '%s\n' "$START" | grep -q 'Status: ok' || {
  echo "APK installed, but launcher activity did not start cleanly" >&2; exit 1;
}

if [[ -d "$HOME/storage/downloads" ]]; then
  adb -s "$TV" exec-out screencap -p > "$HOME/storage/downloads/CleanYourTV-BOXY-after.png" || true
  echo "Screenshot: ~/storage/downloads/CleanYourTV-BOXY-after.png"
fi
echo "STAGED: CleanYourTV installed and opened. Stock Home not disabled or changed."
echo "Backup retained: $BACKUP"
