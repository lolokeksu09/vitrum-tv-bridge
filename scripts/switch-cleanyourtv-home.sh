#!/usr/bin/env bash
# BOXY-only verified HOME handover to official CleanYourTV.
# Attempts a non-destructive switch first; disables only a recognized stock HOME
# after proving the replacement APK starts. Restores the stock HOME on failure.
set -euo pipefail
TV="192.168.0.160:5555"
NEW_PKG="com.gathin.tvhome"
NEW_HOME="com.gathin.tvhome/.MainActivity"
STOCK=""
STOCK_COMPONENT=""
CHANGED=0
VERIFIED=0

for tool in adb date grep sed tr mkdir; do
  command -v "$tool" >/dev/null || { echo "Missing: $tool" >&2; exit 1; }
done
if [[ "$#" -ne 0 ]]; then
  echo "Usage: bash scripts/switch-cleanyourtv-home.sh (no arguments)" >&2
  exit 2
fi
adb connect "$TV" >/dev/null || true
[[ "$(adb -s "$TV" get-state 2>/dev/null || true)" == "device" ]] || {
  echo "ADB unavailable; no changes" >&2; exit 1;
}
MODEL="$(adb -s "$TV" shell getprop ro.product.model | tr -d '\r')"
MAKER="$(adb -s "$TV" shell getprop ro.product.manufacturer | tr -d '\r')"
[[ "$MODEL" == "4K Android TV Box" && "$MAKER" == *[Ss]kyworth* ]] || {
  echo "Unknown TV ($MODEL / $MAKER); refusing Home changes" >&2; exit 1;
}
adb -s "$TV" shell pm path "$NEW_PKG" | grep -q '^package:' || {
  echo "CleanYourTV is not installed; no changes" >&2; exit 1;
}
adb -s "$TV" shell pm list packages -d | grep -qx "package:$NEW_PKG" && {
  echo "CleanYourTV is disabled; no changes" >&2; exit 1;
}
BACKUP="$HOME/cleanyourtv-backups/home-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP"
chmod 700 "$HOME/cleanyourtv-backups" "$BACKUP"
adb -s "$TV" shell pm list packages > "$BACKUP/packages-before.txt"
adb -s "$TV" shell pm list packages -d > "$BACKUP/disabled-before.txt"
adb -s "$TV" shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME > "$BACKUP/resolved-before.txt"
adb -s "$TV" shell cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.HOME > "$BACKUP/home-claimants.txt"

get_focus_package() {
  local raw pkg
  raw="$(adb -s "$TV" shell dumpsys activity activities | tr -d '\r' || true)"
  pkg="$(printf '%s\n' "$raw" | grep -E 'topResumedActivity|mResumedActivity' | grep -oE '[A-Za-z_][A-Za-z0-9_.]*/[A-Za-z0-9_.$]+' | head -n 1 | cut -d/ -f1 || true)"
  if [[ -z "$pkg" ]]; then
    raw="$(adb -s "$TV" shell dumpsys window windows | tr -d '\r' || true)"
    pkg="$(printf '%s\n' "$raw" | grep 'mCurrentFocus' | grep -oE '[A-Za-z_][A-Za-z0-9_.]*/[A-Za-z0-9_.$]+' | head -n 1 | cut -d/ -f1 || true)"
  fi
  printf '%s' "$pkg"
}
rollback() {
  if (( CHANGED == 1 && VERIFIED == 0 )); then
    echo "Home handover not verified: restoring $STOCK" >&2
    adb -s "$TV" shell pm enable --user 0 "$STOCK" >&2 || true
    if [[ -n "$STOCK_COMPONENT" && "$STOCK_COMPONENT" == "$STOCK/"* ]]; then
      adb -s "$TV" shell cmd package set-home-activity --user 0 "$STOCK_COMPONENT" >&2 || true
    fi
    echo "Recovery command: adb -s $TV shell pm enable --user 0 $STOCK" >&2
  fi
}
trap rollback EXIT

START_OUT="$(adb -s "$TV" shell am start -W -n "$NEW_HOME" 2>&1)"
printf '%s\n' "$START_OUT" > "$BACKUP/cleanyourtv-start.txt"
if ! printf '%s\n' "$START_OUT" | grep -q 'Status: ok'; then
  echo "CleanYourTV failed to launch; stock Home preserved. Backup: $BACKUP" >&2
  exit 1
fi

# First try without touching the stock package.
adb -s "$TV" shell cmd package set-home-activity --user 0 "$NEW_HOME" > "$BACKUP/set-home-output.txt"
adb -s "$TV" shell input keyevent 3
sleep 2
FOCUS="$(get_focus_package)"
RESOLVED_FIRST="$(adb -s "$TV" shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1 | tr -d '\r')"
echo "Focused after HOME: $FOCUS; resolver: $RESOLVED_FIRST"
if [[ "$FOCUS" == "$NEW_PKG" && "$RESOLVED_FIRST" == "$NEW_PKG/"* ]]; then
  VERIFIED=1
  echo "HOME_OK: CleanYourTV works without disabling stock. Backup: $BACKUP"
  exit 0
fi

# The foreground activity after HOME identifies the actual stock launcher.
# Never guess a manufacturer package name or change setupwraith.
STOCK="$FOCUS"
case "$STOCK" in
  com.google.android.tvlauncher|com.google.android.apps.tv.launcherx|com.google.android.leanbacklauncher)
    ;;
  *)
    echo "HOME_UNKNOWN: foreground package '$STOCK' is not in the safe stock allowlist." >&2
    echo "No system package disabled. Report: $BACKUP" >&2
    exit 1
    ;;
esac

STOCK_COMPONENT="$(adb -s "$TV" shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME "$STOCK" | tr -d '\r' | tail -n 1 || true)"
printf '%s\n' "$STOCK" > "$BACKUP/stock-package.txt"
printf '%s\n' "$STOCK_COMPONENT" > "$BACKUP/stock-component.txt"
printf 'adb -s %s shell pm enable --user 0 %s\n' "$TV" "$STOCK" > "$BACKUP/RESTORE-STOCK.sh"
echo "Recognized stock Home: $STOCK; disabling only this package."

CHANGED=1
adb -s "$TV" shell pm disable-user --user 0 "$STOCK"
adb -s "$TV" shell pm list packages -d | grep -qx "package:$STOCK" || {
  echo "Android refused stock launcher disable; restoring" >&2; exit 1;
}
adb -s "$TV" shell cmd package set-home-activity --user 0 "$NEW_HOME"
adb -s "$TV" shell input keyevent 3
sleep 2
FOCUS="$(get_focus_package)"
RESOLVED="$(adb -s "$TV" shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1 | tr -d '\r')"
printf '%s\n' "$FOCUS" > "$BACKUP/focus-after.txt"
printf '%s\n' "$RESOLVED" > "$BACKUP/resolved-after.txt"
if [[ "$FOCUS" != "$NEW_PKG" || "$RESOLVED" != "$NEW_PKG/"* ]]; then
  echo "Verification failed: focus=$FOCUS, resolved=$RESOLVED; restoring stock" >&2
  exit 1
fi
VERIFIED=1
echo "HOME_OK: CleanYourTV is focused and resolves as HOME. Stock disabled: $STOCK"
echo "Backup and restore script: $BACKUP"
echo "Now test the PHYSICAL remote Home, Back, Settings and app buttons."
