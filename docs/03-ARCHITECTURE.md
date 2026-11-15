# 03. Arsitektur

## 1. Diagram
```
[PZEM-004T + CT] --UART--> [ESP32] --WiFi/MQTT--> [Mosquitto]
                                                     |
                                                     v
+---------------------- Backend (FastAPI, Python) ----------------------+
| MQTT Ingest -> Validator -> DB (SQLite) -> Aggregator (jam/hari)      |
| Scheduler: laporan, deteksi anomali, cek offline                      |
| AI: AnomalyEngine | ChatAgent (LLM + tools) | LLMClient (abstraksi)   |
| REST API | Telegram Bot (polling)                                     |
+-----------------------------------------------------------------------+
        |                    |                        |
   Dashboard Web      Pengguna Telegram        LLM API (internet)
```
Alur chat: pengguna > Telegram > ChatAgent > LLM memilih tool > tool query DB > hasil kembali ke LLM > jawaban ke pengguna.

## 2. Tech stack
| Lapisan | Pilihan | Alasan |
|---|---|---|
| Firmware | C++ Arduino framework via PlatformIO; PZEM004Tv30, PubSubClient, ArduinoJson | Umum dan banyak contoh |
| Broker | Eclipse Mosquitto (Docker) | Ringan dan gratis |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, paho-mqtt, APScheduler | Cepat dibuat, mudah di-vibe-code |
| Database | SQLite (WAL) untuk MVP, skema kompatibel PostgreSQL | Tanpa server tambahan |
| AI statistik | numpy, pandas; scikit-learn (opsional) | Ringan |
| LLM | Antarmuka `LLMClient`; provider dan model dari env (Gemini atau Claude) | Tidak terkunci vendor |
| Bot | python-telegram-bot v20+ (async) | Matang |
| Dashboard | HTML + JavaScript biasa + Chart.js, disajikan FastAPI | Tanpa build step |
| Deploy dan tes | Docker Compose; pytest, httpx, ruff | Standar |

## 3. Keputusan arsitektur
- **MQTT, bukan HTTP langsung:** ringan untuk ESP32, ada QoS dan Last Will untuk deteksi offline.
- **SQLite dulu:** 5 perangkat x 1 data/10 detik = sekitar 43 ribu baris/hari, masih sangat cukup. Pindah ke PostgreSQL jika perangkat lebih dari 20.
- **AI di server, bukan di ESP32:** ESP32 hanya sensor dan pengirim data.
- **Anomali: aturan dan statistik dulu:** dapat dijelaskan alasannya dan tidak butuh data latih besar. Isolation Forest hanya pembanding.
- **LLM hanya untuk bahasa, bukan hitungan:** semua angka berasal dari tool deterministik.
- **Telegram polling, bukan webhook:** tidak perlu domain atau HTTPS publik.

## 4. Deployment dan keamanan
- `deploy/docker-compose.yml` berisi dua service: `mosquitto` (dengan file password) dan `backend` (port 8000, volume `./data` untuk SQLite, `env_file: .env`, `restart: unless-stopped`).
- Mosquitto: `allow_anonymous false`, satu user per perangkat, ACL agar perangkat hanya boleh publish ke `energy/<device_id>/#`.
- Jika perlu akses dari luar jaringan lokal, gunakan VPN (Tailscale/WireGuard) atau reverse proxy HTTPS. Jangan buka port MQTT ke internet tanpa TLS.
- Rahasia hanya di `.env` (tidak masuk git); sediakan `.env.example`.

Variabel env minimal: `MQTT_HOST`, `MQTT_USER`, `MQTT_PASS`, `DATABASE_URL`, `DASHBOARD_PASSWORD`, `JWT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `TZ=Asia/Jakarta`.

## 5. Struktur repo
```
energy-monitor/
├─ AGENTS.md
├─ README.md
├─ .env.example
├─ docs/
├─ deploy/            docker-compose.yml, mosquitto.conf
├─ firmware/          platformio.ini, src/main.cpp, include/config.example.h
├─ simulator/         publish_fake.py (data sintetis dan skenario anomali)
├─ backend/
│  ├─ app/
│  │  ├─ main.py, config.py, db.py, models.py
│  │  ├─ mqtt_ingest.py, scheduler.py
│  │  ├─ services/    aggregation.py, cost.py, forecast.py
│  │  ├─ ai/          anomaly.py, chat.py, tools.py, llm_client.py
│  │  ├─ bot/         telegram_bot.py
│  │  └─ api/         routes.py, auth.py
│  └─ tests/
└─ dashboard/         index.html, app.js, style.css
```
