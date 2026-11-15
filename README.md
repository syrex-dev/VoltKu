# Monitor Listrik Pintar (IoT + AI)

Alat pemantau listrik berbasis ESP32 + PZEM-004T, dengan dashboard web, bot Telegram, deteksi anomali, dan asisten chat AI berbahasa Indonesia. Disusun untuk dikerjakan lewat vibe coding di Antigravity.

## Daftar dokumen

| File | Isi |
|---|---|
| `AGENTS.md` | Aturan proyek untuk agent (taruh di root repo) |
| `docs/01-PRD.md` | Product Requirements Document |
| `docs/02-SRS.md` | Software Requirements Specification |
| `docs/03-ARCHITECTURE.md` | Arsitektur, tech stack, keputusan, deployment, struktur repo |
| `docs/04-FIRMWARE.md` | Spesifikasi firmware ESP32 |
| `docs/05-DATA-CONTRACT.md` | Kontrak MQTT, REST API, model data |
| `docs/06-AI-ANOMALY.md` | Modul AI #1: deteksi anomali |
| `docs/07-AI-CHAT.md` | Modul AI #2: chat asisten (LLM + tools) |
| `docs/08-TELEGRAM-BOT.md` | Perintah dan format pesan bot |
| `docs/09-TEST-PLAN.md` | Rencana pengujian |
| `docs/10-MILESTONES.md` | Milestone M0-M7 dan prompt awal untuk agent |
| `docs/11-RISKS-BACKLOG.md` | Risiko, mitigasi, backlog |

## Cara memakai di Antigravity

1. Buat repo `energy-monitor/` dan salin seluruh isi folder ini ke dalamnya.
2. Pastikan `AGENTS.md` ada di root repo (atau salin isinya ke folder aturan/rules Antigravity sesuai versi yang Anda pakai).
3. Kerjakan per milestone di `docs/10-MILESTONES.md`. Jangan minta agent membangun semuanya sekaligus.
4. Untuk tiap milestone: minta agent menulis rencana dulu, review, baru eksekusi, lalu jalankan tes.
5. Agent tidak bisa menguji perangkat keras. Backend dikembangkan dengan simulator (M1); firmware Anda flash dan uji sendiri (M4).
6. Bagian yang rawan salah (hitung kWh, tarif, deteksi anomali) wajib punya unit test.

Urutan yang disarankan: M0 > M1 > M2 > M3 (M4 saat komponen sudah datang) > M5 > M6 > M7.
