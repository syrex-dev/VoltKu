# 08. Bot Telegram

## Aturan
- Hanya `chat_id` dalam `TELEGRAM_ALLOWED_CHAT_IDS` yang dilayani; lainnya diabaikan.
- Mode polling (tanpa webhook).
- Teks bebas (bukan perintah) diteruskan ke chat AI (`07-AI-CHAT.md`).

## Perintah
| Perintah | Fungsi |
|---|---|
| `/start` | Mendaftar jika chat_id ada di allowlist |
| `/now` | Kondisi saat ini |
| `/today`, `/week`, `/month` | Ringkasan kWh dan biaya |
| `/forecast` | Proyeksi tagihan bulan ini |
| `/anomali` | Anomali 7 hari terakhir |
| `/tarif <Rp/kWh>` | Ubah tarif (menerima angka desimal dengan koma atau titik, misal `/tarif 1444.70`, dikonversi ke integer sen) |
| `/batas <watt>` | Ubah batas daya |
| `/laporan on\|off` | Aktifkan/matikan laporan otomatis |
| `/perangkat` | Daftar perangkat |

## Jadwal otomatis
- Laporan harian: 21.00 WIB.
- Laporan mingguan: Minggu 20.00 WIB.
- Alert: kapan pun terjadi (dengan cooldown).

## Contoh laporan harian
```
Laporan 15 Nov 2026 (Warung)
Pemakaian: 8,434 kWh | Biaya: ±Rp12.185
Puncak: 1.069,7 W pukul 18.35 WIB
Proyeksi bulan ini: ±Rp461.011 (Basis 7 Hari)
Catatan: beban malam stabil sesuai profil wajar.
```

## Contoh alert
```
[PERINGATAN] Warung - pemakaian tidak biasa
Daya rata-rata 20 menit terakhir: 540 W
Biasanya jam ini (hari kerja): 210 W
Selisih: +330 W. Cek alat yang menyala (kulkas, AC, atau pemanas).
```
