# 04. Spesifikasi Firmware (ESP32)

## Wiring sinyal
| PZEM-004T | ESP32 |
|---|---|
| 5V | VIN / 5V |
| GND | GND |
| TX | GPIO16 (RX2), **lewat pembagi tegangan 10k/20k** (TX PZEM 5 V, ESP32 hanya toleran 3,3 V) |
| RX | GPIO17 (TX2) |

Sisi AC: terminal tegangan PZEM ke fasa dan netral; CT coil dijepit di kabel fasa.

## Perilaku
- `setup()`: WiFi, sinkronisasi NTP, MQTT client (dengan Last Will & Testament retained), PZEM Serial, watchdog timer hardware (WDT).
- `loop()` non-blocking dengan timer `millis()`, tanpa `delay()` panjang. WDT di-reset tiap siklus loop sehat.
- Alur baca & publish:
  - Baca sensor PZEM tiap 1 detik (rolling buffer / filter derau).
  - Tiap 10 detik bentuk payload JSON telemetri persis kontrak `docs/05-DATA-CONTRACT.md`.
  - Sinkronisasi waktu NTP wajib: **jangan mempublikasikan telemetri sebelum waktu valid** diperoleh (`ts >= 2025` atau epoch detik >= 1735689600).
- **Aturan Ring Buffer & QoS 1**:
  - Publish telemetri ke `energy/{device_id}/telemetry` menggunakan **QoS 1**.
  - Sampel baru dimasukkan ke ring buffer (kapasitas 360 sampel = 1 jam offline pada interval 10s).
  - **Sampel HANYA dihapus dari ring buffer setelah menerima konfirmasi PUBACK** dari broker MQTT.
  - Jika koneksi terputus atau PUBACK belum tiba, sampel tetap bertahan di buffer.
  - Saat tersambung kembali, isi ring buffer dipublikasikan secara berurutan (FIFO) hingga habis sebelum mengirim data real-time baru.
  - Jika buffer penuh (360 sampel), sampel terlama ditimpa (drop oldest) dan inkremen counter `buffer_overflow`.
- **Penanganan PZEM NaN / Timeout**:
  - Nilai NaN dari PZEM tidak dikirim; hitung counter error komunikasi.
  - Jika PZEM diam / tidak merespons lebih dari 30 detik, restart port UART2 PZEM dan catat status error.
- **Last Will and Testament (LWT)**:
  - Topik: `energy/{device_id}/status`, QoS 1, Retained: `true`.
  - Pesan LWT: `offline`.
  - Saat berhasil connect: publish status `online` (QoS 1, retained).

## Konfigurasi (`include/config.example.h`)
`WIFI_SSID`, `WIFI_PASS`, `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASS`, `DEVICE_ID`, `PUBLISH_INTERVAL_S`.
File `config.h` asli masuk `.gitignore`.

## Library (PlatformIO)
- `mandulaj/PZEM-004T-v30` (komunikasi UART PZEM)
- `bertmelis/espMqttClient` (klien MQTT asinkron dengan dukungan penuh QoS 1 & callback PUBACK)
- `bblanchon/ArduinoJson` (serialisasi JSON efisien)

## Kontrak data
Topic dan payload mengikuti `05-DATA-CONTRACT.md`.

## Keselamatan pemasangan
- Sisi AC 220 V wajib dalam box tertutup dan terisolasi; tidak ada logam terbuka.
- Matikan MCB saat memasang.
- Pasang sekring kecil di jalur tegangan PZEM.
- Uji dulu dengan beban lampu di meja. Libatkan teknisi listrik bila ragu.
