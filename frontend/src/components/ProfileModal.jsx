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
} from 'lucide-react'
import { apiRequest } from '../api/client'
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
        {/* Ambient Header Gradient Wash */}
        <div className="profile-ref-header-zone">
          <div className="profile-ref-topbar">
            <span aria-hidden="true" />
            <h2 className="profile-ref-page-title">Profil</h2>
            <div className="profile-ref-topbar-actions">
              <button
                type="button"
                className="profile-ref-icon-btn"
                onClick={onClose}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* User Identity Header Row */}
          <div className="profile-ref-identity">
            <div className="profile-ref-identity-left">
              {currentUser?.avatar_url ? (
                <img
                  src={currentUser.avatar_url}
                  alt={displayName}
                  className="profile-ref-avatar"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="profile-ref-avatar profile-avatar-initial">{initialLetter}</div>
              )}
              <div className="profile-ref-identity-copy">
                <div className="profile-ref-name">{displayName}</div>
                <div className="profile-ref-subline">
                  <span>{currentUser?.email || 'Akun Terdaftar'}</span>
                  <span className="profile-ref-dot">·</span>
                  <span>{isGoogleAuth ? 'Google' : 'Email'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Membership Card */}
          {showPlanCard && (
            <div className={`profile-ref-member-card ${isPro ? 'is-pro' : ''}`}>
              <div className="profile-ref-member-main">
                <div className={`profile-ref-gem-badge ${isPro ? 'is-pro' : ''}`}>
                  {isPro ? <Crown size={19} /> : <Gem size={19} />}
                </div>
                <div className="profile-ref-member-copy">
                  <div className="profile-ref-member-title">
                    {isPro ? `${plan.plan_name} Aktif` : `Gabung ${proCfg.name}`}
                  </div>
                  <div className="profile-ref-member-sub">
                    {isPro
                      ? `Kuota ${usedDevices}/${maxDevices < 0 ? '∞' : maxDevices} panel · Riwayat ${plan.limits?.history_days ?? 90} hari`
                      : `Buka ${proMaxText} & riwayat ${proCfg.history_days} hari`}
                  </div>
                </div>
                {onOpenPlanModal && (
                  <button
                    type="button"
                    className={`profile-ref-member-cta ${isPro ? 'is-pro' : ''}`}
                    onClick={() => {
                      onClose()
                      onOpenPlanModal('')
                    }}
                  >
                    {isPro ? 'Detail' : 'Upgrade'}
                  </button>
                )}
              </div>

              <div className="profile-ref-quota-wrap">
                <div className="profile-ref-quota-meta num-tabular">
                  <span>
                    Panel terpakai{' '}
                    <strong>
                      {usedDevices}/{maxDevices < 0 ? 'Tak terbatas' : maxDevices}
                    </strong>
                  </span>
                  <span>
                    {plan.pending_upgrade && !isPro
                      ? plan.pending_upgrade.status === 'awaiting_payment'
                        ? 'Tagihan menunggu bayar'
                        : 'Menunggu verifikasi admin'
                      : `Riwayat ${plan.limits?.history_days ?? 3} hari`}
                  </span>
                </div>
                {maxDevices > 0 && (
                  <div className="profile-ref-quota-bar" aria-hidden="true">
                    <div
                      className={`profile-ref-quota-fill ${isPro ? 'is-pro' : ''}`}
                      style={{ width: `${Math.max(8, quotaPct)}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Warm Gold Promo Strip (or Active Pro Validity Strip) */}
          {showPlanCard && onOpenPlanModal && (
            <button
              type="button"
              className={`profile-ref-promo-strip ${isPro ? 'is-pro' : ''}`}
              onClick={() => {
                onClose()
                onOpenPlanModal('')
              }}
            >
              <span className="profile-ref-promo-left">
                <Crown size={14} />
                <span>
                  {isPro
                    ? plan.expires_at
                      ? `VoltKu Pro aktif hingga ${formatTimeWIB(plan.expires_at)}`
                      : 'VoltKu Pro aktif permanen'
                    : `Coba ${proCfg.name} · Mulai ${formatRp(proCfg.price_monthly_rp)}/bulan`}
                </span>
              </span>
              <ChevronRight size={15} />
            </button>
          )}
        </div>

        {/* Grouped Menu Cards */}
        <div className="profile-ref-body">
          <section className="profile-ref-card-group">
            <button
              type="button"
              className="profile-ref-row"
              onClick={() => {
                setShowAccountEditor((prev) => !prev)
                setAccountMsg(null)
              }}
            >
              <span className="profile-ref-row-icon">
                <UserCog size={18} />
              </span>
              <span className="profile-ref-row-title">Kelola Akun &amp; Kata Sandi</span>
              <ChevronRight
                size={16}
                className={`profile-ref-chevron ${showAccountEditor ? 'rotated' : ''}`}
              />
            </button>

            {showAccountEditor && (
              <div className="profile-account-panel">
                {accountMsg && (
                  <div className={`feedback-msg ${accountMsg.type === 'error' ? 'error' : 'success'}`}>
                    {accountMsg.text}
                  </div>
                )}

                <form onSubmit={handleSaveName} className="profile-account-form">
                  <label className="field-label" htmlFor="prof-edit-name">
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

                <form onSubmit={handleChangePassword} className="profile-account-form" style={{ marginTop: 12 }}>
                  <div className="profile-account-sec-head">
                    <KeyRound size={13} />
                    <span>{hasLocalPassword ? 'Ganti Kata Sandi' : 'Buat Kata Sandi Lokal'}</span>
                    <button
                      type="button"
                      className="profile-account-eye-btn"
                      onClick={() => setShowPasswords((p) => !p)}
                      aria-label={showPasswords ? 'Sembunyikan sandi' : 'Tampilkan sandi'}
                    >
                      {showPasswords ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>

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
                    className="btn btn-secondary btn-compact"
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

            {onOpenSettings && (
              <button
                type="button"
                className="profile-ref-row"
                onClick={() => {
                  onClose()
                  onOpenSettings()
                }}
              >
                <span className="profile-ref-row-icon">
                  <SlidersHorizontal size={18} />
                </span>
                <span className="profile-ref-row-title">Tarif Listrik &amp; Peringatan</span>
                <span className="profile-ref-badge is-blue">PLN</span>
                <ChevronRight size={16} className="profile-ref-chevron" />
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
                <span className="profile-ref-row-icon">
                  <Compass size={18} />
                </span>
                <span className="profile-ref-row-title">Panduan Awal Aplikasi</span>
                <ChevronRight size={16} className="profile-ref-chevron" />
              </button>
            )}

            {onToggleTheme && (
              <button type="button" className="profile-ref-row" onClick={onToggleTheme}>
                <span className="profile-ref-row-icon">
                  {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                </span>
                <span className="profile-ref-row-title">Tema Tampilan</span>
                <span className="profile-ref-badge is-slate">
                  {theme === 'dark' ? 'Gelap' : 'Terang'}
                </span>
                <ChevronRight size={16} className="profile-ref-chevron" />
              </button>
            )}
          </section>

          <section className="profile-ref-card-group">
            {waHref && (
              <a href={waHref} target="_blank" rel="noreferrer" className="profile-ref-row">
                <span className="profile-ref-row-icon">
                  <MessageCircle size={18} />
                </span>
                <span className="profile-ref-row-title">Bantuan WhatsApp</span>
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
                <span className="profile-ref-row-icon">
                  <Send size={18} />
                </span>
                <span className="profile-ref-row-title">Bantuan Telegram</span>
                <span className="profile-ref-badge is-neutral">@{tgHandle}</span>
                <ChevronRight size={16} className="profile-ref-chevron" />
              </a>
            )}

            {supportEmail && (
              <a href={`mailto:${supportEmail}`} className="profile-ref-row">
                <span className="profile-ref-row-icon">
                  <Mail size={18} />
                </span>
                <span className="profile-ref-row-title">Email Dukungan</span>
                <ChevronRight size={16} className="profile-ref-chevron" />
              </a>
            )}

            {onOpenTerms && (
              <button
                type="button"
                className="profile-ref-row"
                onClick={() => onOpenTerms('terms')}
              >
                <span className="profile-ref-row-icon">
                  <ShieldCheck size={18} />
                </span>
                <span className="profile-ref-row-title">Syarat &amp; Privasi</span>
                <span className="profile-ref-badge is-neutral">{termsVersion}</span>
                <ChevronRight size={16} className="profile-ref-chevron" />
              </button>
            )}

            <button
              type="button"
              className="profile-ref-row"
              onClick={() => setShowAboutDetail((prev) => !prev)}
            >
              <span className="profile-ref-row-icon">
                <Info size={18} />
              </span>
              <span className="profile-ref-row-title">Tentang {appName}</span>
              <ChevronRight
                size={16}
                className={`profile-ref-chevron ${showAboutDetail ? 'rotated' : ''}`}
              />
            </button>
            {showAboutDetail && (
              <div className="profile-ref-about-detail">
                <strong>{appName}</strong> — {appTagline}
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
  )
}
