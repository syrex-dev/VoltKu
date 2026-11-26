package com.voltku.energy;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import androidx.core.app.NotificationCompat;

/**
 * Helper native Android untuk kanal notifikasi high-priority (heads-up ala WhatsApp).
 */
public final class VoltKuNotificationHelper {
    public static final String CHANNEL_ALERTS = "voltku_alerts";
    public static final String CHANNEL_INFO = "voltku_info";

    private VoltKuNotificationHelper() {}

    public static void ensureChannels(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationManager nm = context.getSystemService(NotificationManager.class);
        if (nm == null) {
            return;
        }

        Uri defaultSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);

        NotificationChannel alertChannel = new NotificationChannel(
            CHANNEL_ALERTS,
            "Peringatan Listrik VoltKu",
            NotificationManager.IMPORTANCE_HIGH
        );
        alertChannel.setDescription("Notifikasi darurat beban berlebih, tegangan ekstrem, dan perangkat offline.");
        alertChannel.enableLights(true);
        alertChannel.setLightColor(Color.parseColor("#0284c7"));
        alertChannel.enableVibration(true);
        alertChannel.setVibrationPattern(new long[]{0, 260, 140, 260});
        alertChannel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        alertChannel.setSound(defaultSound, null);
        nm.createNotificationChannel(alertChannel);

        NotificationChannel infoChannel = new NotificationChannel(
            CHANNEL_INFO,
            "Info & Tagihan VoltKu",
            NotificationManager.IMPORTANCE_DEFAULT
        );
        infoChannel.setDescription("Info aktivasi paket, laporan harian, dan pemulihan perangkat.");
        infoChannel.enableVibration(true);
        infoChannel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        nm.createNotificationChannel(infoChannel);
    }

    public static void showNotification(
        Context context,
        int notificationId,
        String title,
        String body,
        String category,
        String severity
    ) {
        ensureChannels(context);
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) {
            return;
        }

        String channelId = ("alert".equals(category) || "critical".equals(severity) || "warning".equals(severity))
            ? CHANNEL_ALERTS
            : CHANNEL_INFO;

        Intent openIntent = new Intent(context, MainActivity.class);
        openIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);

        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent contentIntent = PendingIntent.getActivity(context, notificationId, openIntent, flags);

        int iconRes = context.getApplicationInfo().icon != 0
            ? context.getApplicationInfo().icon
            : android.R.drawable.ic_dialog_info;

        Uri soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);

        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, channelId)
            .setSmallIcon(iconRes)
            .setContentTitle(title != null && !title.isEmpty() ? title : "VoltKu")
            .setContentText(body != null ? body : "")
            .setStyle(new NotificationCompat.BigTextStyle().bigText(body != null ? body : ""))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .setSound(soundUri)
            .setAutoCancel(true)
            .setContentIntent(contentIntent);

        nm.notify(notificationId, builder.build());
    }
}

