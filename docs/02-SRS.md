# 02. SRS (Software Requirements Specification)

## 1. Asumsi dan batasan
- Satu PZEM-004T v3.0 dengan CT coil per titik ukur, listrik 1 fasa 220 V.
- WiFi tersedia. Server berjalan di laptop, mini PC, Raspberry Pi, atau VPS kecil yang selalu menyala.
- Waktu disimpan dalam UTC dan ditampilkan dalam Asia/Jakarta (WIB).
- Tarif (Rp/kWh) diisi pengguna sesuai tagihan; sistem tidak mengambilnya otomatis.
- Biaya = kWh x tarif x (1 + persentase tambahan, default 0). Biaya beban atau PPJ hanya masuk jika diisi.
- LLM dipanggil lewat API pihak ketiga (butuh internet dan API key).

## 2. Kebutuhan fungsional

### Firmware (FW) - detail di `04-FIRMWARE.md`
- FW-01 Baca V, I, P, E, f, PF dari PZEM tiap 1 detik; kirim tiap 10 detik (dapat diatur).
- FW-02 Publish ke MQTT QoS 1 dengan timestamp epoch UTC dari NTP.
- FW-03 Reconnect otomatis WiFi dan MQTT. Saat putus, simpan hingga 360 pembacaan di RAM dan kirim ulang setelah tersambung.
- FW-04 Publish status online/offline (retained, dengan Last Will).
- FW-05 Konfigurasi lewat `config.h` (MVP); portal WiFiManager (Should).
- FW-06 Watchdog aktif; restart otomatis jika hang.
- FW-07 Jika PZEM tidak merespons lebih dari 30 detik, kirim status error.

### Backend (BE)
- BE-01 Subscribe `energy/+/telemetry`, validasi skema, simpan ke `readings`.
- BE-02 Tolak dan catat data di luar rentang wajar (V 0-300, I 0-100, P 0-25000).
- BE-03 Hitung delta kWh dari counter E. Jika E turun (counter direset), delta = E baru. Abaikan lonjakan tak wajar.
- BE-04 Agregasi per jam dan per hari (kWh, biaya, daya rata-rata, maks, min).
- BE-05 Retensi data mentah 14 hari; agregat disimpan tanpa batas.
- BE-06 Deteksi perangkat offline (tidak ada data lebih dari 120 detik atau status offline).
- BE-07 Tarif disimpan pada agregat harian; perubahan tarif hanya berlaku ke depan.
- BE-08 REST API sesuai `05-DATA-CONTRACT.md`.

### Alert dan AI (AL)
- AL-01 Alert aturan: daya melewati batas (bertahan >= 60 detik), tegangan di luar 200-240 V (>= 30 detik), perangkat offline.
- AL-02 Alert anomali statistik sesuai `06-AI-ANOMALY.md`.
- AL-03 Cooldown per jenis alert per perangkat (default 30 menit).
- AL-04 Setiap alert disimpan beserta alasan dan angka pendukung.
- AL-05 Laporan harian pukul 21.00 WIB dan mingguan Minggu 20.00 WIB.
- AL-06 Proyeksi tagihan bulan berjalan.
- AL-07 Chat LLM memakai function calling ke data nyata (`07-AI-CHAT.md`). LLM tidak boleh menghitung angka sendiri.

### Telegram (TG) dan Dashboard (UI)
- TG-01 Hanya chat_id dalam allowlist yang dilayani.
- TG-02 Perintah sesuai `08-TELEGRAM-BOT.md`; teks bebas diteruskan ke chat AI.
- UI-01 Kartu real-time (P, V, I, PF, status) dengan auto-refresh 5 detik.
- UI-02 Grafik daya 24 jam, kWh per hari (30 hari), profil daya per jam.
- UI-03 Ringkasan hari/minggu/bulan, biaya, dan proyeksi.
- UI-04 Daftar anomali terbaru dan pengaturan tarif/batas daya.
- UI-05 Responsif untuk HP; login sederhana (password dari env).

## 3. Kebutuhan non-fungsional
| Kategori | Persyaratan |
|---|---|
| Akurasi | Selisih kWh <= 3% terhadap alat pembanding |
| Kinerja | API p95 < 500 ms untuk 30 hari data; balasan chat < 15 detik |
| Keandalan | Ingest tetap jalan saat LLM atau Telegram down; tidak ada data hilang saat backend restart (QoS 1 dan sesi persisten) |
| Keamanan | MQTT dengan user/password per perangkat; rahasia hanya di `.env`; API dengan login; Telegram allowlist; port database tidak terbuka |
| Privasi | Ke LLM hanya dikirim hasil ringkasan tool, bukan data mentah |
| Biaya | Hardware <= Rp300 rb per titik; LLM <= Rp50 rb/bulan (dengan rate limit) |
| Maintainability | Cakupan tes modul inti >= 70%; konfigurasi lewat env; log terstruktur |
| Portabilitas | Jalan dengan `docker compose up` |

## 4. Kriteria penerimaan utama
- Beban lampu 100 W terbaca 95-105 W di dashboard dalam 15 detik.
- WiFi diputus 5 menit lalu disambung: data periode putus muncul tanpa celah.
- ESP32 dimatikan: alert "offline" masuk dalam 3 menit.
- Data sintetis dengan lonjakan +300 W selama 20 menit di jam sepi: anomali terdeteksi. Data sintetis 7 hari normal: 0 alert palsu.
- Pertanyaan "berapa biaya listrik hari ini?" dijawab dengan angka yang sama dengan dashboard.
