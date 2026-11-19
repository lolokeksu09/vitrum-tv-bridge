package dev.lolokeksu.boxyagent;

import android.accessibilityservice.AccessibilityService;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.view.accessibility.AccessibilityEvent;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Activated only after the TV owner grants Accessibility permission in Settings. */
public final class RemoteAccessibilityService extends AccessibilityService {
    private static volatile RemoteAccessibilityService active;
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override public void onServiceConnected() {
        super.onServiceConnected();
        active = this;
    }
    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        // Do not read application text, screen contents or personal information.
    }
    @Override public void onInterrupt() {}
    @Override public void onDestroy() {
        if (active == this) active = null;
        super.onDestroy();
    }

    public static boolean ready() { return active != null; }

    private static boolean onMain(java.util.concurrent.Callable<Boolean> action) {
        RemoteAccessibilityService service = active;
        if (service == null) return false;
        if (Looper.myLooper() == Looper.getMainLooper()) {
            try { return action.call(); } catch (Exception ignored) { return false; }
        }
        CountDownLatch latch = new CountDownLatch(1);
        AtomicBoolean success = new AtomicBoolean(false);
        service.main.post(() -> {
            try { if (active == service) success.set(action.call()); }
            catch (Exception ignored) { /* Not authorized or unavailable. */ }
            finally { latch.countDown(); }
        });
        try { return latch.await(5, TimeUnit.SECONDS) && success.get(); }
        catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    public static boolean home() {
        return onMain(() -> active != null
                && active.performGlobalAction(GLOBAL_ACTION_HOME));
    }

    public static boolean back() {
        return onMain(() -> active != null
                && active.performGlobalAction(GLOBAL_ACTION_BACK));
    }

    public static boolean launch(String packageName) {
        // Called only after AgentPolicy has resolved the package allowlist.
        return onMain(() -> {
            RemoteAccessibilityService service = active;
            if (service == null) return false;
            Intent intent = service.getPackageManager()
                    .getLeanbackLaunchIntentForPackage(packageName);
            if (intent == null)
                intent = service.getPackageManager().getLaunchIntentForPackage(packageName);
            if (intent == null) return false;
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            service.startActivity(intent);
            return true; // Activity launch REQUESTED, not verified foreground.
        });
    }
}
