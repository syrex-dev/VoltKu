# 10. Milestone dan Prompt Awal

Kerjakan berurutan. Di setiap milestone, mulai dengan meminta rencana, review, lalu eksekusi.

## M0. Fondasi
Repo, struktur folder, Docker Compose (Mosquitto + backend "hello"), `.env.example`, lint dan tes dasar berjalan.
> Baca README.md dan AGENTS.md. Buat rencana dulu untuk M0, tunggu persetujuan saya, lalu kerjakan.

## M1. Ingest dan data
Simulator, subscriber MQTT, validasi, tabel, delta kWh, agregasi jam/hari, biaya.
**Selesai jika:** simulator berjalan 1 jam dan angka agregat cocok dengan hitungan manual di unit test.
> Kerjakan M1 sesuai docs/05-DATA-CONTRACT.md dan kebutuhan BE-01 sampai BE-07 di docs/02-SRS.md. Tulis unit test untuk reset counter dan hitung biaya.

## M2. API dan dashboard
Endpoint REST, login, dashboard real-time dan grafik, responsif di HP.
> Kerjakan M2 sesuai bagian REST API di docs/05-DATA-CONTRACT.md dan kebutuhan UI-01 sampai UI-05.

## M3. Telegram dan alert aturan
Bot, allowlist, perintah dasar, alert L1, cooldown, laporan harian/mingguan, proyeksi.
> Kerjakan M3 sesuai docs/08-TELEGRAM-BOT.md dan AL-01, AL-03 sampai AL-06.

## M4. Firmware (paralel; Anda uji sendiri)
Minta agent menulis `main.cpp` sesuai `04-FIRMWARE.md` dan payload di `05-DATA-CONTRACT.md`. Anda flash, cek di Serial Monitor, lalu pastikan data masuk ke backend nyata. Jalankan skenario uji perangkat keras di `09-TEST-PLAN.md`.

## M5. AI anomali
Generator data sintetis, L2 dan L3, mode belajar, pesan alert, tes recall dan alarm palsu. L4 jika waktu cukup.
> Kerjakan M5 sesuai docs/06-AI-ANOMALY.md. Mulai dari generator data sintetis dan tesnya.

## M6. AI chat
`LLMClient`, tools, system prompt, guardrail, rate limit, set evaluasi 15 pertanyaan.
> Kerjakan M6 sesuai docs/07-AI-CHAT.md. LLM tidak boleh menghitung angka. Mulai dengan LLM stub agar tes tidak butuh API key.

## M7. Pengerasan dan uji lapangan
Keamanan MQTT, backup SQLite, log, README pemasangan, uji 1-2 minggu di lokasi nyata, siapkan demo.
