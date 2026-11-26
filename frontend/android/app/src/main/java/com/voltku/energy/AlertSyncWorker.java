package com.voltku.energy;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Worker background Android (WorkManager) untuk mengambil notifikasi baru VoltKu
 * secara berkala ketika aplikasi tertutup / minimize (fallback tanpa Firebase FCM).
 */
public class AlertSyncWorker extends Worker {
    public static final String PREFS_NAME = "voltku_native_push";
    public static final String KEY_API_BASE = "api_base_url";
    public static final String KEY_TOKEN = "auth_token";
    public static final String KEY_LAST_SEEN_ID = "last_seen_id";

    public AlertSyncWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context ctx = getApplicationContext();
        SharedPreferences prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String apiBase = prefs.getString(KEY_API_BASE, "");
        String token = prefs.getString(KEY_TOKEN, "");
        long lastSeenId = prefs.getLong(KEY_LAST_SEEN_ID, 0L);

        if (apiBase == null || apiBase.trim().isEmpty() || token == null || token.trim().isEmpty()) {
            return Result.success();
        }

        String baseClean = apiBase.trim().replaceAll("/+$", "");
        String endpoint = baseClean + "/api/users/notifications?since_id=" + lastSeenId + "&unread_only=true&limit=10";

        HttpURLConnection conn = null;
        try {
            URL url = new URL(endpoint);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(8000);
            conn.setRequestProperty("Authorization", "Bearer " + token.trim());
            conn.setRequestProperty("Accept", "application/json");

            int code = conn.getResponseCode();
            if (code == 401 || code == 403) {
                prefs.edit().remove(KEY_TOKEN).apply();
                return Result.success();
            }
            if (code < 200 || code >= 300) {
                return Result.retry();
            }

            StringBuilder sb = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8)
            )) {
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
            }

            JSONObject json = new JSONObject(sb.toString());
            JSONArray items = json.optJSONArray("items");
            long latestId = json.optLong("latest_id", lastSeenId);

            if (items != null && items.length() > 0) {
                long maxShownId = lastSeenId;
                for (int i = 0; i < items.length(); i++) {
                    JSONObject item = items.optJSONObject(i);
                    if (item == null) continue;
                    long nid = item.optLong("id", 0L);
                    String title = item.optString("title", "VoltKu");
                    String body = item.optString("body", "");
                    String category = item.optString("category", "alert");
                    String severity = item.optString("severity", "warning");

                    if (nid > lastSeenId) {
                        VoltKuNotificationHelper.showNotification(
                            ctx,
                            (int) (100000 + (nid % 100000)),
                            title,
                            body,
                            category,
                            severity
                        );
                        if (nid > maxShownId) {
                            maxShownId = nid;
                        }
                    }
                }
                if (maxShownId > lastSeenId) {
                    prefs.edit().putLong(KEY_LAST_SEEN_ID, maxShownId).apply();
                }
            } else if (latestId > lastSeenId) {
                prefs.edit().putLong(KEY_LAST_SEEN_ID, latestId).apply();
            }

            return Result.success();
        } catch (Exception ignored) {
            return Result.retry();
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }
}

