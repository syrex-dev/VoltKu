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
- `setup()`: WiFi, NTP, MQTT (dengan Last Will), PZEM, watchdog.
- `loop()` non-blocking dengan timer `millis()`, tanpa `delay()` panjang.
- Alur: baca PZEM tiap 1 detik > tiap 10 detik bentuk JSON > publish > jika gagal, masukkan ke ring buffer (maks 360 data).
- Saat tersambung kembali, kirim isi buffer berurutan sebelum data baru.
- Nilai NaN dari PZEM tidak dikirim; hitung counter error. Jika PZEM diam lebih dari 30 detik, kirim status error.
- Waktu dari NTP; kirim `ts` epoch detik UTC.

## Konfigurasi (`include/config.example.h`)
`WIFI_SSID`, `WIFI_PASS`, `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASS`, `DEVICE_ID`, `PUBLISH_INTERVAL_S`.
File `config.h` asli masuk `.gitignore`.

## Library (PlatformIO)
`mandulaj/PZEM-004T-v30`, `knolleary/PubSubClient`, `bblanchon/ArduinoJson`.

## Kontrak data
Topic dan payload mengikuti `05-DATA-CONTRACT.md`.

## Keselamatan pemasangan
- Sisi AC 220 V wajib dalam box tertutup dan terisolasi; tidak ada logam terbuka.
- Matikan MCB saat memasang.
- Pasang sekring kecil di jalur tegangan PZEM.
- Uji dulu dengan beban lampu di meja. Libatkan teknisi listrik bila ragu.
