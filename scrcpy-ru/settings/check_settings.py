#!/usr/bin/env python3
"""Static integration guard: catch schema drift and accidental eager preference writes.

This is not a substitute for Android device testing.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

root=Path(sys.argv[1]).resolve()/"app/src/main" if len(sys.argv)==2 else None
if root is None:raise SystemExit("Usage: check_settings.py /path/to/android_source")
src=(root/"java/ro/sw3g/scrcpy/Options.java").read_text(encoding="utf-8")
group=(root/"java/ro/sw3g/scrcpy/SettingsSections.java").read_text(encoding="utf-8")
main=(root/"java/ro/sw3g/scrcpy/MainActivity.java").read_text(encoding="utf-8")
names=re.findall(r'^\s*\{"([^"]+)",I18n\.t\(R\.string\.',src,re.M)
groups=re.findall(
    r'private static final Set<String> \w+_KEYS = keys\((.*?)\);',
    group,re.S
)
if len(groups)!=4:raise SystemExit("Expected four settings groups")
categorized=[re.findall(r'"([^"]+)"',s) for s in groups]
flat=[key for subset in categorized for key in subset]
if len(names)!=35 or len(set(names))!=35:
    raise SystemExit(f"Options.fields changed: {len(names)} keys")
if set(names)!=set(flat) or len(flat)!=35 or len(set(flat))!=35:
    raise SystemExit("Missing, duplicated or unexpected group keys")
if [len(x) for x in categorized]!=[6,8,12,9]:
    raise SystemExit("Unexpected distribution of groups")
for needle in (
    'SettingsSections.category(f[0])',
    'QualityPresets.apply(',
    'profiles.saveActive(updated',
    'profiles.saveActive(defaults',
    'resetActiveSettings()',
    'settingsExpanded[index]',
):
    if needle not in main:raise SystemExit(f"Missing integration: {needle}")
for forbidden in (
    'sw.setOnCheckedChangeListener((b,checked)->prefs.edit().putString(f[0]',
    'edit.setText(choices[n].value);prefs.edit().putString(key',
):
    if forbidden in main:raise SystemExit("Immediate preference write present")
for suffix in ("","-ro","-ru"):
    file=root/f"res/values{suffix}/strings.xml"
    names_xml=[item.attrib.get("name") for item in ET.parse(file).getroot()]
    if len(names_xml)!=367 or len(set(names_xml))!=367:
        raise SystemExit(f"Locale resource count mismatch in {file}: {len(names_xml)}")
print("PASS: 35 unique settings, four groups 6/8/12/9, no eager switch/choice writes, 367 strings/locale")
