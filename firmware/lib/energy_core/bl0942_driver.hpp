#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include "calibration.hpp"

namespace energy_core {

/**
 * Konfigurasi perangkat keras front-end analog BL0942 pada PCB VoltKu v3.0.
 */
struct BL0942HardwareScale {
    float v_ref = 1.218f;
    float r_top_ohm = 1950000.0f;  // 5 x 390kOhm 1%
    float r_bot_ohm = 510.0f;      // 510 Ohm 1%
    float r_burden_ohm = 0.5f;     // 2 x 1.0 Ohm 1% paralel
    float ct_ratio = 2000.0f;      // 1000.0 untuk CT 30A/50A, 2000.0 untuk CT 100A
};

struct BL0942Reading {
    bool valid = false;
    bool reverse_power = false;
    float v = 0.0f;
    float i = 0.0f;
    float p = 0.0f;
    float e_kwh = 0.0f;
    float f = 50.0f;
    float pf = 1.0f;
};

constexpr size_t BL0942_FULL_PACKET_LEN = 23;
constexpr uint8_t BL0942_READ_CMD_BYTE = 0x58;
constexpr uint8_t BL0942_READ_ALL_ADDR = 0xAA;
constexpr uint8_t BL0942_FRAME_HEAD = 0x55;

inline uint8_t bl0942_checksum(const uint8_t* packet_23) {
    uint32_t sum = BL0942_READ_CMD_BYTE;
    for (size_t i = 0; i < BL0942_FULL_PACKET_LEN - 1; ++i) {
        sum += packet_23[i];
    }
    return static_cast<uint8_t>((~(sum & 0xFFU)) & 0xFFU);
}

inline uint32_t read_u24_le(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) |
           (static_cast<uint32_t>(p[1]) << 8U) |
           (static_cast<uint32_t>(p[2]) << 16U);
}

inline int32_t read_s24_le(const uint8_t* p) {
    uint32_t u = read_u24_le(p);
    if (u & 0x00800000UL) {
        u |= 0xFF000000UL;
    }
    return static_cast<int32_t>(u);
}

/**
 * Mengurai paket penuh 23-byte BL0942 UART (hasil perintah 0x58 0xAA).
 * Format paket:
 * [0]=0x55 HEAD
 * [1..3]=I_RMS (24-bit LE)
 * [4..6]=V_RMS (24-bit LE)
 * [7..9]=I_FAST_RMS
 * [10..12]=WATT (24-bit signed LE)
 * [13..15]=CF_CNT (24-bit pulse count)
 * [16..18]=FREQ (16-bit period + byte 18)
 * [19..21]=STATUS / reserved
 * [22]=CHECKSUM
 */
inline BL0942Reading parse_bl0942_full_packet(
    const uint8_t* pkt,
    size_t len,
    const BL0942HardwareScale& hw = BL0942HardwareScale{}
) {
    BL0942Reading out{};
    if (!pkt || len != BL0942_FULL_PACKET_LEN) {
        return out;
    }
    if (pkt[0] != BL0942_FRAME_HEAD) {
        return out;
    }
    if (bl0942_checksum(pkt) != pkt[22]) {
        return out;
    }

    const uint32_t i_raw = read_u24_le(&pkt[1]);
    const uint32_t v_raw = read_u24_le(&pkt[4]);
    const int32_t w_raw = read_s24_le(&pkt[10]);
    const uint32_t cf_raw = read_u24_le(&pkt[13]);
    const uint16_t freq_raw = static_cast<uint16_t>(pkt[16]) |
                              (static_cast<uint16_t>(pkt[17]) << 8U);

    const double div_ratio =
        static_cast<double>(hw.r_top_ohm + hw.r_bot_ohm) / static_cast<double>(hw.r_bot_ohm);
    const double i_scale = static_cast<double>(hw.ct_ratio) / static_cast<double>(hw.r_burden_ohm);
    const double vref = static_cast<double>(hw.v_ref);

    // V_pin_mV = V_RMS * V_ref / 73989 -> V_line = V_pin_mV * 1e-3 * div_ratio
    const double v_pin_mv = (static_cast<double>(v_raw) * vref) / 73989.0;
    const double v_line = v_pin_mv * 1e-3 * div_ratio;

    // I_pin_mV = I_RMS * V_ref / 305978 -> I_line = I_pin_mV * 1e-3 * (ct_ratio / r_burden)
    const double i_pin_mv = (static_cast<double>(i_raw) * vref) / 305978.0;
    const double i_line = i_pin_mv * 1e-3 * i_scale;

    // P_pin_mV2 = WATT * V_ref^2 / 3537 -> P_line = P_pin_mV2 * 1e-6 * div_ratio * i_scale
    const double p_pin_mv2 = (static_cast<double>(w_raw) * vref * vref) / 3537.0;
    const double p_signed = p_pin_mv2 * 1e-6 * div_ratio * i_scale;

    // Energy per CF pulse in kWh: (1638.4 * 256 * V_ref^2) / (3600000 * 3537) * 1e-6 * div * i_scale
    const double e_per_pulse_kwh =
        ((1638.4 * 256.0 * vref * vref) / (3600000.0 * 3537.0)) * 1e-6 * div_ratio * i_scale;
    const double e_kwh = static_cast<double>(cf_raw) * e_per_pulse_kwh;

    const double freq_hz = (freq_raw > 0) ? (1000000.0 / static_cast<double>(freq_raw)) : 50.0;

    out.valid = true;
    out.reverse_power = (p_signed < -0.5);
    out.v = static_cast<float>(v_line);
    out.i = static_cast<float>(i_line);
    out.p = static_cast<float>(std::fabs(p_signed));
    out.e_kwh = static_cast<float>(e_kwh);
    out.f = static_cast<float>((freq_hz >= 40.0 && freq_hz <= 70.0) ? freq_hz : 50.0);

    const float va = out.v * out.i;
    out.pf = (va > 0.5f) ? clamp_float(out.p / va, 0.0f, 1.0f, 1.0f) : 1.0f;
    return out;
}

} // namespace energy_core

