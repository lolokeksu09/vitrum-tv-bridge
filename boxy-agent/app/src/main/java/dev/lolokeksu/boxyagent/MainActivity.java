package dev.lolokeksu.boxyagent;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * One-screen TV setup designed for a physical remote and viewing from 4–5 m.
 * No change to protocol, GitHub authentication, Android permissions or services.
 * On compact displays and with an on-screen keyboard, the ScrollView is a safe fallback.
 */
public final class MainActivity extends Activity {
    private static final int BG = 0xff000000;
    private static final int PANEL = 0xff10151b;
    private static final int BORDER = 0xff2e3946;
    private static final int WHITE = 0xfff4f7fb;
    private static final int MUTED = 0xffa8b7c7;
    private static final int CYAN = 0xff5ee1de;
    private static final int WARNING = 0xffffcd87;

    private EditText tokenInput;
    private Button publicToggle;
    private TextView statusHeading;
    private TextView statusDetail;
    private TextView accessibilityDetail;
    private TextView tokenDetail;
    private TextView feedback;
    private boolean publicAllowed;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new Runnable() {
        @Override public void run() {
            updateStatus();
            handler.postDelayed(this, 4000);
        }
    };

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable background(int color, int border, int stroke) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(12));
        shape.setStroke(dp(stroke), border);
        return shape;
    }

    private StateListDrawable stateBackground(boolean primary) {
        StateListDrawable states = new StateListDrawable();
        if (primary) {
            states.addState(new int[]{android.R.attr.state_focused},
                    background(0xff86f2eb, WHITE, 3));
            states.addState(new int[]{android.R.attr.state_pressed},
                    background(0xff86f2eb, WHITE, 3));
            states.addState(new int[]{}, background(CYAN, CYAN, 1));
        } else {
            states.addState(new int[]{android.R.attr.state_focused},
                    background(0xff19383d, CYAN, 3));
            states.addState(new int[]{android.R.attr.state_pressed},
                    background(0xff19383d, CYAN, 3));
            states.addState(new int[]{}, background(0xff202832, BORDER, 1));
        }
        return states;
    }

    private TextView text(String value, float sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private Button button(String label, boolean primary) {
        Button view = new Button(this);
        view.setAllCaps(false);
        view.setText(label);
        view.setTextSize(21);
        view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        view.setTextColor(primary ? BG : WHITE);
        view.setBackground(stateBackground(primary));
        view.setGravity(Gravity.CENTER);
        view.setPadding(dp(12), dp(9), dp(12), dp(9));
        view.setMinHeight(dp(68));
        view.setFocusable(true);
        return view;
    }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private LinearLayout row() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setGravity(Gravity.CENTER_VERTICAL);
        return layout;
    }

    private void gap(LinearLayout container, int height) {
        View space = new View(this);
        container.addView(space, new LinearLayout.LayoutParams(1, dp(height)));
    }

    private LinearLayout panel() {
        LinearLayout pane = column();
        pane.setBackground(background(PANEL, BORDER, 1));
        pane.setPadding(dp(19), dp(17), dp(19), dp(17));
        return pane;
    }

    private void feedback(String message, boolean problem) {
        if (feedback != null) {
            feedback.setText(message);
            feedback.setTextColor(problem ? WARNING : MUTED);
        }
        updateStatus();
    }

    private void updateStatus() {
        if (statusHeading == null) return;
        boolean enabled = AgentConfig.enabled(this);
        boolean hasToken = AgentConfig.hasToken(this);
        String detail = AgentConfig.status(this);
        if (!enabled) {
            statusHeading.setText("НЕ ПОДКЛЮЧЁН");
            statusHeading.setTextColor(WHITE);
        } else if (detail.startsWith("Подключён")) {
            statusHeading.setText("ПОДКЛЮЧЁН");
            statusHeading.setTextColor(CYAN);
        } else if (detail.startsWith("Ошибка") || detail.startsWith("ОТКАЗ")
                || detail.startsWith("Автозапуск")) {
            statusHeading.setText("ПРОБЛЕМА СВЯЗИ");
            statusHeading.setTextColor(WARNING);
        } else {
            statusHeading.setText("ПОДКЛЮЧЕНИЕ…");
            statusHeading.setTextColor(WHITE);
        }
        statusDetail.setText(detail);
        accessibilityDetail.setText(RemoteAccessibilityService.ready()
                ? "Пульт: разрешено" : "Пульт: включи спецвозможности");
        accessibilityDetail.setTextColor(RemoteAccessibilityService.ready() ? CYAN : WARNING);
        tokenDetail.setText(hasToken ? "Токен сохранён" : "Токен не задан");
        tokenDetail.setTextColor(hasToken ? MUTED : WARNING);
        if (tokenInput != null && !tokenInput.hasFocus()) {
            tokenInput.setHint(hasToken ? "Уже сохранён · оставь пустым" : "Вставь GitHub token");
        }
    }

    private void updatePublicToggle() {
        publicToggle.setText(publicAllowed
                ? "ПУБЛИЧНЫЙ РЕЖИМ   ·   ВКЛ\nКоманды и ответы видны всем"
                : "ПУБЛИЧНЫЙ РЕЖИМ   ·   ВЫКЛ\nНажми ОК, чтобы разрешить");
        publicToggle.setContentDescription(publicAllowed
                ? "Публичный режим включён. Команды и ответы видны всем. Нажми для отключения."
                : "Публичный режим выключен. Нажми для включения.");
        publicToggle.setTextColor(publicAllowed ? CYAN : WHITE);
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setBackgroundDrawableResource(android.R.color.black);
        publicAllowed = AgentConfig.publicModeEnabled(this);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.setBackgroundColor(BG);

        LinearLayout wrapper = column();
        wrapper.setGravity(Gravity.CENTER_HORIZONTAL);
        wrapper.setPadding(dp(24), dp(18), dp(24), dp(18));
        scroll.addView(wrapper, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        setContentView(scroll);

        int widthPx = getResources().getDisplayMetrics().widthPixels;
        int maxWidthPx = dp(1220);
        int bodyWidth = Math.max(dp(560), Math.min(widthPx - dp(48), maxWidthPx));
        LinearLayout screen = column();
        wrapper.addView(screen, new LinearLayout.LayoutParams(
                Math.min(bodyWidth, widthPx - dp(40)), ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout header = row();
        LinearLayout brand = column();
        TextView title = text("BOXY AGENT", 40, WHITE, true);
        title.setLetterSpacing(0.025f);
        brand.addView(title);
        gap(brand, 3);
        brand.addView(text("Управление ТВ без Termux", 20, MUTED, false));
        header.addView(brand, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView version = text("v0.3", 18, MUTED, true);
        version.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        header.addView(version);
        screen.addView(header);
        gap(screen, 21);

        LinearLayout body = row();
        body.setGravity(Gravity.TOP);
        screen.addView(body, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout left = column();
        LinearLayout right = column();
        LinearLayout.LayoutParams leftParams = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0.43f);
        leftParams.rightMargin = dp(18);
        body.addView(left, leftParams);
        body.addView(right, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0.57f));

        LinearLayout state = panel();
        state.addView(text("СОСТОЯНИЕ", 16, MUTED, true));
        gap(state, 7);
        statusHeading = text("НЕ ПОДКЛЮЧЁН", 27, WHITE, true);
        statusHeading.setSingleLine(true);
        statusHeading.setEllipsize(TextUtils.TruncateAt.END);
        state.addView(statusHeading);
        gap(state, 5);
        statusDetail = text("Не настроен", 17, MUTED, false);
        statusDetail.setMaxLines(2);
        statusDetail.setEllipsize(TextUtils.TruncateAt.END);
        state.addView(statusDetail);
        gap(state, 15);
        accessibilityDetail = text("Пульт: требуется разрешение", 19, WARNING, true);
        accessibilityDetail.setMaxLines(2);
        state.addView(accessibilityDetail);
        gap(state, 6);
        tokenDetail = text("Токен не задан", 18, MUTED, false);
        state.addView(tokenDetail);
        left.addView(state);
        gap(left, 12);

        LinearLayout channel = panel();
        channel.addView(text("КАНАЛ УПРАВЛЕНИЯ", 16, MUTED, true));
        gap(channel, 8);
        TextView repo = text("vitrum-tv-bridge", 25, WHITE, true);
        repo.setSingleLine(true);
        repo.setEllipsize(TextUtils.TruncateAt.END);
        channel.addView(repo);
        gap(channel, 5);
        channel.addView(text("GitHub · lolokeksu09", 18, MUTED, false));
        left.addView(channel);
        gap(left, 12);

        LinearLayout device = panel();
        device.addView(text("ИДЕНТИФИКАТОР ТВ", 16, MUTED, true));
        gap(device, 7);
        TextView deviceId = text(AgentConfig.deviceId(this), 16, CYAN, false);
        deviceId.setTypeface(Typeface.MONOSPACE);
        deviceId.setSingleLine(true);
        deviceId.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        deviceId.setTextIsSelectable(true);
        device.addView(deviceId);
        left.addView(device);
        gap(left, 12);

        LinearLayout minorActions = row();
        Button stop = button("ОСТАНОВИТЬ", false);
        Button reset = button("СБРОСИТЬ", false);
        stop.setTextSize(18);
        reset.setTextSize(18);
        stop.setId(View.generateViewId());
        reset.setId(View.generateViewId());
        LinearLayout.LayoutParams stopParams = new LinearLayout.LayoutParams(0, dp(62), 1);
        stopParams.rightMargin = dp(10);
        minorActions.addView(stop, stopParams);
        minorActions.addView(reset, new LinearLayout.LayoutParams(0, dp(62), 1));
        left.addView(minorActions);

        right.addView(text("ПОДКЛЮЧЕНИЕ", 18, MUTED, true));
        gap(right, 10);
        publicToggle = button("", false);
        publicToggle.setId(View.generateViewId());
        publicToggle.setMinHeight(dp(83));
        publicToggle.setTextSize(20);
        publicToggle.setGravity(Gravity.CENTER_VERTICAL | Gravity.LEFT);
        publicToggle.setPadding(dp(22), dp(10), dp(20), dp(10));
        publicToggle.setOnClickListener(v -> {
            publicAllowed = !publicAllowed;
            updatePublicToggle();
            feedback(publicAllowed ? "Публичный режим разрешён. Введи токен."
                    : "Публичный режим отключён. Команды не будут приниматься.", false);
        });
        updatePublicToggle();
        right.addView(publicToggle, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(86)));
        gap(right, 16);

        right.addView(text("GITHUB TOKEN", 18, MUTED, true));
        gap(right, 8);
        tokenInput = new EditText(this);
        tokenInput.setId(View.generateViewId());
        tokenInput.setSingleLine(true);
        tokenInput.setTextSize(22);
        tokenInput.setTextColor(WHITE);
        tokenInput.setHintTextColor(MUTED);
        tokenInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokenInput.setImeOptions(EditorInfo.IME_ACTION_DONE);
        tokenInput.setSelectAllOnFocus(false);
        tokenInput.setBackground(stateBackground(false));
        tokenInput.setPadding(dp(19), dp(10), dp(19), dp(10));
        tokenInput.setHint(AgentConfig.hasToken(this)
                ? "Уже сохранён · оставь пустым" : "Вставь GitHub token");
        right.addView(tokenInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(71)));
        gap(right, 15);

        Button start = button("СОХРАНИТЬ И ВКЛЮЧИТЬ", true);
        start.setId(View.generateViewId());
        right.addView(start, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(72)));
        gap(right, 11);
        Button accessibility = button("РАЗРЕШИТЬ УПРАВЛЕНИЕ ТВ", false);
        accessibility.setId(View.generateViewId());
        right.addView(accessibility, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(68)));
        gap(right, 13);

        feedback = text("GitHub token с правами Issues · только для этого репозитория",
                18, MUTED, false);
        feedback.setMaxLines(2);
        feedback.setEllipsize(TextUtils.TruncateAt.END);
        right.addView(feedback);

        start.setOnClickListener(v -> {
            if (!publicAllowed) {
                feedback("Сначала разреши публичный режим.", true);
                publicToggle.requestFocus();
                return;
            }
            String suppliedToken = tokenInput.getText().toString().trim();
            try {
                if (!suppliedToken.isEmpty()) AgentConfig.putToken(this, suppliedToken);
                tokenInput.setText("");
                if (!AgentConfig.hasToken(this)) {
                    feedback("Введи GitHub token с правами Issues.", true);
                    tokenInput.requestFocus();
                    return;
                }
                AgentConfig.saveRepo(this, AgentPolicy.PUBLIC_CONTROL_REPO, true);
                AgentConfig.setEnabled(this, true);
                AgentConfig.setStatus(this, "Проверка публичного GitHub…");
                Intent service = new Intent(this, AgentService.class);
                if (Build.VERSION.SDK_INT >= 26) startForegroundService(service);
                else startService(service);
                feedback("Проверяем связь. Затем разреши управление ТВ.", false);
            } catch (Exception ignored) {
                feedback("Не получилось сохранить или запустить. Проверь токен.", true);
            }
        });
        accessibility.setOnClickListener(v -> {
            try {
                startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
            } catch (Exception ignored) {
                feedback("Настройки специальных возможностей недоступны.", true);
            }
        });
        stop.setOnClickListener(v -> {
            AgentConfig.setEnabled(this, false);
            stopService(new Intent(this, AgentService.class));
            AgentConfig.setStatus(this, "Остановлен владельцем");
            feedback("Агент остановлен. Токен сохранён.", false);
        });
        reset.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("Сбросить BOXY Agent?")
                .setMessage("Токен и настройки подключения будут удалены с ТВ. "
                        + "CleanYourTV и остальные приложения не затрагиваются.")
                .setNegativeButton("ОТМЕНА", (dialog, which) -> dialog.dismiss())
                .setPositiveButton("СБРОСИТЬ", (dialog, which) -> {
                    stopService(new Intent(this, AgentService.class));
                    AgentConfig.disconnect(this);
                    tokenInput.setText("");
                    publicAllowed = false;
                    updatePublicToggle();
                    feedback("Настройки подключения удалены.", false);
                })
                .show());

        // Explicit remote sequence; prevents TV D-pad from jumping to a footer action.
        publicToggle.setNextFocusDownId(tokenInput.getId());
        tokenInput.setNextFocusUpId(publicToggle.getId());
        tokenInput.setNextFocusDownId(start.getId());
        start.setNextFocusUpId(tokenInput.getId());
        start.setNextFocusDownId(accessibility.getId());
        accessibility.setNextFocusUpId(start.getId());
        stop.setNextFocusRightId(reset.getId());
        reset.setNextFocusLeftId(stop.getId());

        gap(screen, 18);
        TextView footer = text("Токен остаётся на ТВ  ·  Управление ограничено разрешёнными командами",
                16, MUTED, false);
        footer.setGravity(Gravity.CENTER);
        screen.addView(footer);

        updateStatus();
        publicToggle.requestFocus();
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
