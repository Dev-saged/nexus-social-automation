package com.devsaged.nexussocial;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.Toast;
import java.util.HashMap;
import java.util.Map;

/**
 * AccountLinkerActivity: Pure Android SDK Activity for One-Tap WebView Session & Cookie capture
 * across all 12 supported social media platforms.
 */
public class AccountLinkerActivity extends Activity {

    private WebView loginWebView;
    private String platform;

    private static final Map<String, String> LOGIN_URLS = new HashMap<>();
    static {
        LOGIN_URLS.put("instagram", "https://www.instagram.com/accounts/login/");
        LOGIN_URLS.put("facebook", "https://m.facebook.com/login/");
        LOGIN_URLS.put("threads", "https://www.threads.net/login");
        LOGIN_URLS.put("x_twitter", "https://x.com/i/flow/login");
        LOGIN_URLS.put("linkedin", "https://www.linkedin.com/login");
        LOGIN_URLS.put("tiktok", "https://www.tiktok.com/login");
        LOGIN_URLS.put("youtube", "https://studio.youtube.com/");
        LOGIN_URLS.put("telegram", "https://web.telegram.org/k/");
        LOGIN_URLS.put("bluesky", "https://bsky.app/");
        LOGIN_URLS.put("reddit", "https://www.reddit.com/login/");
        LOGIN_URLS.put("pinterest", "https://www.pinterest.com/login/");
        LOGIN_URLS.put("mastodon", "https://mastodon.social/auth/sign_in");
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        platform = getIntent().getStringExtra("platform");
        if (platform == null) platform = "instagram";
        final String targetUrl = LOGIN_URLS.getOrDefault(platform, "https://www.instagram.com/");

        FrameLayout root = new FrameLayout(this);
        loginWebView = new WebView(this);

        WebSettings settings = loginWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(loginWebView, true);

        loginWebView.setWebViewClient(new WebViewClient());
        loginWebView.loadUrl(targetUrl);

        Button captureBtn = new Button(this);
        captureBtn.setText("✅ حفظ وربط حساب " + platform.toUpperCase() + " تلقائياً");
        captureBtn.setBackgroundColor(Color.parseColor("#10B981"));
        captureBtn.setTextColor(Color.WHITE);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM
        );
        params.setMargins(24, 24, 24, 32);

        captureBtn.setOnClickListener(v -> {
            String currentUrl = loginWebView.getUrl() != null ? loginWebView.getUrl() : targetUrl;
            String cookies = CookieManager.getInstance().getCookie(currentUrl);
            String ua = loginWebView.getSettings().getUserAgentString();
            SessionBridge.sendCapturedSessionToTermux(platform, platform + "_linked", cookies, ua);
            Toast.makeText(this, "تم التقاط جلسة " + platform + " وتشفيرها بنجاح!", Toast.LENGTH_LONG).show();
            finish();
        });

        root.addView(loginWebView);
        root.addView(captureBtn, params);
        setContentView(root);
    }
}
