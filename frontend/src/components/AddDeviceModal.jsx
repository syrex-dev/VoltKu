import React, { useState, useEffect, useRef } from 'react'
import {
  X,
  Wifi,
  Check,
  AlertCircle,
  Radio,
  CheckCircle2,
  Loader2,
  QrCode,
  ArrowLeft,
  ArrowRight,
} from 'lucide-react'
import { apiRequest } from '../api/client'

const DEFAULT_ROOMS = ['Panel Utama', 'Ruang Tamu', 'Kamar Tidur', 'Dapur', 'Lantai 2', 'Warung']
const MCB_OPTIONS = [900, 1300, 2200, 3500, 4400, 5500]

const PAIRING_SLIDES = [
  {
    id: 'wifi-24',
    title: 'Pilih Jaringan Wi-Fi 2.4 GHz',
    desc: 'Sensor ESP32 VoltKu mendukung jaringan Wi-Fi 2.4 GHz rumah/warung untuk koneksi yang stabil dan hemat daya.',
    badge: 'WIFI 2.4 GHz',
  },
  {
    id: 'pairing-mode',
    title: 'Pastikan Lampu Pairing Berkedip',
    desc: 'Nyalakan panel lalu tekan & tahan tombol Pairing selama 3 detik hingga hotspot VoltKu-XXXX aktif.',
    badge: 'HOTSPOT ALAT',
  },
  {
    id: 'quick-connect',
    title: 'Sambung Cepat & Klaim Panel',
    desc: 'Masukkan kode perangkat (ML-XXXXXX) agar panel langsung muncul seragam di Aplikasi APK dan Browser Web.',
    badge: 'SIAP DIPANTAU',
  },
]

function PairingCarouselIllustration({ slideId }) {
  if (slideId === 'wifi-24') {
    return (
      <div className="pairing-illus-card">
        <div className="pairing-phone-mock">
          <div className="pairing-phone-notch" />
          <div className="pairing-wifi-row muted">
            <span>✕ WiFi-5GHz</span>
          </div>
          <div className="pairing-wifi-row active">
            <span>✓ WiFi-2.4GHz Rumah</span>
          </div>
          <div className="pairing-mock-btn">Hubungkan</div>
        </div>
      </div>
    )
  }
  if (slideId === 'pairing-mode') {
    return (
      <div className="pairing-illus-card">
        <div className="pairing-phone-mock">
          <div className="pairing-phone-notch" />
          <div className="pairing-ap-pulse">
            <Wifi size={26} />
          </div>
          <div className="pairing-ap-tag">VoltKu-XXXX</div>
        </div>
      </div>
    )
  }
  return (
    <div className="pairing-illus-card">
      <div className="pairing-phone-mock">
        <div className="pairing-phone-notch" />
        <div className="pairing-done-badge">
          <CheckCircle2 size={28} />
        </div>
        <div className="pairing-ap-tag">Online · Live Watt</div>
      </div>
    </div>
  )
}

export function AddDeviceModal({
  isOpen,
  onClose,
  token,
  existingDevices = [],
  onDeviceAdded,
  onPlanLimitReached,
  onLogout,
}) {
  // Step 0: Panduan Visual Carousel, Step 1: Metode, Step 2: Wi-Fi Alat, Step 3: Pairing Cek, Step 4: Nama & Ruangan, Step 5: Selesai
  const [step, setStep] = useState(0)
  const [slideIdx, setSlideIdx] = useState(0)
  const [deviceId, setDeviceId] = useState('')
  const [deviceName, setDeviceName] = useState('Panel VoltKu Utama')
  const [selectedRoom, setSelectedRoom] = useState('Panel Utama')
  const [customRoom, setCustomRoom] = useState('')
  const [mcbWatt, setMcbWatt] = useState(2200)

  // Live pairing verification state
  const [isSearching, setIsSearching] = useState(false)
  const [countdownSec, setCountdownSec] = useState(180)
  const [pairingStatusMsg, setPairingStatusMsg] = useState('')
  const [pairingFoundOnline, setPairingFoundOnline] = useState(false)
  const [saving, setSaving] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)

  const pollIntervalRef = useRef(null)
  const timerIntervalRef = useRef(null)

  const stopSearchTimers = () => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
    pollIntervalRef.current = null
    timerIntervalRef.current = null
  }

  useEffect(() => {
    if (!isOpen) {
      stopSearchTimers()
      setStep(0)
      setSlideIdx(0)
      setDeviceId('')
      setDeviceName('Panel VoltKu Utama')
      setSelectedRoom('Panel Utama')
      setCustomRoom('')
      setMcbWatt(2200)
      setIsSearching(false)
      setCountdownSec(180)
      setPairingStatusMsg('')
      setPairingFoundOnline(false)
      setErrorMsg(null)
    }
    return () => stopSearchTimers()
  }, [isOpen])

  if (!isOpen) return null

  const cleanDeviceId = deviceId.trim()

  const startLiveDiscovery = () => {
    setErrorMsg(null)
    if (!/^[A-Za-z0-9_-]{2,64}$/.test(cleanDeviceId)) {
      setErrorMsg('Kode Perangkat harus 2-64 karakter (huruf, angka, tanda - atau _), contoh: ML-A1B2C3.')
      return
    }

    stopSearchTimers()
    setIsSearching(true)
    setCountdownSec(180)
    setPairingFoundOnline(false)
    setPairingStatusMsg(`Mencari sinyal "${cleanDeviceId}" dari server...`)

    const checkOnce = async () => {
      try {
        const list = await apiRequest('/api/devices', {}, token, onLogout)
        const found = (list || []).find((d) => d.id.toLowerCase() === cleanDeviceId.toLowerCase())
        if (found) {
          setDeviceId(found.id)
          if (found.status === 'online') {
            stopSearchTimers()
            setIsSearching(false)
            setPairingFoundOnline(true)
            setPairingStatusMsg(`Alat "${found.id}" berhasil ditemukan & sedang Online!`)
            setTimeout(() => setStep(4), 600)
            return
          } else {
            setPairingStatusMsg(`Kode "${found.id}" terdaftar di server, menunggu koneksi online alat...`)
          }
        }
      } catch (err) {
        // Ignore transient poll errors while waiting
      }
    }

    checkOnce()
    pollIntervalRef.current = setInterval(checkOnce, 2500)
    timerIntervalRef.current = setInterval(() => {
      setCountdownSec((prev) => {
        if (prev <= 1) {
          stopSearchTimers()
          setIsSearching(false)
          setPairingStatusMsg('Waktu tunggu 180 detik habis. Anda tetap bisa mendaftarkan alat ini sekarang.')
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const handleSaveDevice = async (e) => {
    e.preventDefault()
    setErrorMsg(null)
    if (!/^[A-Za-z0-9_-]{2,64}$/.test(cleanDeviceId)) {
      setErrorMsg('Kode Perangkat tidak valid.')
      return
    }
    const finalName = deviceName.trim()
    if (!finalName) {
      setErrorMsg('Nama perangkat wajib diisi.')
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

  // Devices already seen by backend that can be picked easily
  const detectedDevices = existingDevices.slice(0, 4)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog-modern pairing-wizard-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header-modern">
          <div className="modal-title-group">
            <Radio size={20} className="modal-title-icon" />
            <div>
              <h3 className="modal-title-text">Tambah Perangkat Baru</h3>
              <div className="wizard-subtitle">Setup mandiri tanpa komputer</div>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        {/* Step Pills */}
        {step >= 1 && step < 5 && (
          <div className="wizard-steps-bar">
            <div className={`wizard-pill ${step >= 1 ? 'active' : ''}`}>1. Persiapan</div>
            <div className={`wizard-pill ${step >= 2 ? 'active' : ''}`}>2. Wi-Fi Alat</div>
            <div className={`wizard-pill ${step >= 3 ? 'active' : ''}`}>3. Pairing</div>
            <div className={`wizard-pill ${step >= 4 ? 'active' : ''}`}>4. Nama</div>
          </div>
        )}

        {errorMsg && <div className="feedback-msg error">{errorMsg}</div>}

        {/* STEP 0: Carousel Ilustrasi Langkah Pairing (Ala Native Smart-Home App) */}
        {step === 0 && (
          <div className="wizard-body pairing-carousel-body">
            <PairingCarouselIllustration slideId={PAIRING_SLIDES[slideIdx].id} />

            <div className="pairing-slide-copy">
              <span className="pairing-slide-badge">{PAIRING_SLIDES[slideIdx].badge}</span>
              <h4 className="pairing-slide-title">{PAIRING_SLIDES[slideIdx].title}</h4>
              <p className="pairing-slide-desc">{PAIRING_SLIDES[slideIdx].desc}</p>
            </div>

            <div className="pairing-dots-row" role="tablist" aria-label="Slide Panduan Pairing">
              {PAIRING_SLIDES.map((s, idx) => (
                <button
                  key={s.id}
                  type="button"
                  role="tab"
                  aria-selected={slideIdx === idx}
                  aria-label={`Langkah ${idx + 1}`}
                  className={`pairing-dot-btn ${slideIdx === idx ? 'active' : ''}`}
                  onClick={() => setSlideIdx(idx)}
                />
              ))}
            </div>

            <div className="pairing-carousel-actions">
              {slideIdx < PAIRING_SLIDES.length - 1 ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  onClick={() => setSlideIdx((prev) => prev + 1)}
                >
                  <span>Lanjut</span>
                  <ArrowRight size={16} />
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  onClick={() => setStep(1)}
                >
                  <span>Mulai Sambungkan Perangkat</span>
                  <ArrowRight size={16} />
                </button>
              )}

              <button
                type="button"
                className="btn btn-secondary"
                style={{ width: '100%' }}
                onClick={() => setStep(3)}
              >
                <QrCode size={15} />
                <span>Sudah Terhubung Wi-Fi? Klaim Langsung</span>
              </button>
            </div>
          </div>
        )}

        {/* STEP 1: Pilih Metode & Mode Pairing */}
        {step === 1 && (
          <div className="wizard-body">
            <div className="wizard-info-callout">
              <AlertCircle size={18} className="text-cyan" style={{ flexShrink: 0 }} />
              <div>
                Pastikan unit VoltKu sudah menyala. Jika lampu biru belum berkedip cepat,
                <strong> tekan &amp; tahan tombol Pairing selama 3 detik</strong>.
              </div>
            </div>

            <div className="pairing-method-list">
              <button
                type="button"
                className="pairing-method-card recommended"
                onClick={() => setStep(2)}
              >
                <div className="method-icon-box">
                  <Wifi size={22} />
                </div>
                <div className="method-text">
                  <div className="method-badge-top">DIREKOMENDASIKAN</div>
                  <div className="method-title">Hubungkan Alat Baru ke Wi-Fi Rumah</div>
                  <div className="method-desc">
                    Sambungkan HP sebentar ke hotspot alat <code>VoltKu-XXXX</code> lalu
                    pilih Wi-Fi rumah Anda langsung dari HP.
                  </div>
                </div>
                <ArrowRight size={18} className="method-arrow" />
              </button>

              <button
                type="button"
                className="pairing-method-card"
                onClick={() => setStep(3)}
              >
                <div className="method-icon-box secondary">
                  <QrCode size={22} />
                </div>
                <div className="method-text">
                  <div className="method-title">Klaim Cepat Pakai Kode Perangkat</div>
                  <div className="method-desc">
                    Jika alat sudah tersambung ke Wi-Fi, langsung masukkan Kode Alat dari stiker
                    casing untuk memantaunya di akun ini.
                  </div>
                </div>
                <ArrowRight size={18} className="method-arrow" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Panduan Sambung Hotspot Captive Portal Alat */}
        {step === 2 && (
          <div className="wizard-body">
            <div className="wifi-freq-compare">
              <div className="freq-box supported">
                <div className="freq-icon ok"><Check size={15} /></div>
                <div className="freq-label">Wi-Fi 2.4 GHz</div>
                <div className="freq-note">Didukung Penuh</div>
              </div>
              <div className="freq-box unsupported">
                <div className="freq-icon no"><X size={15} /></div>
                <div className="freq-label">Wi-Fi 5 GHz</div>
                <div className="freq-note">Tidak Didukung</div>
              </div>
            </div>

            <ol className="pairing-checklist-steps">
              <li>
                Buka menu <strong>Pengaturan Wi-Fi</strong> di HP Anda, lalu sambungkan ke hotspot
                bernama <strong><code>VoltKu-XXXX</code></strong> (atau pindai QR di stiker casing).
              </li>
              <li>
                Layar pengaturan Wi-Fi akan muncul otomatis di HP (atau buka browser ke{' '}
                <strong><code>http://192.168.4.1</code></strong>).
              </li>
              <li>
                Pilih nama Wi-Fi rumah (2.4 GHz), masukkan password Wi-Fi, lalu tekan{' '}
                <strong>Simpan &amp; Hubungkan</strong>.
              </li>
              <li>
                Catat <strong>Kode Perangkat</strong> (misal <code>ML-A1B2C3</code>) yang tampil di
                layar HP atau stiker casing, lalu sambungkan HP kembali ke internet normal.
              </li>
            </ol>

            <div className="wizard-nav-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setStep(1)}>
                <ArrowLeft size={15} />
                <span>Kembali</span>
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setStep(3)}>
                <span>Wi-Fi Alat Sudah Diatur</span>
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Masukkan Kode Alat & Verifikasi Koneksi Real-Time */}
        {step === 3 && (
          <div className="wizard-body">
            <div className="form-field-group">
              <label className="field-label" htmlFor="pairing-device-id">
                Kode Perangkat (Tertera di Stiker Bodi / Layar Setup)
              </label>
              <input
                id="pairing-device-id"
                type="text"
                className="modern-input num-tabular"
                placeholder="Contoh: ML-A1B2C3 atau esp32_device_1"
                value={deviceId}
                onChange={(e) => setDeviceId(e.target.value)}
                disabled={isSearching}
              />
              <small className="field-hint">
                Huruf, angka, tanda hubung (-), atau garis bawah (_) tanpa spasi.
              </small>
            </div>

            {detectedDevices.length > 0 && !isSearching && (
              <div className="detected-chips-wrap">
                <div className="detected-chips-label">Perangkat terdaftar di server:</div>
                <div className="room-chips-row">
                  {detectedDevices.map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      className={`room-chip ${cleanDeviceId === d.id ? 'selected' : ''}`}
                      onClick={() => setDeviceId(d.id)}
                    >
                      {d.id} ({d.status === 'online' ? 'Online' : 'Offline'})
                    </button>
                  ))}
                </div>
              </div>
            )}

            {isSearching || pairingStatusMsg ? (
              <div className="pairing-countdown-card">
                <div className={`countdown-ring ${pairingFoundOnline ? 'found' : ''}`}>
                  {pairingFoundOnline ? (
                    <CheckCircle2 size={36} className="text-emerald" />
                  ) : isSearching ? (
                    <span className="countdown-seconds num-tabular">{countdownSec}s</span>
                  ) : (
                    <AlertCircle size={32} className="text-amber" />
                  )}
                </div>
                <div className="pairing-live-msg">
                  {isSearching && <Loader2 size={14} className="spin-anim" />}
                  <span>{pairingStatusMsg}</span>
                </div>
              </div>
            ) : null}

            <div className="wizard-nav-footer column-mobile">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  stopSearchTimers()
                  setIsSearching(false)
                  setStep(2)
                }}
              >
                <ArrowLeft size={15} />
                <span>Kembali</span>
              </button>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                {cleanDeviceId.length >= 2 && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      stopSearchTimers()
                      setIsSearching(false)
                      setStep(4)
                    }}
                  >
                    Lanjut Beri Nama
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={startLiveDiscovery}
                  disabled={isSearching || !cleanDeviceId}
                >
                  {isSearching ? 'Mencari Alat...' : 'Cek Koneksi Alat'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: Penamaan Perangkat, Ruangan & Batas MCB */}
        {step === 4 && (
          <form className="wizard-body" onSubmit={handleSaveDevice}>
            <div className="form-field-group">
              <label className="field-label" htmlFor="wizard-device-name">
                Nama Perangkat
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

            <div className="form-field-group">
              <label className="field-label">Pilih Lokasi / Ruangan</label>
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
                placeholder="Atau ketik nama ruangan sendiri (opsional)..."
                value={customRoom}
                onChange={(e) => setCustomRoom(e.target.value)}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label">Kapasitas Daya Listrik / MCB (Watt)</label>
              <div className="room-chips-row">
                {MCB_OPTIONS.map((w) => (
                  <button
                    key={w}
                    type="button"
                    className={`room-chip num-tabular ${Number(mcbWatt) === w ? 'selected' : ''}`}
                    onClick={() => setMcbWatt(w)}
                  >
                    {w} VA/W
                  </button>
                ))}
              </div>
            </div>

            <div className="wizard-nav-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setStep(3)}>
                <ArrowLeft size={15} />
                <span>Kembali</span>
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
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
              <CheckCircle2 size={44} />
            </div>
            <h4>Perangkat Berhasil Ditambahkan!</h4>
            <p>
              <strong>{deviceName}</strong> ({cleanDeviceId}) sekarang terdaftar di grup{' '}
              <strong>{customRoom.trim() || selectedRoom}</strong> dengan batas MCB{' '}
              <strong>{mcbWatt} W</strong>.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              style={{ width: '100%', padding: '12px', marginTop: 10 }}
              onClick={onClose}
            >
              Selesai &amp; Pantau Listrik
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
