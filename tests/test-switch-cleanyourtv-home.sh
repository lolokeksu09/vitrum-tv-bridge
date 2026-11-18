#!/usr/bin/env bash
# Simulates ADB responses; NEVER contacts an actual TV.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
cat > "$TEMP/adb" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == connect ]]; then echo connected; exit 0; fi
if [[ "$1" == -s ]]; then shift 2; fi
echo "$*" >> "$MOCK_LOG"
case "$*" in
  get-state) echo device ;;
  "shell getprop ro.product.model") echo "4K Android TV Box" ;;
  "shell getprop ro.product.manufacturer") echo SkyworthDigital ;;
  "shell pm path com.gathin.tvhome") echo "package:/data/app/base.apk" ;;
  "shell pm list packages -d")
    if [[ -f "$MOCK_STATE/disabled" ]]; then echo "package:com.google.android.tvlauncher"; fi ;;
  "shell pm list packages") printf 'package:com.gathin.tvhome\npackage:com.google.android.tvlauncher\n' ;;
  "shell cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.HOME")
    printf 'com.gathin.tvhome/.MainActivity\ncom.google.android.tvlauncher/.MainActivity\n' ;;
  "shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME com.google.android.tvlauncher")
    echo com.google.android.tvlauncher/.MainActivity ;;
  "shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME")
    if [[ "$MOCK_MODE" == already || -f "$MOCK_STATE/disabled" ]]; then
      echo com.gathin.tvhome/.MainActivity
    else
      echo com.google.android.tvlauncher/.MainActivity
    fi ;;
  "shell am start -W -n com.gathin.tvhome/.MainActivity") echo "Status: ok" ;;
  "shell cmd package set-home-activity --user 0 com.gathin.tvhome/.MainActivity") echo Success ;;
  "shell cmd package set-home-activity --user 0 com.google.android.tvlauncher/.MainActivity") echo Success ;;
  "shell input keyevent 3") : ;;
  "shell dumpsys activity activities")
    if [[ "$MOCK_MODE" == unknown ]]; then
      echo "mResumedActivity: ActivityRecord{abcd u0 com.vendor.unknown/.Home t1}"
    elif [[ "$MOCK_MODE" == rollback && -f "$MOCK_STATE/disabled" ]]; then
      echo "mResumedActivity: ActivityRecord{abcd u0 com.android.tv.settings/.system.FallbackHome t1}"
    elif [[ "$MOCK_MODE" == already || -f "$MOCK_STATE/disabled" ]]; then
      echo "mResumedActivity: ActivityRecord{abcd u0 com.gathin.tvhome/.MainActivity t1}"
    else
      echo "mResumedActivity: ActivityRecord{abcd u0 com.google.android.tvlauncher/.MainActivity t1}"
    fi ;;
  "shell pm disable-user --user 0 com.google.android.tvlauncher")
    touch "$MOCK_STATE/disabled"
    echo "new state: disabled-user" ;;
  "shell pm enable --user 0 com.google.android.tvlauncher")
    rm -f "$MOCK_STATE/disabled"
    echo "new state: enabled" ;;
  *) echo "Unexpected mocked command: $*" >&2; exit 42 ;;
esac
MOCK
chmod +x "$TEMP/adb"
for MODE in already blocked unknown rollback; do
  export MOCK_MODE="$MODE"
  export MOCK_STATE="$TEMP/$MODE"
  export MOCK_LOG="$MOCK_STATE/log"
  mkdir -p "$MOCK_STATE/home"
  STATUS=0
  HOME="$MOCK_STATE/home" PATH="$TEMP:$PATH" bash "$ROOT/scripts/switch-cleanyourtv-home.sh" > "$MOCK_STATE/output" 2>&1 || STATUS=$?
  case "$MODE" in
    already)
      [[ "$STATUS" == 0 ]] && grep -q 'HOME_OK:' "$MOCK_STATE/output"
      ! grep -q 'pm disable-user' "$MOCK_LOG" ;;
    blocked)
      [[ "$STATUS" == 0 ]] && grep -q 'HOME_OK:' "$MOCK_STATE/output"
      grep -q 'pm disable-user' "$MOCK_LOG"
      test -f "$MOCK_STATE/disabled" ;;
    unknown)
      [[ "$STATUS" != 0 ]] && grep -q 'HOME_UNKNOWN:' "$MOCK_STATE/output"
      ! grep -q 'pm disable-user' "$MOCK_LOG" ;;
    rollback)
      [[ "$STATUS" != 0 ]] && grep -q 'Verification failed:' "$MOCK_STATE/output"
      grep -q 'pm enable --user 0 com.google.android.tvlauncher' "$MOCK_LOG"
      test ! -f "$MOCK_STATE/disabled" ;;
  esac
  echo "PASS $MODE"
done
