import React, { useState, useEffect } from 'react'
import { X, Save, Trash2, Wifi, AlertTriangle } from 'lucide-react'
import { apiRequest } from '../api/client'

const PRESET_ROOMS = ['Panel Utama', 'Ruang Tamu', 'Kamar Tidur', 'Dapur', 'Lantai 2', 'Warung']

export function DeviceEditModal({
  isOpen,
  onClose,
  device,
  token,
  onDeviceUpdated,
  onDeviceDeleted,
  onLogout,
}) {
  const [name, setName] = useState('')
  const [location, setLocation] = useState('')
  const [mcbWatt, setMcbWatt] = useState(2200)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [feedback, setFeedback] = useState(null)

  useEffect(() => {
    if (device && isOpen) {
      setName(device.name || device.id)
      setLocation(device.location || '')
      setMcbWatt(device.mcb_watt || 2200)
      setConfirmDelete(false)
      setFeedback(null)
    }
  }, [device, isOpen])

  if (!isOpen || !device) return null

  const handleSave = async (e) => {
    e.preventDefault()
    setFeedback(null)
    setSaving(true)
    try {
      const updated = await apiRequest(
        `/api/devices/${device.id}`,
        {
          method: 'PATCH',
          body: {
            name: name.trim(),
            location: location.trim(),
            mcb_watt: parseInt(mcbWatt, 10),
          },
        },
        token,
        onLogout
      )
      setFeedback({ type: 'success', msg: 'Data perangkat berhasil diperbarui!' })
      if (onDeviceUpdated) await onDeviceUpdated(updated)
      setTimeout(() => onClose(), 700)
    } catch (err) {
      setFeedback({ type: 'error', msg: err.message || 'Gagal memperbarui perangkat.' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    setFeedback(null)
    try {
      await apiRequest(
        `/api/devices/${device.id}`,
        { method: 'DELETE' },
        token,
        onLogout
      )
      if (onDeviceDeleted) await onDeviceDeleted(device.id)
      onClose()
    } catch (err) {
      setFeedback({ type: 'error', msg: err.message || 'Gagal menghapus perangkat.' })
      setDeleting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog-modern" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header-modern">
          <div className="modal-title-group">
            <h3 className="modal-title-text">Pengaturan Perangkat</h3>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        {feedback && (
          <div className={`feedback-msg ${feedback.type === 'error' ? 'error' : 'success'}`}>
            {feedback.msg}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div className="form-field-group">
            <label className="field-label">Kode Perangkat (Hardware ID)</label>
            <input type="text" className="modern-input num-tabular" value={device.id} disabled readOnly />
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="edit-dev-name">
              Nama Perangkat
            </label>
            <input
              id="edit-dev-name"
              type="text"
              className="modern-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="edit-dev-loc">
              Ruangan / Lokasi Panel
            </label>
            <div className="room-chips-row" style={{ marginBottom: 8 }}>
              {PRESET_ROOMS.map((r) => (
                <button
                  key={r}
                  type="button"
                  className={`room-chip ${location === r ? 'selected' : ''}`}
                  onClick={() => setLocation(r)}
                >
                  {r}
                </button>
              ))}
            </div>
            <input
              id="edit-dev-loc"
              type="text"
              className="modern-input"
              placeholder="Contoh: Panel Utama"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="edit-dev-mcb">
              Kapasitas MCB Terpasang (Watt)
            </label>
            <div className="input-affix-wrap">
              <input
                id="edit-dev-mcb"
                type="number"
                className="modern-input has-suffix num-tabular"
                min="100"
                max="25000"
                value={mcbWatt}
                onChange={(e) => setMcbWatt(e.target.value)}
                required
              />
              <span className="input-affix-suffix">Watt</span>
            </div>
          </div>

          <div className="wifi-repair-box">
            <div className="wifi-repair-head">
              <Wifi size={15} className="text-cyan" />
              <span>Ganti Jaringan Wi-Fi Alat</span>
            </div>
            <p>
              Jika router rumah diganti, tekan &amp; tahan tombol Pairing fisik di unit selama{' '}
              <strong>3 detik</strong> sampai lampu berkedip cepat, lalu sambungkan HP ke hotspot{' '}
              <code>VoltKu-XXXX</code> untuk memilih Wi-Fi baru.
            </p>
          </div>

          <div className="modal-actions-row" style={{ justifyContent: 'space-between', marginTop: 18 }}>
            {!confirmDelete ? (
              <button
                type="button"
                className="btn btn-danger-ghost"
                onClick={() => setConfirmDelete(true)}
              >
                <Trash2 size={15} />
                <span>Hapus Alat</span>
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-danger-solid"
                onClick={handleDelete}
                disabled={deleting}
              >
                <AlertTriangle size={15} />
                <span>{deleting ? 'Menghapus...' : 'Konfirmasi Hapus Permanen'}</span>
              </button>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Batal
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                <Save size={15} />
                <span>{saving ? 'Menyimpan...' : 'Simpan'}</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

