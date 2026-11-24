import React, { useState, useEffect } from 'react'
import { X, Save, Settings as SettingsIcon } from 'lucide-react'

export function SettingsModal({
  isOpen,
  onClose,
  settings,
  activeDevice,
  onSave,
}) {
  const [tariff, setTariff] = useState('')
  const [powerLimit, setPowerLimit] = useState(2200)
  const [cooldown, setCooldown] = useState(30)
  const [extraPercent, setExtraPercent] = useState(0)
  const [reportHour, setReportHour] = useState(7)
  const [statusMsg, setStatusMsg] = useState(null)
  const [isError, setIsError] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (settings) {
      setTariff((parseInt(settings.tariff_sen_per_kwh, 10) / 100.0).toFixed(2))
      setPowerLimit(settings.power_limit_w)
      setCooldown(settings.alert_cooldown_min)
      setExtraPercent(settings.extra_percent)
      setReportHour(settings.report_hour)
    }
  }, [settings, isOpen])

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatusMsg(null)
    setIsError(false)
    setSaving(true)

    const payload = {
      tariff_rp: tariff.trim(),
      power_limit_w: parseInt(powerLimit, 10),
      alert_cooldown_min: parseInt(cooldown, 10),
      extra_percent: parseFloat(extraPercent),
      report_hour: parseInt(reportHour, 10),
    }

    try {
      await onSave(payload)
      setIsError(false)
      setStatusMsg('Pengaturan berhasil disimpan!')
      setTimeout(() => {
        onClose()
      }, 1200)
    } catch (err) {
      setIsError(true)
      setStatusMsg(err.message || 'Gagal menyimpan pengaturan.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <div className="modal-title-wrap">
            <SettingsIcon size={20} className="text-primary" />
            <h3>Pengaturan Sistem</h3>
          </div>
          <button className="btn-close" onClick={onClose} aria-label="Tutup">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="settings-form">
          <div className="form-group">
            <label htmlFor="input-tariff">Tarif Listrik (Rp/kWh)</label>
            <input
              type="text"
              id="input-tariff"
              value={tariff}
              onChange={(e) => setTariff(e.target.value)}
              placeholder="Contoh: 1444.70"
              required
            />
            <small className="form-help">Maksimal 2 desimal. Contoh: 1444.70 atau 1444,70</small>
          </div>

          <div className="form-group">
            <label htmlFor="input-power-limit">Batas Daya PLN (Watt)</label>
            <input
              type="number"
              id="input-power-limit"
              value={powerLimit}
              onChange={(e) => setPowerLimit(e.target.value)}
              min="100"
              max="25000"
              required
            />
            <small className="form-help">Rentang 100 s.d. 25.000 Watt (Contoh: 2200)</small>
          </div>

          <div className="form-group">
            <label>Kapasitas MCB Perangkat (Info)</label>
            <input
              type="text"
              value={activeDevice ? `${activeDevice.mcb_watt} W` : '-'}
              disabled
              readOnly
              className="input-disabled"
            />
          </div>

          <div className="form-group">
            <label htmlFor="input-cooldown">Cooldown Notifikasi (Menit)</label>
            <input
              type="number"
              id="input-cooldown"
              value={cooldown}
              onChange={(e) => setCooldown(e.target.value)}
              min="5"
              max="1440"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="input-extra-percent">Biaya Tambahan / Pajak (%)</label>
            <input
              type="number"
              id="input-extra-percent"
              value={extraPercent}
              onChange={(e) => setExtraPercent(e.target.value)}
              min="0"
              step="0.1"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="input-report-hour">Jam Laporan Harian (WIB)</label>
            <input
              type="number"
              id="input-report-hour"
              value={reportHour}
              onChange={(e) => setReportHour(e.target.value)}
              min="0"
              max="23"
              required
            />
          </div>

          {statusMsg && (
            <div className={isError ? 'error-msg' : 'status-msg'}>{statusMsg}</div>
          )}

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Batal
            </button>
            <button type="submit" className="btn btn-primary btn-icon-text" disabled={saving}>
              <Save size={16} />
              <span>{saving ? 'Menyimpan...' : 'Simpan Pengaturan'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
