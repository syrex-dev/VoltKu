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
| `POST /api/login` | Login legacy/admin `{"password": "..."}`, mengembalikan token JWT `{"token": "..."}` (`role="admin"`). Gagal berulang mengembalikan HTTP 429 (`Retry-After: N`). |
| `POST /api/users/register` | Registrasi akun pembeli multi-tenant (`name`, `email`, `password` min 6 karakter). Mengembalikan HTTP `201` dengan JWT (`role="user"`) dan profil user. |
| `POST /api/users/login` | Login akun pembeli (`email`, `password`). Mengembalikan JWT (`role="user"`) dan profil user. Gagal berulang mengembalikan HTTP 429. |
| `POST /api/users/google` | Login atau registrasi otomatis akun pembeli menggunakan Google ID Token (`{"id_token": "..."}`, berlaku untuk Web GIS & Android APK). Mengembalikan JWT (`role="user"`) dan profil user. |
| `GET /api/users/oauth-config` | Konfigurasi publik otentikasi klien (`google_enabled`, `google_client_id`, `google_android_client_id`, `terms_version`). |
| `GET /api/users/me` | Profil akun pembeli yang sedang login (`id`, `name`, `email`, `role`, `auth_provider`, `avatar_url`). |
| `POST /api/admin/login` | Login portal Admin terpisah (`/admin`, `{"password": "..."}`). Mengembalikan JWT khusus Admin (`role="admin"`). |
| `GET /api/devices` | Daftar perangkat dan status dinamis (`online`/`offline`). Token `user` hanya melihat perangkat dengan `owner_user_id = user.id`; token `admin` melihat semua. Parameter opsional `include_latest=true`. |
| `POST /api/devices` | Daftarkan atau klaim perangkat (`id`, `name`, `location` opsional, `mcb_watt` 100..25000, `claim` opsional default `false`). Untuk token `user`, mengklaim unit tak bertuan (`owner_user_id = NULL`) ke akun user; menolak (`409`) bila sudah dimiliki akun lain. |
| `PATCH /api/devices/{id}` | Perbarui metadata perangkat (`name`, `location`, `mcb_watt`). Token `user` dibatasi hanya pada perangkat miliknya (`403` bila bukan pemilik). |
| `DELETE /api/devices/{id}` | Hapus perangkat beserta data telemetri dan anomali terkait (khusus pemilik atau admin). Mengembalikan `200` `{"deleted": true, "id": "..."}` atau `404` jika tidak ada. |
| `GET /api/devices/{id}/latest` | Pembacaan terakhir (`ts`, `v`, `i`, `p`, `e`, `f`, `pf`, `rssi`) |
| `GET /api/devices/{id}/series?from=&to=&resolution=auto\|raw\|5m\|1h\|1d` | Data deret waktu (`ts`, `p`, `p_max`, `p_min`, `v`). Resolusi otomatis: <= 5 jam (raw 10s), > 5 jam s.d. 3 hari (5 menit on-the-fly), > 3 hari s.d. 60 hari (`hourly_stats`, `v: null`), > 60 hari (`daily_stats`, `v: null`). Respons memuat `interval_seconds` dan `truncated: bool` (jika > 2000 titik). Resolusi eksplisit yang menghasilkan > 2000 titik dipotong tepat di 2000 titik dan `truncated: true` (tidak pernah mengembalikan ratusan ribu titik). Validasi: `from > to` atau rentang > 366 hari mengembalikan HTTP 422. |
| `GET /api/devices/{id}/summary?range=today\|week\|month&from=&to=` | Rangkuman periode (`from`, `to`, `kwh`, `cost_rp`, `avg_power_w`, `peak_w`, `peak_ts`, `tariff_sen`, `cost_estimated: bool`). Mendukung parameter `range=today\|week\|month` (WIB, minggu mulai Senin) ATAU `from`/`to` (epoch UTC). Parameter `range` bersama `from`/`to` menghasilkan HTTP 422. Validasi `from > to` atau rentang > 366 hari menghasilkan HTTP 422. Biaya pas batas hari memakai akumulasi `daily_stats.cost_rp` (tarif beku, `cost_estimated: false`); sub-hari memakai kWh per jam x tarif hari itu (`cost_estimated: true`). |
| `GET /api/devices/{id}/forecast` | Proyeksi kWh dan biaya akhir bulan berdasarkan rata-rata 7 hari penuh terakhir (`samples >= 90% x 8640`). Respons: `available: bool`, `basis_days`, `low_confidence: bool`, `avg_daily_kwh`, `month_so_far_kwh`, `month_so_far_cost_rp`, `projected_kwh`, `projected_cost_rp`. |
| `GET /api/anomalies?device_id=&from=` | Daftar anomali (token `user` hanya melihat anomali dari perangkat miliknya). |
| `GET /api/settings` | Pengambilan pengaturan aktif (untuk `user`, memadukan preferensi `user_settings` dengan default global). |
| `PATCH /api/settings` | Pembaruan pengaturan (`tariff_rp`, `power_limit_w`, `alert_cooldown_min`, `extra_percent`, `report_hour`). Untuk `user`, disimpan per tenant di `user_settings`. |
| `GET /api/public/access` | Status publik `{"public_read_enabled": bool}` untuk mode Tanpa Login. |
| `GET /api/public/*` | Endpoint pantau *read-only* tanpa login hanya untuk perangkat bertanda `is_public_demo = 1` (`/devices`, `/devices/{id}/latest`, `/series`, `/summary`, `/forecast`, `/anomalies`, `/settings`) saat `public_read_enabled = true`; mengembalikan `401` bila dinonaktifkan Admin atau `404` untuk perangkat privat. |
| `GET /api/admin/overview` | Ringkasan sistem Panel Admin (total/online/offline unit, tenant/user aktif, anomali 7 hari, status MQTT/worker/scheduler/bot, flag akses publik). Wajib `role="admin"`. |
| `GET/POST /api/admin/users`, `PATCH/DELETE /api/admin/users/{id}` | Manajemen akun tenant/pembeli dari Panel Admin (`role="admin"`). |
| `GET /api/admin/devices`, `PATCH /api/admin/devices/{id}` | Inventaris semua perangkat beserta pemilik, toggle `is_public_demo`, dan pengalihan `owner_user_id`. Wajib `role="admin"`. |
| `GET /api/admin/anomalies` | Log anomali lintas semua perangkat dengan filter `device_id`, `severity`, `from`, `limit`. Wajib `role="admin"`. |
| `GET /api/admin/access`, `PATCH /api/admin/access` | Membaca dan mengubah kebijakan `public_read_enabled`. Wajib `role="admin"`. |
| `GET /healthz` | Health check (publik) |

Format error: objek `error` berisi `code` dan `message`. Seluruh endpoint `/api/admin/*` (kecuali `/api/admin/login`) wajib Bearer JWT `role="admin"` (`403` untuk token `user`). Seluruh mutasi (`POST`, `PATCH`, `DELETE`) dan rute `/api/devices*`, `/api/anomalies`, `/api/settings` wajib Bearer JWT. Rute `/api/public/*` hanya mengizinkan `GET` pada unit `is_public_demo = 1` saat `public_read_enabled = true`.

## 3. Model data
```
users(id PK, email UNIQUE, name, password_hash, auth_provider, google_sub UNIQUE NULL, avatar_url NULL, is_active, created_at, last_login_at)
user_settings(user_id PK, key PK, value)
devices(id PK, name, location, mcb_watt, owner_user_id FK->users.id NULL, is_public_demo DEFAULT 0, created_at, last_seen_at, last_data_ts, status)
readings(id PK, device_id, ts, v, i, p, e_kwh, delta_kwh, f, pf, rssi, is_gap)
   index dan unique (device_id, ts)
hourly_stats(device_id, hour_start, kwh, p_avg, p_max, p_min, samples)   PK (device_id, hour_start)
daily_stats(device_id, day, kwh, cost_rp, tariff_sen, p_max, p_base)      PK (device_id, day)
anomalies(id PK, device_id, ts, type, severity, details_json, message, notified)
alert_state(device_id, alert_type, state, since, last_notified_at, details_json)   PK (device_id, alert_type)
scheduled_reports_log(report_type, report_date, sent_at)   PK (report_type, report_date)
settings(key PK, value)   -- tariff_sen_per_kwh, extra_percent, power_limit_w, alert_cooldown_min, report_hour, report_enabled
telegram_users(chat_id PK, name)
chat_log(id PK, chat_id, ts, question, tools_used, answer, tokens)
```
- `cost_rp`: `INTEGER` (Rupiah bulat, dihitung menggunakan Python `Decimal` dengan pembulatan `ROUND_HALF_UP`).
- `tariff_sen`: `INTEGER` (tarif per kWh dalam satuan sen, misal Rp1.444,70/kWh disimpan sebagai 144470).
- `kwh`, `delta_kwh`, `e_kwh`: `REAL` (dibulatkan 3 desimal).
- `is_gap`: `INTEGER` (1 jika selisih waktu $\Delta t > 3 \times \text{interval publish}$, default 0; replay buffer normal bukan gap).
- `p_base`: `REAL`, bernilai `NULL` sebelum pukul 05.00 WIB.
- `alert_state`:
  - `device_id`: `VARCHAR(64)`
  - `alert_type`: `VARCHAR(32)` (`power_limit`, `voltage_low`, `voltage_high`, `offline`, `spike_vs_baseline`, `night_baseload`)
  - `state`: `VARCHAR(16)` (`active`, `cleared`)
  - `since`, `last_notified_at`: `INTEGER` (epoch detik UTC)
  - `details_json`: `TEXT` (metadata pemicu)
  - Diperbarui hanya setelah pengiriman notifikasi berhasil.
- `scheduled_reports_log`:
  - `report_type`: `VARCHAR(16)` (`daily`, `weekly`)
  - `report_date`: `VARCHAR(10)` (`YYYY-MM-DD` WIB)
  - `sent_at`: `INTEGER` (epoch detik UTC)
  - Ditulis HANYA setelah pengiriman laporan sukses untuk menjamin idempotensi jadwal.
- Ambang batas tegangan ($200\text{ V}$ dan $240\text{ V}$, histeresis pemulihan $205\text{ V} - 235\text{ V}$) adalah konstanta konfigurasi aplikasi (`VOLTAGE_MIN_V`, `VOLTAGE_MAX_V`), bukan entri tabel `settings`.

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
  - Input tarif via API / Telegram menerima angka desimal (titik atau koma), maksimal 2 digit di belakang koma, dan dikonversi ke integer sen di batas input. Input lebih dari 2 desimal ditolak.
- **Proyeksi bulan (Forecast)**:
  - Definisi hari penuh: total sampel $\ge 90\% \times 8640 = 7.776$ sampel. Hari parsial (< 7.776 sampel) dikecualikan dari basis rata-rata harian.
  - Basis: 7 hari penuh terakhir yang punya data sebelum hari ini (`day < today_wib`).
  - Jika tidak ada data hari penuh ($N_{\text{basis}} == 0$), kembalikan `available: false` (bukan 0).
  - Jika $N_{\text{basis}} < 3$, set `low_confidence: true`.
  - Formula proyeksi kWh:
    $$\text{projected\_kwh} = \text{month\_so\_far\_kwh} + \max(\text{avg\_daily\_kwh} - \text{today\_kwh}, 0) + (\text{sisa\_hari} \times \text{avg\_daily\_kwh})$$
    dengan `month_so_far_kwh` adalah total konsumsi seluruh hari yang memiliki data di bulan kalender berjalan (termasuk hari ini), dan `sisa_hari` adalah hari kalender yang tersisa di bulan berjalan setelah hari ini.
  - `projected_cost_rp` dihitung dari `projected_kwh` dengan formula biaya di atas menggunakan tarif aktif dan extra_percent.
