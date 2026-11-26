package com.voltku.energy;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.concurrent.TimeUnit;

/**
 * Bridge Capacitor untuk menyimpan sesi API & menjadwalkan WorkManager sinkronisasi notifikasi.
 */
@CapacitorPlugin(name = "VoltKuPushBridge")
public class VoltKuPushBridgePlugin extends Plugin {
    private static final String WORK_NAME = "voltku_alert_sync_periodic";

    @PluginMethod
    public void syncSession(PluginCall call) {
        Context ctx = getContext();
        String apiBaseUrl = call.getString("apiBaseUrl", "");
        String token = call.getString("token", "");
        Long lastSeenId = call.getLong("lastSeenId");

        VoltKuNotificationHelper.ensureChannels(ctx);

        SharedPreferences prefs = ctx.getSharedPreferences(AlertSyncWorker.PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();

        if (token == null || token.trim().isEmpty()) {
            editor.remove(AlertSyncWorker.KEY_TOKEN);
            editor.apply();
            WorkManager.getInstance(ctx).cancelUniqueWork(WORK_NAME);
            JSObject ret = new JSObject();
            ret.put("scheduled", false);
            call.resolve(ret);
            return;
        }

        editor.putString(AlertSyncWorker.KEY_API_BASE, apiBaseUrl != null ? apiBaseUrl.trim() : "");
        editor.putString(AlertSyncWorker.KEY_TOKEN, token.trim());
        if (lastSeenId != null && lastSeenId > 0) {
            long prev = prefs.getLong(AlertSyncWorker.KEY_LAST_SEEN_ID, 0L);
            if (lastSeenId > prev) {
                editor.putLong(AlertSyncWorker.KEY_LAST_SEEN_ID, lastSeenId);
            }
        }
        editor.apply();

        Constraints constraints = new Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build();

        PeriodicWorkRequest workRequest = new PeriodicWorkRequest.Builder(
            AlertSyncWorker.class,
            15,
            TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .build();

        WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
            WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            workRequest
        );

        JSObject ret = new JSObject();
        ret.put("scheduled", true);
        call.resolve(ret);
    }

    @PluginMethod
    public void clearSession(PluginCall call) {
        Context ctx = getContext();
        SharedPreferences prefs = ctx.getSharedPreferences(AlertSyncWorker.PREFS_NAME, Context.MODE_PRIVATE);
        prefs.edit().remove(AlertSyncWorker.KEY_TOKEN).apply();
        WorkManager.getInstance(ctx).cancelUniqueWork(WORK_NAME);
        JSObject ret = new JSObject();
        ret.put("cleared", true);
        call.resolve(ret);
    }
}
