package ro.sw3g.scrcpy;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Pure model/serialization layer. It never stores credentials or touches Android resources. */
final class ProfileCodec {
    static final int SCHEMA = 1;
    static final int MAX_PROFILES = 50;

    static final class Profile {
        final String id, name, transport, host;
        final int port, interactionMode;
        final Map<String,String> settings;
        Profile(String id, String name, String transport, String host, int port, int interactionMode,
                Map<String,String> settings) {
            this.id=id;
            this.name=name;
            this.transport=transport;
            this.host=host;
            this.port=port;
            this.interactionMode=interactionMode;
            this.settings=Collections.unmodifiableMap(new LinkedHashMap<>(settings));
        }
        Profile withSettings(Map<String,String> values, String nextHost, int nextPort, int nextMode) {
            return new Profile(id,name,transport,nextHost,nextPort,nextMode,values);
        }
        Profile withIdentity(String nextName, String nextTransport, String nextHost, int nextPort) {
            return new Profile(id,nextName,nextTransport,nextHost,nextPort,interactionMode,settings);
        }
    }

    static final class Document {
        final String activeProfileId;
        final Map<String,Profile> profiles;
        Document(String active, Map<String,Profile> profiles) {
            this.activeProfileId=active;
            this.profiles=Collections.unmodifiableMap(new LinkedHashMap<>(profiles));
        }
        Profile active() { return profiles.get(activeProfileId); }
        List<Profile> all() { return new ArrayList<>(profiles.values()); }
    }

    private static void checkProfile(Profile p, Map<String,String> defaults) {
        if(p.id==null)throw new IllegalArgumentException("Missing profile ID");
        try { UUID.fromString(p.id); }catch(Exception e){throw new IllegalArgumentException("Invalid profile ID");}
        if(p.name==null || p.name.trim().isEmpty() || p.name.length()>64)
            throw new IllegalArgumentException("Profile name must be 1–64 characters");
        if(!"usb".equals(p.transport) && !"tcp".equals(p.transport))
            throw new IllegalArgumentException("Invalid transport");
        if(p.host==null || p.host.length()>255 || p.host.contains("\n") || p.host.contains("\r")
                || p.host.trim().contains(" ") || !p.host.equals(p.host.trim()))
            throw new IllegalArgumentException("Invalid host");
        if(p.port<1 || p.port>65535)throw new IllegalArgumentException("Port must be 1–65535");
        if(p.interactionMode<0 || p.interactionMode>2)
            throw new IllegalArgumentException("Invalid interaction mode");
        if(!p.settings.keySet().equals(defaults.keySet()))
            throw new IllegalArgumentException("Unknown or missing session setting");
        for(String value:p.settings.values())
            if(value==null || value.length()>8192)
                throw new IllegalArgumentException("Invalid session setting length");
    }
    static void validate(Document doc, Map<String,String> defaults) {
        if(doc==null || doc.profiles.isEmpty() || doc.profiles.size()>MAX_PROFILES)
            throw new IllegalArgumentException("Invalid profile count");
        if(!doc.profiles.containsKey(doc.activeProfileId))
            throw new IllegalArgumentException("Active profile not found");
        for(Map.Entry<String,Profile> e:doc.profiles.entrySet()) {
            if(!e.getKey().equals(e.getValue().id))
                throw new IllegalArgumentException("Profile key/ID mismatch");
            checkProfile(e.getValue(),defaults);
        }
    }

    static String encode(Document doc, Map<String,String> defaults) throws JSONException {
        validate(doc,defaults);
        JSONObject root=new JSONObject();
        root.put("schemaVersion",SCHEMA);
        root.put("activeProfileId",doc.activeProfileId);
        JSONArray entries=new JSONArray();
        for(Profile p:doc.profiles.values()) {
            JSONObject obj=new JSONObject();
            obj.put("id",p.id); obj.put("name",p.name);
            obj.put("transport",p.transport); obj.put("host",p.host);
            obj.put("port",p.port); obj.put("interactionMode",p.interactionMode);
            JSONObject settings=new JSONObject();
            for(Map.Entry<String,String> entry:p.settings.entrySet())
                settings.put(entry.getKey(),entry.getValue());
            obj.put("settings",settings);
            entries.put(obj);
        }
        root.put("profiles",entries);
        return root.toString();
    }

    static Document decode(String json, Map<String,String> defaults) throws JSONException {
        if(json==null || json.length()>1024*1024)
            throw new IllegalArgumentException("Profiles document too large");
        JSONObject root=new JSONObject(json);
        if(root.getInt("schemaVersion")!=SCHEMA)
            throw new IllegalArgumentException("Unsupported profiles schema");
        JSONArray entries=root.getJSONArray("profiles");
        if(entries.length()<1 || entries.length()>MAX_PROFILES)
            throw new IllegalArgumentException("Invalid profile count");
        LinkedHashMap<String,Profile> profiles=new LinkedHashMap<>();
        for(int i=0;i<entries.length();i++){
            JSONObject obj=entries.getJSONObject(i);
            JSONObject saved=obj.getJSONObject("settings");
            java.util.Iterator<String> keys=saved.keys();
            while(keys.hasNext()) {
                String key=keys.next();
                if(!defaults.containsKey(key))throw new IllegalArgumentException("Unknown setting: "+key);
            }
            LinkedHashMap<String,String> options=new LinkedHashMap<>(defaults);
            for(String key:defaults.keySet())
                if(saved.has(key))options.put(key,saved.getString(key));
            Profile p=new Profile(
                obj.getString("id"),obj.getString("name"),obj.getString("transport"),
                obj.getString("host"),obj.getInt("port"),obj.getInt("interactionMode"),options);
            if(profiles.put(p.id,p)!=null)
                throw new IllegalArgumentException("Duplicate profile ID");
        }
        Document document=new Document(root.getString("activeProfileId"),profiles);
        validate(document,defaults);
        return document;
    }
}
