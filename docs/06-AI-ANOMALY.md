# 06. Modul AI #1: Deteksi Anomali

## Pipeline
Job tiap 5 menit mengambil rata-rata daya 5 menit terakhir per perangkat, membandingkannya dengan baseline, lalu memutuskan alert.

| Lapisan | Cara kerja | Status |
|---|---|---|
| L1 Aturan keras | Daya melewati batas, tegangan di luar 200-240 V, perangkat offline | MVP |
| L2 Baseline statistik | Robust z-score terhadap kebiasaan per (hari kerja/akhir pekan, jam) | MVP |
| L3 Beban dasar malam | Median daya 00.00-05.00 hari ini vs median 7 hari sebelumnya | MVP |
| L4 Isolation Forest | Fitur [p_mean, p_std, p_max, sin/cos jam, is_weekend] per jendela 15 menit, latih ulang tiap malam, contamination 0,01 | Should (hanya dicatat, belum memicu alert) |

## Detail L2
- Kelompokkan `p_avg` per jam dari 14 hari terakhir ke bucket (jenis_hari, jam 0-23). Hitung median dan MAD per bucket.
- Minimal 4 sampel per bucket. Jika kurang, pakai bucket jam saja. Jika masih kurang, masuk **mode belajar** (3 hari pertama, tidak mengirim alert).
- Skor: `z = 0.6745 * (x - median) / MAD`, dengan MAD minimum 5% dari median atau 10 W agar tidak meledak.
- Anomali jika z > 3,5 **dan** selisih absolut > 100 W (dapat diatur) **dan** terjadi pada >= 3 jendela 5 menit berturut-turut.

## Detail L3
Alert jika beban dasar malam naik > 30% dan > 30 W dibanding median 7 hari sebelumnya. Menangkap alat yang lupa dimatikan atau kulkas yang mulai boros.

## Output
Disimpan di tabel `anomalies`:
- `type`: power_limit, voltage, offline, spike_vs_baseline, night_baseload, iforest
- `severity`: info, warning, critical
- `details_json`: nilai aktual, baseline, z-score, durasi

Pesan alert dibuat dari template. LLM boleh dipakai opsional untuk memperjelas bahasa, tetap dengan angka dari `details_json`. Berlaku cooldown per jenis alert per perangkat (default 30 menit).

## Pengujian
Buat generator data sintetis (siklus kulkas sekitar 100 W, jam ramai warung, derau), suntikkan anomali, lalu ukur: recall >= 90% dan alarm palsu <= 2 per hari. Skenario wajib: lonjakan +300 W selama 20 menit di jam sepi; beban dasar malam naik 40 W; hari normal 7 hari tanpa alert.
