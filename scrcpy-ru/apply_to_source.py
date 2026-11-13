#!/usr/bin/env python3
"""Apply Russian UI localization to sw3gmach1n3/Scrcpy_for_Android main (2026-10-22).

Usage: python apply_to_source.py /path/to/Scrcpy_for_Android
This script checks expected upstream strings and aborts on an incompatible revision.
"""
from pathlib import Path
from shutil import copyfile
import sys
import xml.etree.ElementTree as ET

repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
source = Path(__file__).resolve().parent
assets = repo / 'app/src/main'
if not (assets / 'java/ro/sw3g/scrcpy/MainActivity.java').is_file():
    sys.exit(f'Не найдены исходники Scrcpy_for_Android: {repo}')

def change(path, old, new):
    body=path.read_text(encoding='utf-8')
    count=body.count(old)
    if count!=1:
        raise RuntimeError(f'Ожидалось ровно одно совпадение {old!r} в {path}, найдено {count}. Обновление отменено.')
    return body.replace(old,new)

# Build every changed file in memory and validate preconditions before writing anything.
updates={}
def patch(rel, changes):
    path=assets/rel
    body=path.read_text(encoding='utf-8')
    for old,new in changes:
        count=body.count(old)
        if count!=1:
            raise RuntimeError(f'Неожиданная версия файла {rel}: найдено {count} совпадений {old!r}. Исходники не изменены.')
        body=body.replace(old,new)
    updates[path]=body

patch('java/ro/sw3g/scrcpy/I18n.java', [
    ('getString("appLanguage","en")', 'getString("appLanguage", Locale.getDefault().getLanguage().equals("ru")?"ru":"en")'),
    ('code="ro".equals(code)?"ro":"en";', 'code=("ro".equals(code)||"ru".equals(code))?code:"en";'),
])
patch('java/ro/sw3g/scrcpy/MainActivity.java', [
    ('"Help",I18n.t(R.string.text_085)', 'I18n.t(R.string.tab_help),I18n.t(R.string.text_085)'),
    ('String[] languages={"English","Română"};', 'String[] languages={"English","Română","Русский"};'),
    ('picker.setSelection(I18n.romanian()?1:0);', 'picker.setSelection("ru".equals(I18n.language())?2:(I18n.romanian()?1:0));'),
    ('String code=position==1?"ro":"en";', 'String code=position==2?"ru":(position==1?"ro":"en");'),
    ('new String[]{"Zoom −","Reset 1×","Zoom +"}', 'new String[]{I18n.t(R.string.session_zoom_out),I18n.t(R.string.session_zoom_reset),I18n.t(R.string.session_zoom_in)}'),
    ('I18n.t(R.string.text_168),"⌂\\nHome",I18n.t(R.string.text_169)', 'I18n.t(R.string.text_168),I18n.t(R.string.session_home),I18n.t(R.string.text_169)'),
    ('I18n.t(R.string.text_171),"Mute",I18n.t(R.string.text_172)', 'I18n.t(R.string.text_171),I18n.t(R.string.session_mute),I18n.t(R.string.text_172)'),
])
patch('java/ro/sw3g/scrcpy/Session.java', [
    ('new IOException("Clipboard invalid")', 'new IOException(I18n.t(R.string.error_clipboard_invalid))'),
])
patch('java/ro/sw3g/scrcpy/HelpView.java', [
    ('I18n.romanian()?"help-ro.json":"help-en.json"', '"ru".equals(I18n.language())?"help-ru.json":(I18n.romanian()?"help-ro.json":"help-en.json")'),
])

def add_resources(rel, entries):
    p=assets/rel
    body=p.read_text(encoding='utf-8')
    if body.count('</resources>')!=1:
        raise ValueError(f'Invalid resource file: {p}')
    for name, _ in entries:
        if f'name="{name}"' in body:
            raise ValueError(f'Already defined: {name} in {p}')
    block=''.join(f'    <string name="{name}" formatted="false">"{value}"</string>\n' for name,value in entries)
    body=body.replace('</resources>',block+'</resources>')
    ET.fromstring(body)
    updates[p]=body

en={
    'tab_help':'Help',
    'session_zoom_out':'Zoom −',
    'session_zoom_reset':'Reset 1×',
    'session_zoom_in':'Zoom +',
    'session_home':'⌂\\nHome',
    'session_mute':'Mute',
    'error_clipboard_invalid':'Clipboard invalid',
}
ro={
    'tab_help':'Ajutor',
    'session_zoom_out':'Micșorează −',
    'session_zoom_reset':'Resetare 1×',
    'session_zoom_in':'Mărește +',
    'session_home':'⌂\\nAcasă',
    'session_mute':'Fără sunet',
    'error_clipboard_invalid':'Clipboard invalid',
}
add_resources('res/values/strings.xml',en.items())
add_resources('res/values-ro/strings.xml',ro.items())
ru_source=source/'app/src/main/res/values-ru/strings.xml'
ru_xml=ru_source.read_text(encoding='utf-8')
ru_root=ET.fromstring(ru_xml)
base_root=ET.fromstring(updates[assets/'res/values/strings.xml'])
ru_names={x.attrib['name'] for x in ru_root}
base_names={x.attrib['name'] for x in base_root}
if ru_names!=base_names:
    raise RuntimeError(f'Russian resources differ from default: missing={base_names-ru_names}, extra={ru_names-base_names}')
# Check the help source before mutation as well.
import json
help_en=assets/'assets/help-en.json'
help_data=json.loads(help_en.read_text(encoding='utf-8'))
if {topic['id'] for topic in help_data['topics']} != {'connect','controls','settings','files','console','server','desktop','about'}:
    raise RuntimeError('Unexpected upstream help structure; no modifications made')
# Don't mutate the repository unless every target and resource has been checked.
for path,body in updates.items():
    path.write_text(body,encoding='utf-8')
destination=assets/'res/values-ru/strings.xml'
destination.parent.mkdir(parents=True,exist_ok=True)
copyfile(ru_source,destination)
import subprocess
subprocess.run([sys.executable,str(source/'scripts/help_ru.py'),str(repo)],check=True)
print('Русская локализация установлена в исходники:',repo)
print('Локализовано строк:',len(ru_names))
print('Соберите APK: ./gradlew assembleDebug -Pandroid.injected.testOnly=false')
