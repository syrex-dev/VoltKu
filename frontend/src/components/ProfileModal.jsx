import React, { useState, useEffect } from 'react'
import {
  X,
  Crown,
  Gem,
  LogOut,
  ChevronRight,
  SlidersHorizontal,
  Compass,
  ShieldCheck,
  Sun,
  Moon,
  MessageCircle,
  Send,
  Mail,
  Info,
  UserCog,
  KeyRound,
  Eye,
  EyeOff,
  Save,
  Pencil,
  Zap,
  History,
  Sparkles,
  Cpu,
  Clock,
  Activity,
  Lock,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { BrandLogo } from './BrandLogo'
import { formatRp, formatTimeWIB } from '../utils/formatters'

function normalizeWaHref(raw = '') {
  const digits = String(raw || '').replace(/[^0-9]/g, '')
  if (!digits) return ''
  if (digits.startsWith('0')) return `https://wa.me/62${digits.slice(1)}`
  return `https://wa.me/${digits}`
}

export function ProfileModal({
  isOpen,
  onClose,
  currentUser = null,
  token = '',
  onUserUpdated,
  theme = 'light',
  onToggleTheme,
  onLogout,
  onReplayTour,
  onOpenTerms,
  onOpenPlanModal,
  onOpenSettings,
  appConfig = {},
}) {
  const [showAboutDetail, setShowAboutDetail] = useState(false)
  const [showAccountEditor, setShowAccountEditor] = useState(false)
  const [editName, setEditName] = useState(currentUser?.name || '')
  const [savingName, setSavingName] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const [savingPassword, setSavingPassword] = useState(false)
  const [accountMsg, setAccountMsg] = useState(null)
  const [failedAvatarUrl, setFailedAvatarUrl] = useState('')

  useEffect(() => {
    if (isOpen) {
      setEditName(currentUser?.name || '')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setAccountMsg(null)
    }
  }, [isOpen, currentUser?.name])

  if (!isOpen) return null

  const hasLocalPassword = currentUser?.has_local_password !== false

  const handleSaveName = async (e) => {
    e.preventDefault()
    if (!token) return
    const trimmed = (editName || '').trim()
    if (trimmed.length < 2) {
      setAccountMsg({ type: 'error', text: 'Nama lengkap minimal 2 karakter.' })
      return
    }
    setSavingName(true)
    setAccountMsg(null)
    try {
      const updated = await apiRequest(
        '/api/users/me',
        { method: 'PATCH', body: { name: trimmed } },
        token,
        onLogout
      )
      if (onUserUpdated) onUserUpdated(updated)
      setAccountMsg({ type: 'success', text: 'Nama profil berhasil diperbarui.' })
    } catch (err) {
      setAccountMsg({ type: 'error', text: err.message || 'Gagal memperbarui nama.' })
    } finally {
      setSavingName(false)
    }
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()
    if (!token) return
    if (hasLocalPassword && !currentPassword) {
      setAccountMsg({ type: 'error', text: 'Masukkan kata sandi saat ini terlebih dahulu.' })
      return
    }
    if (newPassword.length < 6) {
      setAccountMsg({ type: 'error', text: 'Kata sandi baru minimal 6 karakter.' })
      return
    }
    if (newPassword !== confirmPassword) {
      setAccountMsg({ type: 'error', text: 'Konfirmasi kata sandi baru tidak cocok.' })
      return
    }
    setSavingPassword(true)
    setAccountMsg(null)
    try {
      const res = await apiRequest(
        '/api/users/change-password',
        {
          method: 'POST',
          body: {
            current_password: hasLocalPassword ? currentPassword : null,
            new_password: newPassword,
          },
        },
        token,
        onLogout
      )
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      if (onUserUpdated && currentUser) {
        onUserUpdated({
          ...currentUser,
          has_local_password: true,
          auth_provider: currentUser.auth_provider === 'google' ? 'both' : currentUser.auth_provider,
        })
      }
      setAccountMsg({
        type: 'success',
        text: res?.message || 'Kata sandi berhasil diperbarui.',
      })
    } catch (err) {
      setAccountMsg({ type: 'error', text: err.message || 'Gagal mengubah kata sandi.' })
    } finally {
      setSavingPassword(false)
    }
  }

  const appName = appConfig.app_name || 'VoltKu'
  const appTagline = appConfig.app_tagline || 'Pantau listrik rumah lebih tenang dan akurat'
  const termsVersion = appConfig.terms_version || '2026-11-v1'
  const waHref = normalizeWaHref(appConfig.support_whatsapp || '')
  const tgHandle = (appConfig.support_telegram || '').replace(/^@+/, '').trim()
  const supportEmail = (appConfig.support_email || '').trim()
  const showOnboardingRow = Boolean(onReplayTour && appConfig.onboarding_enabled !== false)

  const displayName = currentUser?.name || `Pengguna ${appName}`
  const initialLetter = displayName.trim().charAt(0).toUpperCase() || 'V'
  const hasAvatar = Boolean(currentUser?.avatar_url && failedAvatarUrl !== currentUser.avatar_url)
  const isGoogleAuth =
    currentUser?.auth_provider === 'google' || currentUser?.auth_provider === 'both'

  const plan = currentUser?.plan
  const proCfg = appConfig.plans?.pro || {
    name: 'VoltKu Pro',
    price_monthly_rp: 30000,
    max_devices: 10,
    history_days: 90,
  }
  const showPlanCard = Boolean(plan && plan.freemium_enabled !== false)
  const isPro = Boolean(plan?.is_pro)
  const usedDevices = plan?.usage?.device_count ?? 0
  const maxDevices = plan?.limits?.max_devices ?? 1
  const historyDays = plan?.limits?.history_days ?? (isPro ? proCfg.history_days : 3)
  const quotaPct =
    maxDevices > 0 ? Math.min(100, Math.round((usedDevices / maxDevices) * 100)) : 25
  const proMaxText =
    proCfg.max_devices < 0 ? 'panel tanpa batas' : `hingga ${proCfg.max_devices} panel`

  return (
    <div className="modal-overlay pwa-guide-overlay profile-modal-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern profile-modal-dialog profile-ref-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Profil Akun"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky Top App Header */}
        <div className="profile-sticky-topbar">
          <div className="profile-ref-topbar">
            <span aria-hidden="true" />
            <h2 className="profile-ref-page-title">Profil Saya</h2>
            <div className="profile-ref-topbar-actions">
              <button
                type="button"
                className="profile-ref-icon-btn"
                onClick={onClose}
                aria-label="Tutup Profil"
              >
                <X size={18} />
              </button>
            </div>
          </div>
        </div>

        {/* Scrollable Content Region */}
        <div className="profile-scroll-region">
          {/* Atmospheric Identity Hero */}
          <div className="profile-ref-header-zone">
            <div className="profile-ref-identity">
              <div className="profile-ref-identity-left">
                <div className="profile-avatar-frame">
                  {hasAvatar ? (
                    <img
                      src={currentUser.avatar_url}
                      alt={displayName}
                      className="profile-ref-avatar"
                      referrerPolicy="no-referrer"
                      onError={() => setFailedAvatarUrl(currentUser.avatar_url || '')}
                    />
                  ) : (
                    <div className="profile-ref-avatar profile-avatar-initial">{initialLetter}</div>
                  )}
                  <span
                    className={`profile-provider-badge ${isGoogleAuth ? 'is-google' : 'is-mail'}`}
                    title={isGoogleAuth ? 'Masuk via Google' : 'Masuk via Email'}
                    aria-hidden="true"
                  >
                    {isGoogleAuth ? 'G' : <Mail size={10} strokeWidth={2.5} />}
                  </span>
                </div>

                <div className="profile-ref-identity-copy">
                  <div className="profile-name-tier-row">
                    <span className="profile-ref-name">{displayName}</span>
                    {showPlanCard && (
                      <span className={`profile-tier-chip ${isPro ? 'is-pro' : 'is-free'}`}>
                        {isPro ? <Crown size={11} /> : <Sparkles size={11} />}
                        <span>{isPro ? 'Pro' : 'Free'}</span>
                      </span>
                    )}
                  </div>
                  <div className="profile-ref-subline">
                    <span>{currentUser?.email || 'Akun Terdaftar'}</span>
                    <span className="profile-ref-dot">·</span>
                    <span>{isGoogleAuth ? 'Google' : 'Email'}</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                className={`profile-edit-pill-btn ${showAccountEditor ? 'active' : ''}`}
                onClick={() => {
                  setShowAccountEditor((prev) => !prev)
                  setAccountMsg(null)
                }}
                aria-label="Edit nama atau sandi akun"
                title="Ubah Profil"
              >
                <Pencil size={13} />
                <span>Ubah</span>
              </button>
            </div>

            {/* Unified VIP Membership Card (replaces duplicate upgrade banners) */}
            {showPlanCard && (
              <div className={`profile-vip-card ${isPro ? 'is-pro' : ''}`}>
                <div className="profile-vip-top">
                  <div className={`profile-vip-icon ${isPro ? 'is-pro' : ''}`}>
                    {isPro ? <Crown size={19} /> : <Gem size={19} />}
                  </div>
                  <div className="profile-vip-copy">
                    <div className="profile-vip-title">
                      {isPro ? `${plan.plan_name} Aktif` : `Tingkatkan ke ${proCfg.name}`}
                    </div>
                    <div className="profile-vip-sub">
                      {isPro
                        ? plan.expires_at
                          ? `Berlaku hingga ${formatTimeWIB(plan.expires_at)}`
                          : 'Keanggotaan Pro aktif permanen'
                        : `${proMaxText} & riwayat ${proCfg.history_days} hari · Mulai ${formatRp(proCfg.price_monthly_rp)}/bln`}
                    </div>
                  </div>
                  {onOpenPlanModal && (
                    <button
                      type="button"
                      className={`profile-vip-cta ${isPro ? 'is-pro' : ''}`}
                      onClick={() => {
                        onClose()
                        onOpenPlanModal('')
                      }}
                    >
                      {isPro
                        ? 'Detail'
                        : plan.pending_upgrade
                          ? 'Cek Status'
                          : 'Upgrade'}
                    </button>
                  )}
                </div>

                <div className="profile-vip-stats num-tabular">
                  <div className="profile-vip-stat-chip">
                    <Zap size={12} />
                    <span>
                      Panel:{' '}
                      <strong>
                        {usedDevices}/{maxDevices < 0 ? '∞' : maxDevices}
                      </strong>
                    </span>
                  </div>
                  <div className="profile-vip-stat-chip">
                    <History size={12} />
                    <span>
                      Riwayat: <strong>{historyDays} hari</strong>
                    </span>
                  </div>
                  {plan.pending_upgrade && !isPro && (
                    <span className="profile-vip-pending-tag">
                      {plan.pending_upgrade.status === 'awaiting_payment'
                        ? 'Menunggu bayar'
                        : 'Verifikasi admin'}
                    </span>
                  )}
                </div>

                {maxDevices > 0 && (
                  <div className="profile-vip-track" aria-hidden="true">
                    <div
                      className={`profile-vip-fill ${isPro ? 'is-pro' : ''}`}
                      style={{ width: `${Math.max(8, quotaPct)}%` }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Grouped Clean Cards Body */}
          <div className="profile-ref-body">
            {/* Group 1: Akun & Keamanan */}
            <section className="profile-ref-card-group">
              <button
                type="button"
                className="profile-ref-row"
                onClick={() => {
                  setShowAccountEditor((prev) => !prev)
                  setAccountMsg(null)
                }}
              >
                <span className="profile-ref-row-icon is-blue">
                  <UserCog size={17} />
                </span>
                <span className="profile-ref-row-text">
                  <span className="profile-ref-row-title">Kelola Akun &amp; Kata Sandi</span>
                  <span className="profile-ref-row-sub">
                    Ubah nama tampilan atau atur sandi masuk
                  </span>
                </span>
                <ChevronRight
                  size={16}
                  className={`profile-ref-chevron ${showAccountEditor ? 'rotated' : ''}`}
                />
              </button>

              {showAccountEditor && (
                <div className="profile-account-panel">
                  {accountMsg && (
                    <div
                      className={`feedback-msg ${accountMsg.type === 'error' ? 'error' : 'success'}`}
                      style={{ marginBottom: 10 }}
                    >
                      {accountMsg.text}
                    </div>
                  )}

                  <form onSubmit={handleSaveName} className="profile-account-subcard">
                    <label className="profile-subcard-label" htmlFor="prof-edit-name">
                      Nama Tampilan
                    </label>
                    <div className="profile-account-inline-row">
                      <input
                        id="prof-edit-name"
                        type="text"
                        className="modern-input"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        minLength={2}
                        maxLength={100}
                        required
                      />
                      <button
                        type="submit"
                        className="btn btn-primary btn-compact"
                        disabled={savingName}
                      >
                        <Save size={14} />
                        <span>{savingName ? 'Menyimpan...' : 'Simpan'}</span>
                      </button>
                    </div>
                  </form>

                  <form onSubmit={handleChangePassword} className="profile-account-subcard">
                    <div className="profile-account-sec-head">
                      <KeyRound size={13} />
                      <span>
                        {hasLocalPassword ? 'Ganti Kata Sandi' : 'Tambah Kata Sandi Lokal'}
                      </span>
                      <button
                        type="button"
                        className="profile-account-eye-btn"
                        onClick={() => setShowPasswords((p) => !p)}
                        aria-label={showPasswords ? 'Sembunyikan sandi' : 'Tampilkan sandi'}
                      >
                        {showPasswords ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                    {!hasLocalPassword && (
                      <div className="profile-subcard-hint">
                        Opsional: tambahkan sandi agar Anda tetap bisa masuk dengan email jika tidak
                        menggunakan Google.
                      </div>
                    )}

                    {hasLocalPassword && (
                      <input
                        type={showPasswords ? 'text' : 'password'}
                        className="modern-input"
                        placeholder="Kata sandi saat ini"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        autoComplete="current-password"
                      />
                    )}
                    <input
                      type={showPasswords ? 'text' : 'password'}
                      className="modern-input"
                      placeholder="Kata sandi baru (min. 6 karakter)"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      minLength={6}
                      autoComplete="new-password"
                    />
                    <input
                      type={showPasswords ? 'text' : 'password'}
                      className="modern-input"
                      placeholder="Ulangi kata sandi baru"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      minLength={6}
                      autoComplete="new-password"
                    />
                    <button
                      type="submit"
                      className="btn btn-secondary btn-compact profile-save-pw-btn"
                      disabled={savingPassword}
                    >
                      <KeyRound size={14} />
                      <span>
                        {savingPassword
                          ? 'Memperbarui...'
                          : hasLocalPassword
                            ? 'Perbarui Kata Sandi'
                            : 'Simpan Kata Sandi'}
                      </span>
                    </button>
                  </form>
                </div>
              )}
            </section>

            {/* Group 2: Preferensi & Panduan */}
            <section className="profile-ref-card-group">
              {onOpenSettings && (
                <button
                  type="button"
                  className="profile-ref-row"
                  onClick={() => {
                    onClose()
                    onOpenSettings()
                  }}
                >
                  <span className="profile-ref-row-icon is-amber">
                    <SlidersHorizontal size={17} />
                  </span>
                  <span className="profile-ref-row-text">
                    <span className="profile-ref-row-title">Tarif Listrik &amp; Peringatan</span>
                  </span>
                  <span className="profile-ref-badge is-blue">PLN</span>
                  <ChevronRight size={16} className="profile-ref-chevron" />
                </button>
              )}

              {onToggleTheme && (
                <button
                  type="button"
                  role="switch"
                  aria-checked={theme === 'dark'}
                  className="profile-ref-row"
                  onClick={onToggleTheme}
                >
                  <span className="profile-ref-row-icon is-indigo">
                    {theme === 'dark' ? <Moon size={17} /> : <Sun size={17} />}
                  </span>
                  <span className="profile-ref-row-text">
                    <span className="profile-ref-row-title">Mode Gelap</span>
                    <span className="profile-ref-row-sub">
                      Saat ini: {theme === 'dark' ? 'Tema Gelap' : 'Tema Terang'}
                    </span>
                  </span>
                  <span
                    className={`profile-theme-switch ${theme === 'dark' ? 'is-on' : ''}`}
                    aria-hidden="true"
                  >
                    <span className="profile-theme-knob" />
                  </span>
                </button>
              )}

              {showOnboardingRow && (
                <button
                  type="button"
                  className="profile-ref-row"
                  onClick={() => {
                    onClose()
                    onReplayTour()
                  }}
                >
                  <span className="profile-ref-row-icon is-emerald">
                    <Compass size={17} />
                  </span>
                  <span className="profile-ref-row-text">
                    <span className="profile-ref-row-title">Panduan Awal Aplikasi</span>
                  </span>
                  <ChevronRight size={16} className="profile-ref-chevron" />
                </button>
              )}
            </section>

            {/* Group 3: Dukungan & Informasi */}
            <section className="profile-ref-card-group">
              {waHref && (
                <a href={waHref} target="_blank" rel="noreferrer" className="profile-ref-row">
                  <span className="profile-ref-row-icon is-emerald">
                    <MessageCircle size={17} />
                  </span>
                  <span className="profile-ref-row-text">
                    <span className="profile-ref-row-title">Bantuan WhatsApp</span>
                  </span>
                  <span className="profile-ref-badge is-emerald">Chat</span>
                  <ChevronRight size={16} className="profile-ref-chevron" />
                </a>
              )}

              {tgHandle && (
                <a
                  href={`https://t.me/${tgHandle}`}
                  target="_blank"
                  rel="noreferrer"
                  className="profile-ref-row"
                >
                  <span className="profile-ref-row-icon is-sky">
                    <Send size={17} />
                  </span>
                  <span className="profile-ref-row-text">
                    <span className="profile-ref-row-title">Bantuan Telegram</span>
                  </span>
                  <span className="profile-ref-badge is-neutral">@{tgHandle}</span>
                  <ChevronRight size={16} className="profile-ref-chevron" />
                </a>
              )}

              {supportEmail && (
                <a href={`mailto:${supportEmail}`} className="profile-ref-row">
                  <span className="profile-ref-row-icon is-blue">
                    <Mail size={17} />
                  </span>
                  <span className="profile-ref-row-text">
                    <span className="profile-ref-row-title">Email Dukungan</span>
                  </span>
                  <ChevronRight size={16} className="profile-ref-chevron" />
                </a>
              )}

              {onOpenTerms && (
                <button
                  type="button"
                  className="profile-ref-row"
                  onClick={() => onOpenTerms('terms')}
                >
                  <span className="profile-ref-row-icon is-teal">
                    <ShieldCheck size={17} />
                  </span>
                  <span className="profile-ref-row-text">
                    <span className="profile-ref-row-title">Syarat &amp; Privasi</span>
                  </span>
                  <span className="profile-ref-badge is-neutral">{termsVersion}</span>
                  <ChevronRight size={16} className="profile-ref-chevron" />
                </button>
              )}

              <button
                type="button"
                className="profile-ref-row"
                onClick={() => setShowAboutDetail((prev) => !prev)}
              >
                <span className="profile-ref-row-icon is-slate">
                  <Info size={17} />
                </span>
                <span className="profile-ref-row-text">
                  <span className="profile-ref-row-title">Tentang {appName}</span>
                </span>
                <ChevronRight
                  size={16}
                  className={`profile-ref-chevron ${showAboutDetail ? 'rotated' : ''}`}
                />
              </button>
              {showAboutDetail && (
                <div className="profile-about-card">
                  <div className="profile-about-hero">
                    <div className="profile-about-brand">
                      <BrandLogo
                        theme={theme}
                        displayMode="logo_only"
                        appName={appName}
                        variant="compact"
                      />
                    </div>
                    <p className="profile-about-tagline">{appTagline}</p>
                  </div>

                  <div className="profile-about-features">
                    <div className="profile-about-feat-row">
                      <span className="profile-about-feat-ico is-blue">
                        <Activity size={14} />
                      </span>
                      <div>
                        <strong>Pantau Daya Real-Time</strong>
                        <span>Tegangan, arus, watt, PF, frekuensi &amp; beban MCB secara langsung.</span>
                      </div>
                    </div>
                    <div className="profile-about-feat-row">
                      <span className="profile-about-feat-ico is-amber">
                        <Zap size={14} />
                      </span>
                      <div>
                        <strong>Hitung Tarif &amp; Proyeksi PLN</strong>
                        <span>Estimasi biaya harian, grafik historis &amp; proyeksi akhir bulan.</span>
                      </div>
                    </div>
                    <div className="profile-about-feat-row">
                      <span className="profile-about-feat-ico is-emerald">
                        <Sparkles size={14} />
                      </span>
                      <div>
                        <strong>Asisten AI &amp; Deteksi Anomali</strong>
                        <span>Peringatan dini lonjakan daya, tegangan tak stabil &amp; analisa AI.</span>
                      </div>
                    </div>
                    <div className="profile-about-feat-row">
                      <span className="profile-about-feat-ico is-indigo">
                        <Lock size={14} />
                      </span>
                      <div>
                        <strong>Koneksi Terenkripsi</strong>
                        <span>Komunikasi HTTPS, JWT &amp; MQTT TLS dengan akses terisolasi per akun.</span>
                      </div>
                    </div>
                  </div>

                  <div className="profile-about-specs">
                    <div className="profile-about-spec-item">
                      <Cpu size={13} />
                      <span>Hardware: Smart Panel / PZEM-004T</span>
                    </div>
                    <div className="profile-about-spec-item">
                      <Clock size={13} />
                      <span>Waktu Sistem: Asia/Jakarta (WIB)</span>
                    </div>
                  </div>

                  <div className="profile-about-footer">
                    <span className="profile-about-pkg num-tabular">com.voltku.energy</span>
                    {onOpenTerms && (
                      <div className="profile-about-legal-links">
                        <button type="button" onClick={() => onOpenTerms('terms')}>
                          Syarat
                        </button>
                        <span>·</span>
                        <button type="button" onClick={() => onOpenTerms('privacy')}>
                          Privasi
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </section>

            {onLogout && (
              <button
                type="button"
                className="profile-logout-btn"
                onClick={() => {
                  onClose()
                  onLogout()
                }}
              >
                <LogOut size={15} />
                <span>Keluar dari Akun</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
