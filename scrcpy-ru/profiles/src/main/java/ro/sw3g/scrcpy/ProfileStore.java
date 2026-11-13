package ro.sw3g.scrcpy;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.AtomicFile;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Local, versioned profile store. ADB identities, pairing codes and USB grants
 * deliberately remain outside this file. The legacy preferences are retained.
 */
final class ProfileStore {
    private final AtomicFile file;
    private final LinkedHashMap<String,String> defaults=new LinkedHashMap<>();
    private ProfileCodec.Document document;

    ProfileStore(Context context, SharedPreferences old) throws Exception {
        file=new AtomicFile(new File(context.getFilesDir(),"profiles-v1.json"));
        for(String[] field:Options.fields())defaults.put(field[0],field[2]);
        try(InputStream in=file.openRead()){
            ByteArrayOutputStream output=new ByteArrayOutputStream();
            byte[] buf=new byte[8192];int n;
            while((n=in.read(buf))!=-1){
                if(output.size()+n>1024*1024)throw new IllegalArgumentException("Profiles file too large");
                output.write(buf,0,n);
            }
            document=ProfileCodec.decode(new String(output.toByteArray(),StandardCharsets.UTF_8),defaults);
            for(ProfileCodec.Profile p:document.profiles.values())validateSettings(p.settings);
        }catch(FileNotFoundException notMigrated){
            LinkedHashMap<String,String> settings=new LinkedHashMap<>();
            for(String[] field:Options.fields())
                settings.put(field[0],old.getString(field[0],field[2]));
            int port;
            try {port=Integer.parseInt(old.getString("port","5555"));}
            catch(Exception e){port=5555;}
            if(port<1 || port>65535)port=5555;
            int mode=old.getInt("interactionMode",0);
            if(mode<0 || mode>2)mode=0;
            ProfileCodec.Profile migrated=new ProfileCodec.Profile(
                UUID.randomUUID().toString(),"Текущее устройство","tcp",
                old.getString("host","").trim(),port,mode,settings);
            LinkedHashMap<String,ProfileCodec.Profile> first=new LinkedHashMap<>();
            first.put(migrated.id,migrated);
            // Preserve legacy settings as stored, even if a user previously saved
            // invalid values. Validation is required before the next edited save.
            write(new ProfileCodec.Document(migrated.id,first),false);
        }
    }

    ProfileCodec.Profile active(){return document.active();}
    List<ProfileCodec.Profile> all(){return document.all();}
    String activeId(){return document.activeProfileId;}

    private void validateSettings(Map<String,String> settings) {
        // This method retains all existing scrcpy validation and option names.
        new Options(settings).server();
    }

    private void write(ProfileCodec.Document next, boolean validateOptions) throws Exception {
        String json=ProfileCodec.encode(next,defaults);
        if(validateOptions)for(ProfileCodec.Profile p:next.profiles.values())
            validateSettings(p.settings);
        byte[] bytes=json.getBytes(StandardCharsets.UTF_8);
        if(bytes.length>1024*1024)throw new IllegalArgumentException("Profiles file too large");
        FileOutputStream out=file.startWrite();
        try {
            out.write(bytes);
            file.finishWrite(out);
        }catch(Exception e){
            file.failWrite(out);
            throw e;
        }
        document=next;
    }
    private void replace(ProfileCodec.Profile profile) throws Exception {
        LinkedHashMap<String,ProfileCodec.Profile> next=new LinkedHashMap<>(document.profiles);
        next.put(profile.id,profile);
        write(new ProfileCodec.Document(document.activeProfileId,next),true);
    }

    void saveActive(Map<String,String> settings,String host,String portText,int mode) throws Exception {
        ProfileCodec.Profile current=active();
        int port=Integer.parseInt(portText.trim());
        // Draft TCP profiles may omit host, but a connection requires it.
        ProfileCodec.Profile next=current.withSettings(settings,host.trim(),port,mode);
        replace(next);
    }

    void select(String id,SharedPreferences prefs) throws Exception {
        if(!document.profiles.containsKey(id))throw new IllegalArgumentException("Unknown profile");
        if(!id.equals(document.activeProfileId))write(new ProfileCodec.Document(id,document.profiles),false);
        applyActiveToPrefs(prefs);
    }

    void create(String name,String transport,String host,String portText,SharedPreferences prefs)
            throws Exception {
        ProfileCodec.Profile current=active();
        int port=Integer.parseInt(portText.trim());
        ProfileCodec.Profile added=new ProfileCodec.Profile(
            UUID.randomUUID().toString(),name.trim(),transport,host.trim(),port,
            current.interactionMode,current.settings);
        LinkedHashMap<String,ProfileCodec.Profile> next=new LinkedHashMap<>(document.profiles);
        next.put(added.id,added);
        write(new ProfileCodec.Document(added.id,next),true);
        applyActiveToPrefs(prefs);
    }
    void editActive(String name,String transport,String host,String portText,SharedPreferences prefs)
            throws Exception {
        int port=Integer.parseInt(portText.trim());
        replace(active().withIdentity(name.trim(),transport,host.trim(),port));
        applyActiveToPrefs(prefs);
    }
    void duplicateActive(SharedPreferences prefs) throws Exception {
        ProfileCodec.Profile p=active();
        String base=p.name.length()>58?p.name.substring(0,58):p.name;
        create(base+" (копия)",p.transport,p.host,Integer.toString(p.port),prefs);
    }
    boolean deleteActive(SharedPreferences prefs) throws Exception {
        if(document.profiles.size()==1)return false;
        LinkedHashMap<String,ProfileCodec.Profile> next=new LinkedHashMap<>(document.profiles);
        next.remove(document.activeProfileId);
        String selected=next.keySet().iterator().next();
        write(new ProfileCodec.Document(selected,next),true);
        applyActiveToPrefs(prefs);
        return true;
    }

    void applyActiveToPrefs(SharedPreferences prefs){
        ProfileCodec.Profile current=active();
        SharedPreferences.Editor editor=prefs.edit();
        for(Map.Entry<String,String> entry:current.settings.entrySet())
            editor.putString(entry.getKey(),entry.getValue());
        editor.putString("host",current.host);
        editor.putString("port",Integer.toString(current.port));
        editor.putInt("interactionMode",current.interactionMode);
        // Never modify appLanguage, usbAuto, pairPort or adb-identity.bin.
        editor.apply();
    }
}
