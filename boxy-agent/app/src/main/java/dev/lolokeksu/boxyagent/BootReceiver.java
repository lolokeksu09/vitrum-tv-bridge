package dev.lolokeksu.boxyagent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/** Restart only a previously enabled, already paired agent after TV boots. */
public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        if (!AgentConfig.enabled(context) || !AgentConfig.hasToken(context)
                || !AgentPolicy.allowedRepo(AgentConfig.repo(context))) return;
        try {
            Intent service = new Intent(context, AgentService.class);
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(service);
            else context.startService(service);
        } catch (RuntimeException ignored) {
            AgentConfig.setStatus(context, "Автозапуск заблокирован системой");
        }
    }
}
