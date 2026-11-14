#!/usr/bin/env python3
"""Apply Android TV remote overlay after RU, Profiles v1, and Settings v2.

All exact-match preconditions and XML are checked before writing.
No shell commands, new Android permissions, server/protocol changes or device installs.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import sys

if len(sys.argv)!=2:
    raise SystemExit("Usage: python3 apply_tvremote.py /path/to/android_source")
repo=Path(sys.argv[1]).resolve()
main_root=repo/"app/src/main"
java=main_root/"java/ro/sw3g/scrcpy"
here=Path(__file__).resolve().parent
updates={}

path=java/"MainActivity.java"
body=path.read_text(encoding="utf-8")
def change(before,after):
    global body
    count=body.count(before)
    if count!=1:
        raise RuntimeError(f"MainActivity baseline mismatch ({count} occurrences): {before[:120]!r}")
    body=body.replace(before,after,1)

change(
    '    private Dialog activeConsole;',
    '    private Dialog activeConsole;\n    private TvRemotePanel tvRemotePanel;'
)

# Non-modal overlay launcher on the live player; existing menu remains draggable.
change(
    'player.addView(menu,mp);',
    '''player.addView(menu,mp);
        Button tvButton=button("TV",this::toggleTvRemote);
        tvButton.setContentDescription(I18n.t(R.string.tv_remote_open));
        tvButton.setAlpha(.72f);
        tvButton.setMinWidth(0);tvButton.setMinimumWidth(0);
        tvButton.setPadding(0,0,0,0);
        FrameLayout.LayoutParams tvParams=new FrameLayout.LayoutParams(dp(44),dp(36),Gravity.TOP|Gravity.END);
        tvParams.setMargins(dp(8),dp(10),dp(60),0);
        player.addView(tvButton,tvParams);'''
)

tv_methods='''
    private void toggleTvRemote(){
        if(tvRemotePanel!=null)hideTvRemote();
        else showTvRemote();
    }
    private void showTvRemote(){
        if(tvRemotePanel!=null)return;
        Session current=session;
        if(player==null||remote==null||current==null||!current.connected||current.control==null){
            toast(I18n.t(R.string.tv_remote_unavailable));
            return;
        }
        remote.releaseTouches();
        TvRemotePanel panel=new TvRemotePanel(this,this::sendTvRemoteKey,this::hideTvRemote);
        int width=Math.min(dp(340),Math.max(dp(240),player.getWidth()-dp(24)));
        FrameLayout.LayoutParams layout=new FrameLayout.LayoutParams(
            width,FrameLayout.LayoutParams.WRAP_CONTENT,Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);
        layout.setMargins(dp(8),0,dp(8),dp(14));
        tvRemotePanel=panel;
        player.addView(panel,layout);
    }
    private void hideTvRemote(){
        TvRemotePanel panel=tvRemotePanel;
        tvRemotePanel=null;
        if(panel!=null&&panel.getParent() instanceof FrameLayout)
            ((FrameLayout)panel.getParent()).removeView(panel);
        if(remote!=null)remote.requestFocus();
    }
    private void sendTvRemoteKey(int code){
        if(!TvRemoteKeys.supported(code))return;
        Session current=session;
        if(current==null||!current.connected||current.control==null){
            hideTvRemote();
            toast(I18n.t(R.string.tv_remote_unavailable));
            return;
        }
        current.control.clickKey(code);
    }
'''
change('    private void sessionMenu(){',tv_methods+'    private void sessionMenu(){')
change(
    'tileRow(p.content,new String[]{I18n.t(R.string.text_161),I18n.t(R.string.text_162)},new Runnable[]{()->showActionsPanel(p),this::sessionConsole});',
    '''tileRow(p.content,new String[]{I18n.t(R.string.text_161),I18n.t(R.string.text_162)},new Runnable[]{()->showActionsPanel(p),this::sessionConsole});
        addButton(p.content,I18n.t(R.string.tv_remote_open),()->{
            p.dialog.dismiss();showTvRemote();
        });'''
)
change(
    'private void leavePlayer(){if(leaving)return;leaving=true;',
    'private void leavePlayer(){if(leaving)return;leaving=true;hideTvRemote();'
)
change(
    'public void ended(Session who,String reason,boolean manual){ui.post(()->{if(session!=who)return;session=null;',
    'public void ended(Session who,String reason,boolean manual){ui.post(()->{if(session!=who)return;session=null;hideTvRemote();'
)
change(
    'private void disconnect(){connectionGate.suppressAutoUsb();',
    'private void disconnect(){hideTvRemote();connectionGate.suppressAutoUsb();'
)
updates[path]=body

translations={
  "values":{
    "tv_remote_title":"Android TV remote",
    "tv_remote_open":"TV remote",
    "tv_remote_close":"Close TV remote",
    "tv_remote_hint":"Navigate Android TV without touching the mirrored screen.",
    "tv_remote_unavailable":"Connect first and enable remote control in this profile.",
    "tv_remote_up":"Up",
    "tv_remote_down":"Down",
    "tv_remote_left":"Left",
    "tv_remote_right":"Right",
    "tv_remote_ok":"OK / Select",
    "tv_remote_back":"Back",
    "tv_remote_home":"Home",
    "tv_remote_mute":"Mute",
    "tv_remote_volume_down":"Volume down",
    "tv_remote_volume_up":"Volume up"
  },
  "values-ro":{
    "tv_remote_title":"Telecomandă Android TV",
    "tv_remote_open":"Telecomandă TV",
    "tv_remote_close":"Închide telecomanda",
    "tv_remote_hint":"Navighează pe Android TV fără a atinge ecranul transmis.",
    "tv_remote_unavailable":"Conectează-te și activează controlul în profil.",
    "tv_remote_up":"Sus",
    "tv_remote_down":"Jos",
    "tv_remote_left":"Stânga",
    "tv_remote_right":"Dreapta",
    "tv_remote_ok":"OK / Selectare",
    "tv_remote_back":"Înapoi",
    "tv_remote_home":"Acasă",
    "tv_remote_mute":"Fără sunet",
    "tv_remote_volume_down":"Volum mai mic",
    "tv_remote_volume_up":"Volum mai mare"
  },
  "values-ru":{
    "tv_remote_title":"Пульт Android TV",
    "tv_remote_open":"ТВ-пульт",
    "tv_remote_close":"Закрыть ТВ-пульт",
    "tv_remote_hint":"Управляй приставкой кнопками поверх трансляции.",
    "tv_remote_unavailable":"Сначала подключись и включи управление в профиле.",
    "tv_remote_up":"Вверх",
    "tv_remote_down":"Вниз",
    "tv_remote_left":"Влево",
    "tv_remote_right":"Вправо",
    "tv_remote_ok":"OK / Выбрать",
    "tv_remote_back":"Назад",
    "tv_remote_home":"Главная",
    "tv_remote_mute":"Без звука",
    "tv_remote_volume_down":"Тише",
    "tv_remote_volume_up":"Громче"
  }
}
for locale,data in translations.items():
    path=main_root/f"res/{locale}/strings.xml"
    original=path.read_text(encoding="utf-8")
    for key in data:
        if f'name="{key}"' in original:
            raise RuntimeError(f"Already defined: {key} in {path}")
    if original.count("</resources>")!=1:
        raise RuntimeError(f"Bad resources structure: {path}")
    additions="".join(
        f'    <string name="{key}" formatted="false">"{escape(value)}</string>\n'
        for key,value in data.items()
    )
    modified=original.replace("</resources>",additions+"</resources>")
    ET.fromstring(modified)
    updates[path]=modified

for name in ("TvRemoteKeys.java","TvRemotePanel.java"):
    source=here/"src/main/java/ro/sw3g/scrcpy"/name
    target=java/name
    if target.exists():raise RuntimeError(f"Cannot overwrite: {target}")
    updates[target]=source.read_text(encoding="utf-8")

tests=repo/"app/src/test/java/ro/sw3g/scrcpy/TvRemoteKeysTest.java"
if tests.exists():raise RuntimeError("TV unit test file already exists")
updates[tests]=(here/"src/test/java/ro/sw3g/scrcpy/TvRemoteKeysTest.java").read_text(encoding="utf-8")

# All source mutations happen after validation of every file.
for destination,content in updates.items():
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(content,encoding="utf-8")
print("TV remote overlay patch applied:",len(updates),"files, 15 EN/RO/RU strings")
