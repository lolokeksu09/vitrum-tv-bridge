package ro.sw3g.scrcpy;

import org.junit.Test;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.Assert.*;

public class SettingsSectionsTest {
    private static final String[] ALL = {
        "max_size","video_bit_rate","max_fps","video_codec","video_source",
        "display_id","crop","capture_orientation","angle","video_encoder",
        "video_codec_options","audio","audio_codec","audio_bit_rate",
        "audio_source","audio_dup","audio_encoder","audio_codec_options",
        "camera_id","camera_facing","camera_size","camera_fps","camera_high_speed",
        "new_display","control","show_touches","stay_awake","power_off_on_close",
        "clipboard_autosync","downsize_on_error","screenOff","record","reconnect",
        "mouseSpeed","extra"
    };
    private String[][] fields() {
        String[][] values=new String[ALL.length][];
        for(int i=0;i<ALL.length;i++)values[i]=new String[]{ALL[i]};
        return values;
    }

    @Test public void everyExistingSettingHasExactlyOneSection() {
        SettingsSections.checkContract(fields());
        assertArrayEquals(new int[]{6,8,12,9},SettingsSections.counts(fields()));
    }
    @Test public void advancedContainsCodecTuningButNotBasicQuality() {
        assertEquals(SettingsSections.ADVANCED,SettingsSections.category("video_codec_options"));
        assertEquals(SettingsSections.ADVANCED,SettingsSections.category("extra"));
        assertEquals(SettingsSections.BASIC,SettingsSections.category("max_fps"));
        assertEquals(SettingsSections.MEDIA,SettingsSections.category("record"));
        assertEquals(SettingsSections.CONTROL,SettingsSections.category("mouseSpeed"));
    }
    @Test public void schemaDriftIsRejected() {
        String[][] unexpected=Arrays.copyOf(fields(),ALL.length+1);
        unexpected[ALL.length]=new String[]{"future_setting"};
        try{SettingsSections.checkContract(unexpected);fail("uncategorized key accepted");}
        catch(IllegalArgumentException expected){}
    }
    @Test public void duplicateFieldIsRejected() {
        String[][] dup=fields();
        dup[0]=new String[]{dup[1][0]};
        try{SettingsSections.checkContract(dup);fail("duplicate accepted");}
        catch(IllegalArgumentException expected){}
    }
    @Test public void qualityPresetChangesOnlyFourOptions() {
        Map<String,String> before=new LinkedHashMap<>();
        before.put("max_size","3840");
        before.put("max_fps","120");
        before.put("video_bit_rate","40000000");
        before.put("video_codec","h265");
        before.put("record","false");
        before.put("mouseSpeed","2.0");
        Map<String,String> after=QualityPresets.apply(before,"1280","60","8000000");
        assertEquals("3840",before.get("max_size"));
        assertEquals("h265",before.get("video_codec"));
        assertEquals("1280",after.get("max_size"));
        assertEquals("60",after.get("max_fps"));
        assertEquals("8000000",after.get("video_bit_rate"));
        assertEquals("h264",after.get("video_codec"));
        assertEquals("false",after.get("record"));
        assertEquals("2.0",after.get("mouseSpeed"));
        assertEquals(before.keySet(),after.keySet());
    }
    @Test public void allPresetsProduceDocumentedQuality() {
        Map<String,String> blank=new LinkedHashMap<>();
        assertEquals("1920",QualityPresets.apply(blank,"1920","60","24000000").get("max_size"));
        assertEquals("1280",QualityPresets.apply(blank,"1280","60","8000000").get("max_size"));
        assertEquals("800",QualityPresets.apply(blank,"800","30","2000000").get("max_size"));
    }
    @Test public void undocumentedPresetIsRejected() {
        try{QualityPresets.apply(new LinkedHashMap<>(),"0","1000","0");fail("unknown preset accepted");}
        catch(IllegalArgumentException expected){}
    }
}
