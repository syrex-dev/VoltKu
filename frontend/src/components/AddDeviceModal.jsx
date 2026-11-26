import React, { useState, useEffect, useCallback } from 'react'
import {
  X,
  Wifi,
  Check,
  Radio,
  CheckCircle2,
  QrCode,
  ScanBarcode,
  ArrowLeft,
  ArrowRight,
  Zap,
  Sparkles,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { BarcodeScannerBox } from './BarcodeScannerBox'

const DEFAULT_ROOMS = ['Panel Utama', 'Ruang Tamu', 'Kamar Tidur', 'Dapur', 'Lantai 2', 'Warung']
const MCB_OPTIONS = [900, 1300, 2200, 3500, 4400, 5500]
const DEVICE_ID_RE = /^[A-Za-z0-9_-]{2,64}$/

const WIZARD_STEPS = [
  { num: 1, label: 'Mulai' },
  { num: 2, label: 'Wi-Fi' },
  { num: 3, label: 'Kode' },
  { num: 4, label: 'Nama' },
]

const STEP_SUBTITLES = {
  1: 'Langkah 1 dari 4 · Pilih kondisi alat',
  2: 'Langkah 2 dari 4 · Hubungkan ke Wi-Fi rumah',
  3: 'Langkah 3 dari 4 · Scan barcode atau isi kode',
  4: 'Langkah 4 dari 4 · Beri nama & batas daya',
  5: 'Panel baru siap dipantau',
}

export function AddDeviceModal({
  isOpen,
  onClose,
  token,
  onDeviceAdded,
  onPlanLimitReached,
  onLogout,
}) {
  // Step 1: Persiapan & Kondisi Alat, Step 2: Wi-Fi Alat, Step 3: Kode Alat / Scan Barcode, Step 4: Nama & MCB, Step 5: Selesai
  const [step, setStep] = useState(1)
  const [cameFromWifiStep, setCameFromWifiStep] = useState(false)
  const [showScanner, setShowScanner] = useState(false)
  const [scanBadgeMsg, setScanBadgeMsg] = useState('')
  const [deviceId, setDeviceId] = useState('')
  const [deviceName, setDeviceName] = useState('Panel Utama Rumah')
  const [selectedRoom, setSelectedRoom] = useState('Panel Utama')
  const [customRoom, setCustomRoom] = useState('')
  const [mcbWatt, setMcbWatt] = useState(2200)
  const [savedStatus, setSavedStatus] = useState('offline')
  const [saving, setSaving] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)

  useEffect(() => {
    if (!isOpen) {
      setStep(1)
      setCameFromWifiStep(false)
      setShowScanner(false)
      setScanBadgeMsg('')
      setDeviceId('')
      setDeviceName('Panel Utama Rumah')
      setSelectedRoom('Panel Utama')
      setCustomRoom('')
      setMcbWatt(2200)
      setSavedStatus('offline')
      setErrorMsg(null)
    }
  }, [isOpen])

  const handleBarcodeDetected = useCallback((extractedId) => {
    setDeviceId(extractedId)
    setShowScanner(false)
    setErrorMsg(null)
    setScanBadgeMsg(`Barcode terbaca: ${extractedId}`)
  }, [])

  if (!isOpen) return null

  const cleanDeviceId = deviceId.trim()
  const hasInput = cleanDeviceId.length > 0
  const isDeviceIdValid = DEVICE_ID_RE.test(cleanDeviceId)

  const handleGoToStep4 = (e) => {
    if (e) e.preventDefault()
    setErrorMsg(null)
    if (!isDeviceIdValid) {
      setErrorMsg('Kode perangkat harus 2–64 karakter (huruf, angka, - atau _), tanpa spasi.')
      return
    }
    setStep(4)
  }

  const handleSaveDevice = async (e) => {
    e.preventDefault()
    setErrorMsg(null)
    if (!isDeviceIdValid) {
      setErrorMsg('Kode perangkat tidak valid.')
      return
    }
    const finalName = deviceName.trim()
    if (!finalName) {
      setErrorMsg('Nama panel wajib diisi.')
      return
    }
    const finalRoom = customRoom.trim() || selectedRoom

    setSaving(true)
    try {
      const saved = await apiRequest(
        '/api/devices',
        {
          method: 'POST',
          body: {
            id: cleanDeviceId,
            name: finalName,
            location: finalRoom,
            mcb_watt: parseInt(mcbWatt, 10) || 2200,
            claim: true,
          },
        },
        token,
        onLogout
      )
      setSavedStatus(saved?.status || 'offline')
      if (onDeviceAdded) await onDeviceAdded(saved.id)
      setStep(5)
    } catch (err) {
      if (err?.reason === 'plan_upgrade_required' && onPlanLimitReached) {
        onClose()
        onPlanLimitReached(err.message)
        return
      }
      setErrorMsg(err.message || 'Gagal menyimpan perangkat.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog-modern pairing-wizard-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="wizard-top-sticky">
          {/* Header */}
          <div className="modal-header-modern wizard-modal-header">
            <div className="modal-title-group">
              <div className="wizard-header-icon">
                <Radio size={18} />
              </div>
              <div>
                <h3 className="modal-title-text">Tambah Panel Listrik</h3>
                <div className="wizard-subtitle">{STEP_SUBTITLES[step]}</div>
              </div>
            </div>
            <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
              <X size={18} />
            </button>
          </div>

          {/* 4-Step Progress Stepper */}
          {step >= 1 && step < 5 && (
            <div className="wizard-steps-bar" role="navigation" aria-label="Tahap tambah panel">
              {WIZARD_STEPS.map((item) => {
                const isDone = step > item.num
                const isCurrent = step === item.num
                const stateClass = isDone ? 'done' : isCurrent ? 'current' : 'upcoming'
                return (
                  <button
                    key={item.num}
                    type="button"
                    disabled={!isDone}
                    className={`wizard-pill ${stateClass}`}
                    onClick={() => {
                      if (isDone) {
                        setErrorMsg(null)
                        setStep(item.num)
                      }
                    }}
                  >
                    <span className="wizard-pill-dot" aria-hidden="true">
                      {isDone ? <Check size={11} strokeWidth={3} /> : item.num}
                    </span>
                    <span className="wizard-pill-label">{item.label}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="wizard-scroll-region">
          {errorMsg && <div className="feedback-msg error">{errorMsg}</div>}

          {/* STEP 1: Persiapan & Pilih Kondisi Alat */}
          {step === 1 && (
            <div className="wizard-body">
              <div className="wizard-info-callout">
                <span className="pairing-led-demo" aria-hidden="true">
                  <span className="pairing-led-dot" />
                </span>
                <div>
                  <strong>Siapkan unit VoltKu:</strong> nyalakan alat dan pastikan lampu indikator biru{' '}
                  <strong>berkedip cepat</strong>.{' '}
                  <span className="wizard-muted-inline">
                    Jika belum, tahan tombol Pairing 5 detik sampai lampu berkedip.
                  </span>
                </div>
              </div>

            <div className="wizard-section-ask">Apakah alat sudah terhubung ke Wi-Fi rumah?</div>

            <div className="pairing-method-list">
              <button
                type="button"
                className="pairing-method-card recommended"
                onClick={() => {
                  setErrorMsg(null)
                  setCameFromWifiStep(true)
                  setStep(2)
                }}
              >
                <div className="method-icon-box">
                  <Wifi size={20} />
                </div>
                <div className="method-text">
                  <div className="method-badge-top">ALAT BARU</div>
                  <div className="method-title">Belum, Hubungkan ke Wi-Fi Dulu</div>
                  <div className="method-desc">
                    Ikuti panduan singkat untuk menyambungkan alat ke jaringan Wi-Fi 2.4 GHz rumah Anda.
                  </div>
                </div>
                <ArrowRight size={18} className="method-arrow" />
              </button>

              <button
                type="button"
                className="pairing-method-card"
                onClick={() => {
                  setErrorMsg(null)
                  setCameFromWifiStep(false)
                  setStep(3)
                }}
              >
                <div className="method-icon-box secondary">
                  <QrCode size={20} />
                </div>
                <div className="method-text">
                  <div className="method-title">Sudah Terhubung Wi-Fi</div>
                  <div className="method-desc">
                    Langsung masukkan Kode Perangkat dari stiker bodi untuk menampilkannya di dashboard.
                  </div>
                </div>
                <ArrowRight size={18} className="method-arrow" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Panduan Sambung Wi-Fi 2.4 GHz */}
        {step === 2 && (
          <div className="wizard-body">
            <div className="wifi-freq-compare">
              <div className="freq-box supported">
                <div className="freq-icon ok"><Check size={14} strokeWidth={3} /></div>
                <div>
                  <div className="freq-label">Wi-Fi 2.4 GHz</div>
                  <div className="freq-note">Didukung penuh</div>
                </div>
              </div>
              <div className="freq-box unsupported">
                <div className="freq-icon no"><X size={14} strokeWidth={3} /></div>
                <div>
                  <div className="freq-label">Wi-Fi 5 GHz</div>
                  <div className="freq-note">Tidak didukung</div>
                </div>
              </div>
            </div>

            <div className="wizard-checklist-cards">
              <div className="wizard-check-row">
                <span className="wizard-check-num">1</span>
                <span>
                  Buka menu <strong>Wi-Fi di HP</strong>, lalu sambungkan ke hotspot bernama{' '}
                  <code>VoltKu-XXXX</code>.
                </span>
              </div>
              <div className="wizard-check-row">
                <span className="wizard-check-num">2</span>
                <span>
                  Halaman pengaturan akan muncul otomatis (atau buka <code>192.168.4.1</code> di browser).
                </span>
              </div>
              <div className="wizard-check-row">
                <span className="wizard-check-num">3</span>
                <span>
                  Pilih nama <strong>Wi-Fi rumah (2.4 GHz)</strong>, isi kata sandi, lalu tekan{' '}
                  <strong>Simpan &amp; Hubungkan</strong>.
                </span>
              </div>
              <div className="wizard-check-row">
                <span className="wizard-check-num">4</span>
                <span>
                  Catat <strong>Kode Perangkat</strong> (misal <code>ML-A1B2C3</code>), lalu kembalikan Wi-Fi HP ke internet normal.
                </span>
              </div>
            </div>

            <div className="wizard-nav-footer column-mobile">
              <button
                type="button"
                className="btn btn-secondary wizard-btn-back"
                onClick={() => {
                  setErrorMsg(null)
                  setStep(1)
                }}
              >
                <ArrowLeft size={15} />
                <span>Kembali</span>
              </button>
              <button
                type="button"
                className="btn btn-primary wizard-btn-next"
                onClick={() => {
                  setErrorMsg(null)
                  setCameFromWifiStep(true)
                  setStep(3)
                }}
              >
                <span>Sudah Terhubung, Lanjut</span>
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Scan Barcode / QR atau Masukkan Kode Perangkat */}
        {step === 3 && (
          <form className="wizard-body" onSubmit={handleGoToStep4}>
            {showScanner ? (
              <BarcodeScannerBox
                onDetected={handleBarcodeDetected}
                onClose={() => setShowScanner(false)}
              />
            ) : (
              <>
                <button
                  type="button"
                  className="wizard-scan-launch-card"
                  onClick={() => {
                    setErrorMsg(null)
                    setScanBadgeMsg('')
                    setShowScanner(true)
                  }}
                >
                  <div className="wizard-scan-launch-icon">
                    <ScanBarcode size={22} />
                  </div>
                  <div className="wizard-scan-launch-copy">
                    <div className="wizard-scan-launch-title">Scan Barcode / QR Code Alat</div>
                    <div className="wizard-scan-launch-desc">
                      Gunakan kamera atau foto stiker di bodi / kemasan VoltKu agar terisi otomatis.
                    </div>
                  </div>
                  <span className="wizard-scan-launch-pill">Kamera</span>
                </button>

                <div className="wizard-or-divider">
                  <span>atau ketik kode manual</span>
                </div>
              </>
            )}

            {scanBadgeMsg && (
              <div className="feedback-msg success" style={{ marginBottom: 0 }}>
                {scanBadgeMsg}
              </div>
            )}

            <div className="form-field-group" style={{ marginBottom: 4 }}>
              <label className="field-label" htmlFor="pairing-device-id">
                Kode Perangkat
              </label>
              <div className="wizard-code-input-wrap">
                <input
                  id="pairing-device-id"
                  type="text"
                  className="modern-input wizard-code-input wizard-code-input-with-btn num-tabular"
                  placeholder="Contoh: ML-A1B2C3"
                  value={deviceId}
                  onChange={(e) => {
                    setDeviceId(e.target.value)
                    if (scanBadgeMsg) setScanBadgeMsg('')
                    if (errorMsg) setErrorMsg(null)
                  }}
                  autoCapitalize="characters"
                  autoCorrect="off"
                  spellCheck={false}
                />
                {!showScanner && (
                  <button
                    type="button"
                    className="wizard-inline-scan-btn"
                    title="Scan Barcode / QR"
                    aria-label="Scan Barcode / QR"
                    onClick={() => {
                      setErrorMsg(null)
                      setShowScanner(true)
                    }}
                  >
                    <ScanBarcode size={17} />
                  </button>
                )}
              </div>
              {hasInput && !isDeviceIdValid ? (
                <small className="field-hint wizard-hint-warn">
                  Gunakan minimal 2 karakter huruf, angka, tanda (-), atau (_), tanpa spasi.
                </small>
              ) : (
                <small className="field-hint">
                  Lihat pada stiker bodi alat atau layar HP setelah mengatur Wi-Fi.
                </small>
              )}
            </div>

            <div className="wizard-nav-footer column-mobile">
              <button
                type="button"
                className="btn btn-secondary wizard-btn-back"
                onClick={() => {
                  setShowScanner(false)
                  setErrorMsg(null)
                  setStep(cameFromWifiStep ? 2 : 1)
                }}
              >
                <ArrowLeft size={15} />
                <span>Kembali</span>
              </button>
              <button
                type="submit"
                className="btn btn-primary wizard-btn-next"
                disabled={!isDeviceIdValid}
              >
                <span>Lanjut Beri Nama</span>
                <ArrowRight size={15} />
              </button>
            </div>
          </form>
        )}

        {/* STEP 4: Penamaan Perangkat, Ruangan & Batas Daya PLN */}
        {step === 4 && (
          <form className="wizard-body" onSubmit={handleSaveDevice}>
            <div className="wizard-device-chip-bar">
              <div className="wizard-device-chip-meta">
                <span className="wizard-device-chip-label">Kode Perangkat</span>
                <code className="wizard-device-chip-code">{cleanDeviceId}</code>
              </div>
              <button
                type="button"
                className="wizard-chip-edit-btn"
                onClick={() => {
                  setErrorMsg(null)
                  setStep(3)
                }}
              >
                Ubah
              </button>
            </div>

            <div className="form-field-group" style={{ marginBottom: 0 }}>
              <label className="field-label" htmlFor="wizard-device-name">
                Nama Panel
              </label>
              <input
                id="wizard-device-name"
                type="text"
                className="modern-input"
                placeholder="Misal: Meteran Rumah Utama"
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                required
              />
            </div>

            <div className="form-field-group" style={{ marginBottom: 0 }}>
              <label className="field-label">Lokasi / Ruangan</label>
              <div className="room-chips-row">
                {DEFAULT_ROOMS.map((room) => (
                  <button
                    key={room}
                    type="button"
                    className={`room-chip ${selectedRoom === room && !customRoom ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedRoom(room)
                      setCustomRoom('')
                    }}
                  >
                    {room}
                  </button>
                ))}
              </div>
              <input
                type="text"
                className="modern-input"
                style={{ marginTop: 8 }}
                placeholder="Atau tulis nama ruangan lain..."
                value={customRoom}
                onChange={(e) => setCustomRoom(e.target.value)}
              />
            </div>

            <div className="form-field-group" style={{ marginBottom: 0 }}>
              <label className="field-label">Batas Daya Meteran PLN / MCB</label>
              <div className="room-chips-row">
                {MCB_OPTIONS.map((w) => (
                  <button
                    key={w}
                    type="button"
                    className={`room-chip num-tabular ${Number(mcbWatt) === w ? 'selected' : ''}`}
                    onClick={() => setMcbWatt(w)}
                  >
                    {w} VA
                  </button>
                ))}
              </div>
              <small className="field-hint">
                Digunakan untuk peringatan jika pemakaian daya mendekati batas listrik rumah.
              </small>
            </div>

            <div className="wizard-nav-footer column-mobile">
              <button
                type="button"
                className="btn btn-secondary wizard-btn-back"
                onClick={() => {
                  setErrorMsg(null)
                  setStep(3)
                }}
              >
                <ArrowLeft size={15} />
                <span>Kembali</span>
              </button>
              <button type="submit" className="btn btn-primary wizard-btn-next" disabled={saving}>
                <Check size={16} />
                <span>{saving ? 'Menyimpan...' : 'Simpan & Aktifkan'}</span>
              </button>
            </div>
          </form>
        )}

        {/* STEP 5: Sukses */}
        {step === 5 && (
          <div className="wizard-body wizard-success-box">
            <div className="success-circle-badge">
              <CheckCircle2 size={40} />
            </div>
            <h4>Panel Berhasil Ditambahkan!</h4>
            <div className="wizard-success-summary">
              <div className="wizard-summary-row">
                <span>Nama Panel</span>
                <strong>{deviceName}</strong>
              </div>
              <div className="wizard-summary-row">
                <span>Kode Alat</span>
                <code className="num-tabular">{cleanDeviceId}</code>
              </div>
              <div className="wizard-summary-row">
                <span>Ruangan</span>
                <strong>{customRoom.trim() || selectedRoom}</strong>
              </div>
              <div className="wizard-summary-row">
                <span>Batas Daya</span>
                <strong className="num-tabular">{mcbWatt} VA</strong>
              </div>
              <div className="wizard-summary-row">
                <span>Status Koneksi</span>
                {savedStatus === 'online' ? (
                  <span className="wizard-status-pill online">
                    <Zap size={12} /> Online · Data aktif
                  </span>
                ) : (
                  <span className="wizard-status-pill waiting">
                    <Sparkles size={12} /> Menunggu sinyal alat
                  </span>
                )}
              </div>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ width: '100%', padding: '11px 16px', marginTop: 4 }}
              onClick={onClose}
            >
              Selesai &amp; Pantau Listrik
            </button>
          </div>
        )}
        </div>
      </div>
    </div>
  )
}
