#!/usr/bin/env python3
"""Generate Android Russian string resources from reviewed, stable-key translations."""
from pathlib import Path
from xml.sax.saxutils import escape
import re

here = Path(__file__).resolve().parent
out = here.parent / 'app/src/main/res/values-ru/strings.xml'

def read_pairs(path):
    ret = {}
    for row in path.read_text(encoding='utf-8').splitlines():
        if not row.strip():
            continue
        key, value = row.split('|', 1)
        if key in ret:
            raise ValueError('Duplicate string: ' + key)
        ret[key] = value
    return ret

numbered = read_pairs(here / 'ru.tsv')
assert len(numbered) == 304, f'Missing UI strings: {len(numbered)}'
assert list(numbered) == [f'{i:03}' for i in range(1,305)]
extras = read_pairs(here / 'ru-extra.tsv')
all_strings = {f'text_{k}': v for k,v in numbered.items()}
all_strings.update(extras)

def android_text(v):
    if '\n' in v:
        raise ValueError('Physical line break inside resource')
    return escape(v, {'"':'\\"'}).replace("'", "\\'")

lines = ['<?xml version="1.0" encoding="utf-8"?>','<resources>']
for key, value in all_strings.items():
    if not re.fullmatch('[a-z][a-z0-9_]*',key):
        raise ValueError(key)
    lines.append(f'    <string name="{key}" formatted="false">"{android_text(value)}"</string>')
lines.append('</resources>')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('Generated',out,'with',len(all_strings),'strings')
