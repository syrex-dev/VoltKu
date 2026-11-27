import React, { useMemo, useState } from 'react'
import { QrCode, Copy, Download, Printer, X, Plus, Package, Check } from 'lucide-react'
import { apiRequest } from '../api/client'
import { buildQrMatrix } from '../utils/qrMatrix'
import { InAppSelect } from './InAppSelect'

export function QrStickerSvg({ value, size = 180 }) {
  const qr = useMemo(() => buildQrMatrix(value), [value])
  if (!qr) return null
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${qr.size} ${qr.size}`}
      shapeRendering="crispEdges"
      role="img"
      aria-label={`QR Code ${value}`}
      style={{ background: '#ffffff', display: 'block' }}
    >
      <rect width={qr.size} height={qr.size} fill="#ffffff" />
      {qr.rows.map((cols, y) =>
        cols.map((on, x) =>
          on ? <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill="#0f172a" /> : null
        )
      )}
    </svg>
  )
}

export function DeviceQrStickerModal({ device, appName = 'VoltKu', onClose }) {
  const [copied, setCopied] = useState(false)
  if (!device) return null

  const payload = `VOLTKU:${device.id}`

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(device.id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      // ignore clipboard errors
    }
  }

  const handleDownloadPng = () => {
    const qr = buildQrMatrix(payload)
    if (!qr || typeof document === 'undefined') return
    const canvas = document.createElement('canvas')
    canvas.width = 520
    canvas.height = 640
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.strokeStyle = '#cbd5e1'
    ctx.lineWidth = 4
    ctx.strokeRect(12, 12, canvas.width - 24, canvas.height - 24)

    ctx.fillStyle = '#1677ff'
    ctx.font = 'bold 28px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(appName, canvas.width / 2, 62)

    ctx.fillStyle = '#475569'
    ctx.font = '16px sans-serif'
    ctx.fillText('STIKER PAIRING SMART PANEL', canvas.width / 2, 92)

    const qrBox = 340
    const startX = (canvas.width - qrBox) / 2
    const startY = 122
    const cell = qrBox / qr.size
    ctx.fillStyle = '#0f172a'
    qr.rows.forEach((cols, y) => {
      cols.forEach((on, x) => {
        if (on) {
          ctx.fillRect(startX + x * cell, startY + y * cell, Math.ceil(cell), Math.ceil(cell))
        }
      })
    })

    ctx.fillStyle = '#0f172a'
    ctx.font = 'bold 26px monospace'
    ctx.fillText(device.id, canvas.width / 2, 512)

    ctx.fillStyle = '#475569'
    ctx.font = '18px sans-serif'
    ctx.fillText(
      `${device.name || device.id} · MCB ${device.mcb_watt || 2200} W`,
      canvas.width / 2,
      548
    )
    ctx.font = '14px sans-serif'
    ctx.fillText('Buka aplikasi → Tambah Panel → Scan QR Code ini', canvas.width / 2, 586)

    const link = document.createElement('a')
    link.href = canvas.toDataURL('image/png')
    link.download = `voltku-qr-${device.id}.png`
    link.click()
  }

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern pwa-guide-sheet admin-qr-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`Stiker QR ${device.id}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head">
          <div className="admin-user-cell">
            <span className="admin-qr-head-ico">
              <QrCode size={18} />
            </span>
            <div>
              <h3 className="pwa-guide-title">Stiker QR Pairing Unit</h3>
              <p className="pwa-guide-sub num-tabular">{device.name || device.id}</p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <div className="admin-qr-sticker-card">
          <div className="admin-qr-sticker-brand">{appName} Smart Energy</div>
          <div className="admin-qr-sticker-box">
            <QrStickerSvg value={payload} size={196} />
          </div>
          <div className="admin-qr-sticker-id num-tabular">{device.id}</div>
          <div className="admin-qr-sticker-meta num-tabular">
            Kapasitas MCB {device.mcb_watt || 2200} W · Scan lewat menu Tambah Panel
          </div>
        </div>

        <div className="admin-qr-actions">
          <button type="button" className="btn btn-secondary btn-compact" onClick={handleCopy}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? 'ID Disalin' : 'Salin ID'}</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            onClick={() => typeof window !== 'undefined' && window.print?.()}
          >
            <Printer size={14} />
            <span>Cetak</span>
          </button>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            onClick={handleDownloadPng}
          >
            <Download size={14} />
            <span>Unduh Stiker PNG</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export function AdminStockCreateModal({
  isOpen,
  users = [],
  token,
  onLogout,
  onCreated,
  onNotice,
  onClose,
}) {
  const [mode, setMode] = useState('single') // 'single' | 'batch'
  const [deviceId, setDeviceId] = useState('')
  const [idPrefix, setIdPrefix] = useState('VK-PANEL-')
  const [batchCount, setBatchCount] = useState(5)
  const [name, setName] = useState('Panel VoltKu')
  const [location, setLocation] = useState('')
  const [mcbWatt, setMcbWatt] = useState(2200)
  const [ownerUserId, setOwnerUserId] = useState('0')
  const [isPublicDemo, setIsPublicDemo] = useState(false)
  const [saving, setSaving] = useState(false)
  const [errMsg, setErrMsg] = useState('')

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrMsg('')
    setSaving(true)
    try {
      const payload = {
        count: mode === 'batch' ? Math.max(2, Math.min(30, Number(batchCount) || 2)) : 1,
        name: name.trim() || 'Panel VoltKu',
        location: location.trim() || null,
        mcb_watt: Math.max(100, Math.min(25000, Number(mcbWatt) || 2200)),
        owner_user_id: Number(ownerUserId) > 0 ? Number(ownerUserId) : null,
        is_public_demo: Boolean(isPublicDemo),
      }
      if (mode === 'single') {
        payload.id = deviceId.trim()
      } else {
        payload.id_prefix = idPrefix.trim() || 'VK-PANEL-'
      }
      const res = await apiRequest(
        '/api/admin/devices',
        { method: 'POST', body: payload },
        token,
        onLogout
      )
      onNotice?.({
        type: 'success',
        text: `${res?.count || 1} unit perangkat stok berhasil dibuat (${(res?.created || [])
          .map((d) => d.id)
          .slice(0, 4)
          .join(', ')}${(res?.count || 0) > 4 ? '...' : ''}).`,
      })
      setDeviceId('')
      await onCreated?.(res?.created || [])
      onClose()
    } catch (err) {
      setErrMsg(err?.message || 'Gagal membuat perangkat stok.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Tambah Stok Perangkat Admin"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head">
          <div className="admin-user-cell">
            <span className="admin-qr-head-ico">
              <Package size={18} />
            </span>
            <div>
              <h3 className="pwa-guide-title">Tambah Stok Unit Panel</h3>
              <p className="pwa-guide-sub">Buat 1 unit ID kustom atau batch stok sekaligus untuk ditempel QR.</p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <div className="admin-filter-pills" style={{ marginBottom: 14 }}>
          <button
            type="button"
            className={`admin-chip-btn ${mode === 'single' ? 'active' : ''}`}
            onClick={() => setMode('single')}
          >
            1 Unit (ID Kustom)
          </button>
          <button
            type="button"
            className={`admin-chip-btn ${mode === 'batch' ? 'active' : ''}`}
            onClick={() => setMode('batch')}
          >
            Batch Banyak Unit
          </button>
        </div>

        <form onSubmit={handleSubmit} className="admin-section-stack">
          {mode === 'single' ? (
            <div className="form-field-group">
              <label className="field-label" htmlFor="adm-dev-id">
                ID Perangkat (Sesuai Firmware ESP32)
              </label>
              <input
                id="adm-dev-id"
                type="text"
                className="modern-input num-tabular"
                placeholder="Contoh: VK-2026-001"
                value={deviceId}
                onChange={(e) => setDeviceId(e.target.value)}
                required
                minLength={2}
                maxLength={64}
              />
            </div>
          ) : (
            <div className="settings-fields-grid">
              <div className="form-field-group">
                <label className="field-label" htmlFor="adm-dev-prefix">
                  Prefix ID Otomatis
                </label>
                <input
                  id="adm-dev-prefix"
                  type="text"
                  className="modern-input num-tabular"
                  placeholder="Contoh: VK-2026-"
                  value={idPrefix}
                  onChange={(e) => setIdPrefix(e.target.value)}
                  required
                />
              </div>
              <div className="form-field-group">
                <label className="field-label" htmlFor="adm-dev-qty">
                  Jumlah Unit (2–30)
                </label>
                <input
                  id="adm-dev-qty"
                  type="number"
                  min={2}
                  max={30}
                  className="modern-input num-tabular"
                  value={batchCount}
                  onChange={(e) => setBatchCount(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="adm-dev-name">
                Nama Dasar Unit
              </label>
              <input
                id="adm-dev-name"
                type="text"
                className="modern-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={120}
              />
            </div>
            <div className="form-field-group">
              <label className="field-label" htmlFor="adm-dev-mcb">
                Batas MCB Default (Watt)
              </label>
              <input
                id="adm-dev-mcb"
                type="number"
                min={100}
                max={25000}
                className="modern-input num-tabular"
                value={mcbWatt}
                onChange={(e) => setMcbWatt(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="adm-dev-loc">
                Lokasi / Label Gudang (Opsional)
              </label>
              <input
                id="adm-dev-loc"
                type="text"
                className="modern-input"
                placeholder="Misal: Stok Rak A"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />
            </div>
            <div className="form-field-group">
              <label className="field-label" htmlFor="adm-dev-owner">
                Pemilik Awal (Opsional)
              </label>
              <InAppSelect
                id="adm-dev-owner"
                value={ownerUserId}
                onChange={setOwnerUserId}
                options={[
                  { value: '0', label: '-- Stok Bebas (Belum Diklaim) --' },
                  ...users.map((u) => ({
                    value: String(u.id),
                    label: `${u.name || u.email} (${u.email})`,
                  })),
                ]}
              />
            </div>
          </div>

          <label className="admin-inline-check">
            <input
              type="checkbox"
              checked={isPublicDemo}
              onChange={(e) => setIsPublicDemo(e.target.checked)}
            />
            <span>Tampilkan juga di Mode Demo Publik (Guest)</span>
          </label>

          {errMsg && (
            <p className="feedback-msg error" style={{ margin: 0 }}>
              {errMsg}
            </p>
          )}

          <div className="plan-cta-row">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Batal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              <Plus size={15} />
              <span>{saving ? 'Menyimpan...' : mode === 'batch' ? `Buat ${batchCount} Unit` : 'Buat Unit Stok'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

