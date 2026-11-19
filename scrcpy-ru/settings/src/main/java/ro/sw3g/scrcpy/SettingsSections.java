package ro.sw3g.scrcpy;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * Presentation-only classification. Scrcpy protocol names and stored values
 * are deliberately unchanged; all unlisted future keys remain accessible
 * under Advanced until explicitly categorized.
 */
final class SettingsSections {
    static final int BASIC = 0;
    static final int CONTROL = 1;
    static final int MEDIA = 2;
    static final int ADVANCED = 3;
    static final int COUNT = 4;

    private static Set<String> keys(String... values) {
        return Collections.unmodifiableSet(new HashSet<>(Arrays.asList(values)));
    }
    private static final Set<String> BASIC_KEYS = keys(
        "max_size","video_bit_rate","max_fps","video_codec","audio","audio_codec");
    private static final Set<String> CONTROL_KEYS = keys(
        "control","show_touches","stay_awake","power_off_on_close",
        "clipboard_autosync","screenOff","reconnect","mouseSpeed");
    private static final Set<String> MEDIA_KEYS = keys(
        "record","video_source","audio_bit_rate","audio_source","audio_dup",
        "audio_encoder","audio_codec_options","camera_id","camera_facing",
        "camera_size","camera_fps","camera_high_speed");
    private static final Set<String> ADVANCED_KEYS = keys(
        "display_id","crop","capture_orientation","angle","video_encoder",
        "video_codec_options","new_display","downsize_on_error","extra");

    static int category(String key) {
        if(BASIC_KEYS.contains(key))return BASIC;
        if(CONTROL_KEYS.contains(key))return CONTROL;
        if(MEDIA_KEYS.contains(key))return MEDIA;
        return ADVANCED;
    }

    static int[] counts(String[][] fields) {
        int[] counts = new int[COUNT];
        for(String[] field:fields)counts[category(field[0])]++;
        return counts;
    }

    static void checkContract(String[][] fields) {
        HashSet<String> unique = new HashSet<>();
        for(String[] field:fields) {
            if(!unique.add(field[0]))throw new IllegalArgumentException("Duplicate setting: "+field[0]);
            int hits=(BASIC_KEYS.contains(field[0])?1:0)
                +(CONTROL_KEYS.contains(field[0])?1:0)
                +(MEDIA_KEYS.contains(field[0])?1:0)
                +(ADVANCED_KEYS.contains(field[0])?1:0);
            if(hits!=1)throw new IllegalArgumentException("Uncategorized setting: "+field[0]);
        }
        if(unique.size()!=BASIC_KEYS.size()+CONTROL_KEYS.size()+MEDIA_KEYS.size()+ADVANCED_KEYS.size())
            throw new IllegalArgumentException("Settings group and options schema differ");
    }
}
