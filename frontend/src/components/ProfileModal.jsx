import React from 'react'
import {
  X,
  User,
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

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern profile-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Profil Akun"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head" style={{ marginBottom: 14 }}>
          <div>
            <h3 className="pwa-guide-title">Profil &amp; Akun</h3>
            <p className="pwa-guide-sub">Kelola akun, paket langganan, dan bantuan</p>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <div className="settings-stack-clean">
          {/* Identitas Akun */}
          <section className="clean-sheet profile-hero-sheet">
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
                  {currentUser?.name || `Pengguna ${appName}`}
                </h2>
                <p className="profile-hero-sub">
                  {`${currentUser?.email || ''}${
                    currentUser?.auth_provider === 'google' ||
                    currentUser?.auth_provider === 'both'
                      ? ' · Akun Google'
                      : ''
                  }`}
                </p>
              </div>
            </div>

            {onLogout && (
              <button
                type="button"
                className="btn btn-danger-ghost btn-compact"
                onClick={() => {
                  onClose()
                  onLogout()
                }}
              >
                <LogOut size={14} />
                <span>Keluar</span>
              </button>
            )}
          </section>

          {/* Ringkasan Paket & Kuota (Freemium) */}
          {currentUser?.plan && currentUser.plan.freemium_enabled !== false && (
            <section className="clean-sheet plan-summary-sheet">
              <div className="plan-summary-head">
                <div className="plan-summary-title-group">
                  <span className={`plan-badge-chip ${currentUser.plan.is_pro ? 'is-pro' : ''}`}>
                    <Crown size={14} />
                    <span>{currentUser.plan.plan_name}</span>
                  </span>
                  {currentUser.plan.pending_upgrade && !currentUser.plan.is_pro && (
                    <span className="admin-pill warn">Menunggu Aktivasi</span>
                  )}
                </div>
                {onOpenPlanModal && (
                  <button
                    type="button"
                    className={`btn btn-compact ${currentUser.plan.is_pro ? 'btn-secondary' : 'btn-primary'}`}
                    onClick={() => {
                      onClose()
                      onOpenPlanModal('')
                    }}
                  >
                    {currentUser.plan.is_pro ? 'Detail Paket' : 'Upgrade Pro'}
                  </button>
                )}
              </div>
              <div className="plan-summary-meta num-tabular">
                <span>
                  Panel:{' '}
                  <strong>
                    {currentUser.plan.usage?.device_count ?? 0} /{' '}
                    {currentUser.plan.limits?.max_devices < 0
                      ? 'Tak terbatas'
                      : currentUser.plan.limits?.max_devices ?? 1}
                  </strong>
                </span>
                <span>
                  Riwayat: <strong>{currentUser.plan.limits?.history_days ?? 3} hari</strong>
                </span>
                {currentUser.plan.is_pro && (
                  <span>
                    {currentUser.plan.expires_at
                      ? `Aktif s.d. ${formatTimeWIB(currentUser.plan.expires_at)}`
                      : 'Aktif Permanen'}
                  </span>
                )}
              </div>
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
                  <span>Putar ulang pengenalan fitur &amp; cara tambah panel</span>
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
        </div>
      </div>
    </div>
  )
}

