package ro.sw3g.scrcpy;

import org.junit.Test;
import org.json.JSONObject;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import static org.junit.Assert.*;

public class ProfileCodecTest {
    private LinkedHashMap<String,String> defaults(){
        LinkedHashMap<String,String> values=new LinkedHashMap<>();
        values.put("max_size","1280");
        values.put("video_codec","h264");
        return values;
    }
    private ProfileCodec.Document one(){
        String id=UUID.randomUUID().toString();
        LinkedHashMap<String,ProfileCodec.Profile> profiles=new LinkedHashMap<>();
        profiles.put(id,new ProfileCodec.Profile(id,"TV","tcp","192.0.2.10",5555,2,defaults()));
        return new ProfileCodec.Document(id,profiles);
    }
    @Test public void roundTripRetainsConnectionAndSettings() throws Exception {
        ProfileCodec.Document parsed=ProfileCodec.decode(ProfileCodec.encode(one(),defaults()),defaults());
        assertEquals("TV",parsed.active().name);
        assertEquals("192.0.2.10",parsed.active().host);
        assertEquals(5555,parsed.active().port);
        assertEquals(2,parsed.active().interactionMode);
        assertEquals("h264",parsed.active().settings.get("video_codec"));
    }
    @Test public void snapshotIsIndependentOfSourceMap() throws Exception {
        ProfileCodec.Document d=one();
        ProfileCodec.Profile p=d.active();
        Map<String,String> original=new LinkedHashMap<>(p.settings);
        ProfileCodec.Profile updated=p.withSettings(original,"192.0.2.55",6000,1);
        original.put("max_size","1");
        assertEquals("1280",updated.settings.get("max_size"));
        assertEquals("192.0.2.10",p.host);
        assertEquals("192.0.2.55",updated.host);
        try {updated.settings.put("max_size","7");fail("mutable profile settings");}
        catch(UnsupportedOperationException expected){}
    }
    @Test public void fillsMissingKnownOptionWithDefault() throws Exception {
        ProfileCodec.Document d=one();
        JSONObject root=new JSONObject(ProfileCodec.encode(d,defaults()));
        JSONObject value=root.getJSONArray("profiles").getJSONObject(0).getJSONObject("settings");
        value.remove("video_codec");
        ProfileCodec.Document parsed=ProfileCodec.decode(root.toString(),defaults());
        assertEquals("h264",parsed.active().settings.get("video_codec"));
    }
    @Test public void rejectsUnknownOptionAndSchema() throws Exception {
        JSONObject root=new JSONObject(ProfileCodec.encode(one(),defaults()));
        root.getJSONArray("profiles").getJSONObject(0).getJSONObject("settings").put("malicious_option","yes");
        try {ProfileCodec.decode(root.toString(),defaults());fail("unknown option accepted");}
        catch(IllegalArgumentException expected){}
        root=new JSONObject(ProfileCodec.encode(one(),defaults()));
        root.put("schemaVersion",2);
        try {ProfileCodec.decode(root.toString(),defaults());fail("future schema accepted");}
        catch(IllegalArgumentException expected){}
    }
    @Test public void rejectsInvalidPortAndMissingActiveProfile() throws Exception {
        ProfileCodec.Document doc=one();
        ProfileCodec.Profile current=doc.active();
        LinkedHashMap<String,ProfileCodec.Profile> profiles=new LinkedHashMap<>();
        profiles.put(current.id,new ProfileCodec.Profile(current.id,current.name,"tcp","192.0.2.10",0,0,defaults()));
        try {ProfileCodec.encode(new ProfileCodec.Document(current.id,profiles),defaults());fail("port zero accepted");}
        catch(IllegalArgumentException expected){}
        try {ProfileCodec.encode(new ProfileCodec.Document(UUID.randomUUID().toString(),doc.profiles),defaults());fail("invalid active ID accepted");}
        catch(IllegalArgumentException expected){}
    }
    @Test public void duplicateProfileIdsRejected() throws Exception {
        ProfileCodec.Document d=one();
        JSONObject root=new JSONObject(ProfileCodec.encode(d,defaults()));
        root.getJSONArray("profiles").put(root.getJSONArray("profiles").getJSONObject(0));
        try {ProfileCodec.decode(root.toString(),defaults());fail("duplicate accepted");}
        catch(IllegalArgumentException expected){}
    }
    @Test public void malformedDocumentDoesNotDecode() throws Exception {
        try {ProfileCodec.decode("{not-json}",defaults());fail("broken JSON accepted");}
        catch(Exception expected){}
    }
}
