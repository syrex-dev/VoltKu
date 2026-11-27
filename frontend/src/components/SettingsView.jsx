import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  Save,
  Trash2,
  Wifi,
  AlertTriangle,
  LogIn,
  Lock,
  ChevronRight,
  ChevronDown,
  Check,
  Compass,
  ShieldCheck,
  Zap,
  BellRing,
  RotateCcw,
  Calculator,
  Clock,
  Globe,
  Sun,
  Moon,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatNum, formatRp } from '../utils/formatters'
import {
  INDONESIAN_TIMEZONES,
  getTimeZoneShortLabel,
  useUserPrefs,
} from '../utils/userPrefs'

const PRESET_ROOMS = ['Panel Utama', 'Ruang Tamu', 'Kamar Tidur', 'Dapur', 'Lantai 2', 'Warung']

const PLN_TARIFF_CATEGORIES = [
  { id: 'all', label: 'Semua' },
  { id: 'rumah', label: 'Rumah' },
  { id: 'bisnis', label: 'Bisnis' },
  { id: 'sosial', label: 'Sosial' },
  { id: 'lainnya', label: 'Industri & Pem' },
]

const PLN_TARIFF_PRESETS = [
  // Rumah Tangga (R)
  { id: 'r1-450', category: 'rumah', group: 'Rumah Tangga', label: 'R-1/TR · 450 VA (Subsidi)', tariffRp: '415.00' },
  { id: 'r1-900-sub', category: 'rumah', group: 'Rumah Tangga', label: 'R-1/TR · 900 VA (Subsidi)', tariffRp: '605.00' },
  { id: 'r1-900-rtm', category: 'rumah', group: 'Rumah Tangga', label: 'R-1/TR · 900 VA (RTM)', tariffRp: '1352.00' },
  { id: 'r1-1300', category: 'rumah', group: 'Rumah Tangga', label: 'R-1/TR · 1.300 VA', tariffRp: '1444.70' },
  { id: 'r1-2200', category: 'rumah', group: 'Rumah Tangga', label: 'R-1/TR · 2.200 VA', tariffRp: '1444.70' },
  { id: 'r2-3500', category: 'rumah', group: 'Rumah Tangga', label: 'R-2/TR · 3.500–5.500 VA', tariffRp: '1699.53' },
  { id: 'r3-6600', category: 'rumah', group: 'Rumah Tangga', label: 'R-3/TR · ≥ 6.600 VA', tariffRp: '1699.53' },
  // Bisnis (B)
  { id: 'b1-450', category: 'bisnis', group: 'Bisnis', label: 'B-1/TR · 450 VA', tariffRp: '254.00' },
  { id: 'b1-900', category: 'bisnis', group: 'Bisnis', label: 'B-1/TR · 451–900 VA', tariffRp: '420.00' },
  { id: 'b1-1300', category: 'bisnis', group: 'Bisnis', label: 'B-1/TR · 901–1.300 VA', tariffRp: '966.00' },
  { id: 'b1-2200', category: 'bisnis', group: 'Bisnis', label: 'B-1/TR · 1.301–5.500 VA', tariffRp: '1100.00' },
  { id: 'b2-6600', category: 'bisnis', group: 'Bisnis', label: 'B-2/TR · 6.600 VA–200 kVA', tariffRp: '1444.70' },
  { id: 'b3-tm', category: 'bisnis', group: 'Bisnis', label: 'B-3/TM · > 200 kVA', tariffRp: '1114.74' },
  // Sosial (S)
  { id: 's1-450', category: 'sosial', group: 'Sosial', label: 'S-1/TR · 450 VA', tariffRp: '325.00' },
  { id: 's1-900', category: 'sosial', group: 'Sosial', label: 'S-1/TR · 900 VA', tariffRp: '455.00' },
  { id: 's1-1300', category: 'sosial', group: 'Sosial', label: 'S-1/TR · 1.300 VA', tariffRp: '708.00' },
  { id: 's1-2200', category: 'sosial', group: 'Sosial', label: 'S-1/TR · 2.200 VA', tariffRp: '760.00' },
  { id: 's1-3500', category: 'sosial', group: 'Sosial', label: 'S-1/TR · 3.500 VA–200 kVA', tariffRp: '900.00' },
  { id: 's2-tm', category: 'sosial', group: 'Sosial', label: 'S-2/TM · > 200 kVA', tariffRp: '925.00' },
  // Pemerintah & Industri (P / I)
  { id: 'p1-tr', category: 'lainnya', group: 'Pemerintah & Industri', label: 'P-1/TR · Kantor Pem 6.600 VA–200 kVA', tariffRp: '1699.53' },
  { id: 'p2-tm', category: 'lainnya', group: 'Pemerintah & Industri', label: 'P-2/TM · Kantor Pem > 200 kVA', tariffRp: '1522.88' },
  { id: 'p3-tr', category: 'lainnya', group: 'Pemerintah & Industri', label: 'P-3/TR · Penerangan Jalan Umum', tariffRp: '1699.53' },
  { id: 'i3-tm', category: 'lainnya', group: 'Pemerintah & Industri', label: 'I-3/TM · Industri > 200 kVA', tariffRp: '1114.74' },
  { id: 'i4-tt', category: 'lainnya', group: 'Pemerintah & Industri', label: 'I-4/TT · Industri ≥ 30.000 kVA', tariffRp: '996.74' },
]

const POWER_PRESETS = [450, 900, 1300, 2200, 3500, 4400, 5500, 6600]
const COOLDOWN_PRESETS = [15, 30, 60]
const REPORT_HOUR_QUICK = [7, 12, 20, 21]

function TariffPresetDropdown({ currentTariffNum, selectedPresetId, disabled, onSelect }) {
  const [isOpen, setIsOpen] = useState(false)
  const [catFilter, setCatFilter] = useState('all')
  const wrapRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return undefined
    const handleOutside = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    const handleEsc = (e) => {
      if (e.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('mousedown', handleOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [isOpen])

  const activePreset =
    PLN_TARIFF_PRESETS.find((p) => p.id === selectedPresetId) ||
    PLN_TARIFF_PRESETS.find((p) => Math.abs(currentTariffNum - Number(p.tariffRp)) < 0.01)

  const filtered =
    catFilter === 'all'
      ? PLN_TARIFF_PRESETS
      : PLN_TARIFF_PRESETS.filter((p) => p.category === catFilter)

  return (
    <div className="settings-tariff-dropdown" ref={wrapRef}>
      <button
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className={`settings-hour-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
      >
        <span className="settings-hour-trigger-left">
          <Zap size={15} className="brand-blue-text" />
          <span className="settings-tariff-trigger-label">
            {activePreset ? activePreset.label : 'Pilih Golongan Tarif PLN (atau isi manual)'}
          </span>
        </span>
        <span className="settings-tariff-trigger-right">
          {activePreset && (
            <span className="settings-tariff-rate-chip num-tabular">
              Rp {formatNum(Number(activePreset.tariffRp), 2)}
            </span>
          )}
          <ChevronDown size={15} className="settings-hour-caret" />
        </span>
      </button>

      {isOpen && (
        <div className="settings-tariff-popover" role="listbox" aria-label="Daftar Tarif PLN">
          <div className="settings-tariff-cats">
            {PLN_TARIFF_CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                type="button"
                className={`settings-tariff-cat-btn ${catFilter === cat.id ? 'active' : ''}`}
                onClick={() => setCatFilter(cat.id)}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <div className="settings-tariff-list">
            {filtered.map((item) => {
              const isSelected = activePreset
                ? activePreset.id === item.id
                : Math.abs(currentTariffNum - Number(item.tariffRp)) < 0.01
              return (
                <button
                  key={item.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`header-panel-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    onSelect(item)
                    setIsOpen(false)
                  }}
                >
                  <span className="header-panel-item-copy">
                    <span className="header-panel-item-title">{item.label}</span>
                    <span className="header-panel-item-sub">{item.group}</span>
                  </span>
                  <span className="header-panel-item-right">
                    <span className="header-panel-item-watt num-tabular">
                      Rp {formatNum(Number(item.tariffRp), 2)}
                    </span>
                    {isSelected && <Check size={15} className="header-panel-check" />}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function formatHourLabel(hour, tzShort = 'WIB') {
  const h = Math.max(0, Math.min(23, Number(hour) || 0))
  return `${String(h).padStart(2, '0')}:00 ${tzShort}`
}

function HourPickerDropdown({ value, tzShort = 'WIB', disabled, onChange }) {
  const [isOpen, setIsOpen] = useState(false)
  const wrapRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return undefined
    const handleOutside = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    const handleEsc = (e) => {
      if (e.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('mousedown', handleOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [isOpen])

  return (
    <div className="settings-hour-dropdown" ref={wrapRef}>
      <button
        id="settings-view-report-hour"
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className={`settings-hour-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
      >
        <span className="settings-hour-trigger-left">
          <Clock size={15} />
          <span className="num-tabular">{formatHourLabel(value, tzShort)}</span>
        </span>
        <ChevronDown size={15} className="settings-hour-caret" />
      </button>

      {isOpen && (
        <div className="settings-hour-popover" role="listbox" aria-label="Pilih jam laporan harian">
          <div className="header-panel-popover-head">
            <span>Pilih Jam Kirim</span>
            <span className="header-panel-count">{tzShort}</span>
          </div>
          <div className="settings-hour-grid">
            {Array.from({ length: 24 }, (_, hour) => {
              const isSelected = Number(value) === hour
              return (
                <button
                  key={hour}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`settings-hour-cell num-tabular ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    onChange(hour)
                    setIsOpen(false)
                  }}
                >
                  {String(hour).padStart(2, '0')}:00
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export function SettingsView({
  mode = 'global',
  settings,
  activeDevice,
  token,
  isAuthenticated = false,
  theme = 'light',
  onToggleTheme,
  onSave,
  onDeviceUpdated,
  onDeviceDeleted,
  onOpenLogin,
  onLogout,
  onReplayTour,
  onOpenTerms,
  appConfig = {},
}) {
  const { prefs, updatePrefs } = useUserPrefs()
  const initialTzRef = useRef(prefs.timezone || 'Asia/Jakarta')

  const rawSen = settings?.tariff_sen ?? settings?.tariff_sen_per_kwh
  const rawTariffRp = settings?.tariff_rp
  const rawPowerLimit = settings?.power_limit_w
  const rawCooldown = settings?.alert_cooldown_min
  const rawExtra = settings?.extra_percent
  const rawReportHour = settings?.report_hour
  const rawReportTz = settings?.report_timezone
  const rawReportEnabled = settings?.report_enabled
  const hasServerSettings = Boolean(settings)

  const syncedSnapshot = useMemo(() => {
    if (!hasServerSettings) {
      return {
        tariff: '1444.70',
        powerLimit: 2200,
        cooldown: 30,
        extraPercent: 0,
        reportHour: 21,
        reportTimezone: initialTzRef.current,
        reportEnabled: true,
      }
    }
    const nextTariff =
      rawTariffRp ??
      (Number.isFinite(Number(rawSen)) ? (Number(rawSen) / 100).toFixed(2) : '1444.70')
    return {
      tariff: String(nextTariff),
      powerLimit: rawPowerLimit ?? 2200,
      cooldown: rawCooldown ?? 30,
      extraPercent: rawExtra ?? 0,
      reportHour: rawReportHour ?? 21,
      reportTimezone: rawReportTz || initialTzRef.current || 'Asia/Jakarta',
      reportEnabled: rawReportEnabled !== false,
    }
  }, [
    hasServerSettings,
    rawTariffRp,
    rawSen,
    rawPowerLimit,
    rawCooldown,
    rawExtra,
    rawReportHour,
    rawReportTz,
    rawReportEnabled,
  ])

  const [tariff, setTariff] = useState(() => syncedSnapshot.tariff)
  const [selectedPresetId, setSelectedPresetId] = useState('')
  const [powerLimit, setPowerLimit] = useState(() => syncedSnapshot.powerLimit)
  const [cooldown, setCooldown] = useState(() => syncedSnapshot.cooldown)
  const [extraPercent, setExtraPercent] = useState(() => syncedSnapshot.extraPercent)
  const [reportHour, setReportHour] = useState(() => syncedSnapshot.reportHour)
  const [reportTimezone, setReportTimezone] = useState(() => syncedSnapshot.reportTimezone)
  const [reportEnabled, setReportEnabled] = useState(() => syncedSnapshot.reportEnabled)
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

  const snapshotKey = `${hasServerSettings ? 'srv' : 'def'}|${syncedSnapshot.tariff}|${syncedSnapshot.powerLimit}|${syncedSnapshot.cooldown}|${syncedSnapshot.extraPercent}|${syncedSnapshot.reportHour}|${syncedSnapshot.reportTimezone}|${syncedSnapshot.reportEnabled}`
  const lastAppliedKeyRef = useRef(snapshotKey)
  const isDirtyRef = useRef(false)
  const forceSyncNextRef = useRef(false)

  useEffect(() => {
    if (!forceSyncNextRef.current) {
      if (lastAppliedKeyRef.current === snapshotKey) return
      if (isDirtyRef.current) return
    }
    forceSyncNextRef.current = false
    lastAppliedKeyRef.current = snapshotKey
    setTariff(syncedSnapshot.tariff)
    setPowerLimit(syncedSnapshot.powerLimit)
    setCooldown(syncedSnapshot.cooldown)
    setExtraPercent(syncedSnapshot.extraPercent)
    setReportHour(syncedSnapshot.reportHour)
    setReportTimezone(syncedSnapshot.reportTimezone)
    setReportEnabled(syncedSnapshot.reportEnabled)
  }, [snapshotKey, syncedSnapshot])

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
  const activeTzShort = getTimeZoneShortLabel(reportTimezone || prefs.timezone)

  const isDirty =
    mode === 'global' &&
    (String(tariff).trim() !== String(syncedSnapshot.tariff).trim() ||
      Number(powerLimit) !== Number(syncedSnapshot.powerLimit) ||
      Number(cooldown) !== Number(syncedSnapshot.cooldown) ||
      Number(extraPercent) !== Number(syncedSnapshot.extraPercent) ||
      Number(reportHour) !== Number(syncedSnapshot.reportHour) ||
      String(reportTimezone) !== String(syncedSnapshot.reportTimezone) ||
      Boolean(reportEnabled) !== Boolean(syncedSnapshot.reportEnabled))
  isDirtyRef.current = isDirty

  const handleResetSystem = () => {
    lastAppliedKeyRef.current = snapshotKey
    isDirtyRef.current = false
    setTariff(syncedSnapshot.tariff)
    setPowerLimit(syncedSnapshot.powerLimit)
    setCooldown(syncedSnapshot.cooldown)
    setExtraPercent(syncedSnapshot.extraPercent)
    setReportHour(syncedSnapshot.reportHour)
    setReportTimezone(syncedSnapshot.reportTimezone)
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
      report_timezone: reportTimezone || 'Asia/Jakarta',
      report_enabled: Boolean(reportEnabled),
    }

    try {
      forceSyncNextRef.current = true
      await onSave(payload)
      isDirtyRef.current = false
      lastAppliedKeyRef.current = ''
      updatePrefs({ timezone: payload.report_timezone })
      setSysErr(false)
      setSysMsg('Pengaturan tarif & peringatan berhasil disimpan.')
      setTimeout(() => setSysMsg(null), 3000)
    } catch (err) {
      forceSyncNextRef.current = false
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
                <div className="room-chips-row cols-3" style={{ marginBottom: 8 }}>
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
                <div className="room-chips-row cols-4" style={{ marginBottom: 8 }}>
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
      <section className="settings-overview-strip" aria-label="Ringkasan tarif dan daya aktif">
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
            {reportEnabled ? formatHourLabel(reportHour, activeTzShort) : 'Nonaktif'}
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
            <span className="settings-preset-label">Golongan Tarif PLN ({PLN_TARIFF_PRESETS.length} Pilihan)</span>
            <TariffPresetDropdown
              currentTariffNum={parsedBaseTariff}
              selectedPresetId={selectedPresetId}
              disabled={!isAuthenticated}
              onSelect={(preset) => {
                setSelectedPresetId(preset.id)
                setTariff(preset.tariffRp)
              }}
            />
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
                  onChange={(e) => {
                    setSelectedPresetId('')
                    setTariff(e.target.value)
                  }}
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
            <div className="room-chips-row cols-4" style={{ marginBottom: 8 }}>
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
            <div className="room-chips-row cols-3" style={{ marginBottom: 8 }}>
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
                <label className="field-label">
                  Zona Waktu Daerah (WIB / WITA / WIT)
                </label>
                <div className="settings-tz-pills">
                  {INDONESIAN_TIMEZONES.map((z) => {
                    const activeZone = (reportTimezone || 'Asia/Jakarta') === z.id
                    return (
                      <button
                        key={z.id}
                        type="button"
                        disabled={!isAuthenticated}
                        className={`settings-tz-pill ${activeZone ? 'selected' : ''}`}
                        onClick={() => setReportTimezone(z.id)}
                      >
                        <Globe size={12} />
                        <strong>{z.short}</strong>
                        <span>{z.offset}</span>
                      </button>
                    )
                  })}
                </div>
                <small className="field-hint" style={{ display: 'block', marginBottom: 10 }}>
                  Waktu dicatat UTC di server dan dikirim serta ditampilkan sesuai zona lokal Anda (
                  {activeTzShort}).
                </small>

                <label className="field-label" htmlFor="settings-view-report-hour">
                  Jam Kirim Rekap Harian ({activeTzShort})
                </label>
                <div className="room-chips-row cols-4" style={{ marginBottom: 8 }}>
                  {REPORT_HOUR_QUICK.map((h) => (
                    <button
                      key={h}
                      type="button"
                      disabled={!isAuthenticated}
                      className={`room-chip is-hour-chip num-tabular ${
                        Number(reportHour) === h ? 'selected' : ''
                      }`}
                      onClick={() => setReportHour(h)}
                    >
                      <span>{String(h).padStart(2, '0')}:00</span>
                      <span className="hour-chip-tz">{activeTzShort}</span>
                    </button>
                  ))}
                </div>
                <HourPickerDropdown
                  value={reportHour}
                  tzShort={activeTzShort}
                  disabled={!isAuthenticated}
                  onChange={(hour) => setReportHour(hour)}
                />
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
                <span className="settings-synced-note">Tarif &amp; aturan sudah tersinkronisasi</span>
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

      {onToggleTheme && (
        <section className="clean-sheet app-menu-group" style={{ marginBottom: 0 }}>
          <button
            type="button"
            role="switch"
            aria-checked={theme === 'dark'}
            className="app-menu-row"
            onClick={onToggleTheme}
          >
            <span className="app-menu-icon is-indigo">
              {theme === 'dark' ? <Moon size={17} /> : <Sun size={17} />}
            </span>
            <span className="app-menu-copy">
              <strong>Mode Gelap</strong>
              <span>Saat ini: {theme === 'dark' ? 'Tema Gelap' : 'Tema Terang'}</span>
            </span>
            <span
              className={`profile-theme-switch ${theme === 'dark' ? 'is-on' : ''}`}
              aria-hidden="true"
            >
              <span className="profile-theme-knob" />
            </span>
          </button>
        </section>
      )}

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
