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


