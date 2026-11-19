package ro.sw3g.scrcpy;

import android.view.KeyEvent;

/** Whitelisted Android keycodes for the TV overlay; no shell or ADB command strings. */
final class TvRemoteKeys {
    static final int UP=KeyEvent.KEYCODE_DPAD_UP;
    static final int DOWN=KeyEvent.KEYCODE_DPAD_DOWN;
    static final int LEFT=KeyEvent.KEYCODE_DPAD_LEFT;
    static final int RIGHT=KeyEvent.KEYCODE_DPAD_RIGHT;
    static final int OK=KeyEvent.KEYCODE_DPAD_CENTER;
    static final int BACK=KeyEvent.KEYCODE_BACK;
    static final int HOME=KeyEvent.KEYCODE_HOME;
    static final int VOLUME_DOWN=KeyEvent.KEYCODE_VOLUME_DOWN;
    static final int VOLUME_UP=KeyEvent.KEYCODE_VOLUME_UP;
    static final int MUTE=KeyEvent.KEYCODE_VOLUME_MUTE;

    static boolean supported(int code) {
        switch(code) {
            case UP: case DOWN: case LEFT: case RIGHT: case OK:
            case BACK: case HOME: case VOLUME_DOWN: case VOLUME_UP: case MUTE:
                return true;
            default:
                return false;
        }
    }
    private TvRemoteKeys() {}
}
