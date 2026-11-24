import React, { useState, useEffect } from 'react'
import { X, Check, Sliders, Shield } from 'lucide-react'

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
      setStatusMsg('Pengaturan berhasil diperbarui!')
      setTimeout(() => {
        onClose()
      }, 1000)
    } catch (err) {
      setIsError(true)
      setStatusMsg(err.message || 'Gagal menyimpan pengaturan.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog-modern" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header-modern">
          <div className="modal-title-group">
            <Sliders size={20} className="modal-title-icon" />
            <h3 className="modal-title-text">Parameter Sistem & Biaya</h3>
          </div>
          <button className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {statusMsg && (
            <div className={`feedback-msg ${isError ? 'error' : 'success'}`}>
              {statusMsg}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="form-field-group">
              <label className="field-label" htmlFor="input-tariff">
                Tarif Listrik PLN
              </label>
              <div className="input-affix-wrap">
                <span className="input-affix-prefix">Rp</span>
                <input
                  type="text"
                  id="input-tariff"
                  className="modern-input has-prefix has-suffix num-tabular"
                  value={tariff}
                  onChange={(e) => setTariff(e.target.value)}
                  placeholder="1444.70"
                  required
                />
                <span className="input-affix-suffix">/kWh</span>
              </div>
              <small className="field-hint">Maksimal 2 desimal</small>
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="input-power-limit">
                Batas Daya Kontrak
              </label>
              <div className="input-affix-wrap">
                <input
                  type="number"
                  id="input-power-limit"
                  className="modern-input has-suffix num-tabular"
                  value={powerLimit}
                  onChange={(e) => setPowerLimit(e.target.value)}
                  min="100"
                  max="25000"
                  required
                />
                <span className="input-affix-suffix">Watt</span>
              </div>
              <small className="field-hint">Ambang batas beban (100-25k W)</small>
            </div>
          </div>

          <div className="form-field-group">
            <label className="field-label">Kapasitas MCB Terpasang (Hardware)</label>
            <div className="input-affix-wrap">
              <input
                type="text"
                value={activeDevice ? `${activeDevice.mcb_watt} Watt` : 'Belum terhubung'}
                disabled
                readOnly
                className="modern-input"
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="form-field-group">
              <label className="field-label" htmlFor="input-cooldown">
                Jeda Peringatan Ulang
              </label>
              <div className="input-affix-wrap">
                <input
                  type="number"
                  id="input-cooldown"
                  className="modern-input has-suffix num-tabular"
                  value={cooldown}
                  onChange={(e) => setCooldown(e.target.value)}
                  min="5"
                  max="1440"
                  required
                />
                <span className="input-affix-suffix">Menit</span>
              </div>
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="input-extra-percent">
                Pajak / PPJ / Tambahan
              </label>
              <div className="input-affix-wrap">
                <input
                  type="number"
                  id="input-extra-percent"
                  className="modern-input has-suffix num-tabular"
                  value={extraPercent}
                  onChange={(e) => setExtraPercent(e.target.value)}
                  min="0"
                  step="0.1"
                  required
                />
                <span className="input-affix-suffix">%</span>
              </div>
            </div>
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="input-report-hour">
              Jadwal Rekap Laporan Harian
            </label>
            <div className="input-affix-wrap">
              <input
                type="number"
                id="input-report-hour"
                className="modern-input has-suffix num-tabular"
                value={reportHour}
                onChange={(e) => setReportHour(e.target.value)}
                min="0"
                max="23"
                required
              />
              <span className="input-affix-suffix">:00 WIB</span>
            </div>
          </div>

          <div className="modal-actions-row">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Batal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Menyimpan...' : 'Terapkan Konfigurasi'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
