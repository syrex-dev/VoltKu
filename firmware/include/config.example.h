#pragma once

// Salin file ini menjadi include/config.h dan sesuaikan kredensial pabrik / cloud.
// File config.h asli MASUK KE .gitignore dan JANGAN PERNAH di-commit.
//
// Untuk produk jual lepas:
// - Pembeli mengatur Wi-Fi rumah melalui Captive Portal (MonitorListrik-XXXXXX),
//   kredensial disimpan permanen ke NVS Flash ESP32.
// - Biarkan WIFI_SSID sebagai "NAMA_WIFI_ANDA" jika ingin unit langsung masuk
//   mode pairing saat pertama kali dinyalakan.
// - Setel DEVICE_ID ke "auto" agar setiap unit otomatis mendapat ID unik (ML-XXXXXX).

#define WIFI_SSID "NAMA_WIFI_ANDA"
#define WIFI_PASS "PASSWORD_WIFI_ANDA"

#define MQTT_HOST "192.168.1.100"
#define MQTT_PORT 1883
#define MQTT_USER "energy_backend"
#define MQTT_PASS "PASSWORD_MQTT_ANDA"

#define DEVICE_ID "auto"
#define NTP_SERVER "pool.ntp.org"
#define PUBLISH_INTERVAL_S 10
#define FIRMWARE_VERSION "1.1.0"

// Pin tombol pairing (GPIO0 = tombol BOOT di DevKit) dan LED status (GPIO2)
#define PAIRING_BUTTON_PIN 0
#define STATUS_LED_PIN 2
