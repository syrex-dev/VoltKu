# Laporan Komprehensif Pengembangan: Monitor Listrik Pintar (IoT + AI)

Dokumen ini menyajikan rekam jejak teknis, arsitektur, implementasi kode, hasil verifikasi nyata, serta milestone proyek **Monitor Listrik Pintar** dari awal pengerjaan hingga status pengujian terakhir sebelum memasuki tahap implementasi Milestone M2.

---

## 1. Ikhtisar & Landasan Proyek

Proyek ini bertujuan membangun sistem pemantauan konsumsi energi listrik rumah tangga berbasis IoT dan analisis AI yang handal, presisi, dan aman.

- **Perangkat Keras (Firmware Target)**: ESP32 + PZEM-004T v3.0 (CT Clamp 100A).
- **Protokol Komunikasi**: MQTT via Eclipse Mosquitto 2.0 (TLS/Auth).
- **Backend Service**: Python 3.11/3.12, FastAPI, SQLAlchemy 2 (Core & ORM), SQLite dalam mode WAL (Write-Ahead Logging).
- **Frontend / Dashboard**: Single Page Application (HTML5, Vanilla CSS/JS mobile-first, Chart.js).
- **Prinsip Utama (`AGENTS.md`)**:
  - **Integritas Uang**: Biaya disimpan sebagai integer Rupiah (`cost_rp`), tarif dalam integer sen (`tariff_sen`), dan kalkulasi matematis menggunakan pustaka deterministik `Decimal` dengan pembulatan `ROUND_HALF_UP`. Tidak ada penggunaan tipe data floating-point pada kalkulasi moneter.
  - **Waktu & Zona**: Seluruh pencatatan timestamp internal disimpan dalam format epoch UTC; agregasi harian dan tampilan antarmuka disesuaikan dengan zona waktu Asia/Jakarta (WIB, UTC+7).
  - **Determinisme Data**: LLM tidak diperbolehkan menghitung angka statistik; semua metrik daya, energi, dan biaya berasal dari fungsi deterministik backend.
  - **Keamanan Kredensial**: Tidak ada rahasia, token, atau password yang di-hardcode ke repositori; konfigurasi dibaca eksklusif melalui environment variable (`.env`).

---

## 2. Milestone M0: Fondasi Proyek, Docker, dan Healthcheck

Tujuan Milestone M0 adalah menyiapkan struktur repositori terstandarisasi, alur pengujian otomatis, containerization Docker, dan broker MQTT.

### Implementasi & Arsitektur
1. **Standarisasi Repositori**:
   - Pembuatan [.gitattributes](file:///c:/Users/deder/Music/energy-monitor/.gitattributes) (`* text=auto eol=lf`) untuk konsistensi cross-platform antara host Windows dan lingkungan Linux (WSL/Docker).
   - Konfigurasi [.gitignore](file:///c:/Users/deder/Music/energy-monitor/.gitignore) untuk mengisolasi file rahasia (`.env`, `deploy/passwd`, `firmware/include/config.h`) dan file database lokal.
   - Template konfigurasi lingkungan [.env.example](file:///c:/Users/deder/Music/energy-monitor/.env.example).
2. **Pemisahan Dependensi**:
   - [backend/requirements.txt](file:///c:/Users/deder/Music/energy-monitor/backend/requirements.txt): Runtime dependencies (`fastapi`, `uvicorn`, `pydantic-settings`).
   - [backend/requirements-dev.txt](file:///c:/Users/deder/Music/energy-monitor/backend/requirements-dev.txt): Testing dan linting (`pytest`, `httpx`, `ruff`).
3. **Konfigurasi & Service Health**:
   - [backend/app/config.py](file:///c:/Users/deder/Music/energy-monitor/backend/app/config.py): Kelas `Settings` berbasis `pydantic-settings` dengan nilai default non-rahasia sehingga test suite dapat dijalankan tanpa dependensi file `.env`.
   - [backend/app/main.py](file:///c:/Users/deder/Music/energy-monitor/backend/app/main.py): Endpoint publik tanpa auth `GET /healthz` yang mengembalikan `{"status": "ok"}`.
4. **Containerization & Deployment**:
   - [backend/Dockerfile](file:///c:/Users/deder/Music/energy-monitor/backend/Dockerfile): Base image `python:3.11-slim` dengan pengguna non-root `appuser` (keamanan container) dan [.dockerignore](file:///c:/Users/deder/Music/energy-monitor/backend/.dockerignore).
   - [deploy/docker-compose.yml](file:///c:/Users/deder/Music/energy-monitor/deploy/docker-compose.yml): Orkestrasi service `energy_backend` (port 8000) dan `energy_mosquitto` (port 1883).
   - [deploy/mosquitto.conf](file:///c:/Users/deder/Music/energy-monitor/deploy/mosquitto.conf): Broker MQTT dengan `allow_anonymous false`, autentikasi file password, dan konfigurasi ACL.
   - [deploy/README.md](file:///c:/Users/deder/Music/energy-monitor/deploy/README.md): Dokumentasi langkah inisialisasi password Mosquitto via Docker CLI.

---

## 3. Revisi Kontrak Data & Regulasi Moneter (M1 Preparation)

Sebelum penulisan kode M1, dilakukan peninjauan terhadap kontrak awal di `docs/05-DATA-CONTRACT.md`. Ditemukan bahwa kolom biaya (`cost_rp`) dan tarif (`tariff_rp`) awalnya bertipe `REAL` (float), yang melanggar aturan integritas moneter pada `AGENTS.md`.

### Revisi Formal yang Disetujui:
1. **Penyimpanan Tarif & Biaya**:
   - Kolom tabel `daily_stats.tariff_sen`: disimpan sebagai **integer sen per kWh** (contoh: Rp 1.444,70 disimpan sebagai `144470`).
   - Kolom tabel `daily_stats.cost_rp`: disimpan sebagai **integer Rupiah**.
   - Input tarif dari API/Telegram menerima desimal Rupiah (koma atau titik), yang dikonversi ke sen di boundary layer.
2. **Formula Perhitungan Deterministik**:
   Perhitungan menggunakan pustaka `Decimal` murni tanpa konversi float perantara:
   $$\text{cost\_rp} = \text{quantize}\left(\frac{\text{Decimal}(kwh) \times \text{Decimal}(\text{tariff\_sen}) \times (100 + \text{extra\_percent})}{10000}, \text{ROUND\_HALF\_UP}\right)$$
3. **Pembaruan Dokumen**:
   - Perubahan disahkan pada [docs/05-DATA-CONTRACT.md](file:///c:/Users/deder/Music/energy-monitor/docs/05-DATA-CONTRACT.md), [docs/02-SRS.md](file:///c:/Users/deder/Music/energy-monitor/docs/02-SRS.md) (BE-07), dan [docs/08-TELEGRAM-BOT.md](file:///c:/Users/deder/Music/energy-monitor/docs/08-TELEGRAM-BOT.md).

---

## 4. Milestone M1: Ingest Telemetry, SQLite WAL, Agregasi, dan Simulator

Milestone M1 membangun inti pemrosesan data (data ingestion engine), integritas data sensor, serta kalkulasi energi dan biaya.

### Komponen Kunci yang Dibangun:
1. **Model Data SQLAlchemy 2.0 ([backend/app/models.py](file:///c:/Users/deder/Music/energy-monitor/backend/app/models.py))**:
   - `Device`: metadata perangkat (`id`, `name`, `location`, `mcb_watt`, `status`, `last_seen_at`, `last_data_ts`).
   - `Reading`: data telemetri 10 detik (`ts`, `v`, `i`, `p`, `e_kwh`, `delta_kwh`, `f`, `pf`, `rssi`, `is_gap`) dengan index komposit unik `(device_id, ts)`.
   - `HourlyStat`: agregat per jam UTC (`hour_start`, `kwh`, `p_avg`, `p_max`, `p_min`, `samples`).
   - `DailyStat`: agregat harian WIB (`day`, `kwh`, `cost_rp`, `tariff_sen`, `p_max`, `p_base`).
   - `Setting`: konfigurasi dinamis key-value (`tariff_sen_per_kwh`, `extra_percent`, `power_limit_w`, dll.).
2. **Koneksi Database & WAL Mode ([backend/app/db.py](file:///c:/Users/deder/Music/energy-monitor/backend/app/db.py))**:
   - Mengaktifkan SQLite pragmas: `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA busy_timeout=5000`.
   - Mengeliminasi kemungkinan `database is locked` saat terjadi konkurensi pembacaan dan penulisan.
3. **Validasi Telemetri BE-02 ([backend/app/mqtt_ingest.py](file:///c:/Users/deder/Music/energy-monitor/backend/app/mqtt_ingest.py))**:
   - Rentang operasional: $V \in [0, 300]\text{ V}$, $I \in [0, 100]\text{ A}$, $P \in [0, 25000]\text{ W}$, $E \ge 0\text{ kWh}$.
   - Validasi batas waktu: $ts \ge 1735689600$ (2025-01-01 UTC) dan $ts \le now + 300\text{ s}$ (toleransi drift 5 menit).
4. **Algoritma Delta kWh & Penanganan Anomali ([backend/app/services/delta.py](file:///c:/Users/deder/Music/energy-monitor/backend/app/services/delta.py))**:
   - Baseline pertama diambil dari database (tahan restart aplikasi).
   - Batas lonjakan daya maksimum: $\Delta_{\text{max}} = \frac{1.5 \times \text{mcb\_watt} \times \Delta t}{3.600.000}\text{ kWh}$.
   - Reset counter: jika $e_{\text{baru}} < e_{\text{lama}}$, diperlakukan sebagai reset valid hanya bila $e_{\text{baru}} \le \Delta_{\text{max}}$.
   - Penolakan konsisten: jika terjadi 3 penolakan berturut-turut yang stabil, baseline baru ditetapkan secara otomatis.
   - Deteksi Gap: jika $\Delta t > 3 \times \text{interval publish}$, sampel ditandai sebagai `is_gap = 1` tanpa membuang energi riil.
5. **Rekonsiliasi Out-of-Order / Replay Buffer**:
   - Jika sampel lama tiba terlambat (replay buffer ESP32), backend menghitung delta sampel tersebut terhadap pembacaan sebelum dirinya, lalu merekonsiliasi (mengoreksi) nilai delta sampel berikutnya yang telah tersimpan di database, serta memicu rekalkulasi bucket jam dan hari yang terdampak.
6. **Layanan Ingest Asinkron (`IngestService`)**:
   - Menggunakan `queue.Queue` berkapasitas 1.000 item yang dijembatani oleh satu thread worker penulis (single-writer SQLite architecture).
   - Paho-MQTT 2.x dengan `CallbackAPIVersion.VERSION2`, persistent session (`clean_session=False`), dan pendaftaran topik pada callback `on_connect`.
7. **Agregasi Jam & Hari ([backend/app/services/aggregation.py](file:///c:/Users/deder/Music/energy-monitor/backend/app/services/aggregation.py))**:
   - Batas hari dihitung ketat menurut WIB (`Asia/Jakarta`).
   - Tarif hari lampau dibekukan (`frozen tariff`), sehingga perubahan tarif hari ini tidak mengubah biaya riil hari kemarin.
   - `p_base` (median daya 00.00 - 05.00 WIB) bernilai `NULL` untuk hari berjalan sebelum pukul 05.00 WIB.
8. **Simulator Telemetri ([simulator/publish_fake.py](file:///c:/Users/deder/Music/energy-monitor/simulator/publish_fake.py))**:
   - Mendukung skenario: `normal`, `buffer` (burst flush), `reset` (counter reset), `invalid` (out-of-range), `duplicate` (idempoten), dan `out-of-order`.

---

## 5. LANGKAH 0: Penyempurnaan & Verifikasi Komprehensif Pra-M2

Sebelum memasuki implementasi M2, dilakukan langkah pengetatan, pembersihan data, pengujian properti matematika, dan pembuatan data historis 7 hari.

### Rincian Pelaksanaan & Hasil Aktual

#### 1. Pembaruan Simulator & Direct DB Seed (`--seed-db --backfill-days 7`)
- Menambahkan generator profil beban harian Indonesia realistis:
  - 00:00 - 05:00 WIB: Base load malam (120 - 160 W, kulkas/standby).
  - 05:00 - 08:00 WIB: Beban pagi (400 - 700 W, pompa air/dispenser/rice cooker).
  - 08:00 - 17:00 WIB: Aktivitas siang (250 - 450 W).
  - 17:00 - 22:00 WIB: Puncak malam (750 - 1100 W, lampu/AC/TV).
  - 22:00 - 24:00 WIB: Beban istirahat (250 - 380 W).
  - Derau acak tegangan ($220 \pm 2.5\text{ V}$), frekuensi ($50 \pm 0.1\text{ Hz}$), dan power factor ($0.95 - 0.99$).
- Mode `--seed-db` menyuntikkan data langsung ke database melalui `process_telemetry_payload`:
  - **Total Waktu Eksekusi**: 245,67 detik (~4 menit) untuk 60.480 sampel data.
  - **Jumlah Sampel Tersimpan**: Tepat 60.480 baris `readings`.
  - **Bucket Hourly Stats**: 169 jam (rata-rata 357,9 sampel/jam, mendekati nilai nominal 360 sampel/jam).
  - **Is Gap == 1**: 0 baris (aliran data kontinu sempurna).
  - **Tabel `daily_stats` (8 baris WIB)**:
    - 2026-11-08: 6.162 kWh | Rp 8.902 | P Base: `NULL` (mulai pukul 14:36 WIB).
    - 2026-11-09: 10.933 kWh | Rp 15.795 | P Base: 142.4 W.
    - 2026-11-10: 10.916 kWh | Rp 15.770 | P Base: 142.6 W.
    - 2026-11-11: 10.924 kWh | Rp 15.782 | P Base: 143.0 W.
    - 2026-11-12: 10.934 kWh | Rp 15.796 | P Base: 142.9 W.
    - 2026-11-13: 10.902 kWh | Rp 15.750 | P Base: 142.5 W.
    - 2026-11-14: 10.911 kWh | Rp 15.763 | P Base: 142.5 W.
    - 2026-11-15: 4.744 kWh | Rp 6.854 | P Base: 142.0 W (hari berjalan s.d. 14:36 WIB).

#### 2. Penambahan Kolom Device & Deteksi Offline Dinamis
- Kolom `last_seen_at` dan `last_data_ts` ditambahkan ke model `Device`.
- Logika proteksi: replay buffer masa lampau tidak memundurkan `last_seen_at` maupun `last_data_ts`.
- Fungsi `get_device_status(device, now_utc)` menentukan status `offline` jika `now - last_seen_at > 120` detik atau `device.status == "offline"`.

#### 3. Pengetatan ACL Mosquitto & Hasil Uji Nyata
File [deploy/acl](file:///c:/Users/deder/Music/energy-monitor/deploy/acl) disederhanakan tanpa izin baca untuk perangkat:
```text
user energy_backend
topic readwrite energy/#

pattern write energy/%u/#
```
Pengujian riil melalui [tests/verify_acl.py](file:///c:/Users/deder/Music/energy-monitor/tests/verify_acl.py):
1. `esp32_device_1` publish ke `energy/esp32_device_1/telemetry` $\rightarrow$ Diterima backend (PASS).
2. `esp32_device_1` publish ke `energy/device_lain/telemetry` $\rightarrow$ Tidak diterima backend / ditolak Mosquitto (PASS).
3. `esp32_device_1` subscribe ke `energy/#` $\rightarrow$ Menerima 0 pesan saat backend mempublikasikan pesan (PASS).

#### 4. Pembersihan Data & Verifikasi Lingkungan Runtime Docker
- File database dev `data/energy.db*` dihapus dan dibersihkan sebelum penyemaian data ulang.
- [backend/tests/conftest.py](file:///c:/Users/deder/Music/energy-monitor/backend/tests/conftest.py) diimplementasikan agar seluruh test suite pytest secara otomatis memakai `sqlite:///:memory:` dan `APP_ENV=test`, menjamin isolasi total data produksi dari proses pengujian.
- Pemeriksaan dependensi dev di dalam container Docker production `energy_backend`:
  - `docker compose exec backend python -c 'import pytest'` $\rightarrow$ `ModuleNotFoundError` (DEV_DEPS_ABSENT).
  - `docker compose exec backend python -c 'import ruff'` $\rightarrow$ `ModuleNotFoundError` (RUFF_ABSENT).
  - Terbukti image Docker runtime bersih dari dependensi development.

#### 5. Tes Properti Konservasi Energi pada Kedatangan Acak
Diimplementasikan pada `test_property_random_arrival_delta_conservation` di [backend/tests/test_delta.py](file:///c:/Users/deder/Music/energy-monitor/backend/tests/test_delta.py#L282-L334):
- 50 titik telemetri berurutan diacak menggunakan `random.shuffle`.
- Di-ingest satu per satu ke dalam session database.
- Hasil: Terbukti secara matematis bahwa $\sum \text{delta\_kwh} \equiv e_{\text{terakhir}} - e_{\text{pertama}} = 0.049\text{ kWh}$.

#### 6. Ringkasan Status QA Saat Ini
- **Pytest**: `30 passed in 10.16s` (100% lolos, 0 kegagalan, 0 warning).
- **Ruff Linter**: `All checks passed!` pada seluruh modul (`backend`, `simulator`, `tests`).
- **Ruff Formatter**: `25 files left unchanged` (format PEP 8 standar).
- **Git Commit Terakhir**: `3528913 feat(core): selesaikan langkah 0 (acl ketat, last_seen, seed-db, dan property test)`.

---

## 6. Rencana Pelaksanaan Milestone M2 (API & Dashboard)

Milestone M2 mencakup antarmuka REST API dan antarmuka web dashboard pengguna akhir (mobile-first):

| Modul | Endpoint / Komponen | Deskripsi Teknis |
| :--- | :--- | :--- |
| **Auth** | `POST /api/login` | Login form dengan `hmac.compare_digest`, PyJWT `HS256`, penolakan `alg=none`, brute-force backoff, startup check pada secret key default. |
| **Device** | `GET /api/devices` | Mengembalikan daftar perangkat lengkap dengan status dinamis online/offline (timeout 120 detik dari `last_seen_at`). |
| **Series** | `GET /api/series` | Query series daya on-the-fly: interval raw $\le 6$ jam, bucketing 5 menit ($> 6$ jam s.d. 3 hari), dan agregasi 1 jam ($> 3$ hari). Target latency p95 < 500 ms pada 60k baris. |
| **Forecast** | `GET /api/forecast` | Proyeksi konsumsi dan biaya akhir bulan berbasis rata-rata 7 hari penuh terakhir. Memuat flag `available`, `low_confidence`, dan `basis_days`. |
| **Settings** | `GET/PUT /api/settings` | Pengambilan dan pembaruan konfigurasi tarif listrik, batas daya PLN, cooldown notifikasi, dan persentase biaya tambahan dengan validasi batas nilai. |
| **Export** | `GET /api/export/csv` | Download rekaman data historis berformat CSV dengan format waktu ISO 8601 UTC (`...Z`) dan delimiter koma. |
| **UI** | Web Dashboard SPA | File statis di `backend/static/` (HTML/CSS/JS) dengan render `textContent` (anti-XSS), Content Security Policy (CSP), stat cards ringkasan, grafik garis interaktif, grafik batang harian, auto polling 10 detik, dan dukungan akses WiFi HP. |

---

*Laporan ini disusun secara otomatis berdasarkan rekam jejak Git, log container Docker, dan kueri database aktual proyek Monitor Listrik Pintar.*
