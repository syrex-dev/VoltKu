import React, { useState } from 'react'
import {
  X,
  Settings,
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
} from 'lucide-react'
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

  if (!isOpen) return null

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
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
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
            <span className="profile-ref-topbar-spacer" aria-hidden="true" />
            <h2 className="profile-ref-page-title">Profil</h2>
            <div className="profile-ref-topbar-actions">
              {onOpenSettings && (
                <button
                  type="button"
                  className="profile-ref-icon-btn"
                  title="Setelan Tarif & Peringatan"
                  aria-label="Setelan Tarif & Peringatan"
                  onClick={() => {
                    onClose()
                    onOpenSettings()
                  }}
                >
                  <Settings size={18} />
                </button>
              )}
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

          {/* User Identity Header Row (Open Canvas, Clean Typography) */}
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

            {showPlanCard && onOpenPlanModal && (
              <button
                type="button"
                className="profile-ref-link-btn"
                onClick={() => {
                  onClose()
                  onOpenPlanModal('')
                }}
              >
                <span>{isPro ? 'VoltKu Pro' : 'Kelola Paket'}</span>
                <ChevronRight size={14} />
              </button>
            )}
          </div>

          {/* Membership Card (Inspired by Reference Subscription Card) */}
          {showPlanCard && (
            <div className={`profile-ref-member-card ${isPro ? 'is-pro' : ''}`}>
              <div className="profile-ref-member-main">
                <div className={`profile-ref-gem-badge ${isPro ? 'is-pro' : ''}`}>
                  {isPro ? <Crown size={20} /> : <Gem size={20} />}
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
                      ? 'Menunggu aktivasi admin'
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
                <Crown size={15} />
                <span>
                  {isPro
                    ? plan.expires_at
                      ? `VoltKu Pro aktif hingga ${formatTimeWIB(plan.expires_at)}`
                      : 'VoltKu Pro aktif permanen'
                    : `Coba ${proCfg.name} · Mulai ${formatRp(proCfg.price_monthly_rp)}/bulan`}
                </span>
              </span>
              <ChevronRight size={16} />
            </button>
          )}
        </div>

        {/* Grouped Menu Cards (Clean Outline Icons + Inline Pills + Chevrons) */}
        <div className="profile-ref-body">
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
                <span className="profile-ref-row-icon">
                  <SlidersHorizontal size={19} />
                </span>
                <span className="profile-ref-row-title">Tarif Listrik &amp; Peringatan</span>
                <span className="profile-ref-badge is-blue">PLN</span>
                <ChevronRight size={17} className="profile-ref-chevron" />
              </button>
            )}

            {showPlanCard && onOpenPlanModal && (
              <button
                type="button"
                className="profile-ref-row"
                onClick={() => {
                  onClose()
                  onOpenPlanModal('')
                }}
              >
                <span className="profile-ref-row-icon">
                  <Crown size={19} />
                </span>
                <span className="profile-ref-row-title">Paket &amp; Kuota Panel</span>
                <span className={`profile-ref-badge ${isPro ? 'is-gold' : 'is-neutral'}`}>
                  {isPro ? 'Pro' : 'Gratis'}
                </span>
                <ChevronRight size={17} className="profile-ref-chevron" />
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
                  <Compass size={19} />
                </span>
                <span className="profile-ref-row-title">Panduan Awal Aplikasi</span>
                <ChevronRight size={17} className="profile-ref-chevron" />
              </button>
            )}

            {onToggleTheme && (
              <button type="button" className="profile-ref-row" onClick={onToggleTheme}>
                <span className="profile-ref-row-icon">
                  {theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}
                </span>
                <span className="profile-ref-row-title">Tema Tampilan</span>
                <span className="profile-ref-badge is-slate">
                  {theme === 'dark' ? 'Gelap' : 'Terang'}
                </span>
                <ChevronRight size={17} className="profile-ref-chevron" />
              </button>
            )}
          </section>

          <section className="profile-ref-card-group">
            {waHref && (
              <a href={waHref} target="_blank" rel="noreferrer" className="profile-ref-row">
                <span className="profile-ref-row-icon">
                  <MessageCircle size={19} />
                </span>
                <span className="profile-ref-row-title">Bantuan WhatsApp</span>
                <span className="profile-ref-badge is-emerald">Chat</span>
                <ChevronRight size={17} className="profile-ref-chevron" />
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
                  <Send size={19} />
                </span>
                <span className="profile-ref-row-title">Bantuan Telegram</span>
                <span className="profile-ref-badge is-neutral">@{tgHandle}</span>
                <ChevronRight size={17} className="profile-ref-chevron" />
              </a>
            )}

            {supportEmail && (
              <a href={`mailto:${supportEmail}`} className="profile-ref-row">
                <span className="profile-ref-row-icon">
                  <Mail size={19} />
                </span>
                <span className="profile-ref-row-title">Email Dukungan</span>
                <ChevronRight size={17} className="profile-ref-chevron" />
              </a>
            )}

            {onOpenTerms && (
              <button
                type="button"
                className="profile-ref-row"
                onClick={() => onOpenTerms('terms')}
              >
                <span className="profile-ref-row-icon">
                  <ShieldCheck size={19} />
                </span>
                <span className="profile-ref-row-title">Syarat &amp; Kebijakan Privasi</span>
                <span className="profile-ref-badge is-neutral">{termsVersion}</span>
                <ChevronRight size={17} className="profile-ref-chevron" />
              </button>
            )}

            <button
              type="button"
              className="profile-ref-row"
              onClick={() => setShowAboutDetail((prev) => !prev)}
            >
              <span className="profile-ref-row-icon">
                <Info size={19} />
              </span>
              <span className="profile-ref-row-title">Tentang {appName}</span>
              <ChevronRight
                size={17}
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
              <LogOut size={16} />
              <span>Keluar dari Akun</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
