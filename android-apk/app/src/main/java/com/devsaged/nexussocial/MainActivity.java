package com.devsaged.nexussocial;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;

/**
 * MainActivity: Hosts the Arabic RTL Dashboard served by the local Termux Python Engine
 * (`http://127.0.0.1:5050`), registers the Native Java `AndroidSessionBridge` for One-Tap
 * Account Linking across all 12 platforms, and starts `NetworkWatchdogService` so the phone
 * automatically catches up on comments/DMs/posts whenever internet or power returns.
 */
public class MainActivity extends AppCompatActivity {

    public static final String TERMUX_SERVER_URL = "http://127.0.0.1:5050";
    private WebView dashboardWebView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent serviceIntent = new Intent(this, NetworkWatchdogService.class);
        startService(serviceIntent);

        dashboardWebView = new WebView(this);
        setContentView(dashboardWebView);

        WebSettings settings = dashboardWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(dashboardWebView, true);

        dashboardWebView.addJavascriptInterface(new SessionBridge(this), "AndroidSessionBridge");

        dashboardWebView.setWebChromeClient(new WebChromeClient());
        dashboardWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    view.loadUrl("file:///android_asset/offline_fallback.html");
                }
            }
        });

        dashboardWebView.loadUrl(TERMUX_SERVER_URL);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (dashboardWebView != null && dashboardWebView.getUrl() != null
                && dashboardWebView.getUrl().startsWith(TERMUX_SERVER_URL)) {
            dashboardWebView.evaluateJavascript("if(window.refreshStatus) window.refreshStatus();", null);
        }
    }

    @Override
    public void onBackPressed() {
        if (dashboardWebView != null && dashboardWebView.canGoBack()) {
            dashboardWebView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
