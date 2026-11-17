#pragma once

#include <cstdint>
#include <cstdio>

namespace energy_core {

struct TelemetrySample {
    int64_t ts;
    float v;
    float i;
    float p;
    float e;
    float f;
    float pf;
    int16_t rssi;
    char fw[16];
};

/**
 * Format payload telemetri persis sesuai kontrak docs/05-DATA-CONTRACT.md:
 * {"ts":1731650000,"v":220.5,"i":1.234,"p":272.1,"e":12.345,"f":50.0,"pf":0.98,"rssi":-61,"fw":"1.0.0"}
 *
 * Menggunakan snprintf dengan presisi desimal tetap:
 * - v: 1 desimal (%.1f)
 * - i: 3 desimal (%.3f)
 * - p: 1 desimal (%.1f)
 * - e: 3 desimal (%.3f)
 * - f: 1 desimal (%.1f)
 * - pf: 2 desimal (%.2f)
 * - rssi: integer (%d)
 * - fw: string (%s)
 * - ts: integer epoch (%lld)
 */
inline int format_telemetry_payload(char* dest, size_t max_len, const TelemetrySample& sample) {
    if (!dest || max_len == 0) {
        return -1;
    }

    return std::snprintf(
        dest,
        max_len,
        "{\"ts\":%lld,\"v\":%.1f,\"i\":%.3f,\"p\":%.1f,\"e\":%.3f,\"f\":%.1f,\"pf\":%.2f,\"rssi\":%d,\"fw\":\"%s\"}",
        static_cast<long long>(sample.ts),
        sample.v,
        sample.i,
        sample.p,
        sample.e,
        sample.f,
        sample.pf,
        static_cast<int>(sample.rssi),
        sample.fw
    );
}

} // namespace energy_core

