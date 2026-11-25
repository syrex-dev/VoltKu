import React, { useEffect, useRef, useState } from 'react'
import { Camera, ImagePlus, RefreshCw, X, AlertCircle, Loader2 } from 'lucide-react'

const DEVICE_ID_RE = /^[A-Za-z0-9_-]{2,64}$/

function extractDeviceIdFromScan(rawValue = '') {
  const text = String(rawValue || '').trim()
  if (!text) return ''

  // 1. JSON payload: {"id":"ML-A1B2C3"} atau {"device_id":"..."}
  if (text.startsWith('{') && text.endsWith('}')) {
    try {
      const parsed = JSON.parse(text)
      const candidate = String(
        parsed.device_id || parsed.id || parsed.code || parsed.deviceId || ''
      ).trim()
      if (DEVICE_ID_RE.test(candidate)) return candidate
    } catch {
      // Lanjut cek format lain
    }
  }

  // 2. URL payload: https://.../claim?device=ML-A1B2C3 atau ?id=... atau segmen terakhir
  if (/^https?:\/\//i.test(text)) {
    try {
      const url = new URL(text)
      const fromParam =
        url.searchParams.get('device') ||
        url.searchParams.get('device_id') ||
        url.searchParams.get('id') ||
        url.searchParams.get('code') ||
        ''
      const cleanParam = fromParam.trim()
      if (DEVICE_ID_RE.test(cleanParam)) return cleanParam
      const lastSeg = url.pathname.split('/').filter(Boolean).pop() || ''
      if (DEVICE_ID_RE.test(lastSeg.trim())) return lastSeg.trim()
    } catch {
      // Lanjut cek format lain
    }
  }

  // 3. Prefixed format: VOLTKU:ML-A1B2C3, ID:ML-A1B2C3, SN=ML-A1B2C3
  const prefixMatch = text.match(/^(?:VOLTKU|DEVICE|ID|CODE|SN)\s*[:=]\s*([A-Za-z0-9_-]{2,64})$/i)
  if (prefixMatch?.[1]) {
    return prefixMatch[1].trim()
  }

  // 4. Langsung kode perangkat
  if (DEVICE_ID_RE.test(text)) {
    return text
  }

  // 5. Fallback ambil token valid pertama (mis. teks stiker multi-baris)
  const tokenMatch = text.match(/\b([A-Za-z0-9][A-Za-z0-9_-]{1,63})\b/)
  return tokenMatch ? tokenMatch[1] : text
}

export function BarcodeScannerBox({ onDetected, onClose }) {
  const videoRef = useRef(null)
  const readerRef = useRef(null)
  const fileInputRef = useRef(null)
  const mountedRef = useRef(true)

  const [starting, setStarting] = useState(true)
  const [cameraError, setCameraError] = useState('')
  const [videoDevices, setVideoDevices] = useState([])
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [decodingImage, setDecodingImage] = useState(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    let activeReader = null

    const stopCurrentReader = () => {
      if (activeReader) {
        try {
          activeReader.reset()
        } catch {
          // Abaikan error saat cleanup kamera
        }
        activeReader = null
      }
      if (readerRef.current) {
        try {
          readerRef.current.reset()
        } catch {
          // Abaikan error saat cleanup kamera
        }
        readerRef.current = null
      }
    }

    const startCamera = async () => {
      setStarting(true)
      setCameraError('')

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setStarting(false)
        setCameraError(
          'Browser tidak mendukung akses kamera langsung. Gunakan tombol "Foto / Galeri" di bawah.'
        )
        return
      }

      try {
        const { BrowserMultiFormatReader } = await import('@zxing/library')
        if (cancelled || !mountedRef.current) return

        const reader = new BrowserMultiFormatReader()
        activeReader = reader
        readerRef.current = reader

        // Ambil daftar kamera (jika sudah diberi izin akan muncul semua kamera)
        try {
          const devices = await reader.listVideoInputDevices()
          if (!cancelled && mountedRef.current && Array.isArray(devices)) {
            setVideoDevices(devices)
          }
        } catch {
          // listVideoInputDevices opsional
        }

        const constraints = selectedDeviceId
          ? { video: { deviceId: { exact: selectedDeviceId } }, audio: false }
          : {
              video: {
                facingMode: { ideal: 'environment' },
                width: { ideal: 1280 },
                height: { ideal: 720 },
              },
              audio: false,
            }

        await reader.decodeFromConstraints(constraints, videoRef.current, (result, err) => {
          if (cancelled || !mountedRef.current) return
          if (result) {
            const rawText = result.getText ? result.getText() : String(result)
            const extracted = extractDeviceIdFromScan(rawText)
            if (extracted) {
              stopCurrentReader()
              onDetected(extracted, rawText)
            }
          }
          // NotFoundException pada frame kosong adalah normal
          if (err && err.name && err.name !== 'NotFoundException') {
            // Biarkan kamera terus mencoba frame berikutnya
          }
        })

        if (!cancelled && mountedRef.current) {
          setStarting(false)
          // Refresh daftar kamera setelah izin diberikan agar tombol Ganti Kamera akurat
          try {
            const devicesAfterGrant = await reader.listVideoInputDevices()
            if (!cancelled && mountedRef.current && Array.isArray(devicesAfterGrant)) {
              setVideoDevices(devicesAfterGrant)
            }
          } catch {
            // Abaikan
          }
        }
      } catch (err) {
        if (cancelled || !mountedRef.current) return
        setStarting(false)
        const name = err?.name || ''
        if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
          setCameraError(
            'Izin kamera ditolak. Izinkan akses kamera di browser/HP, atau gunakan "Foto / Galeri".'
          )
        } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
          setCameraError('Kamera tidak ditemukan pada perangkat ini. Gunakan "Foto / Galeri".')
        } else {
          setCameraError(
            'Kamera belum bisa dibuka (pastikan lewat HTTPS). Anda tetap bisa pakai "Foto / Galeri".'
          )
        }
      }
    }

    startCamera()

    return () => {
      cancelled = true
      stopCurrentReader()
    }
  }, [selectedDeviceId, onDetected])

  const handleSwitchCamera = () => {
    if (videoDevices.length < 2) return
    const currentIdx = videoDevices.findIndex((d) => d.deviceId === selectedDeviceId)
    const nextIdx = currentIdx < 0 ? 0 : (currentIdx + 1) % videoDevices.length
    setSelectedDeviceId(videoDevices[nextIdx].deviceId)
  }

  const handleImageFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return

    setDecodingImage(true)
    setCameraError('')
    const objectUrl = URL.createObjectURL(file)
    try {
      const { BrowserMultiFormatReader } = await import('@zxing/library')
      const reader = new BrowserMultiFormatReader()
      const result = await reader.decodeFromImageUrl(objectUrl)
      const rawText = result?.getText ? result.getText() : String(result || '')
      const extracted = extractDeviceIdFromScan(rawText)
      if (extracted) {
        if (readerRef.current) {
          try {
            readerRef.current.reset()
          } catch {
            // Abaikan
          }
        }
        onDetected(extracted, rawText)
      } else {
        setCameraError('Barcode/QR tidak terbaca dari foto. Pastikan gambar jelas & fokus.')
      }
    } catch {
      setCameraError('Barcode atau QR code tidak ditemukan pada gambar tersebut.')
    } finally {
      URL.revokeObjectURL(objectUrl)
      if (mountedRef.current) setDecodingImage(false)
    }
  }

  return (
    <div className="scanner-box-wrap">
      <div className="scanner-box-head">
        <span className="scanner-box-title">
          <Camera size={15} />
          <span>Scan Barcode / QR Stiker Alat</span>
        </span>
        <button type="button" className="scanner-close-pill" onClick={onClose}>
          <X size={14} />
          <span>Tutup</span>
        </button>
      </div>

      {!cameraError ? (
        <div className="scanner-viewport">
          <video
            ref={videoRef}
            className="scanner-video"
            playsInline
            muted
            autoPlay
          />
          <div className="scanner-reticle" aria-hidden="true">
            <span className="scanner-laser" />
          </div>
          {starting && (
            <div className="scanner-loading-overlay">
              <Loader2 size={22} className="spin-anim" />
              <span>Membuka kamera...</span>
            </div>
          )}
        </div>
      ) : (
        <div className="scanner-error-box">
          <AlertCircle size={18} />
          <span>{cameraError}</span>
        </div>
      )}

      <div className="scanner-caption">
        Arahkan kamera ke barcode batang atau QR code pada bodi / kemasan VoltKu.
      </div>

      <div className="scanner-actions-row">
        {videoDevices.length >= 2 && !cameraError && (
          <button type="button" className="btn btn-secondary scanner-action-btn" onClick={handleSwitchCamera}>
            <RefreshCw size={14} />
            <span>Ganti Kamera</span>
          </button>
        )}

        <button
          type="button"
          className="btn btn-secondary scanner-action-btn"
          disabled={decodingImage}
          onClick={() => fileInputRef.current?.click()}
        >
          {decodingImage ? <Loader2 size={14} className="spin-anim" /> : <ImagePlus size={14} />}
          <span>{decodingImage ? 'Membaca foto...' : 'Foto / Galeri'}</span>
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          style={{ display: 'none' }}
          onChange={handleImageFile}
        />
      </div>
    </div>
  )
}

