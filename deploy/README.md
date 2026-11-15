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

