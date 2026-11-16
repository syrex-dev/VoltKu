#pragma once

// Salin file ini menjadi include/config.h dan sesuaikan kredensial.
// File config.h asli MASUK KE .gitignore dan JANGAN PERNAH di-commit.

#define WIFI_SSID "NAMA_WIFI_ANDA"
#define WIFI_PASS "PASSWORD_WIFI_ANDA"

#define MQTT_HOST "192.168.1.100"
#define MQTT_PORT 1883
#define MQTT_USER "device-01"
#define MQTT_PASS "PASSWORD_MQTT_ANDA"

#define DEVICE_ID "device-01"
#define NTP_SERVER "pool.ntp.org"
#define PUBLISH_INTERVAL_S 10
#define FIRMWARE_VERSION "1.0.0"
