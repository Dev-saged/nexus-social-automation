package com.devsaged.nexussocial;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.IBinder;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * NetworkWatchdogService: Listens in real time for internet restoration on the Android phone.
 * The instant Wi-Fi or Mobile Data reconnects after an outage, it pings
 * `POST http://127.0.0.1:5050/api/system/wakeup` so the Termux engine immediately catches up
 * on missed comments, DMs, and scheduled posts!
 */
public class NetworkWatchdogService extends Service {

    private ConnectivityManager connectivityManager;
    private ConnectivityManager.NetworkCallback networkCallback;

    @Override
    public void onCreate() {
        super.onCreate();
        connectivityManager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (connectivityManager != null) {
            NetworkRequest request = new NetworkRequest.Builder()
                    .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    .build();
            networkCallback = new ConnectivityManager.NetworkCallback() {
                @Override
                public void onAvailable(Network network) {
                    notifyTermuxWakeup("android_network_restored");
                }
            };
            try {
                connectivityManager.registerNetworkCallback(request, networkCallback);
            } catch (Exception ignored) {
            }
        }
    }

    public static void notifyTermuxWakeup(final String reason) {
        new Thread(() -> {
            try {
                URL url = new URL(MainActivity.TERMUX_SERVER_URL + "/api/system/wakeup");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setConnectTimeout(4000);
                conn.setReadTimeout(15000);
                conn.setDoOutput(true);
                String body = "{\\"source\\":\\"" + reason + "\\"}";
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(body.getBytes(StandardCharsets.UTF_8));
                }
                conn.getResponseCode();
                conn.disconnect();
            } catch (Exception ignored) {
            }
        }).start();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        notifyTermuxWakeup("watchdog_service_start");
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (connectivityManager != null && networkCallback != null) {
            try {
                connectivityManager.unregisterNetworkCallback(networkCallback);
            } catch (Exception ignored) {
            }
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
