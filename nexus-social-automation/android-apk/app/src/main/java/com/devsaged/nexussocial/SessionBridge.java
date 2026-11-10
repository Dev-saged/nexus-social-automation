package com.devsaged.nexussocial;

import android.content.Context;
import android.content.Intent;
import android.webkit.JavascriptInterface;
import org.json.JSONObject;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class SessionBridge {

    private final Context context;

    public SessionBridge(Context context) {
        this.context = context;
    }

    @JavascriptInterface
    public void openPlatformLogin(String platform) {
        Intent intent = new Intent(context, AccountLinkerActivity.class);
        intent.putExtra("platform", platform);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    @JavascriptInterface
    public void retryLocalServer() {
        Intent intent = new Intent(context, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        context.startActivity(intent);
    }

    public static void sendCapturedSessionToTermux(
            final String platform,
            final String username,
            final String cookieString,
            final String userAgent
    ) {
        new Thread(() -> {
            try {
                URL url = new URL(MainActivity.TERMUX_SERVER_URL + "/api/accounts/capture-session");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(10000);
                conn.setDoOutput(true);

                JSONObject payload = new JSONObject();
                payload.put("platform", platform == null ? "" : platform);
                payload.put("username", username == null ? "" : username);
                payload.put("cookie_string", cookieString == null ? "" : cookieString);
                payload.put("user_agent", userAgent == null ? "" : userAgent);
                String jsonPayload = payload.toString();

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(jsonPayload.getBytes(StandardCharsets.UTF_8));
                }
                conn.getResponseCode();
                conn.disconnect();
            } catch (Exception ignored) {
            }
        }).start();
    }
}
