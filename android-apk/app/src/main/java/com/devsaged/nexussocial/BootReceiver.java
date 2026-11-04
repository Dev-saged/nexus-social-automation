package com.devsaged.nexussocial;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * BootReceiver: Automatically restarts `NetworkWatchdogService` and triggers a Termux Catch-Up
 * cycle whenever the phone boots up after a battery/power outage.
 */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Intent serviceIntent = new Intent(context, NetworkWatchdogService.class);
        context.startService(serviceIntent);
        NetworkWatchdogService.notifyTermuxWakeup("phone_boot_completed");
    }
}
