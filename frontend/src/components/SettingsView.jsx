import React, { useState, useEffect } from 'react'
import { Sliders, Save, CheckCircle2 } from 'lucide-react'

export function SettingsView({ settings, activeDevice, onSave }) {
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
  }, [settings])

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
        setStatusMsg(null)
      }, 3000)
    } catch (err) {
      setIsError(true)
      setStatusMsg(err.message || 'Gagal menyimpan pengaturan.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="section-block">
      <div className="card settings-view-card">
        <div className="section-header">
          <div className="section-title">
            <Sliders size={15} className="text-primary" /> Parameter Sistem & Tarif Listrik
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ marginTop: 12 }}>
          {statusMsg && (
            <div className={`feedback-msg ${isError ? 'error' : 'success'}`}>
              {statusMsg}
            </div>
          )}

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="settings-view-tariff">
                Tarif Listrik PLN
              </label>
              <div className="input-affix-wrap">
                <span className="input-affix-prefix">Rp</span>
                <input
                  type="text"
                  id="settings-view-tariff"
                  className="modern-input has-prefix has-suffix num-tabular"
                  value={tariff}
                  onChange={(e) => setTariff(e.target.value)}
                  placeholder="1444.70"
                  required
                />
                <span className="input-affix-suffix">/kWh</span>
              </div>
              <small className="field-hint">Maksimal 2 desimal (contoh: 1444.70)</small>
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="settings-view-power-limit">
                Batas Daya Kontrak PLN
              </label>
              <div className="input-affix-wrap">
                <input
                  type="number"
                  id="settings-view-power-limit"
                  className="modern-input has-suffix num-tabular"
                  value={powerLimit}
                  onChange={(e) => setPowerLimit(e.target.value)}
                  min="100"
                  max="25000"
                  required
                />
                <span className="input-affix-suffix">Watt</span>
              </div>
              <small className="field-hint">Ambang beban (100 - 25.000 Watt)</small>
            </div>
          </div>

          <div className="form-field-group">
            <label className="field-label">Kapasitas MCB Terpasang (Hardware Sensor)</label>
            <div className="input-affix-wrap">
              <input
                type="text"
                value={activeDevice ? `${activeDevice.name || activeDevice.id}: ${activeDevice.mcb_watt} Watt` : 'Belum terhubung'}
                disabled
                readOnly
                className="modern-input"
              />
            </div>
            <small className="field-hint">Kapasitas fisik pemutus daya yang sedang dipantau</small>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="settings-view-cooldown">
                Jeda Peringatan Ulang (Cooldown)
              </label>
              <div className="input-affix-wrap">
                <input
                  type="number"
                  id="settings-view-cooldown"
                  className="modern-input has-suffix num-tabular"
                  value={cooldown}
                  onChange={(e) => setCooldown(e.target.value)}
                  min="5"
                  max="1440"
                  required
                />
                <span className="input-affix-suffix">Menit</span>
              </div>
              <small className="field-hint">Rentang 5 s.d. 1440 menit</small>
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="settings-view-extra-percent">
                Pajak / PPJ / Biaya Tambahan
              </label>
              <div className="input-affix-wrap">
                <input
                  type="number"
                  id="settings-view-extra-percent"
                  className="modern-input has-suffix num-tabular"
                  value={extraPercent}
                  onChange={(e) => setExtraPercent(e.target.value)}
                  min="0"
                  step="0.1"
                  required
                />
                <span className="input-affix-suffix">%</span>
              </div>
              <small className="field-hint">Persentase tambahan biaya tagihan</small>
            </div>
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="settings-view-report-hour">
              Jadwal Rekap Laporan Harian
            </label>
            <div className="input-affix-wrap">
              <input
                type="number"
                id="settings-view-report-hour"
                className="modern-input has-suffix num-tabular"
                value={reportHour}
                onChange={(e) => setReportHour(e.target.value)}
                min="0"
                max="23"
                required
              />
              <span className="input-affix-suffix">:00 WIB</span>
            </div>
            <small className="field-hint">Jam pengiriman laporan harian (0-23 WIB)</small>
          </div>

          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ minWidth: 160, padding: '10px 20px' }}
              disabled={saving}
            >
              <Save size={16} />
              <span>{saving ? 'Menyimpan...' : 'Simpan Perubahan'}</span>
            </button>
          </div>
        </form>
      </div>
    </section>
  )
}
