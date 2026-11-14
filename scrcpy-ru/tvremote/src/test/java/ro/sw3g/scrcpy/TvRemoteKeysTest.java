package ro.sw3g.scrcpy;

import android.view.KeyEvent;
import org.junit.Test;
import java.util.HashSet;
import java.util.Set;
import static org.junit.Assert.*;

public class TvRemoteKeysTest {
    private final int[] keys = {
        TvRemoteKeys.UP,TvRemoteKeys.DOWN,TvRemoteKeys.LEFT,TvRemoteKeys.RIGHT,TvRemoteKeys.OK,
        TvRemoteKeys.BACK,TvRemoteKeys.HOME,TvRemoteKeys.VOLUME_DOWN,TvRemoteKeys.VOLUME_UP,
        TvRemoteKeys.MUTE
    };

    @Test public void allTenActionsAreAllowed() {
        for(int key:keys)assertTrue("Missing key: "+key,TvRemoteKeys.supported(key));
    }
    @Test public void directionsUseAndroidDpadConstants() {
        assertEquals(KeyEvent.KEYCODE_DPAD_UP,TvRemoteKeys.UP);
        assertEquals(KeyEvent.KEYCODE_DPAD_DOWN,TvRemoteKeys.DOWN);
        assertEquals(KeyEvent.KEYCODE_DPAD_LEFT,TvRemoteKeys.LEFT);
        assertEquals(KeyEvent.KEYCODE_DPAD_RIGHT,TvRemoteKeys.RIGHT);
    }
    @Test public void okUsesDpadCenterNotEnter() {
        assertEquals(KeyEvent.KEYCODE_DPAD_CENTER,TvRemoteKeys.OK);
        assertNotEquals(KeyEvent.KEYCODE_ENTER,TvRemoteKeys.OK);
    }
    @Test public void navigationUsesSystemKeys() {
        assertEquals(KeyEvent.KEYCODE_BACK,TvRemoteKeys.BACK);
        assertEquals(KeyEvent.KEYCODE_HOME,TvRemoteKeys.HOME);
    }
    @Test public void volumeIncludesMute() {
        assertEquals(KeyEvent.KEYCODE_VOLUME_DOWN,TvRemoteKeys.VOLUME_DOWN);
        assertEquals(KeyEvent.KEYCODE_VOLUME_UP,TvRemoteKeys.VOLUME_UP);
        assertEquals(KeyEvent.KEYCODE_VOLUME_MUTE,TvRemoteKeys.MUTE);
    }
    @Test public void noDuplicateKeyCodes() {
        Set<Integer> unique=new HashSet<>();
        for(int key:keys)assertTrue("Duplicate key "+key,unique.add(key));
        assertEquals(10,unique.size());
    }
    @Test public void dangerousOrUnrelatedKeysAreRejected() {
        int[] disallowed={
            -1,0,KeyEvent.KEYCODE_POWER,KeyEvent.KEYCODE_DEL,KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_MENU,KeyEvent.KEYCODE_APP_SWITCH,KeyEvent.KEYCODE_CAMERA,
            KeyEvent.KEYCODE_SETTINGS,99999
        };
        for(int key:disallowed)assertFalse("Unexpected action allowed: "+key,TvRemoteKeys.supported(key));
    }
}
