import React, { useState, useEffect } from 'react'
import {
  X,
  ArrowLeft,
  Settings,
  Crown,
  Gem,
  ChevronRight,
  Zap,
  History,
  Sparkles,
  FlaskConical,
  Cpu,
  CalendarClock,
  HelpCircle,
  Award,
  Info,
  Mail,
  Wifi,
  Bot,
  BellRing,
  Send,
  Wallet,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatDateTimeWIB, formatRp } from '../utils/formatters'
import {
  APP_VERSION_TAG,
  clearAppLock,
  detectDeviceTimeZone,
  getAppLockConfig,
  getUiText,
  triggerHaptic,
  useUserPrefs,
} from '../utils/userPrefs'
import {
  AboutDetailSubView,
  AboutHubSubView,
  AccountDetailSubView,
  AppLockSubView,
  ChangelogSubView,
  CreditsSubView,
  EcosystemSubView,
  EditNameSubView,
  HelpSupportSubView,
  LabsSubView,
  LanguageSubView,
  MyPanelsSubView,
  OfficialChannelsSubView,
  PasswordSubView,
  RateFeedbackModal,
  SchedulesBudgetSubView,
  SettingsSubView,
  TimeZoneSubView,
} from './ProfileSubViews'

function normalizeWaHref(raw = '') {
  const digits = String(raw || '').replace(/[^0-9]/g, '')
  if (!digits) return ''
  if (digits.startsWith('0')) return `https://wa.me/62${digits.slice(1)}`
  return `https://wa.me/${digits}`
}

function maskEmailPreview(email = '') {
  const raw = String(email || '').trim()
  if (!raw.includes('@')) return raw || 'Akun Terdaftar'
  return raw
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
  onOpenUsageGuide,
  onOpenTerms,
  onOpenPlanModal,
  onOpenSettings,
  onOpenAddDevice,
  onSelectDevice,
  devices = [],
  settings = null,
  onSaveSettings,
  isDeviceOnlineFn,
  onTriggerAppLock,
  appConfig = {},
}) {
  const { prefs, updatePrefs } = useUserPrefs()
  const [viewStack, setViewStack] = useState(['main'])
  const [lockCfg, setLockCfg] = useState(() => getAppLockConfig())
  const [showRateModal, setShowRateModal] = useState(false)

  // Account edit states
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
      setViewStack(['main'])
      setEditName(currentUser?.name || '')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setAccountMsg(null)
      setShowRateModal(false)
      setLockCfg(getAppLockConfig())
    }
  }, [isOpen, currentUser?.name])

  if (!isOpen) return null

  const activeView = viewStack[viewStack.length - 1] || 'main'
  const isMainView = activeView === 'main'

  const navigateTo = (nextView) => {
    triggerHaptic(8)
    setAccountMsg(null)
    setViewStack((prev) => [...prev, nextView])
  }

  const goBack = () => {
    triggerHaptic(8)
    setAccountMsg(null)
    setViewStack((prev) => (prev.length > 1 ? prev.slice(0, -1) : ['main']))
  }

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
      triggerHaptic(16)
      setAccountMsg({ type: 'success', text: 'Nama profil berhasil diperbarui.' })
      window.setTimeout(() => goBack(), 450)
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
      triggerHaptic(16)
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
  const waHref = normalizeWaHref(appConfig.support_whatsapp || '')
  const tgHandle = (appConfig.support_telegram || '').replace(/^@+/, '').trim()
  const supportEmail = (appConfig.support_email || '').trim()

  const displayName = currentUser?.name || `Pengguna ${appName}`
  const initialLetter = displayName.trim().charAt(0).toUpperCase() || 'V'
  const hasAvatar = Boolean(currentUser?.avatar_url && failedAvatarUrl !== currentUser.avatar_url)
  const isGoogleAuth =
    currentUser?.auth_provider === 'google' || currentUser?.auth_provider === 'both'

  const plan = currentUser?.plan
  const allPublicPlans = Array.isArray(appConfig.plans?.items) ? appConfig.plans.items : []
  const paidPublicPlans = allPublicPlans.filter((p) => !p.is_default_free && p.slug !== 'free')
  const proCfg = paidPublicPlans.find((p) => p.is_recommended) ||
    paidPublicPlans[0] ||
    appConfig.plans?.pro || {
      name: 'VoltKu Pro',
      price_monthly_rp: 30000,
      effective_monthly_price_rp: 30000,
      max_devices: 10,
      history_days: 90,
      promo_active: false,
    }
  const proEffPrice = Number(proCfg.effective_monthly_price_rp ?? proCfg.price_monthly_rp ?? 30000)
  const proBasePrice = Number(proCfg.price_monthly_rp ?? proEffPrice)
  const proHasPromo = Boolean(proCfg.promo_active) && proBasePrice > proEffPrice
  const showPlanCard = Boolean(currentUser)
  const isPro = Boolean(plan?.is_pro)
  const tierShortLabel = isPro
    ? (plan?.plan_name || 'Pro').replace(/^VoltKu\s+/i, '').trim() || 'Pro'
    : 'Free'
  const usedDevices = plan?.usage?.device_count ?? devices.length ?? 0
  const maxDevices = plan?.limits?.max_devices ?? 1
  const historyDays = plan?.limits?.history_days ?? (isPro ? proCfg.history_days : 3)
  const quotaPct =
    maxDevices > 0 ? Math.min(100, Math.round((usedDevices / maxDevices) * 100)) : 25
  const proMaxText =
    proCfg.max_devices < 0 ? 'panel tanpa batas' : `hingga ${proCfg.max_devices} panel`

  const titleByView = {
    main: getUiText(prefs.locale, 'profileTitle'),
    settings: getUiText(prefs.locale, 'settingsTitle'),
    'edit-name': getUiText(prefs.locale, 'editNameTitle'),
    password: getUiText(prefs.locale, 'passwordTitle'),
    'app-lock': getUiText(prefs.locale, 'appLockTitle'),
    language: getUiText(prefs.locale, 'languageTitle'),
    timezone: getUiText(prefs.locale, 'timezoneTitle'),
    schedules: getUiText(prefs.locale, 'schedulesTitle'),
    'account-detail': getUiText(prefs.locale, 'accountDetailTitle'),
    ecosystem: getUiText(prefs.locale, 'ecosystemTitle'),
    panels: getUiText(prefs.locale, 'panelsTitle'),
    labs: getUiText(prefs.locale, 'labsTitle'),
    help: getUiText(prefs.locale, 'helpTitle'),
    credits: getUiText(prefs.locale, 'creditsTitle'),
    about: getUiText(prefs.locale, 'aboutTitle'),
    'about-detail': `Tentang ${appName}`,
    changelog: getUiText(prefs.locale, 'versionTitle'),
    channels: getUiText(prefs.locale, 'channelsTitle'),
  }

  const handleResetLocalPrefs = () => {
    clearAppLock()
    setLockCfg(getAppLockConfig())
    updatePrefs({
      locale: 'id',
      timezone: detectDeviceTimeZone(),
      vibration: true,
      monthlyBudgetRp: 0,
      budgetAlertEnabled: false,
      labs: {
        proactiveAiTips: true,
        compactCards: false,
        smoothCharts: true,
        weeklyDigestReminder: true,
      },
    })
  }

  const handleOpenAiFromProfile = () => {
    onClose()
    window.dispatchEvent(new CustomEvent('voltku:open-ai-chat'))
  }

  const reportSummaryBadge =
    settings?.report_enabled === false
      ? 'Off'
      : `${String(settings?.report_hour ?? 21).padStart(2, '0')}:00`

  return (
    <div className="modal-overlay pwa-guide-overlay profile-modal-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern profile-modal-dialog profile-ref-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Profil Akun"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky Topbar dengan Gerigi Settings di Main & Panah Kembali di Sub-halaman */}
        <div className="profile-sticky-topbar">
          <div className="profile-ref-topbar">
            {isMainView ? (
              <span aria-hidden="true" />
            ) : (
              <button
                type="button"
                className="profile-ref-icon-btn"
                onClick={goBack}
                aria-label="Kembali"
                title="Kembali"
              >
                <ArrowLeft size={17} />
              </button>
            )}

            <h2 className="profile-ref-page-title">{titleByView[activeView] || 'Profil'}</h2>

            <div className="profile-ref-topbar-actions">
              {activeView === 'edit-name' ? (
                <button
                  type="submit"
                  form="profile-edit-name-form"
                  className="profile-topbar-save-btn"
                  disabled={savingName}
                >
                  {savingName ? '...' : getUiText(prefs.locale, 'save')}
                </button>
              ) : isMainView ? (
                <div className="profile-topbar-right-pair">
                  <button
                    type="button"
                    className="profile-ref-icon-btn"
                    onClick={() => navigateTo('settings')}
                    aria-label="Buka Pengaturan Profil"
                    title="Pengaturan"
                  >
                    <Settings size={17} />
                  </button>
                  <button
                    type="button"
                    className="profile-ref-icon-btn"
                    onClick={onClose}
                    aria-label="Tutup Profil"
                  >
                    <X size={17} />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="profile-ref-icon-btn"
                  onClick={onClose}
                  aria-label="Tutup Profil"
                >
                  <X size={17} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Region Konten Scrollable */}
        <div className="profile-scroll-region">
          {isMainView ? (
            <>
              {/* Hero Identitas & Keanggotaan */}
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
                        <div className="profile-ref-avatar profile-avatar-initial">
                          {initialLetter}
                        </div>
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
                            <span>{tierShortLabel}</span>
                          </span>
                        )}
                      </div>
                      <div className="profile-ref-subline">
                        <span>{maskEmailPreview(currentUser?.email)}</span>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="profile-learn-more-btn"
                    onClick={() => navigateTo('account-detail')}
                  >
                    <span>Detail</span>
                    <ChevronRight size={13} />
                  </button>
                </div>

                {/* Kartu Tawaran Paket / Keanggotaan (Selalu tampil di bawah Profil) */}
                {showPlanCard && (
                  <div className="profile-vip-stack">
                    <div className={`profile-vip-card ${isPro ? 'is-pro' : 'is-offer'}`}>
                      <div className="profile-vip-top">
                        <div className={`profile-vip-icon ${isPro ? 'is-pro' : ''}`}>
                          {isPro ? <Crown size={19} /> : <Gem size={19} />}
                        </div>
                        <div className="profile-vip-copy">
                          <div className="profile-vip-title-row">
                            <span className="profile-vip-title">
                              {isPro
                                ? `${plan?.plan_name || 'Paket Pro'} Aktif`
                                : `Paket ${proCfg.name || 'VoltKu Pro'}`}
                            </span>
                            {!isPro && proHasPromo && (
                              <span className="profile-vip-promo-pill">
                                {proCfg.promo_label || 'PROMO'}
                              </span>
                            )}
                          </div>
                          <div className="profile-vip-sub">
                            {isPro
                              ? plan?.expires_at
                                ? `Berlaku hingga ${formatDateTimeWIB(plan.expires_at)}`
                                : 'Keanggotaan berbayar aktif permanen'
                              : proHasPromo
                                ? `${proMaxText} · Riwayat ${proCfg.history_days} hr · `
                                : `${proMaxText} & riwayat ${proCfg.history_days} hari · Mulai ${formatRp(proEffPrice)}/bln`}
                            {!isPro && proHasPromo && (
                              <span className="num-tabular">
                                <span className="profile-vip-strike">{formatRp(proBasePrice)}</span>{' '}
                                <strong>{formatRp(proEffPrice)}/bln</strong>
                              </span>
                            )}
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
                              : plan?.pending_upgrade
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
                        {plan?.pending_upgrade && !isPro && (
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

                    {onOpenPlanModal && !isPro && (
                      <button
                        type="button"
                        className="profile-promo-strip"
                        onClick={() => {
                          onClose()
                          onOpenPlanModal('')
                        }}
                      >
                        <Crown size={14} />
                        <span>Bandingkan semua paket, promo harga coret &amp; pakai kupon</span>
                        <ChevronRight size={14} style={{ marginLeft: 'auto' }} />
                      </button>
                    )}
                  </div>
                )}

                {/* Banner Sorotan Asli VoltKu (Target Anggaran / Asisten AI) */}
                <div
                  className="profile-spotlight-banner"
                  role="button"
                  tabIndex={0}
                  onClick={() =>
                    Number(prefs.monthlyBudgetRp || 0) > 0
                      ? navigateTo('schedules')
                      : handleOpenAiFromProfile()
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      if (Number(prefs.monthlyBudgetRp || 0) > 0) {
                        navigateTo('schedules')
                      } else {
                        handleOpenAiFromProfile()
                      }
                    }
                  }}
                >
                  <div className="profile-spotlight-copy">
                    <span className="profile-spotlight-eyebrow">
                      {Number(prefs.monthlyBudgetRp || 0) > 0 ? 'TARGET ANGGARAN' : 'ASISTEN PINTAR'}
                    </span>
                    <div className="profile-spotlight-title">
                      {Number(prefs.monthlyBudgetRp || 0) > 0
                        ? `Batas Listrik: ${formatRp(prefs.monthlyBudgetRp)}/bln`
                        : 'Analisa Jam Boros & Biaya AI'}
                    </div>
                  </div>
                  <span className="profile-spotlight-cta">
                    {Number(prefs.monthlyBudgetRp || 0) > 0 ? 'Atur >' : 'Tanya AI >'}
                  </span>
                </div>
              </div>

              {/* Kartu Grup Menu Bersih */}
              <div className="profile-ref-body">
                {/* Grup 1: Ekosistem & Fitur Pintar VoltKu */}
                <section className="profile-ref-card-group">
                  <button
                    type="button"
                    className="profile-ref-row"
                    onClick={() => navigateTo('ecosystem')}
                  >
                    <span className="profile-ref-row-icon is-blue">
                      <Cpu size={17} />
                    </span>
                    <span className="profile-ref-row-text">
                      <span className="profile-ref-row-title">Ekosistem &amp; Koneksi</span>
                    </span>
                    <div className="profile-eco-mini-pills" aria-hidden="true">
                      <span className="eco-dot is-blue" title="MQTT TLS">
                        <Wifi size={11} />
                      </span>
                      <span className="eco-dot is-indigo" title="Asisten AI">
                        <Bot size={11} />
                      </span>
                      <span className="eco-dot is-amber" title="Push Notif">
                        <BellRing size={11} />
                      </span>
                      <span className="eco-dot is-sky" title="Telegram">
                        <Send size={11} />
                      </span>
                    </div>
                    <ChevronRight size={16} className="profile-ref-chevron" />
                  </button>

                  <button
                    type="button"
                    className="profile-ref-row"
                    onClick={() => navigateTo('panels')}
                  >
                    <span className="profile-ref-row-icon is-teal">
                      <Zap size={17} />
                    </span>
                    <span className="profile-ref-row-text">
                      <span className="profile-ref-row-title">Panel &amp; Laporan Saya</span>
                    </span>
                    <span className="profile-ref-badge is-blue num-tabular">
                      {devices.length} Panel
                    </span>
                    <ChevronRight size={16} className="profile-ref-chevron" />
                  </button>

                  <button
                    type="button"
                    className="profile-ref-row"
                    onClick={() => navigateTo('schedules')}
                  >
                    <span className="profile-ref-row-icon is-amber">
                      <CalendarClock size={17} />
                    </span>
                    <span className="profile-ref-row-text">
                      <span className="profile-ref-row-title">Jadwal Laporan &amp; Target</span>
                    </span>
                    <span className="profile-ref-badge is-neutral num-tabular">
                      {reportSummaryBadge}
                    </span>
                    <ChevronRight size={16} className="profile-ref-chevron" />
                  </button>

                  {onOpenSettings && (
                    <button
                      type="button"
                      className="profile-ref-row"
                      onClick={() => {
                        onClose()
                        onOpenSettings()
                      }}
                    >
                      <span className="profile-ref-row-icon is-emerald">
                        <Wallet size={17} />
                      </span>
                      <span className="profile-ref-row-text">
                        <span className="profile-ref-row-title">Tarif PLN &amp; Batas Daya</span>
                      </span>
                      <span className="profile-ref-badge is-emerald">PLN</span>
                      <ChevronRight size={16} className="profile-ref-chevron" />
                    </button>
                  )}

                  <button
                    type="button"
                    className="profile-ref-row"
                    onClick={() => navigateTo('labs')}
                  >
                    <span className="profile-ref-row-icon is-indigo">
                      <FlaskConical size={17} />
                    </span>
                    <span className="profile-ref-row-text">
                      <span className="profile-ref-row-title">VoltKu Labs</span>
                    </span>
                    <span className="profile-ref-badge is-gold">Beta</span>
                    <ChevronRight size={16} className="profile-ref-chevron" />
                  </button>
                </section>

                {/* Grup 2: Dukungan, Apresiasi & Tentang */}
                <section className="profile-ref-card-group">
                  <button
                    type="button"
                    className="profile-ref-row"
                    onClick={() => navigateTo('help')}
                  >
                    <span className="profile-ref-row-icon is-emerald">
                      <HelpCircle size={17} />
                    </span>
                    <span className="profile-ref-row-text">
                      <span className="profile-ref-row-title">Bantuan &amp; Masukan</span>
                    </span>
                    <ChevronRight size={16} className="profile-ref-chevron" />
                  </button>

                  <button
                    type="button"
                    className="profile-ref-row"
                    onClick={() => navigateTo('credits')}
                  >
                    <span className="profile-ref-row-icon is-amber">
                      <Award size={17} />
                    </span>
                    <span className="profile-ref-row-text">
                      <span className="profile-ref-row-title">Apresiasi &amp; Teknologi</span>
                    </span>
                    <ChevronRight size={16} className="profile-ref-chevron" />
                  </button>

                  <button
                    type="button"
                    className="profile-ref-row"
                    onClick={() => navigateTo('about')}
                  >
                    <span className="profile-ref-row-icon is-slate">
                      <Info size={17} />
                    </span>
                    <span className="profile-ref-row-text">
                      <span className="profile-ref-row-title">Tentang {appName}</span>
                    </span>
                    <span className="profile-ref-badge is-neutral num-tabular">
                      {APP_VERSION_TAG}
                    </span>
                    <ChevronRight size={16} className="profile-ref-chevron" />
                  </button>
                </section>
              </div>
            </>
          ) : (
            <div className="profile-ref-body profile-subpage-body">
              {activeView === 'settings' && (
                <SettingsSubView
                  currentUser={currentUser}
                  prefs={prefs}
                  updatePrefs={updatePrefs}
                  lockCfg={lockCfg}
                  settings={settings}
                  theme={theme}
                  onToggleTheme={onToggleTheme}
                  onNavigate={navigateTo}
                  onLogout={onLogout}
                  onClose={onClose}
                />
              )}

              {activeView === 'edit-name' && (
                <EditNameSubView
                  editName={editName}
                  onChangeName={setEditName}
                  feedback={accountMsg}
                  locale={prefs.locale}
                  onSubmit={handleSaveName}
                />
              )}

              {activeView === 'password' && (
                <PasswordSubView
                  hasLocalPassword={hasLocalPassword}
                  currentPassword={currentPassword}
                  setCurrentPassword={setCurrentPassword}
                  newPassword={newPassword}
                  setNewPassword={setNewPassword}
                  confirmPassword={confirmPassword}
                  setConfirmPassword={setConfirmPassword}
                  showPasswords={showPasswords}
                  setShowPasswords={setShowPasswords}
                  saving={savingPassword}
                  feedback={accountMsg}
                  onSubmit={handleChangePassword}
                />
              )}

              {activeView === 'app-lock' && (
                <AppLockSubView
                  currentUser={currentUser}
                  onLockChanged={(nextCfg) => setLockCfg(nextCfg)}
                  onTestLockScreen={() => {
                    onClose()
                    onTriggerAppLock?.()
                  }}
                />
              )}

              {activeView === 'language' && (
                <LanguageSubView prefs={prefs} updatePrefs={updatePrefs} />
              )}

              {activeView === 'timezone' && (
                <TimeZoneSubView
                  prefs={prefs}
                  updatePrefs={updatePrefs}
                  onSyncServerTimezone={(tzId) =>
                    onSaveSettings?.({ report_timezone: tzId })?.catch?.(() => {})
                  }
                />
              )}

              {activeView === 'schedules' && (
                <SchedulesBudgetSubView
                  settings={settings}
                  onSaveSettings={onSaveSettings}
                  prefs={prefs}
                  updatePrefs={updatePrefs}
                />
              )}

              {activeView === 'account-detail' && (
                <AccountDetailSubView
                  currentUser={currentUser}
                  onOpenTerms={onOpenTerms}
                  onNavigate={navigateTo}
                  onResetPrefs={handleResetLocalPrefs}
                />
              )}

              {activeView === 'ecosystem' && (
                <EcosystemSubView
                  devices={devices}
                  isDeviceOnlineFn={isDeviceOnlineFn}
                  settings={settings}
                  onOpenAiChat={handleOpenAiFromProfile}
                  onNavigate={navigateTo}
                />
              )}

              {activeView === 'panels' && (
                <MyPanelsSubView
                  devices={devices}
                  userPlan={plan}
                  isDeviceOnlineFn={isDeviceOnlineFn}
                  onSelectDevice={onSelectDevice}
                  onOpenAddDevice={onOpenAddDevice}
                  onClose={onClose}
                />
              )}

              {activeView === 'labs' && (
                <LabsSubView
                  prefs={prefs}
                  updatePrefs={updatePrefs}
                  isPro={isPro}
                />
              )}

              {activeView === 'help' && (
                <HelpSupportSubView
                  waHref={waHref}
                  tgHandle={tgHandle}
                  supportEmail={supportEmail}
                  onOpenUsageGuide={onOpenUsageGuide}
                  onReplayTour={onReplayTour}
                  onClose={onClose}
                  onOpenRateModal={() => setShowRateModal(true)}
                />
              )}

              {activeView === 'credits' && <CreditsSubView appName={appName} />}

              {activeView === 'about' && (
                <AboutHubSubView
                  appName={appName}
                  waHref={waHref}
                  tgHandle={tgHandle}
                  supportEmail={supportEmail}
                  onNavigate={navigateTo}
                  onOpenTerms={onOpenTerms}
                />
              )}

              {activeView === 'about-detail' && (
                <AboutDetailSubView
                  appName={appName}
                  appTagline={appTagline}
                  theme={theme}
                  onOpenTerms={onOpenTerms}
                />
              )}

              {activeView === 'changelog' && <ChangelogSubView />}

              {activeView === 'channels' && (
                <OfficialChannelsSubView
                  waHref={waHref}
                  tgHandle={tgHandle}
                  supportEmail={supportEmail}
                  appName={appName}
                />
              )}
            </div>
          )}
        </div>
      </div>

      <RateFeedbackModal
        isOpen={showRateModal}
        onClose={() => setShowRateModal(false)}
        appName={appName}
        waHref={waHref}
        supportEmail={supportEmail}
      />
    </div>
  )
}
