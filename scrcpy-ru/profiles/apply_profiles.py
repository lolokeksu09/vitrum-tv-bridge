#!/usr/bin/env python3
"""Apply isolated Profiles v1 patch to an already Russian-localized upstream checkout.
Fail closed when the pinned baseline differs. No upstream protocol/server binary changes.
"""
from pathlib import Path
from shutil import copyfile
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit("Usage: python3 apply_profiles.py /path/to/android_source")
root = Path(sys.argv[1]).resolve() / "app/src/main"
here = Path(__file__).resolve().parent
java = root / "java/ro/sw3g/scrcpy"
updates = {}

def patch(path, changes):
    data = path.read_text(encoding="utf-8")
    for before, after in changes:
        if data.count(before) != 1:
            raise ValueError(f"{path.name}: expected one match, got {data.count(before)}: {before[:100]!r}")
        data = data.replace(before, after, 1)
    updates[path] = data

patch(java / "Options.java", [
    ('    Options(SharedPreferences p){for(String[] f:fields())values.put(f[0],p.getString(f[0],f[2]));}',
     '    Options(SharedPreferences p){for(String[] f:fields())values.put(f[0],p.getString(f[0],f[2]));}\n'
     '    Options(java.util.Map<String,String> p){for(String[] f:fields())values.put(f[0],p.getOrDefault(f[0],f[2]));}'),
])

save_fields_before = ('    private void saveFields(){if(prefs==null)return;'
    'if(page==1&&!fields.isEmpty()){SharedPreferences.Editor e=prefs.edit();'
    'for(Map.Entry<String,View>x:fields.entrySet()){View v=x.getValue();'
    'String val=v instanceof Switch?Boolean.toString(((Switch)v).isChecked()):'
    'v instanceof Spinner?((String[])v.getTag())[((Spinner)v).getSelectedItemPosition()]:'
    '((EditText)v).getText().toString().trim();e.putString(x.getKey(),val);}e.apply();}'
    'if(host!=null)prefs.edit().putString("host",host.getText().toString().trim())'
    '.putString("port",port.getText().toString().trim())'
    '.putString("pairPort",pairPort==null?"":pairPort.getText().toString().trim()).apply();}')

save_fields_after = """
    // Commit an entire validated profile snapshot BEFORE modifying scratch preferences.
    // A failed write leaves the previous snapshot and any ADB identity intact.
    private boolean saveFields(){
        if(prefs==null)return true;
        LinkedHashMap<String,String> values=new LinkedHashMap<>(new Options(prefs).values);
        if(page==1&&!fields.isEmpty()){
            for(Map.Entry<String,View> x:fields.entrySet()){
                View v=x.getValue();
                String value=v instanceof Switch?Boolean.toString(((Switch)v).isChecked()):
                    v instanceof Spinner?((String[])v.getTag())[((Spinner)v).getSelectedItemPosition()]:
                    ((EditText)v).getText().toString().trim();
                values.put(x.getKey(),value);
            }
        }
        String nextHost=host==null?prefs.getString("host",""):host.getText().toString().trim();
        String nextPort=port==null?prefs.getString("port","5555"):port.getText().toString().trim();
        try{
            if(profiles!=null)profiles.saveActive(values,nextHost,nextPort,prefs.getInt("interactionMode",0));
        }catch(Exception e){toast(I18n.t(R.string.profile_error)+": "+e.getMessage());return false;}
        SharedPreferences.Editor editor=prefs.edit();
        for(Map.Entry<String,String> entry:values.entrySet())editor.putString(entry.getKey(),entry.getValue());
        editor.putString("host",nextHost).putString("port",nextPort);
        if(pairPort!=null)editor.putString("pairPort",pairPort.getText().toString().trim());
        editor.apply();
        return true;
    }""".strip("\n")

profile_methods = """
    private void refreshHome(int targetPage){
        if(home!=null)root.removeView(home);
        fields.clear();host=null;port=null;pairPort=null;pairCode=null;
        console=null;usbStatus=null;page=0;
        buildHome();
        if(targetPage!=0)select(targetPage);
    }
    private void addProfilesCard(LinearLayout content){
        LinearLayout card=card(content);
        card.addView(title(I18n.t(R.string.profiles_title)));
        if(profiles==null){
            card.addView(note(I18n.t(R.string.profile_unavailable)+": "+profilesError));
            return;
        }
        for(ProfileCodec.Profile profile:profiles.all()){
            boolean active=profile.id.equals(profiles.activeId());
            String endpoint="usb".equals(profile.transport)?"USB":
                (profile.host.isEmpty()?I18n.t(R.string.profile_no_host):profile.host+":"+profile.port);
            Button selectProfile=button((active?"●  ":"○  ")+profile.name+"  ·  "+endpoint,()->{
                if(profile.id.equals(profiles.activeId()))return;
                if(!saveFields())return;
                try{profiles.select(profile.id,prefs);refreshHome(0);}
                catch(Exception e){toast(I18n.t(R.string.profile_error)+": "+e.getMessage());}
            });
            selectProfile.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
            LinearLayout.LayoutParams row=new LinearLayout.LayoutParams(-1,dp(52));
            row.topMargin=dp(6);card.addView(selectProfile,row);
        }
        ProfileCodec.Profile selected=profiles.active();
        card.addView(note(I18n.t(R.string.profile_current)+": "+selected.name));
        addButton(card,I18n.t(R.string.profile_connect),()->{
            if(!saveFields())return;
            if("usb".equals(profiles.active().transport)){
                connectionGate.allowAutoUsb();scanUsb(true);
            }else begin();
        });
        LinearLayout actions=row();
        Button create=button(I18n.t(R.string.profile_create),()->profileEditor(true));
        Button edit=button(I18n.t(R.string.profile_edit),()->profileEditor(false));
        LinearLayout.LayoutParams half=new LinearLayout.LayoutParams(0,dp(48),1);
        half.setMargins(0,dp(8),dp(4),0);actions.addView(create,half);
        LinearLayout.LayoutParams second=new LinearLayout.LayoutParams(0,dp(48),1);
        second.setMargins(dp(4),dp(8),0,0);actions.addView(edit,second);
        card.addView(actions);
        LinearLayout other=row();
        Button copy=button(I18n.t(R.string.profile_copy),()->{
            if(!saveFields())return;
            try{profiles.duplicateActive(prefs);refreshHome(0);}
            catch(Exception e){toast(I18n.t(R.string.profile_error)+": "+e.getMessage());}
        });
        Button remove=button(I18n.t(R.string.profile_delete),this::deleteProfile);
        LinearLayout.LayoutParams left=new LinearLayout.LayoutParams(0,dp(48),1);
        left.setMargins(0,dp(8),dp(4),0);other.addView(copy,left);
        LinearLayout.LayoutParams right=new LinearLayout.LayoutParams(0,dp(48),1);
        right.setMargins(dp(4),dp(8),0,0);other.addView(remove,right);
        card.addView(other);
        card.addView(note(I18n.t(R.string.profile_next_session)));
    }
    private void profileEditor(boolean creating){
        if(profiles==null||!saveFields())return;
        ProfileCodec.Profile active=profiles.active();
        LinearLayout form=column();form.setPadding(dp(18),0,dp(18),0);
        EditText name=input(form,I18n.t(R.string.profile_name),creating?"":active.name,"Android TV",false);
        form.addView(note(I18n.t(R.string.profile_transport)));
        Spinner transport=new Spinner(this);
        transport.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,
            new String[]{"Wi-Fi ADB","USB"}));
        transport.setSelection("usb".equals(active.transport)?1:0);
        form.addView(transport,new LinearLayout.LayoutParams(-1,dp(46)));
        EditText address=input(form,I18n.t(R.string.profile_host),creating?"":active.host,"192.0.2.10",false);
        EditText tcpPort=input(form,I18n.t(R.string.profile_port),Integer.toString(active.port),"5555",true);
        form.addView(note(I18n.t(R.string.profile_usb_tip)));
        AlertDialog dialog=new AlertDialog.Builder(this)
            .setTitle(I18n.t(creating?R.string.profile_create:R.string.profile_edit))
            .setView(form)
            .setPositiveButton(I18n.t(R.string.profile_save),null)
            .setNegativeButton(I18n.t(R.string.text_076),null).create();
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            try{
                String mode=transport.getSelectedItemPosition()==1?"usb":"tcp";
                if(creating)profiles.create(name.getText().toString(),mode,address.getText().toString(),
                    tcpPort.getText().toString(),prefs);
                else profiles.editActive(name.getText().toString(),mode,address.getText().toString(),
                    tcpPort.getText().toString(),prefs);
                dialog.dismiss();refreshHome(0);
            }catch(Exception e){toast(I18n.t(R.string.profile_error)+": "+e.getMessage());}
        }));
        dialog.show();
    }
    private void deleteProfile(){
        if(profiles==null||!saveFields())return;
        if(profiles.all().size()<=1){toast(I18n.t(R.string.profile_last));return;}
        new AlertDialog.Builder(this)
            .setTitle(I18n.t(R.string.profile_delete))
            .setMessage(I18n.t(R.string.profile_delete_confirm)+" "+profiles.active().name)
            .setPositiveButton(I18n.t(R.string.profile_delete),(d,w)->{
                try{profiles.deleteActive(prefs);refreshHome(0);}
                catch(Exception e){toast(I18n.t(R.string.profile_error)+": "+e.getMessage());}
            })
            .setNegativeButton(I18n.t(R.string.text_076),null).show();
    }
""".strip("\n")

patch(java / "MainActivity.java", [
    ('    private SharedPreferences prefs;', '    private SharedPreferences prefs;\n    private ProfileStore profiles;\n    private String profilesError;'),
    ('I18n.initialize(this);logFile=new File(getFilesDir(),"console.log");',
     'I18n.initialize(this);try{profiles=new ProfileStore(this,prefs);profiles.applyActiveToPrefs(prefs);}'
     'catch(Exception e){profilesError=e.toString();profiles=null;}logFile=new File(getFilesDir(),"console.log");'),
    ('private void select(int n){saveFields();page=n;', 
     'private void select(int n){if(body.getChildCount()>0&&!saveFields())return;page=n;'),
    ('    private void connectionPage(){',
     profile_methods+'\n    private void connectionPage(){'),
    ('LinearLayout content=column();body.addView(scroll(content),new LinearLayout.LayoutParams(-1,-1));\n        LinearLayout c=card(content);',
     'LinearLayout content=column();body.addView(scroll(content),new LinearLayout.LayoutParams(-1,-1));\n        addProfilesCard(content);\n        LinearLayout c=card(content);'),
    ('addButton(content,I18n.t(R.string.text_117),()->{saveFields();try{new Options(prefs).server();',
     'addButton(content,I18n.t(R.string.text_117),()->{if(!saveFields())return;try{new Options(prefs).server();'),
    ('e.apply();fields.clear();body.removeAllViews();settingsPage();',
     'e.apply();fields.clear();if(!saveFields())return;body.removeAllViews();settingsPage();'),
    ('                saveFields();prefs.edit().putString("appLanguage",code).apply();',
     '                if(!saveFields())return;prefs.edit().putString("appLanguage",code).apply();'),
    ('private void preset(String size,String fps,String bitrate){saveFields();prefs.edit()',
     'private void preset(String size,String fps,String bitrate){if(!saveFields())return;prefs.edit()'),
    ('putString("video_codec","h264").apply();fields.clear();body.removeAllViews();settingsPage();',
     'putString("video_codec","h264").apply();fields.clear();if(!saveFields())return;body.removeAllViews();settingsPage();'),
    (save_fields_before, save_fields_after),
    ('try{saveFields();lastOptions=new Options(prefs);lastOptions.server();lastUsb=device;',
     'try{if(!saveFields())return;lastOptions=new Options(prefs);lastOptions.server();lastUsb=device;'),
    ('private void begin(){if(!connectionGate.canStart()||destroyed)return;saveFields();try{',
     'private void begin(){if(!connectionGate.canStart()||destroyed)return;if(!saveFields())return;try{'),
    ('private void pair(){if(!connectionGate.canStart()||destroyed)return;saveFields();',
     'private void pair(){if(!connectionGate.canStart()||destroyed)return;if(!saveFields())return;'),
])

strings = {
  "values": {
    "profiles_title":"Device profiles",
    "profile_unavailable":"Profiles unavailable; current connection is preserved",
    "profile_no_host":"IP not set",
    "profile_current":"Selected",
    "profile_connect":"Connect selected profile",
    "profile_create":"New profile",
    "profile_edit":"Edit profile",
    "profile_copy":"Duplicate profile",
    "profile_delete":"Delete",
    "profile_next_session":"Changes take effect on the next connection.",
    "profile_name":"Profile name",
    "profile_transport":"Connection type",
    "profile_host":"Device IP address",
    "profile_port":"ADB port",
    "profile_usb_tip":"USB profiles use direct OTG. TCP address is ignored for USB.",
    "profile_save":"Save",
    "profile_error":"Profile error",
    "profile_last":"At least one profile must remain",
    "profile_delete_confirm":"Permanently delete profile:"
  },
  "values-ro": {
    "profiles_title":"Profiluri de dispozitive",
    "profile_unavailable":"Profiluri indisponibile; conexiunea actuală este păstrată",
    "profile_no_host":"IP nesetat",
    "profile_current":"Selectat",
    "profile_connect":"Conectează profilul selectat",
    "profile_create":"Profil nou",
    "profile_edit":"Editează profilul",
    "profile_copy":"Duplică profilul",
    "profile_delete":"Șterge",
    "profile_next_session":"Modificările se aplică la următoarea conectare.",
    "profile_name":"Numele profilului",
    "profile_transport":"Tipul conexiunii",
    "profile_host":"Adresa IP a dispozitivului",
    "profile_port":"Port ADB",
    "profile_usb_tip":"Profilurile USB folosesc OTG; adresa TCP nu este utilizată.",
    "profile_save":"Salvează",
    "profile_error":"Eroare de profil",
    "profile_last":"Trebuie să rămână cel puțin un profil",
    "profile_delete_confirm":"Șterge definitiv profilul:"
  },
  "values-ru": {
    "profiles_title":"Профили устройств",
    "profile_unavailable":"Профили недоступны; старое подключение сохранено",
    "profile_no_host":"IP не задан",
    "profile_current":"Выбран",
    "profile_connect":"Подключить выбранный профиль",
    "profile_create":"Новый профиль",
    "profile_edit":"Изменить профиль",
    "profile_copy":"Копировать профиль",
    "profile_delete":"Удалить",
    "profile_next_session":"Изменения действуют со следующего подключения.",
    "profile_name":"Название профиля",
    "profile_transport":"Тип подключения",
    "profile_host":"IP-адрес устройства",
    "profile_port":"Порт ADB",
    "profile_usb_tip":"Для USB используется OTG; TCP-адрес игнорируется.",
    "profile_save":"Сохранить",
    "profile_error":"Ошибка профиля",
    "profile_last":"Нельзя удалять последний профиль",
    "profile_delete_confirm":"Удалить профиль без возможности восстановления:"
  }
}

for locale, translations in strings.items():
    path=root / f"res/{locale}/strings.xml"
    xml=path.read_text(encoding="utf-8")
    if xml.count("</resources>")!=1:
        raise ValueError(f"Unexpected XML: {path}")
    for key in translations:
        if f'name="{key}"' in xml:
            raise ValueError(f"Resource already exists: {key}")
    from xml.sax.saxutils import escape
    values="".join(f'    <string name="{key}" formatted="false">"{escape(value)}"</string>\n'
                   for key,value in translations.items())
    xml=xml.replace("</resources>",values+"</resources>")
    ET.fromstring(xml)
    updates[path]=xml

for name in ("ProfileCodec.java","ProfileStore.java"):
    origin=here / "src/main/java/ro/sw3g/scrcpy" / name
    destination=java/name
    if destination.exists():
        raise ValueError(f"Refusing to overwrite existing source: {destination}")
    updates[destination]=origin.read_text(encoding="utf-8")

build=root.parent.parent / "build.gradle"
build_text=build.read_text(encoding="utf-8")
if build_text.count("dependencies {")!=1:
    raise ValueError("Unexpected Gradle dependencies")
build_text=build_text.replace("dependencies {",
    "dependencies {\n"
    "    testImplementation 'junit:junit:4.13.2'\n"
    "    testImplementation 'org.json:json:20240303'",1)
updates[build]=build_text

test_file=root/"../test/java/ro/sw3g/scrcpy/ProfileCodecTest.java"
if test_file.exists():
    raise ValueError("Tests already exist")
updates[test_file]=(here/"src/test/java/ro/sw3g/scrcpy/ProfileCodecTest.java").read_text(encoding="utf-8")

# All source patch preconditions must pass before any actual write.
for destination,body in updates.items():
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(body,encoding="utf-8")
print(f"Profiles patch applied: {len(updates)} files, 19 resource keys per language")
