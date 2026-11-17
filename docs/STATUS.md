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
| **M4** | Firmware ESP32 | **SELESAI (Kompilasi/Native)** | Logika ring buffer (bebas Head-of-Line blocking), filtering non-blocking, watchdog WDT terintegrasi, penanganan PZEM NaN, fallback template `config.example.h` dengan `#warning`. Lolos 12/12 `pio test -e native` dan lolos build `pio run -e esp32dev`. **Perangkat keras belum diuji** (hardware belum tersedia). |
| **M5** | AI Deteksi Anomali | **PERENCANAAN** | Desain arsitektur L2 (z-score robust MAD), L3 (beban dasar malam), dan generator data sintetis. Menunggu persetujuan rencana. |
| **M6** | AI Chat Asisten | **BELUM DIMULAI** | Menunggu M5 selesai. |
| **M7** | Pengerasan & Lapangan | **BELUM DIMULAI** | Menunggu ketersediaan perangkat keras fisik. |

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
