package ro.sw3g.scrcpy;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.function.IntConsumer;

/**
 * Non-modal overlay rendered inside the local player's FrameLayout.
 * Video behind the panel stays visible; pressing a key never executes shell.
 */
final class TvRemotePanel extends LinearLayout {
    private final Context context;
    private final IntConsumer send;

    TvRemotePanel(Context context, IntConsumer send, Runnable dismiss) {
        super(context);
        this.context=context;
        this.send=send;
        setOrientation(VERTICAL);
        setPadding(dp(14),dp(12),dp(14),dp(14));
        setClickable(true);
        setFocusable(true);
        GradientDrawable background=rounded(0xee13191f,20);
        background.setStroke(dp(1),0xff343f4c);
        setBackground(background);
        setElevation(dp(12));

        LinearLayout heading=row();
        heading.setGravity(Gravity.CENTER_VERTICAL);
        TextView name=new TextView(context);
        name.setText(I18n.t(R.string.tv_remote_title));
        name.setTextColor(Color.WHITE);
        name.setTextSize(17);
        name.setTypeface(null,1);
        heading.addView(name,new LayoutParams(0,dp(48),1));
        name.setGravity(Gravity.CENTER_VERTICAL);
        Button close=button("×",I18n.t(R.string.tv_remote_close),dismiss);
        close.setTextSize(23);
        heading.addView(close,new LayoutParams(dp(48),dp(46)));
        addView(heading);
        TextView description=new TextView(context);
        description.setText(I18n.t(R.string.tv_remote_hint));
        description.setTextSize(12);
        description.setTextColor(0xffa5b8c9);
        description.setPadding(dp(5),0,0,dp(9));
        addView(description);

        directionalRow(new int[]{0,TvRemoteKeys.UP,0},
            new String[]{"","↑",""},
            new int[]{0,R.string.tv_remote_up,0});
        directionalRow(new int[]{TvRemoteKeys.LEFT,TvRemoteKeys.OK,TvRemoteKeys.RIGHT},
            new String[]{"←","OK","→"},
            new int[]{R.string.tv_remote_left,R.string.tv_remote_ok,R.string.tv_remote_right});
        directionalRow(new int[]{0,TvRemoteKeys.DOWN,0},
            new String[]{"","↓",""},
            new int[]{0,R.string.tv_remote_down,0});

        LinearLayout navigation=row();
        navButton(navigation,I18n.t(R.string.tv_remote_back),R.string.tv_remote_back,TvRemoteKeys.BACK);
        navButton(navigation,I18n.t(R.string.tv_remote_home),R.string.tv_remote_home,TvRemoteKeys.HOME);
        navButton(navigation,I18n.t(R.string.tv_remote_mute),R.string.tv_remote_mute,TvRemoteKeys.MUTE);
        addView(navigation);

        LinearLayout volume=row();
        navButton(volume,"−",R.string.tv_remote_volume_down,TvRemoteKeys.VOLUME_DOWN);
        navButton(volume,"+",R.string.tv_remote_volume_up,TvRemoteKeys.VOLUME_UP);
        addView(volume);
    }

    private int dp(float value) {
        return (int)(value*getResources().getDisplayMetrics().density+.5f);
    }
    private GradientDrawable rounded(int color,int radius){
        GradientDrawable drawable=new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radius));
        return drawable;
    }
    private LinearLayout row(){
        LinearLayout row=new LinearLayout(context);
        row.setOrientation(HORIZONTAL);
        return row;
    }
    private Button button(String caption,String description,Runnable action){
        Button button=new Button(context);
        button.setText(caption);
        button.setContentDescription(description);
        button.setAllCaps(false);
        button.setTextSize(15);
        button.setTextColor(0xffe9f2fb);
        button.setMinHeight(dp(48));
        button.setPadding(dp(3),dp(3),dp(3),dp(3));
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x446a9ecd),
            rounded(0xff273643,14),null));
        button.setOnClickListener(v->action.run());
        return button;
    }
    private void send(int keyCode){
        if(TvRemoteKeys.supported(keyCode))send.accept(keyCode);
    }
    private void directionalRow(int[] codes,String[] labels,int[] descriptions){
        LinearLayout row=row();
        for(int index=0;index<3;index++){
            LayoutParams lp=new LayoutParams(0,dp(52),1);
            lp.setMargins(dp(4),dp(3),dp(4),dp(3));
            if(codes[index]==0){
                View blank=new View(context);
                row.addView(blank,lp);
            }else{
                final int code=codes[index];
                Button control=button(labels[index],I18n.t(descriptions[index]),()->send(code));
                if(code==TvRemoteKeys.OK){
                    control.setBackground(new RippleDrawable(ColorStateList.valueOf(0x448db2d8),
                        rounded(0xff2d5875,14),null));
                }
                row.addView(control,lp);
            }
        }
        addView(row);
    }
    private void navButton(LinearLayout parent,String label,int description,int keyCode){
        Button b=button(label,I18n.t(description),()->send(keyCode));
        LayoutParams lp=new LayoutParams(0,dp(49),1);
        lp.setMargins(dp(4),dp(5),dp(4),0);
        parent.addView(b,lp);
    }
}
