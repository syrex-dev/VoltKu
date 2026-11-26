# Panduan Firmware ESP32 - Monitor Listrik Pintar

Firmware ini berjalan pada mikrokontroler **ESP32 DevKit** yang terhubung ke sensor daya **PZEM-004T v3.0** via UART2, mempublikasikan data telemetri real-time melalui MQTT (QoS 1) dengan sinkronisasi waktu NTP dan ring buffer lokal.

---

## 1. Wiring & Skema Perangkat Keras

| Pin PZEM-004T | Pin ESP32 | Keterangan |
|---|---|---|
| **5V** | **VIN / 5V** | Catu daya PZEM (5 V DC) |
| **GND** | **GND** | Ground bersama |
| **TX** | **GPIO 16 (RX2)** | ⚠️ **Wajib lewat pembagi tegangan 10kΩ / 20kΩ** (TX PZEM = 5 V; ESP32 = 3,3 V) |
| **RX** | **GPIO 17 (TX2)** | Langsung dari ESP32 (logika 3,3 V dapat dibaca PZEM) |

> ⚠️ **KESELAMATAN KELISTRIKAN (AC 220 V)**:
> - Terminal AC PZEM terhubung langsung ke listrik 220 V jala-jala.
> - Seluruh modul dan sambungan kabel wajib berada di dalam box tertutup berisolasi (non-konduktif).
> - Selalu matikan MCB utama sebelum memasang atau melepas kabel AC.
> - CT coil hanya dipasang menjepit kabel fasa tunggal (jangan menjepit kedua kabel fasa dan netral sekaligus).

---

## 2. Pembuatan Akun MQTT per Perangkat

Sesuai aturan keamanan Mosquitto (`deploy/acl` dan `deploy/passwd`), setiap perangkat memiliki topik isolasi `energy/%u/#`:

1. Buat username & password perangkat di Mosquitto broker menggunakan kontainer sementara (karena berkas passwd pada kontainer backend `energy_mosquitto` di-mount read-only `:ro`) secara interaktif tanpa opsi `-b`:
   ```bash
   # Linux / WSL / Git Bash:
   docker run --rm -it -v "$PWD/deploy:/mosquitto/config" eclipse-mosquitto:2.0 mosquitto_passwd /mosquitto/config/passwd device-01

   # Windows PowerShell:
   docker run --rm -it -v "${PWD}/deploy:/mosquitto/config" eclipse-mosquitto:2.0 mosquitto_passwd /mosquitto/config/passwd device-01
   ```
   *(Ketikkan kata sandi secara interaktif saat diminta prompt).*

> ⚠️ **Catatan Keamanan Izin Berkas Passwd (Tugas Milestone 7 - M7)**:
> Saat pengujian di Windows/pengembangan lokal, Mosquitto mencatat peringatan perizinan berkas (`Warning: File /mosquitto/config/passwd has world readable permissions. To fix this, use chmod 0700... owner is not root. To fix this, use chown root...`). Pengerasan izin berkas menjadi `chmod 0700` dan kepemilikan `root:root` dijadwalkan dan didokumentasikan secara ketat sebagai tugas hardening pada **Milestone 7 (M7 Deployment & Production Readiness)** saat di-host di lingkungan Linux server produksi.

2. Restart kontainer Mosquitto agar memuat ulang berkas kredensial:
   ```bash
   docker compose -f deploy/docker-compose.yml restart mosquitto
   ```

3. ⚠️ **ATURAN PENAMAAN DEVICE_ID**:
   - `DEVICE_ID` pada firmware **TIDAK BOLEH** berawalan `sim-` (karena prefiks `sim-` otomatis dikecualikan dari evaluasi alert dan pengiriman laporan berkala).
   - `DEVICE_ID` pada firmware **TIDAK BOLEH** berawalan `demo-` (karena prefiks `demo-` dicadangkan untuk testing dan dapat dihapus sewaktu-waktu oleh skrip pembersih `scripts/clean_device.py`).
   - Gunakan nama perangkat riil seperti `device-01`, `esp32-utama`, dsb.

---

## 3. Konfigurasi Firmware (`include/config.h`)

Salin berkas template konfigurasi:
```powershell
Copy-Item firmware\include\config.example.h firmware\include\config.h
```

Sesuaikan parameter di `firmware/include/config.h`:
```cpp
#pragma once

#define WIFI_SSID "NAMA_WIFI_ANDA"
#define WIFI_PASS "PASSWORD_WIFI_ANDA"

#define MQTT_HOST "192.168.1.100"  // IP host broker MQTT
#define MQTT_PORT 1883
#define MQTT_USER "device-01"
#define MQTT_PASS "PASSWORD_MQTT_ANDA"

#define DEVICE_ID "device-01"
#define NTP_SERVER "pool.ntp.org"
#define PUBLISH_INTERVAL_S 10
#define FIRMWARE_VERSION "1.0.0"
```
*(Berkas `config.h` otomatis diabaikan oleh `.gitignore` sehingga tidak akan bocor ke repositori).*

---

## 4. Instruksi Kompilasi & Pengujian di Windows

### A. Pengujian Unit Native (C++ murni)
Menguji logika format payload, sinkronisasi NTP, proteksi PUBACK tak dikenal/ganda, batas drain 5/detik, dan antrean ring buffer QoS 1 tanpa hardware:
```powershell
.venv\Scripts\pio test -d firmware -e native
```
Hasil uji otomatis mengekspor berkas `firmware/test/golden_payload.json` yang divalidasi oleh test suite backend:
```powershell
.venv\Scripts\python -m pytest backend/tests/test_firmware_payload.py -v
```

### B. Kompilasi Firmware ESP32
```powershell
.venv\Scripts\pio run -d firmware -e esp32dev
```

### C. Flash Firmware ke Perangkat Keras (Menunggu Izin/Persetujuan)
> ⚠️ **PERHATIAN**: Jangan melakukan flash atau menyalakan beban AC sebelum mendapatkan persetujuan eksplisit.

Setelah diizinkan dan perangkat ESP32 terhubung melalui port USB:
```powershell
# 1. Identifikasi port COM ESP32 di Windows Device Manager (misal COM3)
# 2. Flash firmware ke ESP32 melalui port COM yang terdeteksi:
.venv\Scripts\pio run -d firmware -e esp32dev -t upload --upload-port COM3

# 3. Membaca Serial Monitor (115200 baud)
.venv\Scripts\pio device monitor -d firmware -b 115200 --port COM3
```

---

## 5. Panduan Verifikasi Bertahap Perangkat Keras (Hardware Test Checklist)

Lakukan verifikasi secara bertahap di meja kerja sebelum dipasang ke instalasi panel listrik rumah.

### Tahap A: Pengujian ESP32 Saja (Tanpa PZEM & Tanpa Tegangan 220 V)
*Tujuan: Memverifikasi stabilitas sistem mikroprosesor, konektivitas WiFi, NTP, dan MQTT tanpa risiko sengatan listrik AC.*

- [ ] **1. Daya & Booting**:
  - Sambungkan board ESP32 ke port USB komputer via kabel data mikro-USB / USB-C.
  - Buka Serial Monitor pada 115200 baud (`.venv\Scripts\pio device monitor -d firmware -b 115200`).
  - Verifikasi pesan boot: `--- Monitor Listrik Pintar (ESP32 Firmware) ---`.
  - Watchdog hardware (WDT) aktif 15 detik; pastikan ESP32 **tidak mengalami boot loop / reset berulang**.
- [ ] **2. Koneksi WiFi & NTP**:
  - Pastikan log menampilkan `[WiFi] Menghubungkan ke <SSID>` dan berhasil tersambung.
  - Alamat IP lokal diperoleh dan ditampilkan di Serial.
  - Kredensial rahasia (password WiFi) **TIDAK PERNAH** tercetak ke Serial.
  - Sinkronisasi NTP berhasil: log mencatat `[NTP] Waktu valid berhasil diperoleh: epoch <ts>` dengan nilai epoch >= 1735689600 (tahun 2025+).
- [ ] **3. Koneksi Broker MQTT & LWT**:
  - ESP32 berhasil tersambung ke broker Mosquitto: `[MQTT] Terhubung ke broker!`.
  - Status `online` (retained, QoS 1) otomatis dipublikasikan ke topik `energy/<DEVICE_ID>/status`.
  - Password MQTT **TIDAK PERNAH** tercetak ke Serial.
- [ ] **4. Perilaku Saat Sensor PZEM Diam / Tidak Terpasang**:
  - Karena kabel UART PZEM belum tersambung, pembacaan PZEM menghasilkan nilai NaN.
  - Log mencatat bahwa tidak ada sampel telemetri yang didorong ke ring buffer (`sampleCount == 0`).
  - Setelah 30 detik tanpa respons PZEM, log mencetak: `[PZEM] Tidak ada respons > 30 detik! Me-restart UART2...`.
  - UART2 di-restart tanpa blocking delay, dan **TIDAK** mempublikasikan payload error ke topik status broker MQTT.
  - Watchdog tetap di-reset secara teratur di `loop()`, mikrokontroler stabil dan tidak restart.

---

### Tahap B: Pengujian ESP32 + Sensor PZEM-004T + Beban Uji Lampu 100 W
*Tujuan: Memverifikasi keakuratan pembacaan parameter kelistrikan riil AC 220 V dan transmisi telemetri.*

- [ ] **1. Pemasangan Fisik Berisolasi (AC 220 V)**:
  - Terminal tegangan AC PZEM dihubungkan ke colokan listrik AC 220 V dengan kabel terisolasi rapi di dalam kotak pelindung non-konduktif.
  - Resistor pembagi tegangan 10kΩ / 20kΩ terpasang pada jalur TX PZEM ke GPIO16 ESP32.
  - Current Transformer (CT) coil dipasang mengelilingi **hanya 1 kawat fasa** dari kabel beban lampu uji 100 W (bukan kedua kawat kabel ganda).
- [ ] **2. Pembacaan Sensor & Transmisi Normal**:
  - Nyalakan beban lampu uji 100 W.
  - Serial monitor mencatat sensor pulih: `[PZEM] Sensor pulih dan kembali membaca data normal.`.
  - Pembacaan sensor terbaca valid setiap 1 detik: Tegangan ~220-230 V, Arus ~0.43-0.46 A, Daya ~95-105 W, Energi bertambah secara kumulatif, Frekuensi ~50 Hz, Power Factor ~0.98-1.00.
  - Setiap 10 detik, telemetri dikumpulkan dan dimasukkan ke ring buffer, kemudian dikirim via MQTT QoS 1 ke topik `energy/<DEVICE_ID>/telemetry`.
  - Broker mengembalikan konfirmasi PUBACK dan ring buffer mengosongkan sampel tersebut secara mulus.
- [ ] **3. Ketahanan Terhadap Nilai NaN Frekuensi / PF**:
  - Jika terjadi interferensi sesaat yang membuat frekuensi atau PF bernilai NaN, firmware melewati nilai NaN tersebut dan mempertahankan nilai valid terakhir tanpa mengarang angka default buatan.
- [ ] **4. Integritas Timestamp**:
  - Jika timestamp sampel sama dengan sampel sebelumnya, firmware melewatinya (`[BUFFER] Timestamp sama dengan sampel sebelumnya, melewati push.`) untuk mencegah duplikasi di database.
- [ ] **5. Pengujian Simulasi Jaringan Terputus (Offline Resilience)**:
  - Putus sambungan WiFi atau matikan broker selama 3 menit.
  - Sampel telemetri terkumpul aman di ring buffer lokal (maksimal 360 sampel / 1 jam retensi offline).
  - Sambungkan kembali WiFi/broker: buffer dikuras secara teratur (maksimal 5 sampel/detik) hingga kosong tanpa ada data yang hilang.

---

### Tabel Pesan Serial Monitor yang Diharapkan (Expected Serial Logs)

| Peristiwa / Status | Pesan Serial yang Diharapkan | Keterangan / Tindakan |
|---|---|---|
| **Boot Awal** | `--- Monitor Listrik Pintar (ESP32 Firmware) ---` | Banner inisialisasi boot firmware |
| **Koneksi WiFi** | `[WiFi] Menghubungkan ke <SSID>` | Mencoba tersambung ke AP WiFi |
| **WiFi Terhubung** | `[WiFi] Terhubung! Alamat IP: <IP>` | Berhasil memperoleh IP lokal dari DHCP |
| **Sinkronisasi NTP** | `[NTP] Memulai sinkronisasi waktu dari <SERVER>` | Request sinkronisasi waktu via UDP |
| **Waktu Valid NTP** | `[NTP] Waktu valid berhasil diperoleh: epoch <TS>` | Epoch >= 1735689600 tercapai, siap telemetri |
| **Koneksi MQTT** | `[MQTT] Terhubung ke broker!` | Tersambung dan publish `online` retained QoS 1 |
| **PZEM Normal** | `[PZEM] Sensor pulih dan kembali membaca data normal.` | Sensor merespons komunikasi UART2 dengan data valid |
| **PZEM Timeout (>30s)** | `[PZEM] Tidak ada respons > 30 detik! Me-restart UART2...` | UART2 di-restart non-blocking; tidak crash |
| **Frekuensi / PF NaN** | `[PZEM] Frekuensi bernilai NaN, melewati akumulasi dan menandai penggunaan nilai valid terakhir.` | Nilai valid terakhir dipertahankan |
| **Timestamp Duplikat** | `[BUFFER] Timestamp sama dengan sampel sebelumnya, melewati push.` | Mencegah duplikasi data telemetri di backend |
| **Buffer Overflow** | `[BUFFER] Peringatan: Overflow terjadi! Total sampel terbuang: <N>` | Terjadi jika offline > 1 jam (> 360 sampel) |
| **MQTT Terputus** | `[MQTT] Terputus dari broker. Alasan: <KODE>` | Masuk mode offline, antrean in-flight dikembalikan ke PENDING |
| **MQTT Reconnect** | `[MQTT] Mencoba menyambung ke broker (backoff <N>s)...` | Percobaan ulang koneksi dengan backoff eksponensial |

---

## 6. Target Perangkat Keras Komersial VoltKu v3.0 (`[env:voltku_v3_c3]`)

Target build `voltku_v3_c3` dirancang untuk papan **ESP32-C3 SuperMini + IC Metering BL0942 + Layar TFT IPS 1.3" (ST7789 240×240)** pada casing DIN-Rail v3.0:

- **Kompilasi Target v3.0:**
  ```powershell
  python -m platformio run -d firmware -e voltku_v3_c3
  ```
- **Alasan Penambahan Dependensi Baru (Khusus `[env:voltku_v3_c3]`):**
  - `lovyan03/LovyanGFX@^1.2.0`: Driver SPI berkecepatan tinggi dengan dukungan PWM backlight untuk layar warna TFT IPS 1.3" ST7789 240×240 pada ESP32-C3 (`SCK=GPIO4, MOSI=GPIO6, DC=GPIO5, RST=GPIO7, CS=GPIO10, BLK=GPIO3`).
  - `ricmoo/QRCode@^0.0.1`: Pembangkit QR Code ringan tanpa dependensi eksternal untuk menampilkan QR setup Wi-Fi langsung di layar saat mode pairing.
  - *(Build bawaan `[env:esp32dev]` tidak menyertakan library layar ini sehingga tetap ringkas dan kompatibel mundur).*
- **Fitur Kalibrasi Presisi (`lib/energy_core/calibration.hpp`):**
  - Profil CT Split-Core (**30A / 50A / 100A**), `v_gain`, `i_gain`, `p_gain`, koreksi beban rendah (`p_low_corr`), *noise floor* (`0.012A`), dan tarif Rupiah tersimpan di NVS (`energy_cfg`) serta dapat disetel melalui Captive Portal (`/save`).
  - Menekan tombol fisik `SW1` (`GPIO9`) singkat akan berpindah halaman layar (`Live Watt & Rupiah` → `kWh & Peak Inrush` → `QR & Info`), sedangkan menahan `>= 3 detik` mengaktifkan mode SoftAP Captive Portal.
