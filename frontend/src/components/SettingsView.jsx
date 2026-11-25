import React, { useState, useEffect, useMemo } from 'react'
import {
  Save,
  Trash2,
  Wifi,
  AlertTriangle,
  LogIn,
  Lock,
  ChevronRight,
  Compass,
  ShieldCheck,
  Zap,
  BellRing,
  RotateCcw,
  Calculator,
  Clock,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatNum, formatRp } from '../utils/formatters'

const PRESET_ROOMS = ['Panel Utama', 'Ruang Tamu', 'Kamar Tidur', 'Dapur', 'Lantai 2', 'Warung']

const PLN_TARIFF_PRESETS = [
  { id: 'r1-900', label: 'R1 900 VA', tariffRp: '1352.00', watt: 900 },
  { id: 'r1-1300', label: 'R1 1300–2200 VA', tariffRp: '1444.70', watt: 2200 },
  { id: 'r2-3500', label: 'R2 3500+ VA', tariffRp: '1699.53', watt: 3500 },
]

const POWER_PRESETS = [900, 1300, 2200, 3500, 4400, 5500]
const COOLDOWN_PRESETS = [15, 30, 60]
const REPORT_HOUR_QUICK = [7, 12, 20, 21]

function formatHourLabel(hour) {
  const h = Math.max(0, Math.min(23, Number(hour) || 0))
  return `${String(h).padStart(2, '0')}:00 WIB`
}

export function SettingsView({
  mode = 'global',
  settings,
  activeDevice,
  token,
  isAuthenticated = false,
  onSave,
  onDeviceUpdated,
  onDeviceDeleted,
  onOpenLogin,
  onLogout,
  onReplayTour,
  onOpenTerms,
  appConfig = {},
}) {
  const [tariff, setTariff] = useState('1444.70')
  const [powerLimit, setPowerLimit] = useState(2200)
  const [cooldown, setCooldown] = useState(30)
  const [extraPercent, setExtraPercent] = useState(0)
  const [reportHour, setReportHour] = useState(21)
  const [reportEnabled, setReportEnabled] = useState(true)
  const [sysMsg, setSysMsg] = useState(null)
  const [sysErr, setSysErr] = useState(false)
  const [savingSys, setSavingSys] = useState(false)

  const [devName, setDevName] = useState('')
  const [devLocation, setDevLocation] = useState('')
  const [devMcb, setDevMcb] = useState(2200)
  const [devMsg, setDevMsg] = useState(null)
  const [savingDev, setSavingDev] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const syncedSnapshot = useMemo(() => {
    if (!settings) {
      return {
        tariff: '1444.70',
        powerLimit: 2200,
        cooldown: 30,
        extraPercent: 0,
        reportHour: 21,
        reportEnabled: true,
      }
    }
    const rawSen = settings.tariff_sen ?? settings.tariff_sen_per_kwh
    const nextTariff =
      settings.tariff_rp ??
      (Number.isFinite(Number(rawSen)) ? (Number(rawSen) / 100).toFixed(2) : '1444.70')
    return {
      tariff: String(nextTariff),
      powerLimit: settings.power_limit_w ?? 2200,
      cooldown: settings.alert_cooldown_min ?? 30,
      extraPercent: settings.extra_percent ?? 0,
      reportHour: settings.report_hour ?? 21,
      reportEnabled: settings.report_enabled !== false,
    }
  }, [settings])

  useEffect(() => {
    setTariff(syncedSnapshot.tariff)
    setPowerLimit(syncedSnapshot.powerLimit)
    setCooldown(syncedSnapshot.cooldown)
    setExtraPercent(syncedSnapshot.extraPercent)
    setReportHour(syncedSnapshot.reportHour)
    setReportEnabled(syncedSnapshot.reportEnabled)
  }, [syncedSnapshot])

  useEffect(() => {
    if (activeDevice) {
      setDevName(activeDevice.name || activeDevice.id)
      setDevLocation(activeDevice.location || '')
      setDevMcb(activeDevice.mcb_watt || 2200)
      setConfirmDelete(false)
      setDevMsg(null)
    }
  }, [activeDevice])

  const parsedBaseTariff = Number(String(tariff).replace(',', '.')) || 0
  const parsedExtraPct = Number(extraPercent) || 0
  const effectiveTariffPerKwh = parsedBaseTariff * (1 + Math.max(0, parsedExtraPct) / 100)
  const sample100KwhCost = Math.round(effectiveTariffPerKwh * 100)

  const isDirty =
    mode === 'global' &&
    (String(tariff).trim() !== String(syncedSnapshot.tariff).trim() ||
      Number(powerLimit) !== Number(syncedSnapshot.powerLimit) ||
      Number(cooldown) !== Number(syncedSnapshot.cooldown) ||
      Number(extraPercent) !== Number(syncedSnapshot.extraPercent) ||
      Number(reportHour) !== Number(syncedSnapshot.reportHour) ||
      Boolean(reportEnabled) !== Boolean(syncedSnapshot.reportEnabled))

  const handleResetSystem = () => {
    setTariff(syncedSnapshot.tariff)
    setPowerLimit(syncedSnapshot.powerLimit)
    setCooldown(syncedSnapshot.cooldown)
    setExtraPercent(syncedSnapshot.extraPercent)
    setReportHour(syncedSnapshot.reportHour)
    setReportEnabled(syncedSnapshot.reportEnabled)
    setSysMsg(null)
    setSysErr(false)
  }

  const handleSaveDevice = async (e) => {
    e.preventDefault()
    if (!activeDevice) return
    setDevMsg(null)
    setSavingDev(true)
    try {
      await apiRequest(
        `/api/devices/${activeDevice.id}`,
        {
          method: 'PATCH',
          body: {
            name: devName.trim(),
            location: devLocation.trim(),
            mcb_watt: parseInt(devMcb, 10),
          },
        },
        token,
        onLogout
      )
      setDevMsg({ type: 'success', text: 'Pengaturan perangkat disimpan.' })
      if (onDeviceUpdated) await onDeviceUpdated()
      setTimeout(() => setDevMsg(null), 3000)
    } catch (err) {
      setDevMsg({ type: 'error', text: err.message || 'Gagal menyimpan perangkat.' })
    } finally {
      setSavingDev(false)
    }
  }

  const handleDeleteDevice = async () => {
    if (!activeDevice) return
    setDeleting(true)
    setDevMsg(null)
    try {
      await apiRequest(
        `/api/devices/${activeDevice.id}`,
        { method: 'DELETE' },
        token,
        onLogout
      )
      if (onDeviceDeleted) await onDeviceDeleted(activeDevice.id)
    } catch (err) {
      setDevMsg({ type: 'error', text: err.message || 'Gagal menghapus perangkat.' })
      setDeleting(false)
    }
  }

  const handleSubmitSystem = async (e) => {
    e.preventDefault()
    setSysMsg(null)
    setSysErr(false)
    setSavingSys(true)

    const payload = {
      tariff_rp: String(tariff).trim().replace(',', '.'),
      power_limit_w: parseInt(powerLimit, 10),
      alert_cooldown_min: parseInt(cooldown, 10),
      extra_percent: parseFloat(extraPercent) || 0,
      report_hour: parseInt(reportHour, 10),
      report_enabled: Boolean(reportEnabled),
    }

    try {
      await onSave(payload)
      setSysErr(false)
      setSysMsg('Pengaturan tarif & peringatan berhasil disimpan.')
      setTimeout(() => setSysMsg(null), 3000)
    } catch (err) {
      setSysErr(true)
      setSysMsg(err.message || 'Gagal menyimpan pengaturan.')
    } finally {
      setSavingSys(false)
    }
  }

  if (mode === 'device') {
    if (!activeDevice) return null
    return (
      <div className="settings-single-wrap">
        <section className="clean-sheet settings-panel-card">
          <div className="settings-panel-header">
            <div>
              <h2 className="settings-panel-title">Pengaturan Panel</h2>
              <div className="settings-panel-subtitle">Sesuaikan nama, lokasi, dan batas daya MCB alat</div>
            </div>
            <span className="settings-device-id-note num-tabular">{activeDevice.id}</span>
          </div>

          {!isAuthenticated && (
            <div className="settings-lock-banner">
              <div className="settings-lock-copy">
                <Lock size={15} />
                <span>Mode Guest. Masuk untuk mengubah atau menghapus alat ini.</span>
              </div>
              {onOpenLogin && (
                <button type="button" className="btn btn-primary btn-compact" onClick={onOpenLogin}>
                  <LogIn size={14} />
                  <span>Masuk</span>
                </button>
              )}
            </div>
          )}

          {devMsg && (
            <div className={`feedback-msg ${devMsg.type === 'error' ? 'error' : 'success'}`}>
              {devMsg.text}
            </div>
          )}

          <form onSubmit={handleSaveDevice}>
            <div className="form-field-group">
              <label className="field-label" htmlFor="set-dev-name">
                Nama Perangkat
              </label>
              <input
                id="set-dev-name"
                type="text"
                className="modern-input"
                value={devName}
                onChange={(e) => setDevName(e.target.value)}
                disabled={!isAuthenticated}
                required
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="set-dev-loc">
                Ruangan
              </label>
              {isAuthenticated && (
                <div className="room-chips-row" style={{ marginBottom: 8 }}>
                  {PRESET_ROOMS.map((r) => (
                    <button
                      key={r}
                      type="button"
                      className={`room-chip ${devLocation === r ? 'selected' : ''}`}
                      onClick={() => setDevLocation(r)}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              )}
              <input
                id="set-dev-loc"
                type="text"
                className="modern-input"
                placeholder="Atau ketik nama ruangan..."
                value={devLocation}
                onChange={(e) => setDevLocation(e.target.value)}
                disabled={!isAuthenticated}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="set-dev-mcb">
                Batas MCB Alat
              </label>
              {isAuthenticated && (
                <div className="room-chips-row" style={{ marginBottom: 8 }}>
                  {POWER_PRESETS.map((w) => (
                    <button
                      key={w}
                      type="button"
                      className={`room-chip num-tabular ${Number(devMcb) === w ? 'selected' : ''}`}
                      onClick={() => setDevMcb(w)}
                    >
                      {w} VA
                    </button>
                  ))}
                </div>
              )}
              <div className="input-affix-wrap">
                <input
                  id="set-dev-mcb"
                  type="number"
                  className="modern-input has-suffix num-tabular"
                  min="100"
                  max="25000"
                  value={devMcb}
                  onChange={(e) => setDevMcb(e.target.value)}
                  disabled={!isAuthenticated}
                  required
                />
                <span className="input-affix-suffix">Watt</span>
              </div>
            </div>

            <div className="wifi-repair-box">
              <div className="wifi-repair-head">
                <Wifi size={15} className="brand-blue-text" />
                <span>Ganti Wi-Fi Alat</span>
              </div>
              <p>
                Tekan &amp; tahan tombol Pairing fisik selama <strong>3 detik</strong> hingga
                lampu berkedip cepat, lalu sambungkan HP ke hotspot <code>VoltKu-XXXX</code>.
              </p>
            </div>

            {isAuthenticated && (
              <div className="settings-actions-spread">
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
                    onClick={handleDeleteDevice}
                    disabled={deleting}
                  >
                    <AlertTriangle size={15} />
                    <span>{deleting ? 'Menghapus...' : 'Konfirmasi Hapus'}</span>
                  </button>
                )}

                <button type="submit" className="btn btn-primary" disabled={savingDev}>
                  <Save size={15} />
                  <span>{savingDev ? 'Menyimpan...' : 'Simpan Alat'}</span>
                </button>
              </div>
            )}
          </form>
        </section>
      </div>
    )
  }

  const termsVersion = appConfig.terms_version || '2026-11-v1'
  const showOnboardingRow = Boolean(onReplayTour && appConfig.onboarding_enabled !== false)

  return (
    <div className="settings-single-wrap settings-stack-col">
      {/* Ringkasan Konfigurasi Aktif */}
      <section className="settings-overview-strip" aria-label="Ringkasan setelan aktif">
        <div className="settings-overview-pill">
          <span className="settings-overview-label">Tarif Efektif</span>
          <strong className="settings-overview-val num-tabular">
            Rp {formatNum(effectiveTariffPerKwh, 2)}/kWh
          </strong>
        </div>
        <div className="settings-overview-pill">
          <span className="settings-overview-label">Batas Daya</span>
          <strong className="settings-overview-val num-tabular">
            {formatNum(Number(powerLimit) || 0, 0)} W
          </strong>
        </div>
        <div className="settings-overview-pill">
          <span className="settings-overview-label">Rekap Harian</span>
          <strong className="settings-overview-val num-tabular">
            {reportEnabled ? formatHourLabel(reportHour) : 'Nonaktif'}
          </strong>
        </div>
      </section>

      {!isAuthenticated && (
        <div className="clean-sheet settings-lock-banner" style={{ marginBottom: 0 }}>
          <div className="settings-lock-copy">
            <Lock size={15} />
            <span>Mode Guest. Masuk untuk mengubah tarif listrik atau aturan peringatan.</span>
          </div>
          {onOpenLogin && (
            <button type="button" className="btn btn-primary btn-compact" onClick={onOpenLogin}>
              <LogIn size={14} />
              <span>Masuk</span>
            </button>
          )}
        </div>
      )}

      {sysMsg && (
        <div className={`feedback-msg ${sysErr ? 'error' : 'success'}`} style={{ marginBottom: 0 }}>
          {sysMsg}
        </div>
      )}

      <form className="settings-stack-col" onSubmit={handleSubmitSystem}>
        {/* KARTU 1: Tarif Listrik & Simulasi Biaya PLN */}
        <section className="clean-sheet settings-panel-card">
          <div className="settings-section-head">
            <div className="settings-section-icon is-blue">
              <Zap size={17} />
            </div>
            <div>
              <h2 className="settings-panel-title">Tarif Listrik PLN</h2>
              <div className="settings-panel-subtitle">
                Pilih golongan daya rumah atau isi tarif per kWh secara manual
              </div>
            </div>
          </div>

          <div className="settings-preset-block">
            <span className="settings-preset-label">Preset Golongan PLN</span>
            <div className="room-chips-row">
              {PLN_TARIFF_PRESETS.map((p) => {
                const isSelected = Math.abs(parsedBaseTariff - Number(p.tariffRp)) < 0.01
                return (
                  <button
                    key={p.id}
                    type="button"
                    disabled={!isAuthenticated}
                    className={`room-chip num-tabular ${isSelected ? 'selected' : ''}`}
                    onClick={() => setTariff(p.tariffRp)}
                  >
                    {p.label}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group" style={{ marginBottom: 0 }}>
              <label className="field-label" htmlFor="settings-view-tariff">
                Tarif Dasar PLN
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
                  disabled={!isAuthenticated}
                  required
                />
                <span className="input-affix-suffix">/kWh</span>
              </div>
              <small className="field-hint">Maksimal 2 angka di belakang koma</small>
            </div>

            <div className="form-field-group" style={{ marginBottom: 0 }}>
              <label className="field-label" htmlFor="settings-view-extra-percent">
                PPJ / Biaya Tambahan
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
                  disabled={!isAuthenticated}
                  required
                />
                <span className="input-affix-suffix">%</span>
              </div>
              <small className="field-hint">Pajak Penerangan Jalan daerah (opsional)</small>
            </div>
          </div>

          <div className="settings-calc-strip num-tabular">
            <Calculator size={15} />
            <span>
              Tarif efektif <strong>Rp {formatNum(effectiveTariffPerKwh, 2)}/kWh</strong> · Estimasi
              100 kWh ≈ <strong>{formatRp(sample100KwhCost)}</strong>
            </span>
          </div>
        </section>

        {/* KARTU 2: Peringatan Beban & Laporan Harian */}
        <section className="clean-sheet settings-panel-card">
          <div className="settings-section-head">
            <div className="settings-section-icon is-amber">
              <BellRing size={17} />
            </div>
            <div>
              <h2 className="settings-panel-title">Peringatan &amp; Laporan Harian</h2>
              <div className="settings-panel-subtitle">
                Atur ambang batas alarm beban listrik dan jadwal ringkasan harian
              </div>
            </div>
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="settings-view-power-limit">
              Batas Daya Peringatan
            </label>
            <div className="room-chips-row" style={{ marginBottom: 8 }}>
              {POWER_PRESETS.map((w) => (
                <button
                  key={w}
                  type="button"
                  disabled={!isAuthenticated}
                  className={`room-chip num-tabular ${Number(powerLimit) === w ? 'selected' : ''}`}
                  onClick={() => setPowerLimit(w)}
                >
                  {w} W
                </button>
              ))}
            </div>
            <div className="input-affix-wrap">
              <input
                type="number"
                id="settings-view-power-limit"
                className="modern-input has-suffix num-tabular"
                value={powerLimit}
                onChange={(e) => setPowerLimit(e.target.value)}
                min="100"
                max="25000"
                disabled={!isAuthenticated}
                required
              />
              <span className="input-affix-suffix">Watt</span>
            </div>
            <small className="field-hint">
              Notifikasi peringatan muncul saat beban listrik melampaui angka ini.
            </small>
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="settings-view-cooldown">
              Jeda Peringatan Ulang
            </label>
            <div className="room-chips-row" style={{ marginBottom: 8 }}>
              {COOLDOWN_PRESETS.map((m) => (
                <button
                  key={m}
                  type="button"
                  disabled={!isAuthenticated}
                  className={`room-chip num-tabular ${Number(cooldown) === m ? 'selected' : ''}`}
                  onClick={() => setCooldown(m)}
                >
                  {m} Menit
                </button>
              ))}
            </div>
            <div className="input-affix-wrap">
              <input
                type="number"
                id="settings-view-cooldown"
                className="modern-input has-suffix num-tabular"
                value={cooldown}
                onChange={(e) => setCooldown(e.target.value)}
                min="5"
                max="1440"
                disabled={!isAuthenticated}
                required
              />
              <span className="input-affix-suffix">Menit</span>
            </div>
            <small className="field-hint">
              Mencegah notifikasi berulang dikirim terlalu rapat saat beban masih tinggi.
            </small>
          </div>

          {/* Toggle Laporan Rekap Harian + Pemilih Jam */}
          <div className="settings-report-box">
            <div className="settings-switch-row">
              <div className="settings-switch-copy">
                <strong>Laporan Rekap Harian</strong>
                <span>Kirim ringkasan pemakaian kWh &amp; estimasi biaya harian secara rutin</span>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={reportEnabled}
                aria-label="Aktifkan Laporan Rekap Harian"
                disabled={!isAuthenticated}
                className={`settings-toggle-switch ${reportEnabled ? 'is-on' : ''}`}
                onClick={() => setReportEnabled((prev) => !prev)}
              >
                <span className="settings-toggle-knob" />
              </button>
            </div>

            {reportEnabled && (
              <div className="settings-report-hour-block">
                <label className="field-label" htmlFor="settings-view-report-hour">
                  Jam Kirim Rekap Harian
                </label>
                <div className="room-chips-row" style={{ marginBottom: 8 }}>
                  {REPORT_HOUR_QUICK.map((h) => (
                    <button
                      key={h}
                      type="button"
                      disabled={!isAuthenticated}
                      className={`room-chip num-tabular ${Number(reportHour) === h ? 'selected' : ''}`}
                      onClick={() => setReportHour(h)}
                    >
                      {formatHourLabel(h)}
                    </button>
                  ))}
                </div>
                <div className="input-affix-wrap">
                  <span className="input-affix-prefix">
                    <Clock size={14} />
                  </span>
                  <select
                    id="settings-view-report-hour"
                    className="modern-input has-prefix num-tabular"
                    value={reportHour}
                    onChange={(e) => setReportHour(Number(e.target.value))}
                    disabled={!isAuthenticated}
                  >
                    {Array.from({ length: 24 }, (_, hour) => (
                      <option key={hour} value={hour}>
                        {formatHourLabel(hour)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>

          {isAuthenticated && (
            <div className="settings-save-bar">
              {isDirty ? (
                <div className="settings-dirty-row">
                  <span className="settings-dirty-badge">Ada perubahan belum disimpan</span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    onClick={handleResetSystem}
                  >
                    <RotateCcw size={14} />
                    <span>Reset</span>
                  </button>
                </div>
              ) : (
                <span className="settings-synced-note">Setelan sudah tersinkronisasi</span>
              )}

              <button
                type="submit"
                className="btn btn-primary settings-save-btn"
                disabled={savingSys}
              >
                <Save size={15} />
                <span>{savingSys ? 'Menyimpan...' : 'Simpan Pengaturan'}</span>
              </button>
            </div>
          )}
        </section>
      </form>

      {!isAuthenticated && (showOnboardingRow || onOpenTerms) && (
        <section className="clean-sheet app-menu-group">
          {showOnboardingRow && (
            <button type="button" className="app-menu-row" onClick={onReplayTour}>
              <span className="app-menu-icon is-blue">
                <Compass size={17} />
              </span>
              <span className="app-menu-copy">
                <strong>Panduan Awal Aplikasi</strong>
                <span>Lihat pengenalan singkat cara memantau daya &amp; biaya</span>
              </span>
              <ChevronRight size={17} className="app-menu-chevron" />
            </button>
          )}
          {onOpenTerms && (
            <button type="button" className="app-menu-row" onClick={() => onOpenTerms('terms')}>
              <span className="app-menu-icon is-emerald">
                <ShieldCheck size={17} />
              </span>
              <span className="app-menu-copy">
                <strong>Syarat Penggunaan &amp; Kebijakan Privasi</strong>
                <span>Versi {termsVersion}</span>
              </span>
              <ChevronRight size={17} className="app-menu-chevron" />
            </button>
          )}
        </section>
      )}
    </div>
  )
}
