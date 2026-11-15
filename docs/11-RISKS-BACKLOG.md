# 11. Risiko, Mitigasi, dan Backlog

## Risiko
| Risiko | Mitigasi |
|---|---|
| Bahaya listrik 220 V saat perakitan | Box tertutup, MCB dimatikan, sekring, uji dengan lampu dulu, libatkan teknisi bila ragu |
| TX PZEM 5 V merusak ESP32 | Pembagi tegangan 10k/20k pada jalur TX |
| Alert palsu membuat pengguna mengabaikan sistem | Mode belajar, cooldown, ambang selisih absolut, persistensi minimal 3 jendela |
| LLM mengarang angka | Function calling, system prompt ketat, set evaluasi, jawaban memuat periode data |
| Biaya API LLM membengkak | Rate limit, batas panggilan tool, model hemat |
| Server mati atau WiFi putus | Buffer di ESP32, QoS 1, `restart: unless-stopped`, alert offline |
| Biaya tidak sama dengan tagihan PLN | Tampilkan sebagai perkiraan; sediakan persentase tambahan (PPJ dan lainnya) |
| Vibe coding menghasilkan kode tidak konsisten | AGENTS.md, milestone kecil, tes wajib, review rencana sebelum eksekusi |

## Backlog setelah MVP
Portal WiFiManager, OTA update, kontrol relay, beberapa pengguna (pemilik kos dan penghuni), tagihan per unit, identifikasi alat (NILM), PostgreSQL/TimescaleDB, PWA, ekspor CSV dan PDF, dukungan listrik 3 fasa.
