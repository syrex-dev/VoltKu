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
| `POST /api/users/register` | Registrasi akun pembeli multi-tenant (`name`, `email`, `password` min 6 karakter, opsional `accept_terms` / `client_id`). Mengembalikan HTTP `201` dengan JWT (`role="user"`) dan profil user serta mencatat persetujuan legal ke database. |
| `POST /api/users/login` | Login akun pembeli (`email`, `password`, opsional `accept_terms` / `client_id`). Mengembalikan JWT (`role="user"`) dan profil user. Gagal berulang mengembalikan HTTP 429. |
| `POST /api/users/forgot-password`, `POST /api/users/reset-password` | Meminta tautan reset kata sandi ke email (respons netral `200`, rate-limit ketat) dan menyetel ulang kata sandi memakai token SHA-256 hash sekali pakai (kedaluwarsa 30 menit). |
| `POST /api/users/google` | Login atau registrasi otomatis akun pembeli menggunakan Google ID Token (`{"id_token": "...", "accept_terms": bool, "client_id": "..."}`, berlaku untuk Web GIS & Android APK). Mengembalikan JWT (`role="user"`) dan profil user. |
| `GET /api/users/oauth-config` | Konfigurasi publik otentikasi klien (`google_enabled`, `google_client_id`, `google_android_client_id`, `terms_version`). |
| `GET /api/users/me`, `POST /api/users/logout-all` | Mengambil profil akun pembeli login (`id`, `name`, `email`, `role`, `auth_provider`, `avatar_url`, `terms_version_accepted`, `terms_accepted_at`, `needs_terms_reconsent`, `plan`), serta mencabut seluruh token JWT aktif user di semua perangkat dengan menaikkan `token_version`. |
| `POST /api/users/change-password` | Mengubah kata sandi akun (atau menambah sandi lokal bagi pengguna Google), sekaligus menaikkan `token_version` untuk mencabut sesi lama dan mengembalikan `token` baru. |
| `POST /api/users/terms-consent` | Menyimpan/memperbarui persetujuan Syarat & Ketentuan + Privasi pengguna login ke `users` & `terms_consents`. |
| `GET /api/users/upgrade-request`, `POST /api/users/upgrade-request` | Melihat riwayat pengajuan upgrade user aktif dan membuat tagihan upgrade ke paket berbayar aktif (`plan_slug` opsional default `pro`, `billing_cycle`: `monthly` \| `yearly`, `discount_code`, `payment_method_id` & `user_note` opsional). |
| `POST /api/users/apply-discount` | Validasi kode promo/kupon terhadap paket & siklus terpilih serta menghitung pratinjau rincian potongan promo + voucher (`base_amount_rp`, `promo_discount_rp`, `voucher_discount_rp`, `final_amount_rp`). |
| `POST /api/users/upgrade-requests/{id}/confirm-payment`, `POST /api/users/upgrade-requests/{id}/cancel`, `GET /api/users/upgrade-requests/{id}/proof` | Mengirim konfirmasi bayar beserta unggahan bukti transfer (`proof_base64` gambar JPG/PNG/WebP, berstatus `verifying`), membatalkan tagihan yang belum diverifikasi (`cancelled`), dan mengunduh pratinjau bukti bayar milik sendiri. |
| `GET /api/public/plans`, `GET /api/public/payment-methods`, `GET /api/payment-methods/{id}/qris` | Daftar paket langganan aktif beserta harga promo, daftar metode pembayaran manual aktif (QRIS, Bank, E-Wallet), dan gambar QRIS terkait. |
| `POST /api/admin/login` | Login portal Admin terpisah (`/admin`, `{"password": "..."}`). Mengembalikan JWT khusus Admin (`role="admin"`). |
| `GET /api/devices` | Daftar perangkat dan status dinamis (`online`/`offline`). Token `user` hanya melihat perangkat dengan `owner_user_id = user.id` beserta indikator `quota_exceeded`; token `admin` melihat semua. Parameter opsional `include_latest=true`, `limit`, `offset`. |
| `POST /api/devices` | Daftarkan atau klaim perangkat (`id`, `name`, `location` opsional, `mcb_watt` 100..25000, `claim` opsional default `false`). Untuk token `user`, mengklaim unit tak bertuan (`owner_user_id = NULL`) ke akun user; menolak (`409`) bila sudah dimiliki akun lain, serta menolak (`403`) bila kuota panel paket user (`max_devices`) terpenuhi saat `freemium_enabled = true`. |
| `PATCH /api/devices/{id}` | Perbarui metadata perangkat (`name`, `location`, `mcb_watt`). Token `user` dibatasi hanya pada perangkat miliknya (`403` bila bukan pemilik). |
| `DELETE /api/devices/{id}` | Hapus perangkat beserta data telemetri dan anomali terkait (khusus pemilik atau admin). Mengembalikan `200` `{"deleted": true, "id": "..."}` atau `404` jika tidak ada. |
| `GET /api/devices/{id}/latest` | Pembacaan terakhir (`ts`, `v`, `i`, `p`, `e`, `f`, `pf`, `rssi`) |
| `GET /api/devices/{id}/series?from=&to=&resolution=auto\|raw\|5m\|1h\|1d` | Data deret waktu (`ts`, `p`, `p_max`, `p_min`, `v`). Resolusi otomatis: <= 5 jam (raw 10s), > 5 jam s.d. 3 hari (5 menit on-the-fly), > 3 hari s.d. 60 hari (`hourly_stats`, `v: null`), > 60 hari (`daily_stats`, `v: null`). Untuk akun `user` paket `free` saat `freemium_enabled = true`, rentang historis dibatasi sesuai `history_days` paket (mengembalikan HTTP `403` bila melebihi batas hari paket). Respons memuat `interval_seconds` dan `truncated: bool` (jika > 2000 titik). Validasi: `from > to` atau rentang > 366 hari mengembalikan HTTP 422. |
| `GET /api/devices/{id}/summary?range=today\|week\|month&from=&to=` | Rangkuman periode (`from`, `to`, `kwh`, `cost_rp`, `avg_power_w`, `peak_w`, `peak_ts`, `tariff_sen`, `cost_estimated: bool`). Mendukung parameter `range=today\|week\|month` (WIB, minggu mulai Senin) ATAU `from`/`to` (epoch UTC). Parameter `range` bersama `from`/`to` menghasilkan HTTP 422. Validasi `from > to` atau rentang > 366 hari menghasilkan HTTP 422. Biaya pas batas hari memakai akumulasi `daily_stats.cost_rp` (tarif beku, `cost_estimated: false`); sub-hari memakai kWh per jam x tarif hari itu (`cost_estimated: true`). |
| `GET /api/devices/{id}/forecast` | Proyeksi kWh dan biaya akhir bulan berdasarkan rata-rata 7 hari penuh terakhir (`samples >= 90% x 8640`). Mengembalikan HTTP `403` untuk akun `user` paket `free` bila `free_forecast_enabled = false`. Respons: `available: bool`, `basis_days`, `low_confidence: bool`, `avg_daily_kwh`, `month_so_far_kwh`, `month_so_far_cost_rp`, `projected_kwh`, `projected_cost_rp`. |
| `GET /api/devices/{id}/export?days=30` | Mengunduh laporan konsumsi harian perangkat berformat CSV (`text/csv`). Memerlukan fitur ekspor aktif (`pro` atau `free_export_enabled = true` atau `role="admin"`). |
| `GET /api/anomalies?device_id=&from=` | Daftar anomali (token `user` hanya melihat anomali perangkat miliknya; tipe lanjutan `l2_spike` & `l3_baseload` disaring bila `anomaly_advanced = false`). |
| `POST /api/chat`, `GET /api/chat/history` | Asisten AI Chat (`{"question": "..."}`) dengan tool deterministik, rate limit 20 pesan/jam/user, audit `chat_log`, dan riwayat pertanyaan. Wajib Bearer JWT. |
| `POST /api/users/push-token`, `DELETE /api/users/push-token` | Registrasi atau penonaktifan token push notifikasi (`android`, `ios`, `web`) untuk pengguna login (FCM HTTP v1). |
| `GET /api/users/notifications`, `POST /api/users/notifications/read` | Mengambil inbox notifikasi tenant (mendukung sinkronisasi inkremental `since_id` oleh worker APK) dan menandai notifikasi sudah dibaca. |
| `GET /api/settings` | Pengambilan pengaturan aktif (untuk `user`, memadukan preferensi `user_settings` dengan default global). |
| `PATCH /api/settings` | Pembaruan pengaturan (`tariff_rp`, `power_limit_w`, `alert_cooldown_min`, `extra_percent`, `report_hour`, `report_timezone`, `report_enabled`). Untuk `user`, disimpan per tenant di `user_settings` dan dipakai penjadwal rekap per zona waktu (WIB/WITA/WIT). |
| `GET /api/public/sync-state`, `GET /api/users/sync-state`, `GET /api/admin/sync-state` | Snapshot revisi ringan untuk sinkronisasi real-time paket, metode bayar, profil, notifikasi, & transaksi antara Publik, User, dan Admin. |
| `GET /api/public/access` | Status publik `{"public_read_enabled": bool}` untuk mode Tanpa Login. |
| `GET /api/public/app-config` | Konfigurasi aplikasi publik non-rahasia (identitas brand, format navbar, pengumuman, tema default, langkah panduan, status auth & Google Sign-In, dokumen Syarat & Ketentuan + Privasi, konfigurasi tampilan paket Freemium, serta kontak dukungan). |
| `POST /api/public/terms-consent` | Mencatat persetujuan Syarat & Ketentuan + Kebijakan Privasi sesi pengunjung/instalasi aplikasi ke `terms_consents`. |
| `GET /api/public/*` | Endpoint pantau *read-only* tanpa login hanya untuk perangkat bertanda `is_public_demo = 1` (`/devices`, `/devices/{id}/latest`, `/series`, `/summary`, `/forecast`, `/anomalies`, `/settings`) saat `public_read_enabled = true`; mengembalikan `401` bila dinonaktifkan Admin atau `404` untuk perangkat privat. |
| `GET /api/admin/overview` | Ringkasan sistem Panel Admin (total/online/offline unit, tenant/user aktif, anomali 7 hari, status MQTT/worker/scheduler/bot, flag akses publik). Wajib `role="admin"`. |
| `GET/POST /api/admin/users`, `PATCH/DELETE /api/admin/users/{id}` | Manajemen akun tenant/pembeli dari Panel Admin (`role="admin"`, mendukung paginasi `limit` & `offset`), termasuk pengaturan paket (`plan_tier`, `plan_expires_at` / masa aktif hari). |
| `GET /api/admin/upgrade-requests`, `PATCH /api/admin/upgrade-requests/{id}`, `GET /api/admin/upgrade-requests/{id}/proof` | Daftar tagihan & bukti pembayaran upgrade pengguna, pratinjau foto bukti transfer, serta konfirmasi persetujuan/penolakan oleh Admin (`approve` otomatis mengaktifkan paket target pada user dan menghitung `plan_expires_at`). |
| `GET/POST /api/admin/plans`, `PATCH/DELETE /api/admin/plans/{id}` | Manajemen CRUD paket langganan dinamis (harga dasar, kuota panel/hari, hak fitur, promo harga coret berbatas waktu, urutan, status aktif) oleh Admin (`role="admin"`). |
| `GET/POST /api/admin/discounts`, `PATCH/DELETE /api/admin/discounts/{id}` | Manajemen CRUD kode promo/voucher diskon (`percent` atau `fixed_rp`, batas maksimal potongan, minimal pembelian, kuota pakai, target paket/durasi, periode berlaku) oleh Admin (`role="admin"`). |
| `GET/POST /api/admin/payment-methods`, `PATCH/DELETE /api/admin/payment-methods/{id}`, `POST /api/admin/payment-methods/{id}/qris` | Manajemen metode pembayaran manual (QRIS + unggah gambar QRIS, Transfer Bank, E-Wallet) dari Panel Admin (`role="admin"`). |
| `GET /api/admin/devices`, `PATCH /api/admin/devices/{id}` | Inventaris perangkat (mendukung paginasi `limit` & `offset`) beserta pemilik, toggle `is_public_demo`, dan pengalihan `owner_user_id`. Wajib `role="admin"`. |
| `GET /api/admin/anomalies` | Log anomali lintas semua perangkat dengan filter `device_id`, `severity`, `from`, `limit`. Wajib `role="admin"`. |
| `GET /api/admin/access`, `PATCH /api/admin/access` | Membaca dan mengubah kebijakan `public_read_enabled`. Wajib `role="admin"`. |
| `GET /api/admin/app-settings`, `PATCH /api/admin/app-settings` | Membaca dan menyimpan seluruh pengaturan aplikasi (identitas, branding navbar, panduan, autentikasi/Google Client ID, teks/versi Syarat & Ketentuan + Privasi, paket & kuota Freemium, operasional default, kontak dukungan). Wajib `role="admin"`. |
| `GET /api/admin/consents` | Audit riwayat persetujuan Syarat & Ketentuan dan Kebijakan Privasi seluruh pengguna & sesi tamu (mendukung `limit` & `offset`). Wajib `role="admin"`. |
| `GET /healthz` | Health check (publik) |

Format error: objek `error` berisi `code` dan `message`. Seluruh endpoint `/api/admin/*` (kecuali `/api/admin/login`) wajib Bearer JWT `role="admin"` (`403` untuk token `user`). Seluruh mutasi (`POST`, `PATCH`, `DELETE`) dan rute `/api/devices*`, `/api/anomalies`, `/api/settings` wajib Bearer JWT. Rute `/api/public/*` hanya mengizinkan `GET` pada unit `is_public_demo = 1` saat `public_read_enabled = true`.

## 3. Model data
```
users(id PK, email UNIQUE, name, password_hash, auth_provider, google_sub UNIQUE NULL, avatar_url NULL, terms_version_accepted NULL, terms_accepted_at NULL, plan_tier DEFAULT 'free', plan_id NULL FK->subscription_plans.id, plan_expires_at NULL, plan_updated_at NULL, is_active, token_version DEFAULT 0, created_at, last_login_at)
subscription_plans(id PK, slug UNIQUE, name, description NULL, badge_text NULL, price_monthly_rp DEFAULT 0, price_yearly_rp DEFAULT 0, promo_discount_type NULL, promo_discount_value DEFAULT 0, promo_label NULL, promo_starts_at NULL, promo_expires_at NULL, max_devices DEFAULT 1, history_days DEFAULT 3, forecast_enabled DEFAULT 0, export_enabled DEFAULT 0, anomaly_advanced DEFAULT 0, features_json NULL, is_default_free DEFAULT 0, is_recommended DEFAULT 0, is_active DEFAULT 1, sort_order DEFAULT 0, created_at, updated_at)
discount_codes(id PK, code UNIQUE, label NULL, discount_type, discount_value, max_discount_rp NULL, min_purchase_rp DEFAULT 0, target_plan_slug NULL, target_cycle NULL, max_uses NULL, used_count DEFAULT 0, starts_at NULL, expires_at NULL, is_active DEFAULT 1, created_at, updated_at)
password_reset_tokens(id PK, user_id FK->users.id, token_hash UNIQUE, expires_at, used_at NULL, created_at)
terms_consents(id PK, user_id FK->users.id NULL, email_snapshot NULL, client_id NULL, terms_version, privacy_version, accepted_via, ip_address NULL, user_agent NULL, accepted_at)
upgrade_requests(id PK, user_id FK->users.id, order_code UNIQUE NULL, requested_tier DEFAULT 'pro', plan_id NULL FK->subscription_plans.id, plan_name_snapshot NULL, billing_cycle DEFAULT 'monthly', base_amount_rp DEFAULT 0, promo_discount_rp DEFAULT 0, discount_code_id NULL FK->discount_codes.id, discount_code NULL, voucher_discount_rp DEFAULT 0, amount_rp, payment_method_id NULL, payment_method_type NULL, payment_method_label NULL, payment_account_number NULL, payment_account_holder NULL, payment_instructions NULL, payment_proof_path NULL, status DEFAULT 'pending', user_note NULL, admin_note NULL, expires_at NULL, submitted_at NULL, created_at, resolved_at NULL)
payment_methods(id PK, type, label, account_number NULL, account_holder NULL, qris_image_path NULL, instructions NULL, is_active DEFAULT 1, sort_order DEFAULT 0, created_at)
user_settings(user_id PK, key PK, value)
devices(id PK, name, location, mcb_watt, owner_user_id FK->users.id NULL, is_public_demo DEFAULT 0, created_at, last_seen_at, last_data_ts, status)
readings(id PK, device_id, ts, v, i, p, e_kwh, delta_kwh, f, pf, rssi, is_gap)
   index dan unique (device_id, ts)
hourly_stats(device_id, hour_start, kwh, p_avg, p_max, p_min, samples)   PK (device_id, hour_start)
daily_stats(device_id, day, kwh, cost_rp, tariff_sen, p_max, p_base)      PK (device_id, day)
anomalies(id PK, device_id, ts, type, severity, details_json, message, notified)
alert_state(device_id, alert_type, state, since, last_notified_at, details_json)   PK (device_id, alert_type)
scheduled_reports_log(report_type, report_date, sent_at)   PK (report_type, report_date)
settings(key PK, value)   -- tariff_sen_per_kwh, extra_percent, power_limit_w, alert_cooldown_min, report_hour, report_timezone, report_enabled
app_config(key PK, value TEXT, updated_at)   -- branding, panduan, legal/terms, auth toggles, paket freemium, kontak dukungan
telegram_users(chat_id PK, name)
chat_log(id PK, chat_id, ts, question, tools_used, answer, tokens)
push_tokens(id PK, user_id FK->users.id, token UNIQUE, platform, device_label NULL, is_active DEFAULT 1, created_at, updated_at)
user_notifications(id PK, user_id FK->users.id, device_id NULL, title, body, category, severity, data_json NULL, event_key UNIQUE NULL, is_read DEFAULT 0, pushed_fcm DEFAULT 0, created_at)
```
- `cost_rp`: `INTEGER` (Rupiah bulat, dihitung menggunakan Python `Decimal` dengan pembulatan `ROUND_HALF_UP`).
- `tariff_sen`: `INTEGER` (tarif per kWh dalam satuan sen, misal Rp1.444,70/kWh disimpan sebagai 144470).
- `kwh`, `delta_kwh`, `e_kwh`: `REAL` (dibulatkan 3 desimal).
- `is_gap`: `INTEGER` (1 jika selisih waktu $\Delta t > 3 \times \text{interval publish}$, default 0; replay buffer normal bukan gap).
- `p_base`: `REAL`, bernilai `NULL` sebelum pukul 05.00 WIB.
- `alert_state`:
  - `device_id`: `VARCHAR(64)`
  - `alert_type`: `VARCHAR(32)` (`power_limit`, `voltage_low`, `voltage_high`, `offline`, `anomaly_l2`, `anomaly_l3`)
  - `state`: `VARCHAR(16)` (`active`, `cleared`)
  - `since`, `last_notified_at`: `INTEGER` (epoch detik UTC)
  - `details_json`: `TEXT` (metadata pemicu)
  - Diperbarui hanya setelah pengiriman notifikasi berhasil.
- `scheduled_reports_log`:
  - `report_type`: `VARCHAR(16)` (`daily`, `weekly`, atau per tenant `u{id}:d`, `u{id}:w`)
  - `report_date`: `VARCHAR(10)` (`YYYY-MM-DD` sesuai zona waktu aktif)
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
