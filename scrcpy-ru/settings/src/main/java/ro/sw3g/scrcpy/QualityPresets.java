package ro.sw3g.scrcpy;

import java.util.LinkedHashMap;
import java.util.Map;

/** Changes only the four documented quality fields, without mutating a live session. */
final class QualityPresets {
    static LinkedHashMap<String,String> apply(Map<String,String> current,
            String size, String fps, String bitrate) {
        if(current==null)throw new IllegalArgumentException("Missing settings");
        if(!("1920".equals(size)&&"60".equals(fps)&&"24000000".equals(bitrate))
           && !("1280".equals(size)&&"60".equals(fps)&&"8000000".equals(bitrate))
           && !("800".equals(size)&&"30".equals(fps)&&"2000000".equals(bitrate)))
            throw new IllegalArgumentException("Unknown quality preset");
        LinkedHashMap<String,String> next=new LinkedHashMap<>(current);
        next.put("max_size",size);
        next.put("max_fps",fps);
        next.put("video_bit_rate",bitrate);
        next.put("video_codec","h264");
        return next;
    }
}
