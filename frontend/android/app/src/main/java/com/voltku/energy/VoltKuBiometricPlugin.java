package com.voltku.energy;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.biometric.BiometricManager;
import androidx.biometric.BiometricPrompt;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.FragmentActivity;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.concurrent.Executor;

/**
 * Bridge Capacitor native AndroidX BiometricPrompt untuk memeriksa kesiapan sensor
 * sidik jari / biometrik perangkat serta menjalankan verifikasi sistem native.
 */
@CapacitorPlugin(name = "VoltKuBiometric")
public class VoltKuBiometricPlugin extends Plugin {

    private static final int ALLOWED_AUTHENTICATORS =
        BiometricManager.Authenticators.BIOMETRIC_STRONG
            | BiometricManager.Authenticators.BIOMETRIC_WEAK;

    @PluginMethod
    public void isAvailable(PluginCall call) {
        JSObject ret = new JSObject();
        try {
            Context ctx = getContext();
            BiometricManager manager = BiometricManager.from(ctx);
            int code = manager.canAuthenticate(ALLOWED_AUTHENTICATORS);
            boolean available = (code == BiometricManager.BIOMETRIC_SUCCESS);

            String status = "unavailable";
            String reason = "Sensor biometrik tidak tersedia di perangkat ini.";
            if (code == BiometricManager.BIOMETRIC_SUCCESS) {
                status = "ready";
                reason = "Sensor sidik jari / biometrik siap digunakan.";
            } else if (code == BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED) {
                status = "none_enrolled";
                reason = "Belum ada sidik jari terdaftar di Pengaturan HP Anda.";
            } else if (
                code == BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE
                    || code == BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE
            ) {
                status = "no_hardware";
                reason = "Perangkat ini belum mendukung sensor sidik jari / biometrik.";
            }

            ret.put("available", available);
            ret.put("status", status);
            ret.put("reason", reason);
            ret.put("platform", "android");
        } catch (Throwable err) {
            ret.put("available", false);
            ret.put("status", "unavailable");
            ret.put("reason", "Pemeriksaan sensor biometrik tidak didukung pada perangkat ini.");
            ret.put("platform", "android");
        }
        call.resolve(ret);
    }

    @PluginMethod
    public void authenticate(PluginCall call) {
        FragmentActivity activity = getActivity();
        if (activity == null) {
            call.reject("Aktivitas Android tidak tersedia.");
            return;
        }

        BiometricManager manager = BiometricManager.from(activity);
        if (manager.canAuthenticate(ALLOWED_AUTHENTICATORS) != BiometricManager.BIOMETRIC_SUCCESS) {
            call.reject("Sensor sidik jari tidak siap atau belum terdaftar.", "NOT_AVAILABLE");
            return;
        }

        String title = call.getString("title", "Buka Kunci VoltKu");
        String subtitle = call.getString("subtitle", "Sentuh sensor sidik jari Anda untuk melanjutkan");
        String negativeText = call.getString("negativeText", "Gunakan PIN");

        activity.runOnUiThread(() -> {
            try {
                Executor executor = ContextCompat.getMainExecutor(activity);
                BiometricPrompt prompt = new BiometricPrompt(
                    activity,
                    executor,
                    new BiometricPrompt.AuthenticationCallback() {
                        @Override
                        public void onAuthenticationSucceeded(
                            @NonNull BiometricPrompt.AuthenticationResult result
                        ) {
                            JSObject ret = new JSObject();
                            ret.put("verified", true);
                            call.resolve(ret);
                        }

                        @Override
                        public void onAuthenticationError(int errorCode, @NonNull CharSequence errString) {
                            JSObject ret = new JSObject();
                            ret.put("verified", false);
                            ret.put(
                                "cancelled",
                                errorCode == BiometricPrompt.ERROR_NEGATIVE_BUTTON
                                    || errorCode == BiometricPrompt.ERROR_USER_CANCELED
                                    || errorCode == BiometricPrompt.ERROR_CANCELED
                            );
                            ret.put("error", errString.toString());
                            call.resolve(ret);
                        }

                        @Override
                        public void onAuthenticationFailed() {
                            // Biarkan pengguna mencoba menempelkan jari lagi hingga berhasil atau batal
                        }
                    }
                );

                BiometricPrompt.PromptInfo promptInfo = new BiometricPrompt.PromptInfo.Builder()
                    .setTitle(title != null ? title : "Buka Kunci VoltKu")
                    .setSubtitle(
                        subtitle != null ? subtitle : "Verifikasi sidik jari untuk membuka aplikasi"
                    )
                    .setNegativeButtonText(
                        negativeText != null ? negativeText : "Gunakan PIN"
                    )
                    .setAllowedAuthenticators(ALLOWED_AUTHENTICATORS)
                    .build();

                prompt.authenticate(promptInfo);
            } catch (Throwable err) {
                call.reject("Gagal menampilkan dialog sidik jari: " + err.getMessage());
            }
        });
    }
}

