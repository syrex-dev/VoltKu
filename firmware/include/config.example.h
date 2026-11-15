#ifndef CONFIG_H
#define CONFIG_H

// Template Kredensial Firmware ESP32
// Salin file ini menjadi config.h dan isi dengan konfigurasi Anda.
// PERINGATAN: Jangan commit config.h ke git!

#define WIFI_SSID "NAMA_WIFI"
#define WIFI_PASSWORD "PASSWORD_WIFI"

#define MQTT_SERVER "192.168.1.100"
#define MQTT_PORT 1883
#define MQTT_USER "esp32_device_1"
#define MQTT_PASSWORD "password_mqtt_device"
#define DEVICE_ID "esp32_device_1"

#endif // CONFIG_H

