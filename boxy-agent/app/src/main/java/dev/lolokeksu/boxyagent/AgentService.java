package dev.lolokeksu.boxyagent;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/** Foreground polling worker. No shell, no screen captures, no installer. */
public final class AgentService extends Service {
    private static final String CHANNEL = "boxy_agent";
    private static final int NOTIFICATION_ID = 31;
    private ScheduledExecutorService worker;

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26)
            nm.createNotificationChannel(new NotificationChannel(CHANNEL,
                    "BOXY Agent", NotificationManager.IMPORTANCE_LOW));
        Intent ui = new Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(this, 0, ui,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification note = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("BOXY Agent")
.setContentText("Подключение к GitHub Issues")
                .setContentIntent(pending)
                .setOngoing(true)
                .build();
        startForeground(NOTIFICATION_ID, note);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (!AgentConfig.enabled(this) || !AgentConfig.hasToken(this)
                || !AgentPolicy.allowedRepo(AgentConfig.repo(this))
                || (AgentConfig.publicModeEnabled(this)
                        && !AgentPolicy.PUBLIC_CONTROL_REPO.equals(AgentConfig.repo(this)))) {
            AgentConfig.setStatus(this, "Не настроено подключение");
            stopSelf();
            return START_NOT_STICKY;
        }
        if (worker == null || worker.isShutdown()) {
            worker = Executors.newSingleThreadScheduledExecutor();
            worker.scheduleWithFixedDelay(this::safePoll, 0, 45, TimeUnit.SECONDS);
        }
        return START_STICKY;
    }

    private void safePoll() {
        try {
            if (!AgentConfig.enabled(this)) { stopSelf(); return; }
            poll();
        } catch (Exception ignored) {
            // Never log tokens, issue content or device details.
            AgentConfig.setStatus(this, "Ошибка связи с GitHub");
        }
    }

    private void poll() throws Exception {
        String repo = AgentConfig.repo(this);
        if (!AgentPolicy.allowedRepo(repo)) throw new IllegalStateException("Invalid repo");
        GithubApi api = new GithubApi(AgentConfig.token(this));
        JSONObject metadata = api.repository(repo);
        boolean githubPrivate = metadata.optBoolean("private", false);
        if (!AgentPolicy.allowedControlRepo(repo, githubPrivate,
                        AgentConfig.publicModeEnabled(this))
                || !repo.equals(metadata.optString("full_name", ""))
                || !AgentPolicy.OWNER.equals(
                        metadata.optJSONObject("owner") == null ? "" :
                                metadata.optJSONObject("owner").optString("login", ""))) {
            AgentConfig.setStatus(this, "ОТКАЗ: недопустимый канал или владелец");
            return;
        }
        JSONArray items = api.openIssues(repo);
        ArrayList<JSONObject> eligible = new ArrayList<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject found = items.optJSONObject(i);
            if (found != null) eligible.add(found);
        }
        // REST returns newest first to avoid an old-issue backlog.
        // Execute fresh requests in ascending issue order for predictable control.
        eligible.sort(Comparator.comparingInt(item -> item.optInt("number", 0)));
        for (JSONObject issue : eligible) {
            if (issue == null || issue.has("pull_request")) continue;
            int n = issue.optInt("number", 0);
            if (n <= AgentConfig.lastIssue(this)) continue;
            JSONObject author = issue.optJSONObject("user");
            if (author == null || !AgentPolicy.OWNER.equals(author.optString("login"))) continue;
            if (!AgentPolicy.fresh(issue.optString("created_at"), System.currentTimeMillis()))
                continue;
            String title = issue.optString("title");
            String body = issue.optString("body");
            if (body.length() > 300 || body.length() < 2) continue;
            JSONObject request;
            try { request = new JSONObject(body); } catch (Exception ignored) { continue; }
            String op = request.optString("op");
            Object version = request.opt("v");
            if (!(version instanceof Integer) ||
                    !AgentPolicy.exactRequest(title, ((Integer) version), op,
                            request.optString("device"), AgentConfig.deviceId(this),
                            request.length())
                    || !request.has("v") || !request.has("op") || !request.has("device"))
                continue;

            // Persistent guard BEFORE action: an interrupted acknowledgement cannot
            // cause duplicate remote key presses on next boot/poll.
            if (!AgentConfig.markIssue(this, n)) continue;
            String status;
            try { status = runAllowed(op) ? "SUCCESS" : "UNAVAILABLE"; }
            catch (Exception ignored) { status = "ERROR"; }
            String comment = AgentPolicy.RESULT_MARKER + "\nStatus: " + status
                    + " / " + op + "\nExecution acknowledged by paired BOXY Agent.";
            api.comment(repo, n, comment);
            api.close(repo, n);
            AgentConfig.setStatus(this, "Команда обработана");
        }
        AgentConfig.setStatus(this, githubPrivate ? "Подключён к приватному каналу"
                : "Подключён к ПУБЛИЧНОМУ каналу — команды видны всем");
    }

    private boolean runAllowed(String op) {
        if ("ping".equals(op)) return true;
        if ("home".equals(op)) return RemoteAccessibilityService.home();
        if ("back".equals(op)) return RemoteAccessibilityService.back();
        String pkg = AgentPolicy.appPackage(op);
        return pkg != null && RemoteAccessibilityService.launch(pkg);
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    @Override public void onDestroy() {
        if (worker != null) worker.shutdownNow();
        worker = null;
        super.onDestroy();
    }
}
