#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace energy_core {

struct CalibrationConfig {
    float v_gain = 1.0f;
    float v_offset = 0.0f;
    float i_gain = 1.0f;
    float i_offset = 0.0f;
    float p_gain = 1.0f;
    float p_low_corr_w = 0.0f;
    float noise_floor_a = 0.012f;
    uint16_t ct_rating_a = 100;  // 30, 50, atau 100 A
};

struct CalibratedReading {
    float v;
    float i;
    float p;
    float f;
    float pf;
    bool below_noise_floor;
};

inline float clamp_float(float val, float lo, float hi, float fallback) {
    if (!std::isfinite(val)) {
        return fallback;
    }
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
}

inline void sanitize_calibration(CalibrationConfig& cfg) {
    cfg.v_gain = clamp_float(cfg.v_gain, 0.5f, 1.5f, 1.0f);
    cfg.v_offset = clamp_float(cfg.v_offset, -25.0f, 25.0f, 0.0f);
    cfg.i_gain = clamp_float(cfg.i_gain, 0.2f, 2.5f, 1.0f);
    cfg.i_offset = clamp_float(cfg.i_offset, -0.5f, 0.5f, 0.0f);
    cfg.p_gain = clamp_float(cfg.p_gain, 0.2f, 2.5f, 1.0f);
    cfg.p_low_corr_w = clamp_float(cfg.p_low_corr_w, -15.0f, 15.0f, 0.0f);
    cfg.noise_floor_a = clamp_float(cfg.noise_floor_a, 0.0f, 0.2f, 0.012f);
    if (cfg.ct_rating_a != 30 && cfg.ct_rating_a != 50 && cfg.ct_rating_a != 100) {
        cfg.ct_rating_a = 100;
    }
}

/**
 * Mengembalikan rasio lilitan CT sekunder (default 1000:1 untuk 30A/50A, 2000:1 untuk 100A).
 */
inline float ct_turns_ratio_for_rating(uint16_t ct_rating_a) {
    if (ct_rating_a == 30 || ct_rating_a == 50) {
        return 1000.0f;
    }
    return 2000.0f;
}

/**
 * Menerapkan kalibrasi multi-titik (gain, offset, koreksi beban rendah, dan noise floor)
 * pada hasil pembacaan mentah sensor agar beban kecil lebih presisi.
 */
inline CalibratedReading apply_calibration(
    float raw_v,
    float raw_i,
    float raw_p,
    float raw_f,
    float raw_pf,
    const CalibrationConfig& raw_cfg
) {
    CalibrationConfig cfg = raw_cfg;
    sanitize_calibration(cfg);

    CalibratedReading out{};
    float v = std::isfinite(raw_v) ? (raw_v * cfg.v_gain + cfg.v_offset) : 0.0f;
    if (v < 0.0f) v = 0.0f;
    out.v = v;

    float i_abs = std::isfinite(raw_i) ? std::fabs(raw_i) : 0.0f;
    float i_cal = i_abs * cfg.i_gain + cfg.i_offset;
    if (i_cal < 0.0f) i_cal = 0.0f;

    if (i_cal < cfg.noise_floor_a) {
        out.i = 0.0f;
        out.p = 0.0f;
        out.pf = 1.0f;
        out.below_noise_floor = true;
    } else {
        out.i = i_cal;
        out.below_noise_floor = false;
        float p_abs = std::isfinite(raw_p) ? std::fabs(raw_p) : 0.0f;
        float p_cal = p_abs * cfg.p_gain + cfg.p_low_corr_w;
        if (p_cal < 0.0f) p_cal = 0.0f;
        out.p = p_cal;

        float s_va = out.v * out.i;
        if (std::isfinite(raw_pf) && raw_pf >= 0.05f && raw_pf <= 1.0f &&
            cfg.p_gain == 1.0f && cfg.p_low_corr_w == 0.0f) {
            out.pf = raw_pf;
        } else if (s_va > 0.5f) {
            out.pf = clamp_float(out.p / s_va, 0.0f, 1.0f, 1.0f);
        } else {
            out.pf = 1.0f;
        }
    }

    out.f = (std::isfinite(raw_f) && raw_f >= 40.0f && raw_f <= 70.0f) ? raw_f : 50.0f;
    return out;
}

/**
 * Pelacak konsumsi energi harian (dalam satuan mWh integer agar bebas drift float)
 * dan kalkulator estimasi biaya Rupiah konsisten dengan docs/05-DATA-CONTRACT.md.
 */
class DailyRupiahTracker {
public:
    explicit DailyRupiahTracker(uint32_t tariff_sen = 144470, uint16_t extra_percent = 0)
        : tariff_sen_(tariff_sen), extra_percent_(extra_percent) {}

    void set_tariff(uint32_t tariff_sen, uint16_t extra_percent = 0) {
        tariff_sen_ = tariff_sen;
        extra_percent_ = extra_percent;
    }

    void reset_day(int day_key = -1) {
        energy_mwh_ = 0;
        day_key_ = day_key;
    }

    int day_key() const { return day_key_; }

    void add_power_sample(float power_w, uint32_t dt_ms, int day_key = -1) {
        if (day_key >= 0 && day_key_ >= 0 && day_key != day_key_) {
            reset_day(day_key);
        } else if (day_key >= 0 && day_key_ < 0) {
            day_key_ = day_key;
        }
        if (!std::isfinite(power_w) || power_w <= 0.0f || dt_ms == 0) {
            return;
        }
        // mWh = W * dt_ms / 3600
        double add_mwh = (static_cast<double>(power_w) * static_cast<double>(dt_ms)) / 3600.0;
        if (add_mwh > 0.0) {
            energy_mwh_ += static_cast<int64_t>(std::llround(add_mwh));
        }
    }

    float kwh() const {
        return static_cast<float>(energy_mwh_) / 1000000.0f;
    }

    int64_t energy_mwh() const { return energy_mwh_; }

    /**
     * Rumus persis kontrak data:
     * cost_rp = round((kwh * tariff_sen * (100 + extra_percent)) / 10_000)
     *         = round((wh * tariff_sen * (100 + extra_percent)) / 10_000_000)
     * Menggunakan int64_t murni (bebas __int128 agar kompatibel MCU 32-bit ESP32/ESP32-C3).
     */
    int64_t cost_rp() const {
        if (energy_mwh_ <= 0 || tariff_sen_ == 0) {
            return 0;
        }
        const int64_t wh = (energy_mwh_ + 500LL) / 1000LL;
        if (wh <= 0) {
            return 0;
        }
        const int64_t num = wh *
                            static_cast<int64_t>(tariff_sen_) *
                            static_cast<int64_t>(100U + extra_percent_);
        const int64_t den = 10000000LL;
        return (num + (den / 2)) / den;
    }

private:
    int64_t energy_mwh_ = 0;
    uint32_t tariff_sen_ = 144470;
    uint16_t extra_percent_ = 0;
    int day_key_ = -1;
};

/**
 * Pelacak lonjakan daya sesaat (inrush / beban puncak) pada pembacaan 1 detik.
 */
class PeakTracker {
public:
    void observe(float p_w, float i_a) {
        if (std::isfinite(p_w) && p_w > peak_power_w_) {
            peak_power_w_ = p_w;
        }
        if (std::isfinite(i_a) && i_a > peak_current_a_) {
            peak_current_a_ = i_a;
        }
    }

    void reset() {
        peak_power_w_ = 0.0f;
        peak_current_a_ = 0.0f;
    }

    float peak_power_w() const { return peak_power_w_; }
    float peak_current_a() const { return peak_current_a_; }

private:
    float peak_power_w_ = 0.0f;
    float peak_current_a_ = 0.0f;
};

} // namespace energy_core
