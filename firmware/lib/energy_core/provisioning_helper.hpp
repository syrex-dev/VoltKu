#pragma once

#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace energy_core {

/**
 * Memeriksa apakah nilai konfigurasi masih kosong atau berupa placeholder template.
 */
inline bool is_placeholder_value(const char* val) {
    if (!val || val[0] == '\0') {
        return true;
    }
    return (std::strcmp(val, "NAMA_WIFI_ANDA") == 0 ||
            std::strcmp(val, "PASSWORD_WIFI_ANDA") == 0 ||
            std::strcmp(val, "PASSWORD_MQTT_ANDA") == 0 ||
            std::strcmp(val, "auto") == 0 ||
            std::strcmp(val, "AUTO") == 0);
}

/**
 * Membentuk ID perangkat unik deterministik dari 48-bit MAC ESP32: "ML-XXXXXX"
 * menggunakan 3 byte terakhir MAC sehingga unik per unit produksi.
 */
inline int format_device_id_from_mac(uint64_t efuse_mac, char* dest, size_t max_len) {
    if (!dest || max_len < 10) {
        return -1;
    }
    uint8_t b3 = static_cast<uint8_t>((efuse_mac >> 24) & 0xFF);
    uint8_t b4 = static_cast<uint8_t>((efuse_mac >> 32) & 0xFF);
    uint8_t b5 = static_cast<uint8_t>((efuse_mac >> 40) & 0xFF);
    return std::snprintf(dest, max_len, "ML-%02X%02X%02X", b3, b4, b5);
}

/**
 * Membentuk nama hotspot SoftAP dari DEVICE_ID: "VoltKu-<suffix>"
 */
inline int format_ap_ssid_from_device_id(const char* device_id, char* dest, size_t max_len) {
    if (!dest || max_len < 16) {
        return -1;
    }
    if (!device_id || device_id[0] == '\0') {
        return std::snprintf(dest, max_len, "VoltKu-Setup");
    }
    size_t len = std::strlen(device_id);
    const char* suffix = (len > 6) ? (device_id + len - 6) : device_id;
    // Skip leading '-' if suffix starts right after "ML-"
    if (suffix[0] == '-' && suffix[1] != '\0') {
        ++suffix;
    }
    return std::snprintf(dest, max_len, "VoltKu-%s", suffix);
}

/**
 * Memvalidasi nama DEVICE_ID aman untuk topik MQTT & URL (alfanumerik, '-', '_').
 */
inline bool is_valid_device_id(const char* device_id) {
    if (!device_id) {
        return false;
    }
    size_t len = std::strlen(device_id);
    if (len < 2 || len > 64) {
        return false;
    }
    for (size_t i = 0; i < len; ++i) {
        unsigned char c = static_cast<unsigned char>(device_id[i]);
        if (!std::isalnum(c) && c != '-' && c != '_') {
            return false;
        }
    }
    return true;
}

} // namespace energy_core

