package dev.lolokeksu.boxyagent;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private static final int WHITE = Color.rgb(244, 247, 251);
    private static final int MUTED = Color.rgb(149, 159, 174);
    private static final int CYAN = Color.rgb(80, 213, 209);
    private EditText repoInput;
    private EditText tokenInput;
    private TextView status;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new Runnable() {
        @Override public void run() {
            if (status != null) status.setText("Состояние: " + AgentConfig.status(MainActivity.this)
                    + "\n" + (RemoteAccessibilityService.ready()
                    ? "Управление Home/Back: разрешено" : "Управление Home/Back: требуется разрешение")
                    + "\n" + (AgentConfig.hasToken(MainActivity.this)
                    ? "Токен: защищён Android Keystore" : "Токен: не настроен"));
            handler.postDelayed(this, 5000);
        }
    };

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
    private GradientDrawable shape(int bg, int line) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(bg);
        d.setCornerRadius(dp(10));
        d.setStroke(dp(1), line);
        return d;
    }
    private Button button(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(16);
        b.setTextColor(WHITE);
        b.setAllCaps(false);
        StateListDrawable state = new StateListDrawable();
        state.addState(new int[]{android.R.attr.state_focused}, shape(0xff164b51, CYAN));
        state.addState(new int[]{android.R.attr.state_pressed}, shape(0xff164b51, CYAN));
        state.addState(new int[]{}, shape(0xff20262f, 0xff3a4552));
        b.setBackground(state);
        b.setPadding(dp(16), dp(12), dp(16), dp(12));
        return b;
    }
    private TextView text(String value, int size, int color) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(size);
        v.setTextColor(color);
        return v;
    }
    private void addSpace(LinearLayout layout, int size) {
        View v = new View(this);
        layout.addView(v, new LinearLayout.LayoutParams(1, dp(size)));
    }
    private void message(String value) {
        status.setText(value);
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setBackgroundDrawableResource(android.R.color.black);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout content = new LinearLayout(this);
        content.setPadding(dp(52), dp(30), dp(52), dp(36));
        content.setOrientation(LinearLayout.VERTICAL);
        content.setBackgroundColor(Color.BLACK);
        scroll.addView(content);
        setContentView(scroll);

        TextView headline = text("BOXY AGENT", 30, WHITE);
        headline.setTypeface(null, android.graphics.Typeface.BOLD);
        content.addView(headline);
        addSpace(content, 8);
        content.addView(text("Прямое управление приставкой без Termux", 18, MUTED));
        addSpace(content, 20);

        TextView id = text("Идентификатор устройства: " + AgentConfig.deviceId(this), 14, CYAN);
        id.setTextIsSelectable(true);
        content.addView(id);
        addSpace(content, 18);
        content.addView(text("Приватный GitHub-репозиторий (владелец: lolokeksu09)", 16, WHITE));
        addSpace(content, 8);

        repoInput = new EditText(this);
        repoInput.setSingleLine(true);
        repoInput.setTextColor(WHITE);
        repoInput.setHintTextColor(MUTED);
        repoInput.setBackground(shape(0xff12171d, 0xff35414c));
        repoInput.setPadding(dp(16), dp(12), dp(16), dp(12));
        repoInput.setInputType(InputType.TYPE_CLASS_TEXT);
        repoInput.setHint("lolokeksu09/имя-приватного-репозитория");
        repoInput.setText(AgentConfig.repo(this));
        content.addView(repoInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addSpace(content, 14);
        content.addView(text("Fine-grained GitHub token — доступ только к Issues этого репозитория", 16, WHITE));
        addSpace(content, 8);

        tokenInput = new EditText(this);
        tokenInput.setSingleLine(true);
        tokenInput.setTextColor(WHITE);
        tokenInput.setHintTextColor(MUTED);
        tokenInput.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokenInput.setHint(AgentConfig.hasToken(this) ? "Токен сохранён — оставь пустым"
                                                    : "Введи токен (не отправляй его в чат)");
        tokenInput.setBackground(shape(0xff12171d, 0xff35414c));
        tokenInput.setPadding(dp(16), dp(12), dp(16), dp(12));
        content.addView(tokenInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addSpace(content, 18);

        Button start = button("Сохранить и включить");
        start.setOnClickListener(v -> {
            String selected = repoInput.getText().toString().trim();
            String suppliedToken = tokenInput.getText().toString().trim();
            if (!AgentPolicy.allowedRepo(selected)) {
                message("Укажи приватный репозиторий в своём GitHub-аккаунте.");
                return;
            }
            try {
                if (!suppliedToken.isEmpty()) AgentConfig.putToken(this, suppliedToken);
                tokenInput.setText("");
                if (!AgentConfig.hasToken(this)) {
                    message("Сначала введи fine-grained token.");
                    return;
                }
                AgentConfig.saveRepo(this, selected);
                AgentConfig.setEnabled(this, true);
                AgentConfig.setStatus(this, "Проверка приватного GitHub…");
                Intent service = new Intent(this, AgentService.class);
                if (Build.VERSION.SDK_INT >= 26) startForegroundService(service);
                else startService(service);
                message("Агент запущен. Для Home/Back активируй спецвозможности ниже.");
            } catch (Exception ignored) {
                message("Не удалось сохранить настройки. Проверь токен и разрешения.");
            }
        });
        content.addView(start);
        addSpace(content, 10);

        Button accessibility = button("Открыть специальные возможности Android TV");
        accessibility.setOnClickListener(v -> {
            try { startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)); }
            catch (Exception ignored) { message("Не удалось открыть специальные возможности."); }
        });
        content.addView(accessibility);
        addSpace(content, 10);

        Button stop = button("Остановить агента");
        stop.setOnClickListener(v -> {
            AgentConfig.setEnabled(this, false);
            stopService(new Intent(this, AgentService.class));
            AgentConfig.setStatus(this, "Остановлен владельцем");
            message("Агент остановлен, токен сохранён.");
        });
        content.addView(stop);
        addSpace(content, 10);

        Button forget = button("Отключить и стереть токен");
        forget.setOnClickListener(v -> {
            stopService(new Intent(this, AgentService.class));
            AgentConfig.disconnect(this);
            repoInput.setText("");
            tokenInput.setText("");
            message("Подключение удалено из настроек приложения.");
        });
        content.addView(forget);
        addSpace(content, 24);

        status = text("Подключение не настроено", 15, MUTED);
        status.setPadding(dp(16), dp(14), dp(16), dp(14));
        status.setBackground(shape(0xff12171d, 0xff23313a));
        content.addView(status);
        addSpace(content, 20);
        content.addView(text("Безопасность: только приватный репозиторий, команды владельца, "
                + "без ADB-shell, скриншотов, установки APK и изменения системных пакетов. "
                + "Управление Home/Back требует разрешения Android Accessibility.", 13, MUTED));
    }

    @Override protected void onResume() {
        super.onResume();
        handler.removeCallbacks(refresh);
        handler.post(refresh);
    }
    @Override protected void onPause() {
        handler.removeCallbacks(refresh);
        super.onPause();
    }
}
