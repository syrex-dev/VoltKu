import React, { useState } from 'react'
import { Zap, ArrowRight, X, Server, HelpCircle, UserCheck } from 'lucide-react'

function GoogleIconSvg() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.3 0 6.08-1.09 8.105-2.96l-3.88-3.05c-1.09.73-2.49 1.16-4.225 1.16-3.24 0-5.985-2.19-6.97-5.14H1.02v3.14C3.035 21.155 7.21 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.03 14.01A7.19 7.19 0 0 1 4.65 12c0-.7.13-1.37.38-2.01V6.85H1.02A11.98 11.98 0 0 0 0 12c0 1.93.46 3.76 1.02 5.15l4.01-3.14Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.79 0 3.4.615 4.67 1.825l3.5-3.5C18.075 1.19 15.295 0 12 0 7.21 0 3.035 2.845 1.02 6.85l4.01 3.14C6.015 6.94 8.76 4.75 12 4.75Z"
      />
    </svg>
  )
}

export function LoginModal({
  onLogin,
  onRegister,
  onGoogleLogin,
  googleEnabled = false,
  termsAccepted = true,
  onOpenTerms,
  onOpenServerConfig,
  onTryGuest,
  error,
  canClose = false,
  onClose,
  subtitle = 'Pantau dan kelola pemakaian listrik rumah secara real-time',
}) {
  const [authTab, setAuthTab] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [localAgreed, setLocalAgreed] = useState(termsAccepted)
  const [localError, setLocalError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLocalError(null)
    if (!localAgreed) {
      setLocalError('Centang persetujuan Syarat Penggunaan & Kebijakan Privasi terlebih dahulu.')
      return
    }
    if (!email.trim() || !password.trim()) return

    if (authTab === 'register' && name.trim().length < 2) {
      setLocalError('Nama lengkap minimal 2 karakter.')
      return
    }
    if (authTab === 'register' && password.length < 6) {
      setLocalError('Kata sandi minimal 6 karakter.')
      return
    }

    setSubmitting(true)
    try {
      if (authTab === 'login') {
        await onLogin(email.trim(), password)
      } else if (onRegister) {
        await onRegister(name.trim(), email.trim(), password)
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleGoogleClick = async () => {
    setLocalError(null)
    if (!localAgreed) {
      setLocalError('Centang persetujuan Syarat Penggunaan & Kebijakan Privasi terlebih dahulu.')
      return
    }
    if (!onGoogleLogin) return
    setGoogleLoading(true)
    try {
      await onGoogleLogin()
    } catch (err) {
      setLocalError(err?.message || 'Gagal masuk menggunakan Google.')
    } finally {
      setGoogleLoading(false)
    }
  }

  const displayError = localError || error

  return (
    <div
      className={canClose ? 'modal-overlay pwa-guide-overlay' : 'auth-hero-backdrop clean-auth-bg'}
      onClick={canClose && onClose ? onClose : undefined}
    >
      <div
        className="auth-card-modern clean-auth-card native-welcome-card"
        style={{ position: 'relative' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top utility row ala mobile smart-home app */}
        <div className="native-auth-top-bar">
          {onOpenServerConfig ? (
            <button
              type="button"
              className="native-auth-util-btn"
              onClick={onOpenServerConfig}
              title="Atur alamat server backend"
            >
              <Server size={14} />
              <span>Server</span>
            </button>
          ) : (
            <span />
          )}

          <div className="native-auth-top-right">
            {onOpenTerms && (
              <button
                type="button"
                className="native-auth-util-btn"
                onClick={() => onOpenTerms('terms')}
              >
                <HelpCircle size={14} />
                <span>Ketentuan</span>
              </button>
            )}
            {canClose && onClose && (
              <button
                type="button"
                className="btn-icon-close"
                onClick={onClose}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            )}
          </div>
        </div>

        <div className="auth-header">
          <div className="clean-app-logo">
            <Zap size={28} />
          </div>
          <h2 className="auth-title">VoltKu</h2>
          <p className="auth-subtitle">{subtitle}</p>
        </div>

        <div className="user-auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={authTab === 'login'}
            className={`user-auth-tab ${authTab === 'login' ? 'active' : ''}`}
            onClick={() => {
              setAuthTab('login')
              setLocalError(null)
            }}
          >
            Masuk
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={authTab === 'register'}
            className={`user-auth-tab ${authTab === 'register' ? 'active' : ''}`}
            onClick={() => {
              setAuthTab('register')
              setLocalError(null)
            }}
          >
            Daftar Akun
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {authTab === 'register' && (
            <div className="form-field-group">
              <label className="field-label" htmlFor="user-name-input">
                Nama Lengkap
              </label>
              <input
                type="text"
                id="user-name-input"
                className="modern-input"
                placeholder="Contoh: Budi Santoso"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoComplete="name"
              />
            </div>
          )}

          <div className="form-field-group">
            <label className="field-label" htmlFor="user-email-input">
              Email
            </label>
            <input
              type="email"
              id="user-email-input"
              className="modern-input"
              placeholder="nama@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              autoFocus={authTab === 'login'}
            />
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="password-input">
              Kata Sandi
            </label>
            <input
              type="password"
              id="password-input"
              className="modern-input"
              placeholder={authTab === 'register' ? 'Minimal 6 karakter' : 'Masukkan kata sandi'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={authTab === 'register' ? 'new-password' : 'current-password'}
            />
          </div>

          <label className="auth-terms-check-row">
            <input
              type="checkbox"
              checked={localAgreed}
              onChange={(e) => {
                setLocalAgreed(e.target.checked)
                setLocalError(null)
              }}
            />
            <span>
              Saya menyetujui{' '}
              <button
                type="button"
                className="app-inline-link"
                onClick={() => onOpenTerms && onOpenTerms('terms')}
              >
                Syarat Penggunaan
              </button>{' '}
              &amp;{' '}
              <button
                type="button"
                className="app-inline-link"
                onClick={() => onOpenTerms && onOpenTerms('privacy')}
              >
                Kebijakan Privasi
              </button>
            </span>
          </label>

          {displayError && <div className="feedback-msg error">{displayError}</div>}

          <button
            type="submit"
            className="btn btn-primary auth-submit-pill"
            style={{ width: '100%', padding: '12px 18px', fontSize: '15px' }}
            disabled={submitting || googleLoading}
          >
            <span>
              {submitting
                ? authTab === 'register'
                  ? 'Mendaftarkan...'
                  : 'Memverifikasi...'
                : authTab === 'register'
                ? 'Buat Akun Sekarang'
                : 'Masuk'}
            </span>
            {!submitting && <ArrowRight size={17} />}
          </button>
        </form>

        {onGoogleLogin && (
          <>
            <div className="auth-divider-or">
              <span>atau</span>
            </div>

            <button
              type="button"
              className="google-auth-btn"
              onClick={handleGoogleClick}
              disabled={submitting || googleLoading}
              title={
                googleEnabled
                  ? 'Masuk cepat menggunakan Akun Google Anda'
                  : 'Membutuhkan GOOGLE_CLIENT_ID di server'
              }
            >
              <GoogleIconSvg />
              <span>
                {googleLoading ? 'Menghubungkan ke Google...' : 'Lanjutkan dengan Google'}
              </span>
            </button>
            {!googleEnabled && (
              <div className="google-setup-hint">
                Aktifkan <code>GOOGLE_CLIENT_ID</code> di <code>.env</code> server untuk login
                Google langsung.
              </div>
            )}
          </>
        )}

        {onTryGuest && (
          <div className="native-try-guest-wrap">
            <button type="button" className="native-try-guest-btn" onClick={onTryGuest}>
              <span className="native-try-guest-circle">
                <UserCheck size={18} />
              </span>
              <span className="native-try-guest-label">Coba Sekarang (Mode Guest)</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
