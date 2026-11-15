# 05. Kontrak Data (MQTT, REST API, Model Data)

Dokumen ini adalah sumber kebenaran. Perubahan wajib disetujui pemilik proyek.

## 1. MQTT
| Topic | Arah | QoS | Isi |
|---|---|---|---|
| `energy/{device_id}/telemetry` | ESP32 > broker | 1 | Data pengukuran |
| `energy/{device_id}/status` | ESP32 > broker | 1, retained | `online` / `offline` (LWT) |

Payload telemetry:
```json
{"ts":1731650000,"v":220.5,"i":1.234,"p":272.1,"e":12.345,"f":50.0,"pf":0.98,"rssi":-61,"fw":"1.0.0"}
```
`ts` epoch detik UTC, `v` volt, `i` ampere, `p` watt, `e` kWh kumulatif dari PZEM, `f` Hz, `pf` power factor, `rssi` dBm, `fw` versi firmware.

## 2. REST API
| Method dan path | Fungsi |
|---|---|
| `POST /api/login` | Login, mengembalikan token |
| `GET /api/devices` | Daftar perangkat dan status |
| `GET /api/devices/{id}/latest` | Pembacaan terakhir |
| `GET /api/devices/{id}/series?from=&to=&interval=raw\|hour\|day` | Data deret waktu |
| `GET /api/devices/{id}/summary?range=today\|week\|month` | kWh, biaya, rata-rata, puncak |
| `GET /api/devices/{id}/forecast` | Proyeksi kWh dan biaya akhir bulan |
| `GET /api/anomalies?device_id=&from=` | Daftar anomali |
| `GET/PATCH /api/settings` | Tarif, batas daya, jam laporan |
| `GET /healthz` | Health check |

Format error: objek `error` berisi `code` dan `message`. Semua endpoint kecuali `/healthz` dan `/api/login` butuh token.

## 3. Model data
```
devices(id PK, name, location, mcb_watt, created_at)
readings(id PK, device_id, ts, v, i, p, e_kwh, delta_kwh, f, pf, rssi)
   index dan unique (device_id, ts)
hourly_stats(device_id, hour_start, kwh, p_avg, p_max, p_min, samples)   PK (device_id, hour_start)
daily_stats(device_id, day, kwh, cost_rp, tariff_rp, p_max, p_base)      PK (device_id, day)
anomalies(id PK, device_id, ts, type, severity, details_json, message, notified)
settings(key PK, value)   -- tariff_rp_per_kwh, extra_percent, power_limit_w, alert_cooldown_min, report_hour
telegram_users(chat_id PK, name)
chat_log(id PK, chat_id, ts, question, tools_used, answer, tokens)
```
`p_base` = median daya pukul 00.00-05.00 (beban dasar malam).

## 4. Aturan perhitungan
- `delta_kwh` = `e_kwh` sekarang - `e_kwh` sebelumnya. Jika negatif (counter reset), `delta_kwh` = `e_kwh` sekarang. Jika delta tak masuk akal (mis. lebih besar dari daya maksimum x selisih waktu), abaikan dan catat.
- Biaya = kWh x `tariff_rp_per_kwh` x (1 + `extra_percent`/100).
- Proyeksi bulan = kWh sampai hari ini + rata-rata kWh harian 7 hari terakhir x sisa hari, lalu x tarif.
