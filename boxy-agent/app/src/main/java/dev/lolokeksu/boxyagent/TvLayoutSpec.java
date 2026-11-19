package dev.lolokeksu.boxyagent;

/** Pure spacing policy. Text sizes remain unchanged for viewing from 4–5 m. */
public final class TvLayoutSpec {
    private TvLayoutSpec() {}

    /** A 1080p TV may expose 540–720 layout dp depending on display density. */
    public static boolean compactVertical(float heightDp) {
        return Float.isFinite(heightDp) && heightDp < 760f;
    }

    /** Keep useful gaps while cutting empty vertical space by about 45%. */
    public static int verticalGap(int normalDp, boolean compact) {
        if (normalDp <= 0) return 0;
        if (!compact) return normalDp;
        return Math.max(2, Math.round(normalDp * 0.55f));
    }
}
