# Panduan Praktis: Merakit Sendiri Monitor Listrik Pintar (IoT + AI)

> Panduan ini ditulis khusus untuk pemula yang belum pernah belajar kelistrikan atau desain 3D.  
> Semua langkah dijelaskan dengan bahasa sederhana dan praktis.

---

## 1. Bagaimana Alat Ini Bekerja?

Konsep alat ini sangat sederhana dan aman:

1. **Klem Sensor Arus (CT Split-Core):** Bentuknya seperti jepitan jemuran. Cukup dijepitkan melingkari **satu kabel fasa utama** di panel listrik. Tidak ada kabel yang dipotong atau dikupas kawatnya.
2. **Modul PZEM-004T:** Menghitung voltase, arus, watt, dan total kWh pemakaian listrik rumah.
3. **ESP32:** Mengirim hasil perhitungan daya lewat Wi-Fi ke layar Dashboard laptop/HP dan bot Telegram Anda.

---

## 2. Daftar Belanja Komponen (Tinggal Cari di Tokopedia / Shopee)

Semua komponen mudah ditemukan secara online (total estimasi **Rp 311.244**, sebelum ongkir dan jasa cetak casing 3D):

| Nama Barang di Toko Online | Harga | Catatan Pembelian | Link Olshop (Shopee & Tokopedia) |
| --- | --- | --- | --- |
| **ESP32 DevKit V1** (30 pin) | Rp 70.000 | Pilih varian **30 pin (Micro-USB)** yang kakinya sudah disolder. | [Shopee](https://id.shp.ee/JtLBhy25) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=ESP32%20DevKit%20V1%2030%20pin) |
| **Sensor PZEM-004T v3.0 / V4.0 (100A)** | Rp 181.560 | V3.0 & V4.0 kompatibel. **Wajib varian Open / Split-Core CT 100A** (klem buka-tutup), bukan donat tertutup & bukan 10A. | [Shopee](https://id.shp.ee/BnUa5bVR) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=PZEM-004T%20100A%20Open%20CT) |
| **Resistor 10kΩ** (1/4 watt) | Rp 1.500 | Pembagi tegangan pelindung pin RX ESP32. | [Shopee](https://id.shp.ee/e22JYEwS) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=resistor%2010k%201%2F4%20watt) |
| **Resistor 20kΩ** (1/4 watt) | Rp 3.000 | Pasangan pembagi tegangan (10kΩ + 20kΩ). | [Shopee](https://id.shp.ee/uZE2xT5h) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=resistor%2020k%201%2F4%20watt) |
| **Kabel Jumper Dupont Female-to-Female** (20 cm) | Rp 6.499 | Untuk menyambung pin tanpa perlu solder. | [Shopee](https://id.shp.ee/xcisrN8J) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=kabel%20jumper%20dupont%20female%20to%20female%2020cm) |
| **Charger HP 5V** | Rp 17.000 | Adaptor USB 5V (1A/2A) untuk catu daya ESP32. | [Shopee](https://id.shp.ee/cU5BVdNP) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=adaptor%20charger%205V%202A) |
| **Kabel Micro USB (Data)** | Rp 10.000 | Untuk flash firmware dari laptop dan suplai daya 5V. | [Shopee](https://id.shp.ee/XJb4pVXk) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=kabel%20data%20micro%20usb) |
| **Kabel Listrik NYAF 0.75 mm² Merah** | Rp 1.900 | Beli 1 meter untuk jalur fasa pengukur voltase. | [Shopee](https://id.shp.ee/xWopGdzV) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=kabel%20nyaf%200.75mm%20merah) |
| **Kabel Listrik NYAF 0.75 mm² Biru** | Rp 1.900 | Beli 1 meter untuk jalur netral pengukur voltase. | [Shopee](https://id.shp.ee/tcgCYbrz) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=kabel%20nyaf%200.75mm%20biru) |
| **Sekring Kaca 5x20 mm 0.5A** | Rp 1.775 | Pengaman arus lebih jalur pengukur tegangan AC. | [Shopee](https://id.shp.ee/DrKdi7Ud) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=sekring%20kaca%205x20%200.5A) |
| **Inline Fuse Holder 5x20 mm** | Rp 910 | Rumah sekring kabel gantung 5x20 mm. | [Shopee](https://id.shp.ee/YB6xA5ik) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=inline%20fuse%20holder%205x20mm) |
| **Baut M3 x 20 mm (4 pcs)** | Rp 6.000 | Pilih varian panjang **20 mm** (*countersunk*) untuk penutup casing v2.0. | [Shopee](https://id.shp.ee/SJiUeVMY) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=baut%20M3%2020mm%20flat%20head) |
| **Baut M2.5 x 6 mm (8 pcs)** | Rp 9.200 | Baut penahan board ESP32 dan PZEM ke standoff casing. | [Shopee](https://id.shp.ee/4MSXiWnQ) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=baut%20M2.5%206mm) |

**Alat kerja di rumah:** Obeng kecil (+/-), tespen listrik, gunting/tang potong, dan isolasi listrik hitam ([Shopee](https://shopee.co.id/search?keyword=tespen%20listrik%20obeng%20kecil) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=tespen%20listrik%20obeng%20kecil)).

**Jasa cetak 3D print:** [Shopee](https://shopee.co.id/search?keyword=jasa%20cetak%203d%20print) • [Tokopedia](https://www.tokopedia.com/search?st=product&q=jasa%20cetak%203d%20print).

---

## 3. Cara Memesan Cetak Casing 3D

Anda tidak perlu memiliki mesin printer 3D sendiri. Cukup gunakan jasa cetak 3D di Tokopedia / Shopee:

1. Buka folder proyek dan ambil file:
   - `hardware/casing_3d/energy_monitor_case.blend` (File proyek Blender asli), atau
   - `hardware/casing_3d/export/enclosure_bottom_base.stl` (Wadah bawah)
   - `hardware/casing_3d/export/enclosure_top_lid.stl` (Tutup atas)
2. Salin pesan ini ke chat toko jasa 3D print:
   > *"Halo kak, mau order cetak 3D untuk 2 file terlampir (Base dan Lid):*  
   > *- Bahan: PETG atau ABS (Bila tidak ada, boleh PLA+)*  
   > *- Infill: 25%, Layer Height: 0.20 mm, Wall Lines: 3 - 4 lapis dinding.*  
   > *Mohon info estimasi berat dan total biayanya kak. Terima kasih!"*
3. Biaya cetak biasanya berkisar antara **Rp 35.000 - Rp 50.000**.

---

## 4. Cara Menyambungkan Kabel (Wiring Sederhana)

Hanya ada 4 kabel dari sensor PZEM ke ESP32:

- **Pin 5V PZEM** ──► **Pin VIN / 5V ESP32** (Kabel Merah)
- **Pin GND PZEM** ──► **Pin GND ESP32** (Kabel Hitam)
- **Pin RX PZEM** ──► **Pin GPIO 17 ESP32** (Kabel Biru)
- **Pin TX PZEM** ──► Sambungkan ke **Resistor 10kΩ**, lalu ujung lainnya ke **Pin GPIO 16 ESP32** (Kabel Hijau).  
  *Dari sambungan antara resistor 10k dan GPIO 16, pasang **Resistor 20kΩ** menuju ke **GND**.*

> **Tips Tanpa Solder:** Kaki resistor cukup dipilin rapat bersama ujung kabel jumper, lalu bungkus dengan isolasi hitam.

---

## 5. Mengisi Program ke ESP32 (Flash Firmware)

1. Colokkan board ESP32 ke laptop menggunakan kabel USB data.
2. Buka file `firmware/include/config.h`, masukkan nama Wi-Fi dan password rumah Anda:

   ```cpp
   #define WIFI_SSID "NAMA_WIFI_RUMAH"
   #define WIFI_PASS "PASSWORD_WIFI"
   #define MQTT_HOST "192.168.1.100"  // IP komputer server
   #define DEVICE_ID "device-01"
   ```

3. Buka terminal PowerShell di folder proyek dan ketik satu baris perintah:

   ```powershell
   .venv\Scripts\pio run -d firmware -e esp32dev -t upload
   ```

4. Tunggu sampai muncul tulisan **[SUCCESS]**. Program sudah berhasil masuk!

---

## 6. Pemasangan Aman ke Panel MCB Rumah

Patuhi 3 aturan keselamatan dasar:

1. **Matikan MCB Utama PLN** di meteran luar rumah (posisi OFF).
2. **Sentuhkan tespen** ke kabel di dalam panel. Pastikan lampu tespen MATI TOTAL.
3. Selalu gunakan sandal karet kering saat bekerja.

**Langkah Pasang:**

1. **Jepitkan Klem CT:** Cari kabel fasa tebal (biasanya hitam atau cokelat) yang keluar dari bawah MCB. Lingkarkan klem CT pada kabel tersebut dan kunci sampai bunyi *klik*. *(Ingat: HANYA jepit 1 kawat fasa saja).*
2. **Kabel Pengukur Voltase:** Sambungkan kabel merah (bersekring) ke baut bawah MCB, dan kabel biru ke busbar kabel netral.
3. **Nyalakan Kembali Listrik:** Nyalakan kembali MCB PLN ke posisi ON. Colokkan charger HP ke port USB alat. Alat akan menyala dan mulai memantau daya listrik secara otomatis.

---

## 7. Solusi Kendala Umum

- **Daya terbaca 0 Watt terus?**  
  Kemungkinan klem CT menjepit kabel ganda (fasa dan netral terjepit sekaligus sehingga saling meniadakan). Buka klem, lalu jepitkan pada **satu kawat fasa saja**.
- **Angka daya muncul tanda minus (-)?**  
  Arah klem CT terbalik. Buka klem dan balik posisinya 180 derajat pada kabel.
- **Nilai terbaca 'nan'?**  
  Baut kabel AC 220V di modul PZEM belum kencang (karena chip sensor butuh daya dari listrik AC), atau kabel data jumper kendor.
