# 06. Modul AI #1: Deteksi Anomali

## Pipeline
Job evaluasi alert L1 berjalan tiap 15 detik memeriksa jendela telemetri terbaru, sedangkan job analitik L2-L4 berjalan berkala (5 menit / harian) membandingkan data terhadap baseline.

| Lapisan | Cara kerja | Status |
|---|---|---|
| L1 Aturan keras | Daya melewati batas, tegangan di luar 200-240 V, perangkat offline | MVP |
| L2 Baseline statistik | Robust z-score terhadap kebiasaan per (hari kerja/akhir pekan, jam) | MVP |
| L3 Beban dasar malam | Median daya 00.00-05.00 hari ini vs median 7 hari sebelumnya | MVP |
| L4 Isolation Forest | Fitur [p_mean, p_std, p_max, sin/cos jam, is_weekend] per jendela 15 menit, latih ulang tiap malam, contamination 0,01 | Should (hanya dicatat, belum memicu alert) |

## Detail L1 (Aturan Keras Real-Time)
- **Cakupan Jendela & Toleransi**: Pemicuan alert L1 memerlukan jendela telemetri yang terisi penuh secara berkelanjutan:
  - Daya lebih batas (`power_limit`): jendela >= 60 detik (minimal 3 sampel @ 10s).
  - Tegangan di luar batas 200-240 V (`voltage`): jendela >= 30 detik (minimal 2 sampel @ 10s).
  - Toleransi cakupan: sampel tertua dalam jendela wajib `<= awal_jendela + 15 detik` (1,5 x interval publish 10s) atau memiliki sampel pendahulu yang juga melewati batas. Sampel yang baru muncul setelah gap data atau restart (cakupan sempit ~20 detik) tidak boleh memicu alert palsu.
- **Histeresis & Pemulihan (Recovery)**: Daya dianggap pulih setelah ~1 menit (60 detik) data telemetri konsisten normal di bawah ambang histeresis (P < 0,95 x limit daya). Pemulihan tegangan memerlukan 30 detik data normal (205-235 V). Pemulihan tidak membuat baris baru, melainkan mencatat `resolved_at` pada `details_json` di episode anomali yang sama.
- **Perangkat Offline**: Status tampilan (dashboard, /perangkat) dapat langsung menampilkan status offline dari pesan LWT MQTT. Namun, **alert notifikasi offline HANYA terpicu** jika selisih waktu telemetri `now - last_seen_at > 120 detik`. LWT offline tanpa jeda waktu 120 detik tidak memicu alert notifikasi. Episode alert offline dicatat ke tabel `anomalies`.

## Detail L2
- **Kelengkapan Jendela 5 Menit**: Suatu jendela 5 menit dinyatakan **lengkap** jika memiliki `>= 24 dari 30 pembacaan` telemetri (80%). Jendela yang tidak lengkap (< 80%) diabaikan dari perhitungan baseline.
- **Kecukupan Bucket Baseline (14 Hari)**:
  - Kelompokkan jendela 5 menit lengkap dari 14 hari terakhir ke dalam bucket `(jenis_hari, jam 0-23)`, dengan `jenis_hari` terbagi atas hari kerja (Senin–Jumat) dan akhir pekan (Sabtu–Minggu). Hitung median dan MAD per bucket.
  - Bucket `(jenis_hari, jam)` dinyatakan **cukup** jika memiliki `>= 24 jendela lengkap dari >= 2 hari berbeda`.
  - **Fallback**: Jika bucket `(jenis_hari, jam)` belum cukup, lakukan fallback ke **bucket jam saja** (menggabungkan data seluruh jenis hari pada jam yang sama).
  - **Mode Belajar**: Jika bucket jam saja masih belum cukup atau data telemetri historis `< 3 hari penuh`, sistem masuk ke **mode belajar** (hanya mengumpulkan data, tidak memicu alert notifikasi).
- **Skor Z Robust**: `z = 0.6745 * (x - median) / MAD`, dengan MAD minimum 5% dari median atau 10 W agar pembagi tidak meledak.
- **Pemicuan Anomali**: Anomali jika `z > 3,5` **dan** selisih absolut `> 100 W` (dapat diatur) **dan** terjadi pada `>= 3 jendela 5 menit berturut-turut`.

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
