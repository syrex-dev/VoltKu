# Panduan Deployment Mosquitto & Backend

Direktori ini berisi konfigurasi deployment berbasis Docker Compose untuk broker MQTT (Mosquitto) dan service backend FastAPI.

## 1. Persiapan File Environment (.env)

Sebelum menjalankan container, salin file template `.env.example` di root proyek menjadi `.env`:

```bash
# Dari root direktori repositori
cp .env.example .env
```
Sesuaikan nilai konfigurasi (misal password dan secret key) di dalam `.env` jika diperlukan. Jangan pernah commit file `.env` ke git.

## 2. Pembuatan File Password Mosquitto (`passwd`)

Mosquitto dikonfigurasi dengan `allow_anonymous false` dan membutuhkan file password (`passwd`).

### Menggunakan Docker (Direkomendasikan)
Untuk membuat file `passwd` dan menambahkan user backend serta user perangkat ESP32:

```bash
# Masuk ke folder deploy
cd deploy

# Buat file passwd baru dengan user pertama (backend)
docker run --rm -v "${PWD}:/mosquitto/config" eclipse-mosquitto:2.0 mosquitto_passwd -c -b /mosquitto/config/passwd energy_backend ganti_password_mqtt_backend

# Tambahkan user untuk perangkat ESP32 (tanpa flag -c agar tidak menimpa file)
docker run --rm -v "${PWD}:/mosquitto/config" eclipse-mosquitto:2.0 mosquitto_passwd -b /mosquitto/config/passwd esp32_device_1 password_mqtt_device
```

### Menggunakan mosquitto_passwd Lokal (Jika Terpasang di Host)
```bash
cd deploy
mosquitto_passwd -c passwd energy_backend
mosquitto_passwd passwd esp32_device_1
```

> **Catatan Keamanan:** File `passwd` berisi hash kredensial dan sudah dimasukkan ke `.gitignore` agar tidak pernah ter-commit ke repositori.

## 3. Menjalankan Docker Compose

Setelah file `.env` dan `passwd` siap, jalankan Docker Compose:

```bash
# Dari folder deploy (atau root dengan flag -f deploy/docker-compose.yml)
docker compose up -d --build
```

## 4. Cek Status Kontainer & Log
```bash
docker compose ps
docker compose logs -f
```

## 5. Panduan Akses Dashboard dari HP (Jaringan WiFi Lokal)
> **Catatan:** Dashboard disajikan via HTTP polos (unencrypted) dan hanya diperuntukkan untuk jaringan lokal (LAN) privat.
> Status pengujian: **Belum diverifikasi dari HP** (diuji melalui konfigurasi port forwarding host).

Docker Compose sudah memetakan port `0.0.0.0:8000`, sehingga tidak perlu mengubah variabel `HOST` di `.env`.

### Langkah-langkah Konfigurasi:
1. **Dapatkan Alamat IP Host Windows (LAN)**:
   Jalankan di PowerShell:
   ```powershell
   Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi*' | Select-Object -ExpandProperty IPAddress
   ```
   Misalnya didapatkan IP `192.168.1.15`.

2. **Buka Port pada Windows Firewall (Profile Private)**:
   Buka PowerShell sebagai Administrator dan jalankan:
   ```powershell
   New-NetFirewallRule -DisplayName "Energy Monitor Web Dashboard" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
   ```

3. **Penanganan Jaringan WSL2**:
   Karena Docker berjalan di dalam WSL2, paket jaringan dari WiFi HP menuju Windows perlu diteruskan ke VM WSL2:
   - **Opsi A (Direkomendasikan untuk Windows 11 22H2+)**:
     Tambahkan konfigurasi berikut pada file `%USERPROFILE%\.wslconfig`:
     ```ini
     [wsl2]
     networkingMode=mirrored
     ```
     Lalu restart WSL via PowerShell: `wsl --shutdown`.
   - **Opsi B (Portproxy ke IP WSL2)**:
     Dapatkan IP WSL2 dengan perintah `wsl hostname -I` (perhatikan bahwa IP ini dapat berubah setiap restart WSL), lalu buat aturan portproxy di PowerShell Administrator:
     ```powershell
     $wslIp = (wsl hostname -I).Trim().Split()[0]
     netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIp
     ```

4. **Buka dari Browser HP**:
   Hubungkan smartphone ke jaringan WiFi yang sama, lalu buka:
   `http://192.168.1.15:8000` (sesuaikan dengan IP LAN PC Anda).

## 6. Penyimpanan Database SQLite (Named Volume `energy_data`)

Database SQLite produksi disimpan di dalam named volume Docker `energy_data` (terpasang di `/app/data` di dalam container) dan **tidak menggunakan bind mount host** (`./data`).

### Alasan Arsitektur:
Penggunaan named volume Docker Linux murni mengeliminasi potensi konflik file locking dan korupsi mode SQLite WAL (*Write-Ahead Logging*) yang dapat terjadi saat file database diakses bersamaan melalui lapisan filesystem 9P/drvfs antara host Windows dan lingkungan Linux container.

### Peringatan Penghapusan Volume:
> [!WARNING]
> Menjalankan perintah `docker compose down -v` akan **menghapus volume Docker `energy_data` beserta seluruh data pengukuran di dalamnya secara permanen**. Untuk menghentikan container tanpa menghapus data, gunakan `docker compose down` (tanpa flag `-v`) atau `docker compose stop`.

### Rencana Cadangan Data (Backup SQLite untuk M7):
Untuk menjamin ketahanan data terhadap risiko penghapusan volume dan bencana hardware, pada Milestone 7 (M7) akan diimplementasikan mekanisme backup terjadwal berkala menggunakan **SQLite Online Backup API** (`sqlite3.Connection.backup` atau `VACUUM INTO '/app/data/backups/energy_backup_YYYYMMDD.db'`). Mekanisme ini menjamin snapshot database konsisten dan aman meskipun transaksi MQTT sedang berlangsung.

### Aturan Eksekusi Skrip Database:
Semua skrip yang menyentuh, membaca, atau menulis ke database (`energy.db`) **wajib dijalankan di dalam container backend**, BUKAN dari lingkungan host Windows:

```bash
# Menjalankan seeding database:
docker compose exec backend python scripts/seed_db.py

# Menjalankan benchmark latensi kueri di dalam container:
docker compose exec backend python scripts/benchmark_container.py

# Memeriksa integritas database:
docker compose exec backend python -c "import sqlite3; con = sqlite3.connect('/app/data/energy.db'); print(con.execute('PRAGMA integrity_check').fetchall())"
```

## 7. Panduan Pengujian Manual Telegram Bot (Milestone 3)

### A. Konfigurasi Kredensial (.env)
Buka file `.env` di root repositori dan masukkan token bot serta daftar chat ID yang diizinkan:
```env
TELEGRAM_BOT_TOKEN=<token_dari_BotFather>
TELEGRAM_ALLOWED_CHAT_IDS=<chat_id_anda>
BOT_ENABLED=true
```
> **Catatan Keamanan:**
> - Chat ID dapat diperoleh dengan mengirim pesan ke `@userinfobot` di Telegram.
> - Kredensial dan token **jangan pernah dicetak di log, commit ke git, atau disebarkan**.
> - Tanpa token (kosong), bot otomatis dinonaktifkan dan backend FastAPI berjalan normal.

### B. Menjalankan Ulang Backend
Setelah `.env` diisi, restart container backend:
```bash
docker compose up -d --build backend
```
Periksa log startup untuk memastikan bot berhasil diinisialisasi:
```bash
docker compose logs backend | grep -i "telegram"
```

### C. Daftar Skenario Uji Manual
1. **Uji Keamanan Allowlist**:
   - Kirim pesan `/start` dari akun Telegram yang **tidak terdaftar** di `TELEGRAM_ALLOWED_CHAT_IDS`.
   - **Hasil yang diharapkan:** Bot sama sekali tidak merespons (silent drop), tanpa mencatat `chat_id` asing atau konten pesan ke dalam log (anti-leak).

2. **Uji Perintah Informasi (Akun Terdaftar)**:
   - `/start` : Menampilkan pesan panduan dan daftar perintah.
   - `/perangkat` : Menampilkan daftar seluruh perangkat, status (ONLINE/OFFLINE), kapasitas MCB, dan timestamp data terakhir.
   - `/now` : Menampilkan daya (W), tegangan (V), arus (A), PF, frekuensi (Hz), dan RSSI. Coba juga `/now <device_id>`.
   - `/today` : Ringkasan energi (kWh), biaya (Rp), dan beban puncak (W) hari ini.
   - `/week` : Ringkasan energi dan biaya minggu ini (dihitung sejak Senin WIB).
   - `/month` : Ringkasan energi dan biaya bulan kalender berjalan.
   - `/forecast` : Proyeksi konsumsi dan tagihan PLN akhir bulan beserta basis hari.
   - `/anomali` : Riwayat peringatan dan anomali 7 hari terakhir (maks 20 baris, terbaru dulu).

3. **Uji Perintah Pengaturan**:
   - `/tarif 1444,70` : Mengubah tarif listrik PLN (menerima koma atau titik; tolak bila > 2 desimal seperti `/tarif 1444.755`).
   - `/batas 2500` : Mengubah batas daya peringatan menjadi 2500 Watt.
   - `/laporan off` lalu `/laporan on` : Mengaktifkan / menonaktifkan pengiriman laporan berkala otomatis.

4. **Uji Notifikasi Alert Real-Time & Pembersihan**:
   - Jalankan simulator skenario overload:
     ```bash
     python simulator/publish_fake.py --device demo-1 --mode overload --overload-seconds 120
     ```
   - Bot akan menerima notifikasi:
     - `[PERINGATAN] demo-1 - Daya melebihi batas wajar: ... W > ... W` (setelah overload bertahan >= 60s).
     - `[PULIH] demo-1 - Daya normal kembali: ... W` (setelah fase pemulihan).
     - `[PERINGATAN] demo-1 - Perangkat offline ...` (sekitar 120 detik setelah simulator dihentikan).
   - Setelah pengujian selesai, bersihkan seluruh data pengujian `demo-1`:
     ```bash
     docker compose exec backend python scripts/clean_device.py demo-1
     ```

## 8. Konfigurasi Akun MQTT & Hak Akses ACL Broker (Mosquitto)

Aturan otorisasi topik MQTT diatur di `deploy/acl`:

```text
user energy_backend
topic readwrite energy/#

pattern write energy/%u/#
```

### Penjelasan Hak Akses:
1. **Akun Simulator / Backend (`energy_backend`)**:
   - Menggunakan kredensial `MQTT_USER=energy_backend` dan `MQTT_PASS` dari `.env`.
   - Memiliki izin `topic readwrite energy/#` (akses penuh ke seluruh hierarki topik `energy/`).
   - Alasan lolos ACL: Simulator telemetri (`simulator/publish_fake.py`) secara default menggunakan akun `energy_backend`, sehingga simulator bebas mempublikasikan data ke topik perangkat apa pun (seperti `energy/demo-1/telemetry` atau `energy/sim-warung/telemetry`).
2. **Akun Perangkat Fisik / ESP32**:
   - Setiap perangkat fisik login dengan username yang persis sama dengan `device_id` miliknya.
   - Directive `pattern write energy/%u/#` mencocokkan `%u` dengan username MQTT yang terotentikasi.
   - Perangkat dengan username `esp32_device_1` hanya diizinkan mempublikasikan ke `energy/esp32_device_1/#` dan ditolak oleh broker jika mencoba mempublikasikan ke topik perangkat lain atau subscribe ke `energy/#`.



