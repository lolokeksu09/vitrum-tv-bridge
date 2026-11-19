package dev.lolokeksu.boxyagent;

import org.junit.Test;
import static org.junit.Assert.*;

public final class TvLayoutSpecTest {
    @Test public void shortTvModeDoesNotDependOnResolutionLabel() {
        assertTrue(TvLayoutSpec.compactVertical(540));
        assertTrue(TvLayoutSpec.compactVertical(720));
        assertFalse(TvLayoutSpec.compactVertical(900));
        assertFalse(TvLayoutSpec.compactVertical(Float.NaN));
    }

    @Test public void onlyWhitespaceShrinksOnShortTv() {
        assertEquals(12, TvLayoutSpec.verticalGap(12, false));
        assertEquals(7, TvLayoutSpec.verticalGap(12, true));
        assertEquals(2, TvLayoutSpec.verticalGap(2, true));
        assertEquals(0, TvLayoutSpec.verticalGap(0, true));
    }
}
