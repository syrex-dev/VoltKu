# 09. Rencana Pengujian

| Level | Cakupan |
|---|---|
| Unit | Hitung biaya, delta kWh dan reset counter, agregasi, forecast, robust z-score, validasi tool |
| Integrasi | Simulator > MQTT > DB > API; bot dengan Telegram palsu; chat dengan LLM palsu (stub) |
| Evaluasi AI | Set 15 pertanyaan chat; data sintetis 7 hari untuk anomali |
| Perangkat keras | Beban lampu 100 W; bandingkan kWh dengan alat ukur pembanding (toleransi 3%); uji putus WiFi dan listrik |
| Lapangan | 1-2 minggu di lokasi nyata, catat alert benar/palsu dan umpan balik pengguna |

## Skenario uji perangkat keras
1. Lampu 100 W: daya terbaca 95-105 W dalam 15 detik.
2. Putus WiFi 5 menit: tidak ada celah data setelah tersambung kembali.
3. Matikan ESP32: alert offline dalam 3 menit.
4. Restart backend: tidak ada data hilang (QoS 1).
5. Nyalakan beban lebih dari batas daya: alert masuk dalam 1-2 menit.
6. Bandingkan akumulasi kWh 24 jam dengan alat pembanding: selisih <= 3%.

## Aturan
- Tes tidak boleh memanggil LLM atau Telegram asli.
- Cakupan tes modul inti (`services/`, `ai/`) >= 70%.
- Semua tes berjalan dengan satu perintah (`pytest`).
