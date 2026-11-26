# Status Proyek: Monitor Listrik Pintar

Dokumen ini mencatat status implementasi terkini dari setiap milestone secara jujur dan transparan, termasuk pemisahan antara pengujian software/simulator dengan backlog pengujian perangkat keras fisik.

> **Catatan Prioritas**: Perangkat keras ESP32, modul PZEM-004T, dan integrasi bot Telegram langsung saat ini **DIPARKIR** (komponen fisik belum dibeli). Seluruh validasi milestone berikutnya (M5 dst.) dijalankan penuh menggunakan simulator MQTT dan generator data sintetis deterministik.

---

## 1. Tabel Status Milestone

| Milestone | Deskripsi | Status | Catatan Validasi & Keterbatasan |
|---|---|---|---|
| **M0** | Fondasi | **SELESAI** | Docker compose, konfigurasi env, linting ruff, struktur proyek dasar. |
| **M1** | Ingest & Data | **SELESAI** | Subscriber MQTT, validasi payload, kalkulasi delta kWh, agregasi biaya, simulator berjalan. Unit test lengkap. |
| **M2** | API & Dashboard | **SELESAI** | FastAPI REST API aman (JWT), dashboard web responsif (desktop/mobile), indikator status perangkat (online/offline). |
| **M3** | Alert Aturan & Bot | **SELESAI (Simulasi)** | Logika alert L1 (offline, overload, tegangan abnormal), deduplikasi, retry per-chat, laporan terjadwal, dan decoupled mode lolos tes unit/simulator. **Telegram asli belum diuji secara langsung** dengan server Telegram resmi (menggunakan stub & NullNotifier). |
| **M4** | Firmware ESP32 | **SELESAI (Kompilasi/Native)** | Firmware v1.1 (PZEM-004T) dan v3.0 (`voltku_v3_c3`: BL0942 + kalibrasi NVS + layar IPS TFT + MQTT TLS opsional). Lolos `pio test -e native` dan build `pio run -e esp32dev` + `voltku_v3_c3`. **Perangkat keras fisik belum diuji** (unit belum dirakit). |
| **M5** | AI Deteksi Anomali | **SELESAI** | Mesin deteksi L2 (Robust Z-Score MAD) & L3 (baseload malam), validator generator sintetis 90 hari, multi-tenant anomaly scoping lolos pytest. |
| **M6** | AI Chat Asisten & Notifikasi Android | **SELESAI** | Tool-calling AI (`POST /api/chat` + Telegram `/ask`) dengan 7 tool deterministik, guardrails tegangan tinggi/prompt-injection, rate limit 20 pesan/jam, widget UI chat; plus dual-engine notifikasi Android ala WA (FCM HTTP v1 + `WorkManager` + `@capacitor/local-notifications`). Eval `chat_eval.yaml` (15 pertanyaan) menggunakan `LLMStub` lolos uji; live LLM & build APK Java menunggu kunci Firebase/Android Studio. |
| **M7** | Pengerasan, MQTT TLS & Hardware v3 | **SELESAI (Software & CAD/PCB)** | Hardening security headers, CORS, rate-limit per-IP, dukungan MQTT TLS (`8883`, `mosquitto-tls.conf`, `generate_mqtt_certs.sh`, `MQTT_USE_TLS`), desain mekanik 3D DIN-Rail Signature v3.1, & PCB v3.0 siap produksi. **Uji lapangan fisik** ditunda sampai komponen fisik tiba. |

---

## 2. Backlog Pengujian Perangkat Keras (Ditunda Sampai Perangkat Tersedia)

Item-item pengujian berikut memerlukan interaksi fisik dengan mikrokontroler, sensor, atau jaringan eksternal dan **ditunda sampai perangkat keras dibeli dan tersedia**:

1. **Uji Beban Terukur (Lampu 100 W)**:
   - Memverifikasi pembacaan sensor PZEM-004T terhadap beban resistif murni 100 W dengan deviasi < 5%.
   - Status: *Ditunda sampai perangkat tersedia*.
2. **Uji Putus WiFi 5 Menit**:
   - Memutuskan router/AP selama 5 menit saat firmware aktif mengirim data.
   - Memverifikasi buffer lokal menampung hingga 100 sampel dan melakukan drain saat koneksi pulih tanpa sampel ganda atau hilang.
   - Status: *Ditunda sampai perangkat tersedia*.
3. **Uji Backend Restart saat Firmware Berjalan**:
   - Me-restart container backend/broker MQTT saat ESP32 aktif.
   - Memverifikasi reconnect otomatis ESP32 dan pengiriman pesan buffered.
   - Status: *Ditunda sampai perangkat tersedia*.
4. **Uji Akurasi kWh 24 Jam vs Alat Ukur Pembanding**:
   - Membandingkan akumulasi energi pada kWh meter resmi/alat ukur referensi komersial selama 24 jam continuous.
   - Status: *Ditunda sampai perangkat tersedia*.
5. **Uji ESP32 Dicabut / Mati Listrik**:
   - Mematikan daya ESP32 secara tiba-tiba dan memverifikasi deteksi alert offline L1 di backend tepat waktu.
   - Status: *Ditunda sampai perangkat tersedia*.
6. **Flash & Serial Monitor Fisik**:
   - Flashing firmware biner ke modul ESP32-WROOM fisik, monitoring boot log, baud rate PZEM, dan stabilitas watchdog timer.
   - Status: *Ditunda sampai perangkat tersedia*.
7. **Pengujian Bot Telegram Live**:
   - Uji komunikasi dua arah langsung dengan API Telegram resmi (`https://api.telegram.org`) menggunakan token aktif dan chat ID sebenarnya.
   - Status: *Ditunda sampai perangkat tersedia / kanal notifikasi diaktifkan kembali*.
