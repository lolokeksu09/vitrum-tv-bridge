package dev.lolokeksu.boxyagent;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.SecureRandom;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class AgentConfig {
    private static final String PREFS = "boxy_agent_local";
    private static final String KEY_ALIAS = "boxy_agent_github_token";
    private static final SecureRandom RAND = new SecureRandom();

    private AgentConfig() {}
    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static synchronized String deviceId(Context context) {
        String saved = prefs(context).getString("deviceId", "");
        if (saved != null && saved.matches("[0-9a-f]{32}")) return saved;
        byte[] b = new byte[16]; RAND.nextBytes(b);
        StringBuilder hex = new StringBuilder(32);
        for (byte v : b) hex.append(String.format(java.util.Locale.ROOT, "%02x", v & 255));
        String id = hex.toString();
        prefs(context).edit().putString("deviceId", id).commit();
        return id;
    }

    private static SecretKey secretKey() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        KeyStore.Entry found = ks.getEntry(KEY_ALIAS, null);
        if (found instanceof KeyStore.SecretKeyEntry)
            return ((KeyStore.SecretKeyEntry) found).getSecretKey();
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
        return generator.generateKey();
    }

    public static synchronized void putToken(Context context, String token) throws Exception {
        if (token == null || token.length() < 8 || token.length() > 1024
                || token.contains("\n") || token.contains("\r"))
            throw new IllegalArgumentException("Invalid token");
        Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.ENCRYPT_MODE, secretKey());
        byte[] iv = c.getIV();
        byte[] cipher = c.doFinal(token.getBytes(StandardCharsets.UTF_8));
        String stored = Base64.encodeToString(iv, Base64.NO_WRAP) + ":"
                + Base64.encodeToString(cipher, Base64.NO_WRAP);
        if (!prefs(context).edit().putString("secret", stored).commit())
            throw new IllegalStateException("Could not save encrypted token");
    }

    public static synchronized String token(Context context) {
        try {
            String stored = prefs(context).getString("secret", "");
            if (stored == null || stored.isEmpty()) return "";
            String[] parts = stored.split(":", -1);
            if (parts.length != 2) return "";
            byte[] iv = Base64.decode(parts[0], Base64.DEFAULT);
            if (iv.length != 12) return "";
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.DECRYPT_MODE, secretKey(), new GCMParameterSpec(128, iv));
            return new String(c.doFinal(Base64.decode(parts[1], Base64.DEFAULT)),
                    StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            // Never return ciphertext or log key failures.
            return "";
        }
    }

    public static boolean hasToken(Context context) { return !token(context).isEmpty(); }
    public static String repo(Context context) { return prefs(context).getString("repo", ""); }
    public static boolean enabled(Context context) { return prefs(context).getBoolean("enabled", false); }
    public static int lastIssue(Context context) { return prefs(context).getInt("lastIssue", 0); }
    public static String status(Context context) { return prefs(context).getString("status", "Не настроен"); }

    public static void setStatus(Context context, String status) {
        prefs(context).edit().putString("status", status).apply();
    }
    public static void saveRepo(Context context, String repo) {
        if (!AgentPolicy.allowedRepo(repo)) throw new IllegalArgumentException("Invalid private repo");
        SharedPreferences.Editor editor = prefs(context).edit().putString("repo", repo);
        if (!repo.equals(prefs(context).getString("repo", ""))) editor.putInt("lastIssue", 0);
        editor.apply();
    }
    public static void setEnabled(Context context, boolean value) {
        prefs(context).edit().putBoolean("enabled", value).commit();
    }
    /** At-most-once execution: persist the issued number BEFORE performing the operation. */
    public static boolean markIssue(Context context, int number) {
        if (number <= lastIssue(context)) return false;
        return prefs(context).edit().putInt("lastIssue", number).commit();
    }
    public static void disconnect(Context context) {
        prefs(context).edit().putBoolean("enabled", false).remove("secret")
                .remove("repo").putInt("lastIssue", 0).commit();
    }
}
