# 05. Kontrak Data (MQTT, REST API, Model Data)

Dokumen ini adalah sumber kebenaran. Perubahan wajib disetujui pemilik proyek.

## 1. MQTT
| Topic | Arah | QoS | Isi |
|---|---|---|---|
| `energy/{device_id}/telemetry` | ESP32 > broker | 1 | Data pengukuran |
| `energy/{device_id}/status` | ESP32 > broker | 1, retained | `online` / `offline` (LWT) |

> **Catatan Keamanan:** `device_id` wajib sama persis dengan username MQTT perangkat yang terotentikasi, karena Mosquitto ACL membatasi hak akses publish per user menggunakan pola `%u` (`energy/%u/#`).

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
| `GET/PATCH /api/settings` | Tarif, batas daya, jam laporan (menerima tarif Rp desimal, misal 1444.70) |
| `GET /healthz` | Health check |

Format error: objek `error` berisi `code` dan `message`. Semua endpoint kecuali `/healthz` dan `/api/login` butuh token.

## 3. Model data
```
devices(id PK, name, location, mcb_watt, created_at)
readings(id PK, device_id, ts, v, i, p, e_kwh, delta_kwh, f, pf, rssi, is_gap)
   index dan unique (device_id, ts)
hourly_stats(device_id, hour_start, kwh, p_avg, p_max, p_min, samples)   PK (device_id, hour_start)
daily_stats(device_id, day, kwh, cost_rp, tariff_sen, p_max, p_base)      PK (device_id, day)
anomalies(id PK, device_id, ts, type, severity, details_json, message, notified)
settings(key PK, value)   -- tariff_sen_per_kwh, extra_percent, power_limit_w, alert_cooldown_min, report_hour
telegram_users(chat_id PK, name)
chat_log(id PK, chat_id, ts, question, tools_used, answer, tokens)
```
- `cost_rp`: `INTEGER` (Rupiah bulat, dihitung menggunakan Python `Decimal` dengan pembulatan `ROUND_HALF_UP`).
- `tariff_sen`: `INTEGER` (tarif per kWh dalam satuan sen, misal Rp1.444,70/kWh disimpan sebagai 144470).
- `kwh`, `delta_kwh`, `e_kwh`: `REAL` (dibulatkan 3 desimal).
- `is_gap`: `INTEGER` (1 jika selisih waktu $\Delta t > 3 \times \text{interval publish}$, default 0; replay buffer normal bukan gap).
- `p_base`: `REAL`, bernilai `NULL` sebelum pukul 05.00 WIB.

## 4. Aturan perhitungan
- **Delta kWh**:
  - Dihitung dalam integer Wh: `round(e * 1000)`.
  - Sampel pertama dicek dari database (bukan memori); jika belum ada record sebelumnya untuk `device_id`, `delta_kwh = 0.0`.
  - Urutan kalkulasi berdasarkan `ts` (bukan urutan tiba).
  - Batas lonjakan tak wajar:
    $$\Delta kWh_{max} = \frac{mcb\_watt \times 1.5 \times \Delta t_{eff}}{3600 \times 1000}$$
    dengan $\Delta t_{eff} = \max(\Delta t, \text{interval\_publish})$.
  - Jika $e$ turun (counter reset), `delta_kwh = e_baru` asalkan $e_{baru} \le \Delta kWh_{max}$.
  - Sampel yang ditolak TIDAK memajukan baseline.
  - Tiga penolakan berturut-turut yang konsisten menetapkan baseline baru (`delta_kwh = 0.0`, log warning).
  - Jika terjadi gap waktu panjang ($\Delta t > 3 \times \text{interval publish}$), delta tetap dihitung (energi riil), `is_gap = 1`, dan dicatat di jam kedatangan sampel.
  - Validasi `ts` (BE-02): tolak jika $ts > now + 5\text{ menit}$ atau $ts < 1735689600$ (2025-01-01 00:00:00 UTC).
- **Biaya**:
  - Dihitung seluruhnya dengan `Decimal` tanpa float di tengah:
    $$\text{cost\_rp} = \left( \frac{\text{Decimal}(\text{str}(kwh)) \times \text{Decimal}(tariff\_sen) \times (\text{Decimal}(100) + \text{Decimal}(\text{str}(extra\_percent)))}{\text{Decimal}(10000)} \right).\operatorname{quantize}(\text{Decimal}("1"), \text{ROUND\_HALF\_UP})$$
    *(Uji verifikasi: 3.2 kWh, tariff_sen 144470, extra 0 -> Rp4.623).*
  - Hari berjalan memakai tarif aktif di `settings`; hari lampau membekukan `tariff_sen` di baris `daily_stats` masing-masing (rekalkulasi hari lampau tidak mengubah tarif lama).
  - Input tarif via API / Telegram menerima angka desimal (titik atau koma) dan dikonversi ke integer sen di batas input.
- **Proyeksi bulan**: kWh sampai hari ini + (rata-rata kWh harian 7 hari terakhir x sisa hari), lalu dikalikan tarif.
