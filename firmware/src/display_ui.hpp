#pragma once

#if defined(ENABLE_TFT_DISPLAY) && ENABLE_TFT_DISPLAY

#include <LovyanGFX.hpp>
#include <cstdio>
#include <cstring>
#include <qrcode.h>

#ifndef TFT_SCK_PIN
#define TFT_SCK_PIN 4
#endif
#ifndef TFT_MOSI_PIN
#define TFT_MOSI_PIN 6
#endif
#ifndef TFT_DC_PIN
#define TFT_DC_PIN 5
#endif
#ifndef TFT_RST_PIN
#define TFT_RST_PIN 7
#endif
#ifndef TFT_CS_PIN
#define TFT_CS_PIN 10
#endif
#ifndef TFT_BLK_PIN
#define TFT_BLK_PIN 3
#endif

namespace voltku_ui {

class LGFX_VoltKu : public lgfx::LGFX_Device {
    lgfx::Panel_ST7789 _panel_instance;
    lgfx::Bus_SPI _bus_instance;
    lgfx::Light_PWM _light_instance;

public:
    LGFX_VoltKu() {
        {
            auto cfg = _bus_instance.config();
            cfg.spi_host = SPI2_HOST;
            cfg.spi_mode = 3;
            cfg.freq_write = 40000000;
            cfg.freq_read = 16000000;
            cfg.spi_3wire = true;
            cfg.use_lock = true;
            cfg.dma_channel = SPI_DMA_CH_AUTO;
            cfg.pin_sclk = TFT_SCK_PIN;
            cfg.pin_mosi = TFT_MOSI_PIN;
            cfg.pin_miso = -1;
            cfg.pin_dc = TFT_DC_PIN;
            _bus_instance.config(cfg);
            _panel_instance.setBus(&_bus_instance);
        }
        {
            auto cfg = _panel_instance.config();
            cfg.pin_cs = TFT_CS_PIN;
            cfg.pin_rst = TFT_RST_PIN;
            cfg.pin_busy = -1;
            cfg.panel_width = 240;
            cfg.panel_height = 240;
            cfg.offset_x = 0;
            cfg.offset_y = 0;
            cfg.offset_rotation = 0;
            cfg.invert = true;
            cfg.rgb_order = false;
            cfg.dlen_16bit = false;
            cfg.bus_shared = false;
            _panel_instance.config(cfg);
        }
        {
            auto cfg = _light_instance.config();
            cfg.pin_bl = TFT_BLK_PIN;
            cfg.invert = false;
            cfg.freq = 12000;
            cfg.pwm_channel = 1;
            _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance);
        }
        setPanel(&_panel_instance);
    }
};

struct DisplaySnapshot {
    float v = 0.0f;
    float i = 0.0f;
    float p = 0.0f;
    float e_kwh = 0.0f;
    float f = 50.0f;
    float pf = 1.0f;
    float peak_w = 0.0f;
    int64_t cost_rp = 0;
    int32_t rssi = -99;
    uint32_t buf_count = 0;
    uint16_t ct_rating_a = 100;
    bool wifi_ok = false;
    bool mqtt_ok = false;
    bool sensor_ok = false;
    bool pairing_mode = false;
    const char* device_id = "ML-000000";
    const char* ap_ssid = "VoltKu-Setup";
    const char* driver_name = "BL0942";
};

class DisplayController {
public:
    void begin() {
        tft_.init();
        tft_.setRotation(1);  // 90 deg agar modul ST7789 39x27.8mm terpasang horizontal simetris di casing v3.1
        tft_.setBrightness(215);
        tft_.fillScreen(0x0821);
        initialized_ = true;
    }

    void next_page() {
        page_ = (page_ + 1) % 3;
        force_redraw_ = true;
    }

    uint8_t page() const { return page_; }

    void render(const DisplaySnapshot& snap) {
        if (!initialized_) return;

        if (snap.pairing_mode) {
            render_qr_page(snap, true);
            return;
        }

        if (force_redraw_) {
            tft_.fillScreen(0x0821);
            force_redraw_ = false;
        }

        if (page_ == 0) {
            render_live_page(snap);
        } else if (page_ == 1) {
            render_energy_page(snap);
        } else {
            render_qr_page(snap, false);
        }
    }

private:
    LGFX_VoltKu tft_;
    bool initialized_ = false;
    uint8_t page_ = 0;
    bool force_redraw_ = true;

    void draw_header(const char* tag, bool wifi_ok, bool mqtt_ok) {
        tft_.fillRect(0, 0, 240, 28, 0x0A26);
        tft_.setTextSize(1);
        tft_.setTextColor(0x3E7F, 0x0A26);
        tft_.setCursor(10, 8);
        tft_.print("VoltKu");
        tft_.setTextColor(0x94B2, 0x0A26);
        tft_.print(" | ");
        tft_.print(tag);

        uint16_t badge_col = (wifi_ok && mqtt_ok) ? 0x0528 : (wifi_ok ? 0xCA00 : 0xB800);
        tft_.fillRoundRect(168, 5, 64, 18, 5, badge_col);
        tft_.setTextColor(0xFFFF, badge_col);
        tft_.setCursor(176, 10);
        tft_.print((wifi_ok && mqtt_ok) ? "ONLINE" : (wifi_ok ? "MQTT.." : "OFFLINE"));
    }

    void render_live_page(const DisplaySnapshot& s) {
        draw_header("LIVE", s.wifi_ok, s.mqtt_ok);

        // Panel Daya Utama (Watt)
        tft_.fillRoundRect(10, 36, 220, 72, 10, 0x10A4);
        tft_.setTextColor(0x94B2, 0x10A4);
        tft_.setTextSize(1);
        tft_.setCursor(20, 44);
        tft_.print("DAYA AKTIF SAAT INI");

        char buf[40];
        std::snprintf(buf, sizeof(buf), "%.1f W", s.p);
        tft_.setTextColor(s.p > 2000.0f ? 0xFB20 : 0xFFE0, 0x10A4);
        tft_.setTextSize(3);
        tft_.setCursor(20, 62);
        tft_.print(buf);

        // Panel Biaya Hari Ini (Rupiah)
        tft_.fillRoundRect(10, 114, 220, 44, 8, 0x09E3);
        tft_.setTextColor(0x7FE0, 0x09E3);
        tft_.setTextSize(1);
        tft_.setCursor(20, 121);
        tft_.print("ESTIMASI BIAYA HARI INI");
        std::snprintf(buf, sizeof(buf), "Rp %lld", static_cast<long long>(s.cost_rp));
        tft_.setTextSize(2);
        tft_.setCursor(20, 134);
        tft_.print(buf);

        // Grid 4 Metrik: Volt, Ampere, Hz, PF
        tft_.fillRoundRect(10, 164, 106, 32, 6, 0x10A4);
        tft_.fillRoundRect(124, 164, 106, 32, 6, 0x10A4);
        tft_.setTextSize(1);
        tft_.setTextColor(0x5E7F, 0x10A4);
        std::snprintf(buf, sizeof(buf), "%.1f V", s.v);
        tft_.setCursor(18, 175);
        tft_.print(buf);
        std::snprintf(buf, sizeof(buf), "%.2f A", s.i);
        tft_.setCursor(132, 175);
        tft_.print(buf);

        tft_.fillRoundRect(10, 202, 220, 30, 6, 0x0842);
        tft_.setTextColor(0xCE79, 0x0842);
        std::snprintf(
            buf, sizeof(buf),
            "PF %.2f | %.1f Hz | Buf %u",
            s.pf, s.f, static_cast<unsigned>(s.buf_count)
        );
        tft_.setCursor(18, 213);
        tft_.print(buf);
    }

    void render_energy_page(const DisplaySnapshot& s) {
        draw_header("ENERGI", s.wifi_ok, s.mqtt_ok);
        char buf[48];

        tft_.fillRoundRect(10, 38, 220, 56, 8, 0x10A4);
        tft_.setTextSize(1);
        tft_.setTextColor(0x94B2, 0x10A4);
        tft_.setCursor(20, 46);
        tft_.print("TOTAL KWH TERCATAT");
        std::snprintf(buf, sizeof(buf), "%.3f kWh", s.e_kwh);
        tft_.setTextSize(2);
        tft_.setTextColor(0x3E7F, 0x10A4);
        tft_.setCursor(20, 64);
        tft_.print(buf);

        tft_.fillRoundRect(10, 102, 220, 56, 8, 0x10A4);
        tft_.setTextSize(1);
        tft_.setTextColor(0x94B2, 0x10A4);
        tft_.setCursor(20, 110);
        tft_.print("PUNCAK / INRUSH SESI");
        std::snprintf(buf, sizeof(buf), "%.1f W", s.peak_w);
        tft_.setTextSize(2);
        tft_.setTextColor(0xFD20, 0x10A4);
        tft_.setCursor(20, 128);
        tft_.print(buf);

        tft_.fillRoundRect(10, 166, 220, 64, 8, 0x0842);
        tft_.setTextSize(1);
        tft_.setTextColor(0xCE79, 0x0842);
        std::snprintf(buf, sizeof(buf), "Driver: %s | CT %uA", s.driver_name, s.ct_rating_a);
        tft_.setCursor(18, 178);
        tft_.print(buf);
        std::snprintf(buf, sizeof(buf), "Wi-Fi RSSI: %d dBm", static_cast<int>(s.rssi));
        tft_.setCursor(18, 196);
        tft_.print(buf);
        std::snprintf(buf, sizeof(buf), "ID: %s", s.device_id);
        tft_.setCursor(18, 214);
        tft_.print(buf);
    }

    void render_qr_page(const DisplaySnapshot& s, bool is_pairing) {
        draw_header(is_pairing ? "SETUP" : "INFO", s.wifi_ok, s.mqtt_ok);
        char qr_payload[96];
        std::snprintf(qr_payload, sizeof(qr_payload), "WIFI:T:nopass;S:%s;;", s.ap_ssid);

        QRCode qrcode;
        uint8_t qrcodeData[qrcode_getBufferSize(3)];
        qrcode_initText(&qrcode, qrcodeData, 3, ECC_LOW, qr_payload);

        const int scale = 4;
        const int qr_px = qrcode.size * scale;
        const int x0 = (240 - qr_px) / 2;
        const int y0 = 42;
        tft_.fillRoundRect(x0 - 8, y0 - 8, qr_px + 16, qr_px + 16, 8, 0xFFFF);
        for (uint8_t y = 0; y < qrcode.size; ++y) {
            for (uint8_t x = 0; x < qrcode.size; ++x) {
                uint16_t col = qrcode_getModule(&qrcode, x, y) ? 0x0000 : 0xFFFF;
                tft_.fillRect(x0 + x * scale, y0 + y * scale, scale, scale, col);
            }
        }

        tft_.setTextSize(1);
        tft_.setTextColor(0xFFE0, 0x0821);
        tft_.setCursor(18, y0 + qr_px + 18);
        tft_.print("AP: ");
        tft_.print(s.ap_ssid);
        tft_.setTextColor(0x94B2, 0x0821);
        tft_.setCursor(18, y0 + qr_px + 34);
        tft_.print("ID: ");
        tft_.print(s.device_id);
    }
};

} // namespace voltku_ui

#endif  // ENABLE_TFT_DISPLAY

