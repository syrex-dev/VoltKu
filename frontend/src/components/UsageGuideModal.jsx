import React, { useState } from 'react'
import { ArrowLeft, Plus, Wifi, Sparkles, BookOpen, CheckCircle2, Zap, SlidersHorizontal, Bot } from 'lucide-react'

function StepPhoneMockup({ stepNum }) {
  if (stepNum === 1) {
    return (
      <div className="ug-illus-card">
        <svg viewBox="0 0 260 120" className="ug-illus-svg" aria-hidden="true">
          <rect x="46" y="18" width="168" height="84" rx="16" className="ug-mock-panel" />
          <rect x="64" y="34" width="54" height="52" rx="10" className="ug-mock-box" />
          <path d="M84 48 L77 60 H85 L82 72 L95 57 H86 Z" fill="#1677ff" />
          <circle cx="152" cy="54" r="16" className="ug-led-halo" />
          <circle cx="152" cy="54" r="7" fill="#1677ff" />
          <path d="M168 38 L184 28" stroke="#60a5fa" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M172 54 L190 54" stroke="#60a5fa" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M168 70 L184 80" stroke="#60a5fa" strokeWidth="2.5" strokeLinecap="round" />
          <rect x="132" y="78" width="56" height="16" rx="8" fill="#1677ff" />
          <text x="160" y="89" textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="700">
            Tahan 5 dtk
          </text>
        </svg>
      </div>
    )
  }

  if (stepNum === 2) {
    return (
      <div className="ug-phone-frame">
        <svg viewBox="0 0 210 190" className="ug-phone-svg" aria-hidden="true">
          <rect x="20" y="8" width="170" height="176" rx="22" className="ug-phone-shell" />
          <rect x="28" y="16" width="154" height="160" rx="15" className="ug-phone-screen" />
          <rect x="78" y="21" width="54" height="5" rx="2.5" className="ug-phone-notch" />
          {/* Header & Room Tabs */}
          <rect x="38" y="36" width="60" height="8" rx="4" className="ug-ui-muted" />
          <rect x="38" y="56" width="134" height="24" rx="8" fill="#1677ff" opacity="0.16" />
          <rect x="44" y="65" width="44" height="6" rx="3" fill="#1677ff" />
          <circle cx="159" cy="68" r="10" fill="#1677ff" />
          <path d="M159 63 V73 M154 68 H164" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" />
          {/* Highlight Dashed Box & Arrow */}
          <rect
            x="145"
            y="54"
            width="28"
            height="28"
            rx="8"
            fill="none"
            stroke="#f59e0b"
            strokeWidth="2"
            strokeDasharray="3 2"
          />
          <path d="M126 116 C138 106, 148 96, 155 86" fill="none" stroke="#ffffff" strokeWidth="3.5" strokeLinecap="round" />
          <path d="M148 89 L156 85 L157 94" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M126 116 C138 106, 148 96, 155 86" fill="none" stroke="#1677ff" strokeWidth="2" strokeLinecap="round" />
          {/* Empty Box Preview */}
          <rect x="65" y="108" width="80" height="24" rx="12" fill="#1677ff" />
          <text x="105" y="123" textAnchor="middle" fill="#ffffff" fontSize="8.5" fontWeight="700">
            + Tambah Sekarang
          </text>
        </svg>
      </div>
    )
  }

  if (stepNum === 3) {
    return (
      <div className="ug-phone-frame">
        <svg viewBox="0 0 210 190" className="ug-phone-svg" aria-hidden="true">
          <rect x="20" y="8" width="170" height="176" rx="22" className="ug-phone-shell" />
          <rect x="28" y="16" width="154" height="160" rx="15" className="ug-phone-screen" />
          <rect x="78" y="21" width="54" height="5" rx="2.5" className="ug-phone-notch" />
          <rect x="40" y="34" width="90" height="8" rx="4" className="ug-ui-muted" />
          {/* Highlighted Card 1: Quick Pairing / Wi-Fi 2.4GHz */}
          <rect x="38" y="54" width="134" height="48" rx="11" fill="#1677ff" />
          <circle cx="57" cy="78" r="11" fill="rgba(255,255,255,0.22)" />
          <path d="M51 78 Q57 72 63 78 M54 81 Q57 78 60 81" fill="none" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" />
          <rect x="74" y="67" width="76" height="7" rx="3.5" fill="#ffffff" />
          <rect x="74" y="80" width="60" height="5" rx="2.5" fill="rgba(255,255,255,0.75)" />
          <rect
            x="35"
            y="51"
            width="140"
            height="54"
            rx="13"
            fill="none"
            stroke="#fbbf24"
            strokeWidth="2"
            strokeDasharray="4 3"
          />
          {/* Card 2 */}
          <rect x="38" y="114" width="134" height="38" rx="10" className="ug-ui-card" />
          <rect x="48" y="128" width="70" height="6" rx="3" className="ug-ui-muted" />
          {/* Arrow */}
          <path d="M126 142 L106 106" fill="none" stroke="#1677ff" strokeWidth="3" strokeLinecap="round" />
          <path d="M104 115 L105 105 L114 109" fill="none" stroke="#1677ff" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    )
  }

  if (stepNum === 4) {
    return (
      <div className="ug-phone-frame">
        <svg viewBox="0 0 210 190" className="ug-phone-svg" aria-hidden="true">
          <rect x="20" y="8" width="170" height="176" rx="22" className="ug-phone-shell" />
          <rect x="28" y="16" width="154" height="160" rx="15" className="ug-phone-screen" />
          <rect x="78" y="21" width="54" height="5" rx="2.5" className="ug-phone-notch" />
          {/* 2.4GHz Badge */}
          <rect x="40" y="34" width="94" height="16" rx="8" fill="rgba(16,185,129,0.18)" />
          <text x="87" y="45" textAnchor="middle" fill="#10b981" fontSize="8" fontWeight="700">
            Hanya Wi-Fi 2.4 GHz ✓
          </text>
          {/* SSID & Password box */}
          <rect x="38" y="58" width="134" height="66" rx="10" className="ug-ui-card" />
          <rect x="46" y="68" width="84" height="16" rx="6" className="ug-ui-inset" />
          <text x="52" y="79" fill="#64748b" fontSize="7.5" fontWeight="600">
            Wi-Fi Rumah (2.4G)
          </text>
          <rect x="46" y="92" width="118" height="18" rx="6" className="ug-ui-inset" />
          <text x="52" y="104" fill="#64748b" fontSize="9" fontWeight="700">
            • • • • • • • •
          </text>
          {/* Save & Next button */}
          <rect x="38" y="136" width="134" height="24" rx="12" fill="#1677ff" />
          <text x="105" y="151" textAnchor="middle" fill="#ffffff" fontSize="8.5" fontWeight="700">
            Simpan &amp; Lanjut →
          </text>
        </svg>
      </div>
    )
  }

  return (
    <div className="ug-phone-frame">
      <svg viewBox="0 0 210 190" className="ug-phone-svg" aria-hidden="true">
        <rect x="20" y="8" width="170" height="176" rx="22" className="ug-phone-shell" />
        <rect x="28" y="16" width="154" height="160" rx="15" className="ug-phone-screen" />
        <rect x="78" y="21" width="54" height="5" rx="2.5" className="ug-phone-notch" />
        {/* QR Scan Viewport */}
        <rect x="42" y="34" width="126" height="68" rx="10" fill="#0f172a" />
        <rect x="66" y="44" width="78" height="48" rx="8" fill="none" stroke="#38bdf8" strokeWidth="2" />
        <line x1="72" y1="68" x2="138" y2="68" stroke="#38bdf8" strokeWidth="2" />
        {/* Input code filled */}
        <rect x="42" y="110" width="126" height="22" rx="7" className="ug-ui-card" />
        <text x="50" y="124" fill="#1677ff" fontSize="8.5" fontWeight="700">
          ML-A1B2C3 ✓
        </text>
        <rect x="42" y="140" width="126" height="24" rx="12" fill="#10b981" />
        <text x="105" y="155" textAnchor="middle" fill="#ffffff" fontSize="8.5" fontWeight="700">
          Selesai &amp; Pantau Listrik
        </text>
      </svg>
    </div>
  )
}

export function UsageGuideModal({ isOpen, onClose, onStartAddDevice }) {
  const [guideTab, setGuideTab] = useState('pairing')

  if (!isOpen) return null

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern ug-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Panduan Cara Pemakaian VoltKu"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Clean Header matching eWeLink Guide screen */}
        <div className="ug-sticky-head">
          <div className="ug-topbar">
            <button
              type="button"
              className="ug-back-btn"
              onClick={onClose}
              aria-label="Kembali"
            >
              <ArrowLeft size={19} />
            </button>
            <h2 className="ug-title">Cara Pemakaian VoltKu</h2>
            <span aria-hidden="true" style={{ width: 32 }} />
          </div>

          <div className="ug-tab-row" role="tablist" aria-label="Pilih topik panduan">
            <button
              type="button"
              role="tab"
              aria-selected={guideTab === 'pairing'}
              className={`ug-tab-pill ${guideTab === 'pairing' ? 'active' : ''}`}
              onClick={() => setGuideTab('pairing')}
            >
              <Wifi size={14} />
              <span>Pasang Panel</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={guideTab === 'usage'}
              className={`ug-tab-pill ${guideTab === 'usage' ? 'active' : ''}`}
              onClick={() => setGuideTab('usage')}
            >
              <BookOpen size={14} />
              <span>Pantau &amp; AI</span>
            </button>
          </div>
        </div>

        {/* Scrollable Editorial Article Body */}
        <div className="ug-scroll-body">
          {guideTab === 'pairing' ? (
            <div className="ug-article">
              <div className="ug-intro-note">
                Sebelum mulai menautkan unit VoltKu baru, pastikan ponsel Anda terhubung ke
                jaringan <strong>Wi-Fi 2.4 GHz</strong> rumah (bukan 5 GHz).
              </div>

              <div className="ug-section-heading">Panduan Pairing Cepat (Quick Pairing)</div>

              <div className="ug-step-block">
                <p className="ug-step-text">
                  <strong>1.</strong> Colokkan panel VoltKu ke listrik, lalu tekan dan tahan tombol{' '}
                  <strong>Pairing</strong> selama <strong>5 detik</strong> sampai lampu indikator
                  biru berkedip cepat.
                </p>
                <StepPhoneMockup stepNum={1} />
              </div>

              <div className="ug-step-block">
                <p className="ug-step-text">
                  <strong>2.</strong> Buka aplikasi VoltKu di tab <strong>Beranda</strong>, lalu
                  ketuk ikon <strong>+</strong> atau tombol <strong>+ Tambah Sekarang</strong>.
                </p>
                <StepPhoneMockup stepNum={2} />
              </div>

              <div className="ug-step-block">
                <p className="ug-step-text">
                  <strong>3.</strong> Pilih <strong>Belum, Hubungkan ke Wi-Fi Dulu</strong> untuk
                  alat baru (atau langsung pilih <strong>Sudah Terhubung Wi-Fi</strong> jika alat
                  sudah online).
                </p>
                <StepPhoneMockup stepNum={3} />
              </div>

              <div className="ug-step-block">
                <p className="ug-step-text">
                  <strong>4.</strong> Sambungkan Wi-Fi HP ke hotspot <code>VoltKu-XXXX</code>{' '}
                  (atau buka <code>192.168.4.1</code>), pilih Wi-Fi 2.4 GHz rumah, isi kata sandi,
                  lalu tekan <strong>Simpan &amp; Hubungkan</strong>.
                </p>
                <StepPhoneMockup stepNum={4} />
              </div>

              <div className="ug-step-block">
                <p className="ug-step-text">
                  <strong>5.</strong> Kembalikan HP ke Wi-Fi internet biasa, lalu{' '}
                  <strong>Scan Barcode / QR Code</strong> pada stiker bodi unit VoltKu dan atur
                  nama ruangan serta batas daya MCB rumah.
                </p>
                <StepPhoneMockup stepNum={5} />
              </div>

              {onStartAddDevice && (
                <button
                  type="button"
                  className="ewl-primary-pill-btn ug-cta-btn"
                  onClick={() => {
                    onClose()
                    onStartAddDevice()
                  }}
                >
                  <Plus size={17} strokeWidth={2.5} />
                  <span>Pasang Panel Sekarang</span>
                </button>
              )}
            </div>
          ) : (
            <div className="ug-article">
              <div className="ug-intro-note">
                Setelah panel terhubung, Anda bisa memantau listrik rumah secara real-time,
                melihat grafik biaya Rupiah, hingga bertanya langsung ke Asisten AI.
              </div>

              <div className="ug-feature-cards">
                <div className="ug-feature-card">
                  <span className="ug-feat-icon is-blue">
                    <Zap size={18} />
                  </span>
                  <div className="ug-feat-copy">
                    <strong>1. Pantau Beban Live &amp; Grafik</strong>
                    <p>
                      Ketuk kartu panel di Beranda untuk membuka tab <strong>Live</strong> (daya
                      Watt, tegangan V, arus A, PF, frekuensi) serta tab <strong>Konsumsi</strong>{' '}
                      untuk grafik harian dan riwayat jam paling boros.
                    </p>
                  </div>
                </div>

                <div className="ug-feature-card">
                  <span className="ug-feat-icon is-amber">
                    <SlidersHorizontal size={18} />
                  </span>
                  <div className="ug-feat-copy">
                    <strong>2. Atur Golongan Tarif PLN &amp; Batas MCB</strong>
                    <p>
                      Buka tab <strong>Setelan</strong> atau ketuk <strong>Atur Alat</strong> pada
                      panel untuk memilih tarif PLN R-1/R-2/Bisnis agar hitungan biaya Rupiah dan
                      proyeksi akhir bulan akurat sesuai meteran rumah.
                    </p>
                  </div>
                </div>

                <div className="ug-feature-card">
                  <span className="ug-feat-icon is-emerald">
                    <CheckCircle2 size={18} />
                  </span>
                  <div className="ug-feat-copy">
                    <strong>3. Peringatan Anomali &amp; Notifikasi Instan</strong>
                    <p>
                      Cek tab <strong>Peringatan</strong> atau ikon lonceng untuk riwayat tegangan
                      tidak stabil, lonjakan daya mendadak, atau perangkat offline dalam 7 hari
                      terakhir.
                    </p>
                  </div>
                </div>

                <div className="ug-feature-card">
                  <span className="ug-feat-icon is-indigo">
                    <Bot size={18} />
                  </span>
                  <div className="ug-feat-copy">
                    <strong>4. Tanya Asisten VoltKu AI</strong>
                    <p>
                      Ketuk tombol <strong>Tanya AI</strong> di pojok kanan bawah untuk menanyakan
                      biaya listrik hari ini, jam tersibuk, proyeksi tagihan bulan ini, atau
                      pengecekan anomali dengan cepat.
                    </p>
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="ewl-primary-pill-btn ug-cta-btn"
                onClick={onClose}
              >
                <Sparkles size={16} />
                <span>Mengerti, Kembali ke Beranda</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

