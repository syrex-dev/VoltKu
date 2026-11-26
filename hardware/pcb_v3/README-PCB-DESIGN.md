# Desain Custom PCB & BOM Komersial — VoltKu Pro v3.0

Dokumentasi teknis **Tahap 2** untuk menurunkan HPP perangkat keras ke target **± Rp 95.000 – Rp 135.000/unit** sekaligus meningkatkan akurasi pembacaan beban kecil dan keamanan isolasi AC/DC.

## 1. Spesifikasi Mekanik PCB (`45.0 × 34.0 mm`)
- **Ukuran Papan:** `45.0 × 34.0 mm`, 2-layer FR4 ketebalan `1.6 mm`, tembaga `1 oz` (cocok tepat di dudukan `PCB_Standoff` pada [generate_casing_v3.py](file:///d:/Coding/energy-monitor/hardware/casing_3d/generate_casing_v3.py)).
- **Lubang Baut:** 4 × lubang M2.5 (`Ø 2.7 mm`) pada koordinat `(±19.0, ±13.5 mm)` dari titik tengah papan.
- **Zona Isolasi Galvanik (`≥ 6.5 mm`):**
  - **Sisi Kiri (`X < -4.0 mm`, Domain `MAINS_ISO`):** Referensi `GND_AC` (Netral AC) untuk `BL0942`, pembagi tegangan HV 5-resistor seri (`5 × 390kΩ`), filter RC, *burden resistor* CT `0.5Ω`, dan TVS clamp `SMAJ5.0CA`.
  - **Jalur Penghalang Isolasi (`X = -4.0 .. -1.0 mm`, tanpa copper pour):** Ditempati hanya oleh komponen bersertifikat isolasi: **`B0505S-1WR3`** (`1500VDC` DC-DC isolator) dan **`ADuM1201ARZ`** (`2500Vrms` digital UART isolator), serta slot milled opsional.
  - **Sisi Kanan (`X > -1.0 mm`, Domain `SAFE_DC`):** Referensi `GND_SAFE` yang aman disentuh melalui USB-C (`ESP32-C3 SuperMini`, header `TFT IPS 1.3"`, tombol `SW1`, `ME6211` 3.3V LDO).
- **Komponen Off-Board di Bay Terpisah Casing v3.0:**
  - `PS1` (`HLK-PM01` 5V 3W AC-DC 4000VAC) ditempatkan di bay atas casing (`Y = +30.5 mm`).
  - `J1` (`KF301-2P` AC 220V terminal sekrup), `F1` (`Sekring 0.5A 5x20mm`), `RV1` (`MOV 10D471K`), dan `J2` (konektor CT eksternal) diakses dari bay bawah casing (`Y = -34.5 mm`).

## 2. Mapping Pin `ESP32-C3` ↔ `BL0942` & `TFT IPS 1.3"`
| Fungsi | Pin `ESP32-C3` | Terhubung ke | Keterangan |
|---|---|---|---|
| Metering RX | `GPIO0` (`UART1 RX`) | `ADuM1201 VO2` ← `BL0942 TX` | Bebas dari pin USB (`GPIO18/19`) & `UART0` (`GPIO20/21`) |
| Metering TX | `GPIO1` (`UART1 TX`) | `ADuM1201 VI1` → `BL0942 RX` | Kecepatan `4800 bps` (`SEL=0, SCLK_BPS=0`) |
| TFT SCK | `GPIO4` | `J3 Pin 3 (SCL)` | SPI Clock untuk `ST7789 240×240` |
| TFT MOSI | `GPIO6` | `J3 Pin 4 (SDA)` | SPI Data |
| TFT RES | `GPIO7` | `J3 Pin 5 (RES)` | Hardware Reset |
| TFT DC | `GPIO5` | `J3 Pin 6 (DC)` | Data/Command |
| TFT CS | `GPIO10` | `J3 Pin 7 (CS)` | Opsional (jika modul 8-pin) |
| TFT BLK | `GPIO3` | `J3 Pin 8 (BLK)` | Backlight PWM |
| Tombol PAIR / MENU | `GPIO9` | `SW1` (active-low) | Tahan ≥3 detik untuk Captive Portal / klik singkat ganti halaman layar |
| LED Wi-Fi/Data | `GPIO21` | `LED2` via `R14 (1kΩ)` | Indikator konektivitas panel depan |

## 3. Perhitungan Akurasi & Kalibrasi Sisi Sensor
- **Pembagi Tegangan AC (`VP`):** `R_top = 5 × 390kΩ = 1.95 MΩ`, `R_bottom = 510Ω` (`C3 = 68nF`).
  - Pada `220 Vrms`: `V_VP = 220 × (510 / 1,950,510) = 57.5 mVrms` (di dalam rentang optimal `BL0942` maks `70 mVrms`).
- **Sensing Arus (`IP/IN`) via Split-Core CT Eksternal (`R_burden = 0.5Ω`, 2 × `1.0Ω 1%` paralel):**
  - Pada CT `50A / 50mA` (`1000:1`): arus penuh `50A` menghasilkan `50mA × 0.5Ω = 25.0 mVrms` (aman di bawah batas `30 mVrms` `BL0942`, sekaligus resolusi arus kecil rumah tangga **2× lebih tajam** dibanding CT 100A).
  - Pada CT `100A / 50mA` (`PZCT-02` `2000:1`): arus penuh `100A` menghasilkan `50mA × 0.5Ω = 25.0 mVrms`.
- **Tanpa Kendali Beban AC:** Sesuai [AGENTS.md](file:///d:/Coding/energy-monitor/AGENTS.md), papan tidak memiliki relay pemutus beban AC untuk menjaga keamanan dan isolasi penuh.

## 4. Estimasi HPP Produksi per Unit (Skala Batch)

| Komponen / Biaya | Qty 10 Unit (Semi-Custom) | Qty 50 Unit (Batch Komersial) | Qty 100+ Unit (Produksi) |
|---|---|---|---|
| PCB 2-Layer + SMT Assembly (JLCPCB, incl. `BL0942`, `ADuM1201`, passives) | Rp 45.000 | Rp 28.000 | Rp 21.000 |
| `ESP32-C3 SuperMini` / Bare `ESP32-C3-MINI-1` | Rp 28.000 | Rp 23.000 | Rp 19.500 |
| Isolator DC-DC `B0505S-1WR3` + PSU `HLK-PM01` + Terminal/Fuse/MOV | Rp 36.000 | Rp 29.000 | Rp 24.000 |
| Layar `TFT IPS 1.3" 240×240` (`ST7789`) | Rp 26.000 | Rp 21.000 | Rp 17.500 |
| Split-Core CT Clamp OEM (`30A/50A/100A`) | Rp 32.000 | Rp 25.000 | Rp 21.000 |
| Casing 3D Print PETG / Kotak DIN Standar + Baut | Rp 32.000 | Rp 20.000 | Rp 12.000 |
| **Total HPP per Unit** | **Rp 199.000** | **Rp 146.000** | **Rp 115.000** |

*(Bandingkan dengan biaya rakitan modul DIY eceran sebelumnya Rp 311.244 + casing Rp 40.000 = Rp 351.244 — efisiensi HPP mencapai **43%–67%**, siap bersaing langsung dengan meteran Tuya `Rp 150rb–300rb` dengan fitur software/AI yang jauh lebih lengkap).*

## 5. Verifikasi Desain
Jalankan skrip verifikasi otomatis:
```powershell
python hardware\pcb_v3\verify_pcb_design.py
```
