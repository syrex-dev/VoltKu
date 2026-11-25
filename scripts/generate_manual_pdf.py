"""
Script Generator PDF Manual Book: Monitor Listrik Pintar (Edisi Human-Friendly / Non-AI Feel)
Didesain dengan pendekatan buku panduan konsumen modern (ala Apple/IKEA/Adafruit):
- Tipografi besar, bersih, dan nyaman dibaca (10pt - 11pt, bukan teks mikroskopis).
- Bahasa santai, jelas, dan manusiawi (tanpa jargon kaku atau istilah robotik).
- Diagram wiring visual SVG berwarna (bukan teks ASCII yang bikin pusing).
- Setiap halaman memiliki 1 fokus materi yang lapang dengan ruang bernapas yang cukup.
- Total 8 halaman presisi A4.
"""

import base64
import os
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")
HARDWARE_DIR = os.path.join(PROJECT_DIR, "hardware", "casing_3d")

RENDER_IMG_PATH = os.path.join(HARDWARE_DIR, "render_preview.png")
HTML_OUTPUT_PATH = os.path.join(DOCS_DIR, "manual_book.html")
PDF_OUTPUT_PATH = os.path.join(DOCS_DIR, "MANUAL-BOOK-PERAKITAN-DAN-INSTALASI.pdf")

# Load 3D Render Image as Base64
img_b64 = ""
if os.path.exists(RENDER_IMG_PATH):
    with open(RENDER_IMG_PATH, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

# Template HTML Modern & Bersih
html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Buku Panduan Perakitan & Instalasi - Monitor Listrik Pintar</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 16mm 18mm 16mm 18mm;
      @bottom-right {{
        content: counter(page);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 9pt;
        color: #94a3b8;
      }}
    }}

    *, *::before, *::after {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #334155;
      background: #ffffff;
      line-height: 1.6;
      font-size: 10pt;
    }}

    /* Halaman A4 Presisi */
    .page {{
      width: 100%;
      height: 265mm;
      max-height: 265mm;
      page-break-after: always;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      overflow: hidden;
      position: relative;
    }}

    .page:last-child {{
      page-break-after: avoid;
    }}

    .page-body {{
      flex-grow: 1;
    }}

    /* Header Navigasi Kecil per Halaman */
    .page-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 12px;
      margin-bottom: 20px;
      border-bottom: 1px solid #e2e8f0;
    }}

    .page-header .category {{
      font-size: 8.5pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #2563eb;
    }}

    .page-header .doc-title {{
      font-size: 8.5pt;
      color: #94a3b8;
    }}

    /* Tipografi Judul */
    h1.main-title {{
      font-size: 24pt;
      font-weight: 800;
      color: #0f172a;
      line-height: 1.2;
      margin-bottom: 8px;
      letter-spacing: -0.5px;
    }}

    h2.section-heading {{
      font-size: 17pt;
      font-weight: 800;
      color: #0f172a;
      line-height: 1.25;
      margin-bottom: 8px;
      letter-spacing: -0.3px;
    }}

    p.lead {{
      font-size: 11pt;
      color: #64748b;
      margin-bottom: 22px;
      line-height: 1.5;
    }}

    /* Kartu & Box */
    .card {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 16px 18px;
      margin-bottom: 14px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }}

    .card-title {{
      font-size: 11.5pt;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .card-accent {{
      background: #f8fafc;
      border-left: 4px solid #2563eb;
    }}

    .card-success {{
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      border-left: 4px solid #16a34a;
    }}

    .card-warning {{
      background: #fffbeb;
      border: 1px solid #fef08a;
      border-left: 4px solid #d97706;
    }}

    .card-danger {{
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-left: 4px solid #dc2626;
    }}

    /* Grid 2 Kolom */
    .grid-2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }}

    /* Step Item Elegan */
    .step-box {{
      display: flex;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 16px;
      padding: 14px 16px;
      background: #f8fafc;
      border-radius: 10px;
      border: 1px solid #e2e8f0;
    }}

    .step-badge {{
      background: #2563eb;
      color: #ffffff;
      font-size: 11pt;
      font-weight: 800;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}

    .step-text h3 {{
      font-size: 11pt;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 3px;
    }}

    .step-text p {{
      font-size: 9.5pt;
      color: #475569;
      line-height: 1.45;
    }}

    /* Tabel Bersih & Luas */
    table.clean-table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      margin: 14px 0;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid #e2e8f0;
    }}

    table.clean-table th {{
      background: #f1f5f9;
      color: #0f172a;
      font-weight: 700;
      font-size: 9pt;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid #cbd5e1;
    }}

    table.clean-table td {{
      padding: 10px 14px;
      font-size: 9.5pt;
      border-bottom: 1px solid #f1f5f9;
      vertical-align: middle;
      color: #334155;
    }}

    table.clean-table tr:last-child td {{
      border-bottom: none;
    }}

    table.clean-table tr:nth-child(even) td {{
      background: #fafafa;
    }}

    .tag-price {{
      display: inline-block;
      background: #ecfdf5;
      color: #15803d;
      font-weight: 700;
      font-size: 8.5pt;
      padding: 3px 8px;
      border-radius: 6px;
      border: 1px solid #a7f3d0;
    }}

    /* Template Pesan Chat */
    .chat-bubble {{
      background: #f8fafc;
      border: 1.5px dashed #3b82f6;
      border-radius: 12px;
      padding: 16px 20px;
      margin: 16px 0;
      color: #0f172a;
      font-size: 9.5pt;
      line-height: 1.5;
    }}

    /* Footer Halaman */
    .page-footer {{
      padding-top: 12px;
      border-top: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      color: #94a3b8;
      font-size: 8.5pt;
    }}

    /* Cover Styling */
    .cover-container {{
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      height: 100%;
      padding: 20px 0;
    }}

    .cover-tag {{
      display: inline-block;
      background: #eff6ff;
      color: #2563eb;
      font-size: 9pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      padding: 6px 14px;
      border-radius: 9999px;
      margin-bottom: 16px;
      border: 1px solid #bfdbfe;
    }}

    .cover-image {{
      text-align: center;
      margin: 25px 0;
      background: #090d16;
      border-radius: 16px;
      padding: 16px;
      border: 1px solid #1e293b;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
    }}

    .cover-image img {{
      max-width: 90%;
      max-height: 230px;
      display: block;
      margin: 0 auto;
    }}

    .cover-meta {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 20px;
    }}

    .meta-box {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 12px 14px;
      text-align: center;
    }}

    .meta-box span {{
      display: block;
      font-size: 7.5pt;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #64748b;
      margin-bottom: 2px;
    }}

    .meta-box strong {{
      font-size: 10pt;
      color: #0f172a;
    }}
  </style>
</head>
<body>

  <!-- ==========================================
       HALAMAN 1: SAMPUL RESMI & MINIMALIS
       ========================================== -->
  <div class="page">
    <div class="cover-container">
      <div>
        <div class="cover-tag">PANDUAN PRAKTIS • RAMAH PEMULA</div>
        <h1 class="main-title">Monitor Listrik Pintar</h1>
        <p class="lead" style="font-size: 13pt; margin-bottom: 0;">
          Panduan Lengkap Merangkai, Membuat, dan Menginstalasi Sendiri di Rumah (IoT + AI)
        </p>
      </div>

      <div class="cover-image">
        <img src="data:image/png;base64,{img_b64}" alt="3D Render Enclosure Monitor Listrik Pintar">
        <div style="color: #94a3b8; font-size: 8.5pt; margin-top: 8px;">
          Desain Fisik Casing 3D: Modul Pengaman Berisolasi (DIN Rail Standar Panel MCB)
        </div>
      </div>

      <div>
        <div class="card card-accent" style="margin-bottom: 16px;">
          <div class="card-title">✨ Dibuat Khusus untuk Non-Teknisi & Non-Desainer</div>
          <p style="font-size: 9.5pt; color: #475569;">
            Anda tidak perlu ahli kelistrikan atau bisa software 3D. Seluruh berkas cetak sudah siap diserahkan ke jasa print, komponen mudah dibeli online, dan pemasangan dijamin <strong>100% aman tanpa memotong kabel PLN</strong>.
          </p>
        </div>

        <div class="cover-meta">
          <div class="meta-box">
            <span>Tingkat Kesulitan</span>
            <strong>Sangat Mudah</strong>
          </div>
          <div class="meta-box">
            <span>Estimasi Biaya</span>
            <strong>± Rp 200 Ribuan</strong>
          </div>
          <div class="meta-box">
            <span>Metode Sensor</span>
            <strong>Non-Invasif (Klem)</strong>
          </div>
        </div>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 1 dari 8</span>
    </div>
  </div>

  <!-- ==========================================
       HALAMAN 2: BAGAIMANA ALAT INI BEKERJA?
       ========================================== -->
  <div class="page">
    <div class="page-body">
      <div class="page-header">
        <span class="category">Bagian 1 • Konsep Dasar</span>
        <span class="doc-title">Monitor Listrik Pintar</span>
      </div>

      <h2 class="section-heading">Bagaimana Alat Ini Bekerja?</h2>
      <p class="lead">
        Sebelum mulai, mari pahami konsep sederhananya. Alat ini dirancang dengan prinsip kerja yang sangat aman dan praktis.
      </p>

      <div class="step-box">
        <div class="step-badge">1</div>
        <div class="step-text">
          <h3>Klem Sensor Arus (Seperti Stetoskop Dokter)</h3>
          <p>
            Alat ini menggunakan sensor arus jenis <strong>Split-Core CT</strong> berbentuk klem buka-tutup. Klem ini cukup dijepitkan melingkari kabel listrik utama. Sensor akan membaca aliran listrik secara magnetik <strong>tanpa perlu memotong atau mengupas kulit kabel sama sekali</strong>.
          </p>
        </div>
      </div>

      <div class="step-box">
        <div class="step-badge">2</div>
        <div class="step-text">
          <h3>Modul PZEM-004T (Kalkulator Daya Presisi)</h3>
          <p>
            Sinyal dari klem arus dan kabel tegangan dihitung secara otomatis oleh modul PZEM-004T menjadi parameter lengkap: Voltase (V), Arus (A), Watt nyata (W), dan total konsumsi listrik bulanan (kWh).
          </p>
        </div>
      </div>

      <div class="step-box">
        <div class="step-badge">3</div>
        <div class="step-text">
          <h3>Otak ESP32 (Mengirim Data ke Wi-Fi Rumah)</h3>
          <p>
            Mikrokontroler kecil ESP32 mengambil hasil perhitungan PZEM tiap detik, lalu mengirimkannya melalui sinyal Wi-Fi ke layar Dashboard laptop/HP dan mengirimkan laporan/notifikasi bahaya ke bot Telegram Anda.
          </p>
        </div>
      </div>

      <div class="card card-success" style="margin-top: 20px;">
        <div class="card-title">🛡️ Kenapa Pemasangannya Dijamin Aman?</div>
        <p style="font-size: 9.5pt; color: #166534; line-height: 1.5;">
          • <strong>Tidak Ada Beban yang Dilepas:</strong> Listrik rumah tetap mengalir normal seperti biasa.<br>
          • <strong>Sekat Pembatas Fisik:</strong> Casing 3D yang kita buat memiliki dinding pemisah (*barrier*) agar kabel listrik AC 220V tidak mungkin menyentuh bagian elektronik mikro 5V.<br>
          • <strong>Tanpa Biaya Bulanan:</strong> Seluruh sistem bekerja mandiri di jaringan rumah Anda.
        </p>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 2 dari 8</span>
    </div>
  </div>

  <!-- ==========================================
       HALAMAN 3: DAFTAR BELANJA KOMPONEN
       ========================================== -->
  <div class="page">
    <div class="page-body">
      <div class="page-header">
        <span class="category">Bagian 2 • Pengadaan Bahan</span>
        <span class="doc-title">Daftar Belanja</span>
      </div>

      <h2 class="section-heading">Daftar Belanja Komponen</h2>
      <p class="lead">
        Semua barang di bawah ini sangat umum dan dapat langsung Anda beli di Tokopedia atau Shopee.
      </p>

      <table class="clean-table">
        <thead>
          <tr>
            <th style="width: 32%;">Nama Komponen</th>
            <th style="width: 18%;">Harga Estimasi</th>
            <th style="width: 50%;">Catatan Pembelian (Penting)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>ESP32 DevKit V1</strong></td>
            <td><span class="tag-price">Rp 55.000</span></td>
            <td>Pilih varian 30 atau 38 pin yang kakinya sudah tersolder rapi.</td>
          </tr>
          <tr>
            <td><strong>PZEM-004T v3.0 (100A)</strong></td>
            <td><span class="tag-price">Rp 95.000</span></td>
            <td><strong>Wajib pilih varian Split-Core CT</strong> (klem biru/hitam buka-tutup), jangan varian donat tertutup!</td>
          </tr>
          <tr>
            <td><strong>Resistor 10kΩ & 20kΩ</strong></td>
            <td><span class="tag-price">Rp 1.000</span></td>
            <td>Resistor 1/4 watt biasa untuk melindungi pin ESP32 dari lonjakan sinyal.</td>
          </tr>
          <tr>
            <td><strong>Kabel Jumper Dupont (F-to-F)</strong></td>
            <td><span class="tag-price">Rp 8.000</span></td>
            <td>Panjang 20 cm (1 papan isi 10 kabel) untuk menghubungkan pin tanpa solder.</td>
          </tr>
          <tr>
            <td><strong>Charger HP 5V + Kabel USB</strong></td>
            <td><span class="tag-price">Rp 20.000</span></td>
            <td>Charger HP biasa (1A atau 2A) untuk menyalakan alat dengan aman.</td>
          </tr>
          <tr>
            <td><strong>Kabel Listrik NYAF 0.75 mm²</strong></td>
            <td><span class="tag-price">Rp 10.000</span></td>
            <td>Beli 1 meter kabel merah (fasa) dan 1 meter kabel biru (netral).</td>
          </tr>
          <tr>
            <td><strong>Sekring Kaca 5x20mm 0.5A</strong></td>
            <td><span class="tag-price">Rp 4.000</span></td>
            <td>Lengkap dengan rumah sekring (*inline fuse holder*) sebagai pengaman.</td>
          </tr>
          <tr>
            <td><strong>Baut M3 (4 pcs) & M2.5 (8 pcs)</strong></td>
            <td><span class="tag-price">Rp 6.000</span></td>
            <td>M3 x 12mm untuk penutup casing, M2.5 x 6mm untuk penahan board.</td>
          </tr>
        </tbody>
      </table>

      <div style="text-align: right; font-weight: 700; font-size: 9.5pt; color: #2563eb; margin-bottom: 14px;">
        Total Biaya Komponen: ± Rp 199.000 - Rp 220.000
      </div>

      <div class="card card-accent">
        <div class="card-title">🔧 Perkakas Rumah Tangga yang Diperlukan:</div>
        <p style="font-size: 9pt; color: #475569; line-height: 1.5;">
          • 1 buah <strong>Obeng Plus (+) dan Minus (-) kecil</strong>.<br>
          • 1 buah <strong>Tespen listrik</strong> (wajib untuk cek arus sebelum pegang panel).<br>
          • 1 buah <strong>Gunting / tang potong kecil</strong> dan <strong>isolasi listrik hitam</strong>.
        </p>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 3 dari 8</span>
    </div>
  </div>

  <!-- ==========================================
       HALAMAN 4: CARA CETAK CASING 3D
       ========================================== -->
  <div class="page">
    <div class="page-body">
      <div class="page-header">
        <span class="category">Bagian 3 • Casing Pelindung</span>
        <span class="doc-title">Cetak 3D Casing</span>
      </div>

      <h2 class="section-heading">Cara Memesan Cetak Casing 3D</h2>
      <p class="lead">
        Anda tidak perlu punya printer 3D sendiri. Di Tokopedia atau Shopee ada banyak jasa print 3D dengan biaya terjangkau (sekitar Rp 35.000 - Rp 50.000).
      </p>

      <div class="card">
        <div class="card-title">📁 File yang Harus Anda Serahkan:</div>
        <p style="font-size: 9.5pt; color: #475569; margin-bottom: 8px;">
          Semua file ini sudah siap di komputer Anda (di dalam folder proyek):
        </p>
        <ul style="font-size: 9pt; color: #334155; margin-left: 20px; line-height: 1.6;">
          <li><strong>Opsi Utama (File Blender):</strong> <code>hardware/casing_3d/energy_monitor_case.blend</code></li>
          <li><strong>Opsi Standar Jasa Cetak (File STL):</strong><br>
            1. <code>hardware/casing_3d/export/enclosure_bottom_base.stl</code> (Wadah Bawah)<br>
            2. <code>hardware/casing_3d/export/enclosure_top_lid.stl</code> (Tutup Atas)
          </li>
        </ul>
      </div>

      <div class="card-title" style="margin-top: 16px;">💬 Contoh Chat ke Admin Jasa Cetak 3D:</div>
      <div class="chat-bubble">
        "Halo kak, saya mau order jasa 3D print untuk mencetak 2 file terlampir (Base dan Lid):<br><br>
        • <strong>Bahan Filament:</strong> PETG atau ABS (Warna Abu-Abu / Hitam / Putih). Bila tidak ada, boleh PLA+.<br>
        • <strong>Infill:</strong> 25% (Pola Grid atau Gyroid).<br>
        • <strong>Layer Height:</strong> 0.20 mm (Kerapatan standar halus).<br>
        • <strong>Wall Perimeters:</strong> 3 - 4 lapis dinding.<br><br>
        Mohon info estimasi berat total dan biayanya kak. Terima kasih!"
      </div>

      <div class="card card-success">
        <div class="card-title">💡 Kenapa Direkomendasikan Bahan PETG atau ABS?</div>
        <p style="font-size: 9pt; color: #166534;">
          Bahan PETG dan ABS lebih tahan terhadap panas udara di dalam box panel listrik dibandingkan PLA biasa. Namun jika jasa print hanya menyediakan PLA+, pilihlah varian <strong>PLA+ (Plus)</strong> yang juga sudah cukup kokoh.
        </p>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 4 dari 8</span>
    </div>
  </div>

  <!-- ==========================================
       HALAMAN 5: PANDUAN MERANGKAI KABEL (WIRING)
       ========================================== -->
  <div class="page">
    <div class="page-body">
      <div class="page-header">
        <span class="category">Bagian 4 • Rangkaian Elektronik</span>
        <span class="doc-title">Diagram Sambungan Kabel</span>
      </div>

      <h2 class="section-heading">Diagram Sambungan Kabel (Wiring)</h2>
      <p class="lead">
        Hanya ada 4 kabel sinyal dari PZEM ke ESP32. Sangat simpel dan bisa dirangkai tanpa solder.
      </p>

      <!-- DIAGRAM SVG VECTOR BERSIH & JELAS -->
      <div style="text-align: center; margin: 15px 0;">
        <svg viewBox="0 0 680 230" width="100%" height="auto" style="background:#090d16; border-radius:12px; border:1px solid #1e293b; font-family: -apple-system, sans-serif;">
          <!-- Modul PZEM-004T (Kiri) -->
          <rect x="30" y="30" width="180" height="170" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" />
          <text x="120" y="55" fill="#38bdf8" font-size="12" font-weight="800" text-anchor="middle">PZEM-004T v3.0</text>
          <text x="120" y="70" fill="#94a3b8" font-size="9" text-anchor="middle">Modul Sensor Listrik</text>
          
          <!-- Pin PZEM -->
          <rect x="170" y="90" width="30" height="16" rx="3" fill="#ef4444" />
          <text x="185" y="102" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">5V</text>
          
          <rect x="170" y="115" width="30" height="16" rx="3" fill="#3b82f6" />
          <text x="185" y="127" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">RX</text>
          
          <rect x="170" y="140" width="30" height="16" rx="3" fill="#10b981" />
          <text x="185" y="152" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">TX</text>
          
          <rect x="170" y="165" width="30" height="16" rx="3" fill="#475569" />
          <text x="185" y="177" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">GND</text>

          <!-- Modul ESP32 (Kanan) -->
          <rect x="470" y="30" width="180" height="170" rx="8" fill="#1e293b" stroke="#0ea5e9" stroke-width="1.5" />
          <text x="560" y="55" fill="#38bdf8" font-size="12" font-weight="800" text-anchor="middle">ESP32 DevKit</text>
          <text x="560" y="70" fill="#94a3b8" font-size="9" text-anchor="middle">Mikrokontroler Wi-Fi</text>

          <!-- Pin ESP32 -->
          <rect x="480" y="90" width="36" height="16" rx="3" fill="#ef4444" />
          <text x="498" y="102" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">VIN</text>
          
          <rect x="480" y="115" width="36" height="16" rx="3" fill="#3b82f6" />
          <text x="498" y="127" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">GPIO17</text>
          
          <rect x="480" y="140" width="36" height="16" rx="3" fill="#10b981" />
          <text x="498" y="152" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">GPIO16</text>
          
          <rect x="480" y="165" width="36" height="16" rx="3" fill="#475569" />
          <text x="498" y="177" fill="#fff" font-size="8" font-weight="700" text-anchor="middle">GND</text>

          <!-- Jalur Kabel Warna-Warni -->
          <!-- 5V ke VIN -->
          <path d="M 200 98 L 480 98" stroke="#ef4444" stroke-width="2.5" fill="none" />
          
          <!-- RX ke GPIO17 (TX2) -->
          <path d="M 200 123 L 480 123" stroke="#3b82f6" stroke-width="2.5" fill="none" />

          <!-- TX ke Resistor Divider ke GPIO16 -->
          <path d="M 200 148 L 270 148" stroke="#10b981" stroke-width="2.5" fill="none" />
          
          <!-- Resistor 10k -->
          <rect x="270" y="141" width="38" height="14" rx="2" fill="#f59e0b" stroke="#fff" stroke-width="1" />
          <text x="289" y="152" fill="#0f172a" font-size="7.5" font-weight="800" text-anchor="middle">10kΩ</text>
          
          <path d="M 308 148 L 480 148" stroke="#10b981" stroke-width="2.5" fill="none" />

          <!-- Resistor 20k turun ke GND -->
          <circle cx="340" cy="148" r="3" fill="#10b981" />
          <path d="M 340 148 L 340 162" stroke="#64748b" stroke-width="2" fill="none" />
          <rect x="325" y="162" width="30" height="14" rx="2" fill="#f59e0b" stroke="#fff" stroke-width="1" />
          <text x="340" y="173" fill="#0f172a" font-size="7.5" font-weight="800" text-anchor="middle">20kΩ</text>
          <path d="M 340 176 L 340 188 L 410 188" stroke="#64748b" stroke-width="2" fill="none" />

          <!-- GND ke GND -->
          <path d="M 200 173 L 480 173" stroke="#94a3b8" stroke-width="2.5" stroke-dasharray="4,4" fill="none" />
        </svg>
      </div>

      <div class="card card-warning">
        <div class="card-title">⚠️ Kenapa Harus Ada Resistor 10kΩ dan 20kΩ?</div>
        <p style="font-size: 9pt; color: #92400e; line-height: 1.5;">
          Modul PZEM mengeluarkan sinyal listrik 5 Volt, sedangkan otak ESP32 bekerja pada 3.3 Volt. Resistor 10k dan 20k ini berfungsi seperti "kran penurun tekanan" sederhana agar chip ESP32 awet dan tidak kepanasan.
        </p>
      </div>

      <div class="card" style="margin-top: 10px;">
        <div class="card-title">💡 Cara Menyambungkan Resistor Tanpa Solder:</div>
        <p style="font-size: 9pt; color: #475569;">
          Cukup pilin (putar rapat) kawat kaki resistor bersama ujung kawat kabel jumper Dupont, lalu balut dengan isolasi listrik hitam agar kencang dan tidak bersentuhan dengan kabel lain.
        </p>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 5 dari 8</span>
    </div>
  </div>

  <!-- ==========================================
       HALAMAN 6: MENGISI PROGRAM KE ESP32
       ========================================== -->
  <div class="page">
    <div class="page-body">
      <div class="page-header">
        <span class="category">Bagian 5 • Perangkat Lunak</span>
        <span class="doc-title">Pengisian Program (Flash)</span>
      </div>

      <h2 class="section-heading">Mengisi Program ke ESP32 (Flash)</h2>
      <p class="lead">
        Lakukan langkah ini di laptop/PC Anda sebelum memasang alat ke dalam box panel listrik.
      </p>

      <div class="step-box">
        <div class="step-badge">1</div>
        <div class="step-text">
          <h3>Colokkan ESP32 ke Laptop Menggunakan Kabel USB</h3>
          <p>
            Gunakan kabel USB yang bisa mentransfer data (kabel bawaan smartphone Android biasanya bisa). Lampu merah kecil di board ESP32 akan menyala.
          </p>
        </div>
      </div>

      <div class="step-box">
        <div class="step-badge">2</div>
        <div class="step-text">
          <h3>Masukkan Nama Wi-Fi & Password Rumah Anda</h3>
          <p>
            Buka file <code>firmware/include/config.h</code> di laptop Anda dengan Notepad atau VS Code. Ganti nama Wi-Fi dan password dengan milik rumah Anda:
          </p>
          <div style="background:#090d16; color:#38bdf8; padding:8px 12px; border-radius:6px; font-family:monospace; font-size:8pt; margin-top:6px;">
            #define WIFI_SSID <span style="color:#34d399;">"Wi-Fi_Rumah_Anda"</span><br>
            #define WIFI_PASS <span style="color:#34d399;">"Password_Wi-Fi_Anda"</span><br>
            #define DEVICE_ID <span style="color:#fbbf24;">"device-01"</span>
          </div>
        </div>
      </div>

      <div class="step-box">
        <div class="step-badge">3</div>
        <div class="step-text">
          <h3>Jalankan Perintah Upload (Satu Baris Saja)</h3>
          <p>
            Buka PowerShell di laptop Anda, lalu ketikkan perintah berikut dan tekan Enter:
          </p>
          <div style="background:#090d16; color:#34d399; padding:8px 12px; border-radius:6px; font-family:monospace; font-size:8.5pt; font-weight:700; margin-top:6px;">
            .venv\Scripts\pio run -d firmware -e esp32dev -t upload
          </div>
          <p style="margin-top: 6px;">
            Tunggu sampai proses mencapai 100% dan muncul tulisan hijau: <strong>[SUCCESS]</strong>. Selesai! Program sudah masuk ke dalam chip ESP32 Anda.
          </p>
        </div>
      </div>

      <div class="card card-accent" style="margin-top: 14px;">
        <div class="card-title">🔍 Cara Memastikan Program Berjalan Normal:</div>
        <p style="font-size: 9pt; color: #475569;">
          Ketikkan perintah: <code>.venv\Scripts\pio device monitor -d firmware -b 115200</code><br>
          Jika muncul tulisan: <code>[WiFi] Terhubung!</code> dan <code>[MQTT] Terhubung ke broker!</code>, berarti ESP32 Anda sudah 100% sehat dan siap bekerja!
        </p>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 6 dari 8</span>
    </div>
  </div>

  <!-- ==========================================
       HALAMAN 7: PEMASANGAN AMAN KE PANEL LISTRIK
       ========================================== -->
  <div class="page">
    <div class="page-body">
      <div class="page-header">
        <span class="category">Bagian 6 • Instalasi Rumah</span>
        <span class="doc-title">Pemasangan ke Box Panel MCB</span>
      </div>

      <h2 class="section-heading">Pemasangan Aman ke Panel MCB (K3)</h2>
      <p class="lead">
        Ikuti 3 aturan emas keselamatan ini. Anda tidak perlu takut tersetrum selama mematuhi panduan ini.
      </p>

      <div class="card card-danger">
        <div class="card-title">🚨 3 ATURAN EMAS KESELAMATAN (WAJIB DIBACA):</div>
        <p style="font-size: 9pt; color: #991b1b; line-height: 1.5;">
          1. <strong>Matikan MCB Utama PLN:</strong> Turunkan tuas MCB di meteran luar rumah ke posisi <strong>OFF</strong> sebelum membuka box panel.<br>
          2. <strong>Cek dengan Tespen:</strong> Tempelkan obeng tespen ke terminal kabel listrik di dalam box. Pastikan lampu tespen <strong>MATI TOTAL</strong>.<br>
          3. <strong>Gunakan Sandal Karet:</strong> Selalu gunakan alas kaki karet yang kering selama pengerjaan.
        </p>
      </div>

      <div class="step-box" style="margin-top: 16px;">
        <div class="step-badge">1</div>
        <div class="step-text">
          <h3>Jepitkan Klem Sensor CT pada Kabel Fasa (Hitam/Cokelat)</h3>
          <p>
            Cari kabel tebal yang keluar dari bawah MCB utama rumah Anda. Buka pengait klem sensor CT, lingkarkan pada kabel tersebut, lalu tekan hingga berbunyi <em>klik</em>.<br>
            <strong style="color: #dc2626;">PENTING:</strong> Klem HANYA boleh melingkari 1 kabel fasa saja. Jangan menjepit kabel fasa dan netral bersamaan!
          </p>
        </div>
      </div>

      <div class="step-box">
        <div class="step-badge">2</div>
        <div class="step-text">
          <h3>Sambungkan 2 Kabel Pengukur Voltase</h3>
          <p>
            Kabel merah (bersekring 0.5A) dimasukkan ke baut terminal bawah MCB.<br>
            Kabel biru dimasukkan ke terminal kabel netral di box panel.<br>
            Kedua kabel ini dimasukkan ke terminal baut AC pada casing alat Anda.
          </p>
        </div>
      </div>

      <div class="step-box">
        <div class="step-badge">3</div>
        <div class="step-text">
          <h3>Posisikan Casing & Nyalakan Kembali Listrik</h3>
          <p>
            Jepitkan casing ke rel panel atau rekatkan di dinding dalam box panel dengan double tape 3M. Colokkan adaptor charger HP ke port USB ESP32. Naikkan kembali MCB PLN ke posisi <strong>ON</strong>. Selesai!
          </p>
        </div>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 7 dari 8</span>
    </div>
  </div>

  <!-- ==========================================
       HALAMAN 8: TANYA JAWAB & SOLUSI MASALAH
       ========================================== -->
  <div class="page">
    <div class="page-body">
      <div class="page-header">
        <span class="category">Bagian 7 • Tanya Jawab</span>
        <span class="doc-title">Troubleshooting</span>
      </div>

      <h2 class="section-heading">Tanya Jawab & Solusi Masalah</h2>
      <p class="lead">
        Jika ada kendala saat pengujian pertama kali, berikut jawaban dan solusi praktisnya.
      </p>

      <div class="card" style="margin-bottom: 12px;">
        <div class="card-title">❓ Kenapa angka daya di Dashboard selalu 0 Watt padahal lampu menyala?</div>
        <p style="font-size: 9pt; color: #475569; margin-top: 4px;">
          <strong>Penyebab:</strong> Klem sensor CT Anda menjepit kabel ganda (kabel fasa dan netral terjepit bersamaan), sehingga medan magnetnya saling meniadakan.<br>
          <strong>Solusi:</strong> Buka klem CT, pisahkan kedua urat kabel, dan jepitkan klem pada <strong>satu kawat kabel fasa saja</strong>.
        </p>
      </div>

      <div class="card" style="margin-bottom: 12px;">
        <div class="card-title">❓ Angka daya atau faktor daya (PF) muncul tanda minus (-), kenapa?</div>
        <p style="font-size: 9pt; color: #475569; margin-top: 4px;">
          <strong>Penyebab:</strong> Arah hadap klem sensor CT terbalik pada kabel.<br>
          <strong>Solusi:</strong> Sangat mudah! Buka klem CT, lalu balik posisinya 180 derajat pada kabel yang sama.
        </p>
      </div>

      <div class="card" style="margin-bottom: 12px;">
        <div class="card-title">❓ Pada monitor serial tertulis nilai 'nan' (Not a Number)?</div>
        <p style="font-size: 9pt; color: #475569; margin-top: 4px;">
          <strong>Penyebab:</strong> Komunikasi kabel data antara PZEM dan ESP32 kendor, ATAU kabel AC 220V belum terpasang kencang.<br>
          <strong>Solusi:</strong> Pastikan baut kabel AC 220V sudah kencang (karena chip sensor PZEM mengambil daya dari listrik AC), dan periksa kembali sambungan resistor 10k/20k.
        </p>
      </div>

      <div class="card" style="margin-bottom: 12px;">
        <div class="card-title">❓ ESP32 tidak bisa tersambung ke Wi-Fi rumah?</div>
        <p style="font-size: 9pt; color: #475569; margin-top: 4px;">
          <strong>Penyebab:</strong> Huruf besar/kecil password salah, atau router hanya memancarkan frekuensi 5 GHz.<br>
          <strong>Solusi:</strong> Pastikan router memancarkan frekuensi 2.4 GHz (standar seluruh router rumah di Indonesia). Periksa kembali penulisan password di <code>config.h</code>.
        </p>
      </div>

      <div class="card card-success" style="margin-top: 16px;">
        <div class="card-title">🎉 Selamat! Alat Anda Resmi Beroperasi!</div>
        <p style="font-size: 9pt; color: #166534;">
          Sekarang Anda bisa memantau konsumsi listrik rumah secara real-time dari Dashboard web dan menerima peringatan bot Telegram saat ada pemborosan daya atau potensi anomali.
        </p>
      </div>
    </div>
    <div class="page-footer">
      <span>Monitor Listrik Pintar • Panduan Perakitan Mandiri</span>
      <span>Halaman 8 dari 8</span>
    </div>
  </div>

</body>
</html>
"""

with open(HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"-> File HTML berhasil diperbarui: {HTML_OUTPUT_PATH}")

# Panggil Google Chrome Headless untuk cetak PDF berkualitas tinggi
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
cmd = [
    CHROME_PATH,
    "--headless=new",
    "--disable-gpu",
    "--no-pdf-header-footer",
    f"--print-to-pdf={PDF_OUTPUT_PATH}",
    HTML_OUTPUT_PATH
]

print("Menjalankan Google Chrome Headless untuk menghasilkan PDF booklet 8 halaman...")
result = subprocess.run(cmd, capture_output=True, text=True)
if os.path.exists(PDF_OUTPUT_PATH):
    size_kb = os.path.getsize(PDF_OUTPUT_PATH) / 1024
    print(f"-> SUKSES! PDF berhasil dibuat: {PDF_OUTPUT_PATH} ({size_kb:.1f} KB)")
else:
    print(f"Gagal membuat PDF: {result.stderr}")
