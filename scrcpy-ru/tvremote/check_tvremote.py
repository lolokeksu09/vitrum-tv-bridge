#!/usr/bin/env python3
"""Focused source integration guard: TV key whitelist, overlay lifecycle, resources.
Does not assert live ADB control or visual appearance.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

if len(sys.argv)!=2:raise SystemExit("Usage: python3 check_tvremote.py /path/to/android_source")
root=Path(sys.argv[1]).resolve()/"app/src/main"
base=root/"java/ro/sw3g/scrcpy"
main=(base/"MainActivity.java").read_text(encoding="utf-8")
panel=(base/"TvRemotePanel.java").read_text(encoding="utf-8")
keys=(base/"TvRemoteKeys.java").read_text(encoding="utf-8")
actions=re.findall(r'static final int (\w+)=KeyEvent\.(KEYCODE_\w+);',keys)
expected={
"UP":"KEYCODE_DPAD_UP","DOWN":"KEYCODE_DPAD_DOWN","LEFT":"KEYCODE_DPAD_LEFT",
"RIGHT":"KEYCODE_DPAD_RIGHT","OK":"KEYCODE_DPAD_CENTER",
"BACK":"KEYCODE_BACK","HOME":"KEYCODE_HOME",
"VOLUME_DOWN":"KEYCODE_VOLUME_DOWN","VOLUME_UP":"KEYCODE_VOLUME_UP",
"MUTE":"KEYCODE_VOLUME_MUTE"
}
if dict(actions)!=expected:raise SystemExit(f"Unexpected TV keycodes: {actions}")
for marker in (
    'Button tvButton=button("TV",this::toggleTvRemote)',
    'private void showTvRemote()',
    'private void hideTvRemote()',
    'private void sendTvRemoteKey(int code)',
    'current.control.clickKey(code)',
    'if(current==null||!current.connected||current.control==null)',
    'private void leavePlayer(){if(leaving)return;leaving=true;hideTvRemote();',
    'private void disconnect(){hideTvRemote();',
    'session=null;hideTvRemote();',
    'TvRemotePanel panel=new TvRemotePanel(',
):
    if marker not in main:raise SystemExit("Missing TV overlay integration: "+marker)
if re.search(r'(\.shell\(|\.adb\W|Runtime\.getRuntime|ProcessBuilder)',panel):
    raise SystemExit("TV remote contains a shell or ADB call")
if panel.count('TvRemoteKeys.')<10:
    raise SystemExit("TV panel lacks full 10-key map")
for suffix in ("","-ro","-ru"):
    xml=root/f"res/values{suffix}/strings.xml"
    doc=ET.parse(xml).getroot()
    names=[s.attrib.get("name") for s in doc]
    if len(names)!=382 or len(set(names))!=382:
        raise SystemExit(f"Wrong number of strings: {xml} {len(names)}")
    for key in ("tv_remote_title","tv_remote_open","tv_remote_close","tv_remote_unavailable",
                "tv_remote_up","tv_remote_down","tv_remote_left","tv_remote_right","tv_remote_ok",
                "tv_remote_back","tv_remote_home","tv_remote_volume_down","tv_remote_volume_up","tv_remote_mute"):
        if key not in names:raise SystemExit(f"Missing translation {suffix}: {key}")
print("PASS: 10 whitelisted Android TV keys, overlay lifecycle and 382 strings in EN/RO/RU")
