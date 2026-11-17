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
  - [ ] Sinkronisasi NTP berhasil (`ts >= 1735689600`). Sebelum waktu valid tercapai, telemetri tidak dipublikasikan ke broker.
- [ ] **4. Telemetri Normal (Lampu Pijar ~60W)**:
  - [ ] PZEM terbaca valid tiap detik (V ~220V, I ~0.27A, P ~60W).
  - [ ] Payload JSON terkirim tiap 10 detik via MQTT QoS 1.
  - [ ] Ring buffer kosong / ter-drain cepat saat online.
- [ ] **5. Simulasi Offline & Recovery Buffer**:
  - [ ] Matikan broker MQTT / putus router WiFi selama 3 menit (18 sampel tertampung di buffer).
  - [ ] Nyalakan kembali router / broker: buffer terkuras teratur (maks 5 sampel/s) hingga kosong.
  - [ ] Tidak ada sampel duplikat atau data corrupt di backend SQLite.
