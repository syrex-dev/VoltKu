import React, { useState, useEffect } from 'react'
import {
  Save,
  Trash2,
  Wifi,
  AlertTriangle,
  LogOut,
  LogIn,
  Lock,
  ChevronRight,
  Compass,
  ShieldCheck,
  Sun,
  Moon,
  Info,
  User,
  MessageCircle,
  Send,
  Mail,
} from 'lucide-react'
import { apiRequest } from '../api/client'

const PRESET_ROOMS = ['Panel Utama', 'Ruang Tamu', 'Kamar Tidur', 'Dapur', 'Lantai 2', 'Warung']

function normalizeWaHref(raw = '') {
  const digits = String(raw || '').replace(/[^0-9]/g, '')
  if (!digits) return ''
  if (digits.startsWith('0')) return `https://wa.me/62${digits.slice(1)}`
  return `https://wa.me/${digits}`
}

export function SettingsView({
  mode = 'global',
  settings,
  activeDevice,
  token,
  isAuthenticated = false,
  currentUser = null,
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
  const [tariff, setTariff] = useState('')
  const [powerLimit, setPowerLimit] = useState(2200)
  const [cooldown, setCooldown] = useState(30)
  const [extraPercent, setExtraPercent] = useState(0)
  const [reportHour, setReportHour] = useState(7)
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

  useEffect(() => {
    if (settings) {
      const rawSen = settings.tariff_sen ?? settings.tariff_sen_per_kwh
      const nextTariff =
        settings.tariff_rp ??
        (Number.isFinite(Number(rawSen)) ? (Number(rawSen) / 100).toFixed(2) : '1444.70')
      setTariff(String(nextTariff))
      setPowerLimit(settings.power_limit_w ?? 2200)
      setCooldown(settings.alert_cooldown_min ?? 30)
      setExtraPercent(settings.extra_percent ?? 0)
      setReportHour(settings.report_hour ?? 21)
    }
  }, [settings])

  useEffect(() => {
    if (activeDevice) {
      setDevName(activeDevice.name || activeDevice.id)
      setDevLocation(activeDevice.location || '')
      setDevMcb(activeDevice.mcb_watt || 2200)
      setConfirmDelete(false)
      setDevMsg(null)
    }
  }, [activeDevice])

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
      tariff_rp: tariff.trim(),
      power_limit_w: parseInt(powerLimit, 10),
      alert_cooldown_min: parseInt(cooldown, 10),
      extra_percent: parseFloat(extraPercent),
      report_hour: parseInt(reportHour, 10),
    }

    try {
      await onSave(payload)
      setSysErr(false)
      setSysMsg('Pengaturan tarif & sistem disimpan.')
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
            <h2 className="settings-panel-title">Pengaturan Perangkat</h2>
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

  const appName = appConfig.app_name || 'VoltKu'
  const appTagline = appConfig.app_tagline || 'Monitor Listrik Pintar'
  const termsVersion = appConfig.terms_version || '2026-11-v1'
  const showOnboardingRow = Boolean(onReplayTour && appConfig.onboarding_enabled !== false)
  const waHref = normalizeWaHref(appConfig.support_whatsapp)
  const tgHandle = (appConfig.support_telegram || '').replace(/^@/, '').trim()
  const supportEmail = (appConfig.support_email || '').trim()

  return (
    <div className="settings-single-wrap settings-stack-col">
      <section className="clean-sheet profile-hero-card">
        <div className="profile-hero-left">
          {currentUser?.avatar_url ? (
            <img
              src={currentUser.avatar_url}
              alt={currentUser.name || 'Profil'}
              className="profile-avatar-img"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="profile-avatar-fallback">
              <User size={24} />
            </div>
          )}
          <div className="profile-hero-copy">
            <h2 className="profile-hero-name">
              {isAuthenticated ? currentUser?.name || `Pengguna ${appName}` : 'Mode Tamu'}
            </h2>
            <p className="profile-hero-sub">
              {isAuthenticated
                ? `${currentUser?.email || ''}${
                    currentUser?.auth_provider === 'google' ||
                    currentUser?.auth_provider === 'both'
                      ? ' · Akun Google'
                      : ''
                  }`
                : 'Masuk untuk mengelola panel pribadi Anda'}
            </p>
          </div>
        </div>

        {!isAuthenticated && onOpenLogin ? (
          <button
            type="button"
            className="btn btn-primary btn-compact"
            onClick={onOpenLogin}
          >
            <span>Masuk</span>
            <ChevronRight size={15} />
          </button>
        ) : (
          onLogout && (
            <button
              type="button"
              className="btn btn-danger-ghost btn-compact"
              onClick={onLogout}
            >
              <LogOut size={14} />
              <span>Keluar</span>
            </button>
          )
        )}
      </section>

      {/* Menu Aplikasi & Dukungan */}
      <section className="clean-sheet app-menu-group">
        {showOnboardingRow && (
          <button type="button" className="app-menu-row" onClick={onReplayTour}>
            <span className="app-menu-icon is-blue">
              <Compass size={17} />
            </span>
            <span className="app-menu-copy">
              <strong>Panduan Awal Aplikasi</strong>
              <span>Putar ulang pengenalan fitur &amp; cara tambah panel</span>
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
              <span>
                Versi {termsVersion}
                {currentUser?.terms_version_accepted
                  ? ` · Disetujui (${currentUser.terms_version_accepted})`
                  : ''}
              </span>
            </span>
            <ChevronRight size={17} className="app-menu-chevron" />
          </button>
        )}

        {onToggleTheme && (
          <button type="button" className="app-menu-row" onClick={onToggleTheme}>
            <span className="app-menu-icon is-slate">
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </span>
            <span className="app-menu-copy">
              <strong>Tema Tampilan Aplikasi</strong>
              <span>{theme === 'dark' ? 'Mode Gelap aktif' : 'Mode Terang aktif'}</span>
            </span>
            <ChevronRight size={17} className="app-menu-chevron" />
          </button>
        )}

        {waHref && (
          <a href={waHref} target="_blank" rel="noreferrer" className="app-menu-row">
            <span className="app-menu-icon is-emerald">
              <MessageCircle size={17} />
            </span>
            <span className="app-menu-copy">
              <strong>Bantuan WhatsApp</strong>
              <span>Hubungi dukungan teknis {appName}</span>
            </span>
            <ChevronRight size={17} className="app-menu-chevron" />
          </a>
        )}

        {tgHandle && (
          <a
            href={`https://t.me/${tgHandle}`}
            target="_blank"
            rel="noreferrer"
            className="app-menu-row"
          >
            <span className="app-menu-icon is-blue">
              <Send size={17} />
            </span>
            <span className="app-menu-copy">
              <strong>Bantuan Telegram</strong>
              <span>@{tgHandle}</span>
            </span>
            <ChevronRight size={17} className="app-menu-chevron" />
          </a>
        )}

        {supportEmail && (
          <a href={`mailto:${supportEmail}`} className="app-menu-row">
            <span className="app-menu-icon is-amber">
              <Mail size={17} />
            </span>
            <span className="app-menu-copy">
              <strong>Email Dukungan</strong>
              <span>{supportEmail}</span>
            </span>
            <ChevronRight size={17} className="app-menu-chevron" />
          </a>
        )}

        <div className="app-menu-row is-static">
          <span className="app-menu-icon is-slate">
            <Info size={17} />
          </span>
          <span className="app-menu-copy">
            <strong>Tentang {appName}</strong>
            <span>{appTagline}</span>
          </span>
        </div>
      </section>

      <section className="clean-sheet settings-panel-card">
        <div className="settings-panel-header">
          <h2 className="settings-panel-title">Tarif Listrik &amp; Peringatan</h2>
        </div>

        {!isAuthenticated && (
          <div className="settings-lock-banner">
            <div className="settings-lock-copy">
              <Lock size={15} />
              <span>Mode Guest. Masuk untuk mengubah tarif atau aturan sistem.</span>
            </div>
            {onOpenLogin && (
              <button type="button" className="btn btn-primary btn-compact" onClick={onOpenLogin}>
                <LogIn size={14} />
                <span>Masuk</span>
              </button>
            )}
          </div>
        )}

        <form onSubmit={handleSubmitSystem}>
          {sysMsg && (
            <div className={`feedback-msg ${sysErr ? 'error' : 'success'}`}>{sysMsg}</div>
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
                  disabled={!isAuthenticated}
                  required
                />
                <span className="input-affix-suffix">/kWh</span>
              </div>
              <small className="field-hint">Maksimal 2 angka di belakang koma</small>
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="settings-view-power-limit">
                Batas Daya Peringatan
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
                  disabled={!isAuthenticated}
                  required
                />
                <span className="input-affix-suffix">Watt</span>
              </div>
            </div>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="settings-view-cooldown">
                Jeda Peringatan Ulang
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
                  disabled={!isAuthenticated}
                  required
                />
                <span className="input-affix-suffix">Menit</span>
              </div>
            </div>

            <div className="form-field-group">
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
            </div>
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="settings-view-report-hour">
              Jam Rekap Laporan Harian
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
                disabled={!isAuthenticated}
                required
              />
              <span className="input-affix-suffix">:00 WIB</span>
            </div>
          </div>

          {isAuthenticated && (
            <div className="settings-save-footer">
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
        </form>
      </section>
    </div>
  )
}
