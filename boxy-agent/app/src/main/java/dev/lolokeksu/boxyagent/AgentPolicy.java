package dev.lolokeksu.boxyagent;

import java.time.Instant;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Pattern;

public final class AgentPolicy {
    public static final String OWNER = "lolokeksu09";
    public static final String PREFIX = "BOXYAGENT/v1 ";
    public static final String RESULT_MARKER = "<!-- boxy-agent-v1-result -->";
    private static final Pattern REPO = Pattern.compile(
            "^" + OWNER + "/[A-Za-z0-9_.-]{1,100}$");
    private static final Map<String, String> PACKAGES;
    static {
        Map<String,String> known = new HashMap<>();
        known.put("youtube", "com.google.android.youtube.tv");
        known.put("vkvideo", "com.vk.tv");
        known.put("browsehere", "com.tcl.browser");
        known.put("v2rayng", "com.v2ray.ang");
        PACKAGES = Collections.unmodifiableMap(known);
    }

    private AgentPolicy() {}

    public static boolean allowedRepo(String repo) {
        return repo != null && REPO.matcher(repo).matches()
                && !repo.contains("..") && !repo.endsWith(".");
    }

    public static boolean allowedCommand(String op) {
        return "ping".equals(op) || "home".equals(op) || "back".equals(op)
                || PACKAGES.containsKey(op);
    }

    public static String appPackage(String op) { return PACKAGES.get(op); }

    public static boolean fresh(String timestamp, long nowMs) {
        try {
            long created = Instant.parse(timestamp).toEpochMilli();
            long delta = nowMs - created;
            return delta >= -30_000L && delta <= 180_000L;
        } catch (Exception ignored) { return false; }
    }

    public static boolean exactRequest(String title, int version, String op,
                                       String sentTo, String deviceId,
                                       int fieldCount) {
        return version == 1 && fieldCount == 3 && allowedCommand(op)
                && (PREFIX + op).equals(title)
                && deviceId != null && deviceId.equals(sentTo);
    }
}
