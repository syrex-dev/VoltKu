# 01. PRD (Product Requirements Document)

## 1. Ringkasan produk
Alat pemantau listrik berbasis ESP32 dan PZEM-004T yang mengirim data pemakaian ke server, lalu menampilkannya di dashboard web dan Telegram. Lapisan AI memberi (a) peringatan pemakaian tidak wajar dan (b) asisten chat berbahasa Indonesia untuk bertanya soal pemakaian dan biaya.

## 2. Masalah yang diselesaikan
- Pemilik warung, kos, dan UMKM tidak tahu alat mana atau jam berapa listrik boros sampai tagihan datang.
- Batas daya tetap (mis. "> 1500 W") sering salah: terlalu sensitif, atau tidak menangkap pemborosan kecil yang berlangsung lama.
- Grafik kurang ramah bagi orang awam; mereka lebih nyaman bertanya dengan bahasa sehari-hari.

## 3. Target pengguna
| Persona | Kebutuhan utama |
|---|---|
| Pemilik warung/UMKM | Tahu biaya listrik harian kulkas/freezer, dapat laporan otomatis |
| Pemilik kos | Pantau tiap unit, data pemakaian sebagai dasar penagihan |
| Pemilik rumah | Alert saat ada yang boros atau lupa dimatikan |
| Developer | Sistem mudah di-deploy, di-demo, dan dikembangkan |

## 4. Tujuan dan metrik keberhasilan
| Tujuan | Metrik | Target MVP |
|---|---|---|
| Data akurat | Selisih kWh vs alat ukur pembanding | <= 3% |
| Data andal | Data terkirim per hari | >= 98% |
| Alert berguna | Alert yang dinilai pengguna masuk akal | >= 80% |
| Alert tidak berisik | Alert palsu per hari per perangkat | <= 2 |
| Chat benar | Jawaban dengan angka benar (15 pertanyaan uji) | >= 90% |
| Adopsi | Lokasi nyata yang mencoba | >= 2 lokasi, 2 minggu |

## 5. Ruang lingkup
**Masuk MVP:** 1 sampai 5 perangkat dengan 1 pemilik; dashboard web; bot Telegram; deteksi anomali statistik; chat LLM dengan function calling; tarif dapat diatur; laporan harian dan mingguan; proyeksi tagihan bulanan.

**Di luar MVP:** multi-pengguna/penagihan, aplikasi mobile native, kontrol relay, identifikasi alat (NILM), pembayaran, OTA update.

## 6. User stories dan prioritas
| ID | Pengguna ingin ... | Prioritas |
|---|---|---|
| US-01 | Melihat daya, tegangan, arus saat ini | Must |
| US-02 | Melihat kWh dan biaya hari ini, minggu ini, bulan ini | Must |
| US-03 | Menerima laporan harian di Telegram pukul 21.00 WIB | Must |
| US-04 | Diberi tahu jika daya melewati batas yang saya tentukan | Must |
| US-05 | Diberi tahu jika perangkat offline | Must |
| US-06 | Diberi tahu jika pemakaian tidak wajar dibanding kebiasaan | Must |
| US-07 | Bertanya lewat chat, mis. "Kenapa listrik minggu ini naik?" | Must |
| US-08 | Melihat proyeksi tagihan bulan ini | Should |
| US-09 | Mengubah tarif dan batas daya lewat Telegram atau dashboard | Should |
| US-10 | Melihat beberapa perangkat (kamar kos) dalam satu dashboard | Should |
| US-11 | Mengunduh data CSV | Could |
| US-12 | Memutus beban lewat relay | Won't (backlog) |
