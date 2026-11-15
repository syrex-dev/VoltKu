# Panduan Deployment Mosquitto & Backend

Direktori ini berisi konfigurasi deployment berbasis Docker Compose untuk broker MQTT (Mosquitto) dan service backend FastAPI.

## 1. Pembuatan File Password Mosquitto (`passwd`)

Mosquitto dikonfigurasi dengan `allow_anonymous false` dan membutuhkan file password (`passwd`).

### Menggunakan Docker (Direkomendasikan)
Untuk membuat file `passwd` dan menambahkan user backend serta user perangkat ESP32:

```bash
# Masuk ke folder deploy
cd deploy

# Buat file passwd baru dengan user pertama (backend)
docker run --rm -it -v "${PWD}:/mosquitto/config" eclipse-mosquitto:2.0 mosquitto_passwd -c /mosquitto/config/passwd energy_backend

# Tambahkan user untuk perangkat ESP32 (tanpa flag -c agar tidak menimpa file)
docker run --rm -it -v "${PWD}:/mosquitto/config" eclipse-mosquitto:2.0 mosquitto_passwd /mosquitto/config/passwd esp32_device_1
```

### Menggunakan mosquitto_passwd Lokal (Jika Terpasang di Host)
```bash
cd deploy
mosquitto_passwd -c passwd energy_backend
mosquitto_passwd passwd esp32_device_1
```

> **Catatan Keamanan:** File `passwd` berisi hash kredensial dan sudah dimasukkan ke `.gitignore` agar tidak pernah ter-commit ke repositori.

## 2. Menjalankan Docker Compose

Pastikan file `.env` sudah disiapkan di root proyek berdasarkan template `.env.example`:

```bash
# Dari root proyek
cp .env.example .env

# Jalankan service mosquitto dan backend
docker compose -f deploy/docker-compose.yml up -d
```

## 3. Cek Status Kontainer & Log
```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f
```
