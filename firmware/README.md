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

1. Buat username & password perangkat di Mosquitto broker:
   ```bash
   mosquitto_passwd deploy/passwd device-01
   ```
2. Pastikan `DEVICE_ID` pada firmware sama dengan username MQTT (`device-01`).

---

## 3. Konfigurasi Firmware

Salin file template konfigurasi:
```bash
cp firmware/include/config.example.h firmware/include/config.h
```

Sesuaikan parameter di `firmware/include/config.h`:
```cpp
#define WIFI_SSID "NAMA_WIFI"
#define WIFI_PASS "PASSWORD_WIFI"

#define MQTT_HOST "192.168.1.100"  // IP host broker MQTT
#define MQTT_PORT 1883
#define MQTT_USER "device-01"
#define MQTT_PASS "PASSWORD_MQTT"

#define DEVICE_ID "device-01"
#define NTP_SERVER "pool.ntp.org"
#define PUBLISH_INTERVAL_S 10
#define FIRMWARE_VERSION "1.0.0"
```
*(File `config.h` otomatis diabaikan oleh `.gitignore` sehingga tidak akan bocor ke repositori).*

---

## 4. Instruksi Kompilasi & Pengujian di Windows

### A. Pengujian Unit Native (C++ murni)
Menguji logika format payload dan antrean ring buffer QoS 1 tanpa hardware:
```powershell
.venv\Scripts\pio test -e native
```
Hasil uji otomatis mengekspor berkas `firmware/test/golden_payload.json` yang divalidasi oleh test suite backend.

### B. Kompilasi Firmware ESP32
```powershell
.venv\Scripts\pio run -e esp32dev
```

### C. Flash Firmware ke Perangkat Keras (Belum dijalankan / Menunggu Persetujuan)
Setelah diizinkan dan perangkat ESP32 terhubung melalui port USB:
```powershell
# Identifikasi port COM ESP32 (misal COM3)
.venv\Scripts\pio run -e esp32dev -t upload --upload-port COM3

# Membuka Serial Monitor (115200 baud)
.venv\Scripts\pio device monitor -b 115200
```

---

## 5. Checklist Pengujian Perangkat Keras (Hardware Test Checklist)

Lakukan verifikasi bertahap di meja kerja dengan beban uji lampu pijar/solder sebelum dipasang ke instalasi rumah:

- [ ] **1. Pemeriksaan Visual & Multimeter**:
  - [ ] Resistor pembagi tegangan 10k/20k terpasang dengan benar pada jalur TX PZEM ke GPIO16.
  - [ ] Tidak ada kawat terkelupas atau logam terbuka pada sisi tegangan tinggi 220 V.
- [ ] **2. Boot & Serial Log**:
  - [ ] ESP32 boot normal, WDT aktif 15s.
  - [ ] Kredensial WiFi dan password MQTT **TIDAK tercetak** di serial monitor.
- [ ] **3. Konektivitas & NTP**:
  - [ ] WiFi terhubung dan mendapat alamat IP.
  - [ ] Sinkronisasi NTP berhasil (`ts >= 1735689600`). Sebelum waktu valid tercapai, telemetri tidak dipublikasikan.
- [ ] **4. Pembacaan Sensor PZEM-004T**:
  - [ ] Nilai tegangan terbaca wajar (~220-230 V).
  - [ ] Beban uji (misal lampu 60W) menghasilkan pembacaan arus (~0,27 A), daya (~60 W), dan power factor (~1,00).
- [ ] **5. Pengujian MQTT & QoS 1**:
  - [ ] Pesan status `online` (retained, QoS 1) diterima di topic `energy/device-01/status`.
  - [ ] Telemetri terkirim tiap 10 detik ke `energy/device-01/telemetry` dengan format JSON persis kontrak.
  - [ ] Broker mengirim PUBACK dan slot ring buffer dibersihkan.
- [ ] **6. Pengujian Last Will and Testament (LWT)**:
  - [ ] Cabut daya ESP32 secara tiba-tiba: broker harus mempublikasikan `offline` (retained) pada `energy/device-01/status`.
- [ ] **7. Pengujian Offline Buffering & Replay**:
  - [ ] Putuskan koneksi WiFi selama 2 menit (beban tetap menyala).
  - [ ] Sambungkan kembali WiFi: periksa bahwa ~12 sampel yang tersimpan di ring buffer terkirim bertahap secara FIFO tanpa ada data yang hilang.

