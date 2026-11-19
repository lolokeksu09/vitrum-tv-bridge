#!/usr/bin/env python3
"""Stage 2: grouped settings editor and profile-safe quality presets.

Apply after apply_to_source.py and profiles/apply_profiles.py.
All exact-match checks complete before any file is modified.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import sys
import xml.etree.ElementTree as ET

if len(sys.argv)!=2:
    raise SystemExit("Usage: python3 apply_settings.py /path/to/android_source")
repo=Path(sys.argv[1]).resolve()
root=repo/"app/src/main"
java=root/"java/ro/sw3g/scrcpy"
here=Path(__file__).resolve().parent
updates={}

def replace_once(body,before,after,filename):
    count=body.count(before)
    if count!=1:
        raise ValueError(f"{filename}: expected one match for {before[:90]!r}, got {count}")
    return body.replace(before,after,1)

main=java/"MainActivity.java"
body=main.read_text(encoding="utf-8")
def main_replace(before,after):
    global body
    body=replace_once(body,before,after,main.name)

main_replace(
    '    private final Map<String,View> fields=new LinkedHashMap<>();',
    '    private final Map<String,View> fields=new LinkedHashMap<>();\n'
    '    private final boolean[] settingsExpanded={true,false,false,false};'
)
main_replace(
    '        Options o=new Options(prefs);fields.clear();',
    '''        Options o=new Options(prefs);fields.clear();
        String[] groupNames={
            I18n.t(R.string.settings_group_basic),
            I18n.t(R.string.settings_group_control),
            I18n.t(R.string.settings_group_media),
            I18n.t(R.string.settings_group_advanced)
        };
        String[] groupDescriptions={
            I18n.t(R.string.settings_desc_basic),
            I18n.t(R.string.settings_desc_control),
            I18n.t(R.string.settings_desc_media),
            I18n.t(R.string.settings_desc_advanced)
        };
        LinearLayout[] sectionContent=new LinearLayout[SettingsSections.COUNT];
        Button[] groupButtons=new Button[SettingsSections.COUNT];
        int[] totals=SettingsSections.counts(Options.fields());
        for(int group=0;group<SettingsSections.COUNT;group++){
            final int index=group;
            LinearLayout section=card(content);
            String label=groupNames[group]+" · "+totals[group];
            Button header=button((settingsExpanded[group]?"⌄  ":"›  ")+label,()->{
                settingsExpanded[index]=!settingsExpanded[index];
                sectionContent[index].setVisibility(settingsExpanded[index]?View.VISIBLE:View.GONE);
                groupButtons[index].setText((settingsExpanded[index]?"⌄  ":"›  ")
                    +groupNames[index]+" · "+totals[index]);
            });
            header.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
            header.setTextSize(16);
            section.addView(header,new LinearLayout.LayoutParams(-1,dp(52)));
            section.addView(note(groupDescriptions[group]));
            LinearLayout entries=column();
            entries.setVisibility(settingsExpanded[group]?View.VISIBLE:View.GONE);
            section.addView(entries);
            sectionContent[group]=entries;
            groupButtons[group]=header;
        }'''
)
main_replace(
    'for(String[] f:Options.fields()){LinearLayout c=card(content);',
    'for(String[] f:Options.fields()){LinearLayout c=card(sectionContent[SettingsSections.category(f[0])]);'
)
main_replace(
    'c.addView(sw);sw.setOnCheckedChangeListener((b,checked)->prefs.edit().putString(f[0],Boolean.toString(checked)).apply());v=sw;',
    'c.addView(sw);v=sw;'
)
main_replace(
    'else{edit.setText(choices[n].value);prefs.edit().putString(key,choices[n].value).apply();}',
    'else{edit.setText(choices[n].value);}'
)
main_replace(
    '    private void preset(String size,String fps,String bitrate){if(!saveFields())return;prefs.edit().putString("max_size",size).putString("max_fps",fps).putString("video_bit_rate",bitrate).putString("video_codec","h264").apply();fields.clear();if(!saveFields())return;body.removeAllViews();settingsPage();}',
    '''    private void preset(String size,String fps,String bitrate){
        if(!saveFields())return;
        LinkedHashMap<String,String> updated;
        try{
            updated=QualityPresets.apply(new Options(prefs).values,size,fps,bitrate);
            if(profiles!=null){
                profiles.saveActive(updated,prefs.getString("host",""),
                    prefs.getString("port","5555"),prefs.getInt("interactionMode",0));
                profiles.applyActiveToPrefs(prefs);
            }else{
                SharedPreferences.Editor editor=prefs.edit();
                for(Map.Entry<String,String> entry:updated.entrySet())
                    editor.putString(entry.getKey(),entry.getValue());
                editor.apply();
            }
        }catch(Exception e){toast(I18n.t(R.string.profile_error)+": "+e.getMessage());return;}
        fields.clear();body.removeAllViews();settingsPage();
    }
    private void resetActiveSettings(){
        LinkedHashMap<String,String> defaults=new LinkedHashMap<>();
        for(String[] field:Options.fields())defaults.put(field[0],field[2]);
        try{
            if(profiles!=null){
                profiles.saveActive(defaults,prefs.getString("host",""),
                    prefs.getString("port","5555"),prefs.getInt("interactionMode",0));
                profiles.applyActiveToPrefs(prefs);
            }else{
                SharedPreferences.Editor editor=prefs.edit();
                for(String[] field:Options.fields())editor.remove(field[0]);
                editor.apply();
            }
        }catch(Exception e){toast(I18n.t(R.string.profile_error)+": "+e.getMessage());return;}
        fields.clear();body.removeAllViews();settingsPage();
    }'''
)
main_replace(
    'addButton(content,I18n.t(R.string.text_120),()->new AlertDialog.Builder(this).setMessage(I18n.t(R.string.text_121)).setPositiveButton(I18n.t(R.string.text_122),(d,w)->{SharedPreferences.Editor e=prefs.edit();for(String[]f:Options.fields())e.remove(f[0]);e.apply();fields.clear();if(!saveFields())return;body.removeAllViews();settingsPage();}).setNegativeButton(I18n.t(R.string.text_076),null).show());',
    'addButton(content,I18n.t(R.string.text_120),()->new AlertDialog.Builder(this).setMessage(I18n.t(R.string.text_121)).setPositiveButton(I18n.t(R.string.text_122),(d,w)->resetActiveSettings()).setNegativeButton(I18n.t(R.string.text_076),null).show());'
)
main_replace(
    'presets.addView(note(I18n.t(R.string.text_111)));',
    '''presets.addView(note(I18n.t(R.string.text_111)));
        if(profiles!=null){
            LinearLayout selected=card(content);
            selected.addView(note(I18n.t(R.string.settings_editing_profile)));
            selected.addView(title(profiles.active().name));
            addButton(selected,I18n.t(R.string.settings_devices),()->select(0));
        }'''
)
main_replace(
    '        addButton(presets,I18n.t(R.string.text_114),()->preset("800","30","2000000"));',
    '        addButton(presets,I18n.t(R.string.text_114),()->preset("800","30","2000000"));\n'
    '        presets.addView(note(I18n.t(R.string.settings_quality_note)));'
)
main_replace(
    '        addButton(content,I18n.t(R.string.text_117),()->{if(!saveFields())return;',
    '        content.addView(note(I18n.t(R.string.settings_media_note)));\n'
    '        addButton(content,I18n.t(R.string.text_117),()->{if(!saveFields())return;'
)
updates[main]=body

translations={
  "values": {
    "settings_editing_profile":"Editing the profile",
    "settings_devices":"Back to my devices",
    "settings_group_basic":"Essential settings",
    "settings_group_control":"Remote control",
    "settings_group_media":"Recording, audio and camera",
    "settings_group_advanced":"Advanced server options",
    "settings_desc_basic":"Resolution, frame rate, bitrate and primary codecs.",
    "settings_desc_control":"Input, cursor, reconnect and power behaviour.",
    "settings_desc_media":"MP4 recording, audio sources and camera capture.",
    "settings_desc_advanced":"Crop, rotation, encoder details and extra server keys.",
    "settings_quality_note":"A preset changes four fields in the active profile; other settings are preserved.",
    "settings_media_note":"MP4 recording needs H.264 video and AAC audio when sound is enabled."
  },
  "values-ro": {
    "settings_editing_profile":"Editezi profilul",
    "settings_devices":"Înapoi la dispozitivele mele",
    "settings_group_basic":"Setări esențiale",
    "settings_group_control":"Control la distanță",
    "settings_group_media":"Înregistrare, audio și cameră",
    "settings_group_advanced":"Opțiuni avansate pentru server",
    "settings_desc_basic":"Rezoluție, FPS, debit video și codecuri principale.",
    "settings_desc_control":"Intrare, cursor, reconectare și alimentare.",
    "settings_desc_media":"Înregistrare MP4, surse audio și captură cameră.",
    "settings_desc_advanced":"Decupare, rotație, encodere și opțiuni suplimentare.",
    "settings_quality_note":"Presetarea schimbă patru câmpuri doar în profilul activ.",
    "settings_media_note":"Înregistrarea MP4 necesită H.264 și AAC când sunetul este activ."
  },
  "values-ru": {
    "settings_editing_profile":"Настройки профиля",
    "settings_devices":"Назад к моим устройствам",
    "settings_group_basic":"Основные",
    "settings_group_control":"Управление",
    "settings_group_media":"Запись, звук и камера",
    "settings_group_advanced":"Расширенные",
    "settings_desc_basic":"Разрешение, FPS, битрейт и основные кодеки.",
    "settings_desc_control":"Касания, курсор, переподключение и питание.",
    "settings_desc_media":"Запись MP4, источники звука и захват камеры.",
    "settings_desc_advanced":"Обрезка, поворот, энкодеры и параметры сервера.",
    "settings_quality_note":"Пресет меняет четыре настройки только активного профиля.",
    "settings_media_note":"Для записи MP4 нужны H.264 и AAC, если включён звук."
  }
}
for locale,strings in translations.items():
    target=root/f"res/{locale}/strings.xml"
    src=target.read_text(encoding="utf-8")
    for key in strings:
        if f'name="{key}"' in src:
            raise ValueError(f"Duplicate resource {key} in {target}")
    lines="".join(
        f'    <string name="{key}" formatted="false">"{escape(value)}</string>\n'
        for key,value in strings.items()
    )
    src=replace_once(src,"</resources>",lines+"</resources>",target.name)
    ET.fromstring(src)
    updates[target]=src

for kind,names in (
    ("main",("SettingsSections.java","QualityPresets.java")),
    ("test",("SettingsSectionsTest.java",))
):
    src_dir=here/"src"/kind/"java/ro/sw3g/scrcpy"
    dest_dir=repo/"app/src"/kind/"java/ro/sw3g/scrcpy"
    for name in names:
        src=src_dir/name
        dest=dest_dir/name
        if dest.exists():raise ValueError(f"Refusing overwrite of {dest}")
        updates[dest]=src.read_text(encoding="utf-8")

# Commit changes only after all prerequisites passed, including XML parsing.
for path,value in updates.items():
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value,encoding="utf-8")
print("Settings v2 patch applied; wrote",len(updates),"files;",
      len(next(iter(translations.values()))),"new strings per locale")
