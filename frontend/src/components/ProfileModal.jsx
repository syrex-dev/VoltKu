import React from 'react'
import {
  X,
  Crown,
  LogOut,
  ChevronRight,
  Compass,
  ShieldCheck,
  Sun,
  Moon,
  MessageCircle,
  Send,
  Mail,
  Info,
  Sparkles,
} from 'lucide-react'
import { formatTimeWIB } from '../utils/formatters'

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
  appConfig = {},
}) {
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
  const showPlanCard = Boolean(plan && plan.freemium_enabled !== false)
  const usedDevices = plan?.usage?.device_count ?? 0
  const maxDevices = plan?.limits?.max_devices ?? 1
  const quotaPct =
    maxDevices > 0 ? Math.min(100, Math.round((usedDevices / maxDevices) * 100)) : 25

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern profile-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Profil & Akun"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="profile-modal-top">
          <span className="profile-modal-kicker">Akun Saya</span>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <div className="settings-stack-clean">
          {/* Identitas Akun */}
          <section className="clean-sheet profile-hero-card">
            <div className="profile-hero-left">
              {currentUser?.avatar_url ? (
                <img
                  src={currentUser.avatar_url}
                  alt={displayName}
                  className="profile-avatar-img"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="profile-avatar-fallback profile-avatar-initial">
                  {initialLetter}
                </div>
              )}
              <div className="profile-hero-copy">
                <div className="profile-name-row">
                  <h2 className="profile-hero-name">{displayName}</h2>
                  <span className="profile-auth-tag">
                    {isGoogleAuth ? 'Google' : 'Email'}
                  </span>
                </div>
                <p className="profile-hero-sub">{currentUser?.email || ''}</p>
              </div>
            </div>
          </section>

          {/* Ringkasan Paket & Kuota (Freemium) */}
          {showPlanCard && (
            <section className={`clean-sheet plan-summary-sheet ${plan.is_pro ? 'is-pro' : ''}`}>
              <div className="plan-summary-head">
                <div className="plan-summary-title-group">
                  <span className={`plan-badge-chip ${plan.is_pro ? 'is-pro' : ''}`}>
                    <Crown size={14} />
                    <span>{plan.plan_name}</span>
                  </span>
                  {plan.pending_upgrade && !plan.is_pro && (
                    <span className="admin-pill warn">Menunggu Aktivasi</span>
                  )}
                </div>
                {onOpenPlanModal && (
                  <button
                    type="button"
                    className={`btn btn-compact ${plan.is_pro ? 'btn-secondary' : 'btn-primary'}`}
                    onClick={() => {
                      onClose()
                      onOpenPlanModal('')
                    }}
                  >
                    {!plan.is_pro && <Sparkles size={13} />}
                    <span>{plan.is_pro ? 'Detail Paket' : 'Upgrade Pro'}</span>
                  </button>
                )}
              </div>

              <div className="plan-quota-block">
                <div className="plan-quota-labels num-tabular">
                  <span>
                    Kuota Panel:{' '}
                    <strong>
                      {usedDevices} / {maxDevices < 0 ? 'Tak terbatas' : maxDevices}
                    </strong>
                  </span>
                  <span>
                    Riwayat <strong>{plan.limits?.history_days ?? 3} hari</strong>
                  </span>
                </div>
                {maxDevices > 0 && (
                  <div className="plan-quota-track" aria-hidden="true">
                    <div
                      className={`plan-quota-fill ${plan.is_pro ? 'is-pro' : ''}`}
                      style={{ width: `${Math.max(8, quotaPct)}%` }}
                    />
                  </div>
                )}
              </div>

              {plan.is_pro && (
                <div className="plan-summary-meta num-tabular">
                  <span>
                    {plan.expires_at
                      ? `Masa aktif hingga ${formatTimeWIB(plan.expires_at)}`
                      : 'Aktif Permanen'}
                  </span>
                </div>
              )}
            </section>
          )}

          {/* Menu Aplikasi, Legal & Dukungan */}
          <section className="clean-sheet app-menu-group">
            {showOnboardingRow && (
              <button
                type="button"
                className="app-menu-row"
                onClick={() => {
                  onClose()
                  onReplayTour()
                }}
              >
                <span className="app-menu-icon is-blue">
                  <Compass size={17} />
                </span>
                <span className="app-menu-copy">
                  <strong>Panduan Awal Aplikasi</strong>
                  <span>Pengenalan singkat fitur &amp; cara pasang panel</span>
                </span>
                <ChevronRight size={17} className="app-menu-chevron" />
              </button>
            )}

            {onOpenTerms && (
              <button
                type="button"
                className="app-menu-row"
                onClick={() => onOpenTerms('terms')}
              >
                <span className="app-menu-icon is-emerald">
                  <ShieldCheck size={17} />
                </span>
                <span className="app-menu-copy">
                  <strong>Syarat &amp; Kebijakan Privasi</strong>
                  <span>
                    Versi {termsVersion}
                    {currentUser?.terms_version_accepted ? ' · Sudah disetujui' : ''}
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
                  <strong>Tema Tampilan</strong>
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
