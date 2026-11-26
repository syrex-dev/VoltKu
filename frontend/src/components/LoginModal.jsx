import React, { useState, useEffect, useRef } from 'react'
import { Capacitor } from '@capacitor/core'
import { ArrowRight, ArrowLeft, X, UserCheck, Mail, KeyRound } from 'lucide-react'
import { BrandLogo } from './BrandLogo'
import { loadGoogleGsiScript } from '../utils/googleAuth'

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
  onForgotPassword,
  onResetPassword,
  initialResetToken = '',
  onClearResetToken,
  googleEnabled = false,
  googleClientId = '',
  registrationEnabled = true,
  termsAccepted = true,
  onOpenTerms,
  onTryGuest,
  error,
  canClose = false,
  onClose,
  theme = 'light',
  appName = 'VoltKu',
  brandDisplay = 'logo_only',
  subtitle = 'Pantau listrik rumah lebih tenang dan akurat',
}) {
  const [authTab, setAuthTab] = useState('login')
  const [viewMode, setViewMode] = useState(() => (initialResetToken ? 'reset' : 'auth'))
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [localAgreed, setLocalAgreed] = useState(termsAccepted)
  const [localError, setLocalError] = useState(null)
  const [localSuccess, setLocalSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [gsiReady, setGsiReady] = useState(false)

  const gsiBtnWrapRef = useRef(null)
  const agreedRef = useRef(localAgreed)
  const onGoogleLoginRef = useRef(onGoogleLogin)

  useEffect(() => {
    agreedRef.current = localAgreed
  }, [localAgreed])

  useEffect(() => {
    onGoogleLoginRef.current = onGoogleLogin
  }, [onGoogleLogin])

  useEffect(() => {
    setLocalAgreed(termsAccepted)
  }, [termsAccepted])

  useEffect(() => {
    if (!registrationEnabled && authTab === 'register') {
      setAuthTab('login')
    }
  }, [registrationEnabled, authTab])

  useEffect(() => {
    if (initialResetToken) {
      setViewMode('reset')
      setLocalError(null)
      setLocalSuccess('')
    }
  }, [initialResetToken])

  useEffect(() => {
    const cleanCid = String(googleClientId || '').trim()
    if (!googleEnabled || !cleanCid || !onGoogleLoginRef.current || Capacitor.isNativePlatform()) {
      setGsiReady(false)
      return undefined
    }

    let cancelled = false
    loadGoogleGsiScript()
      .then((gsiId) => {
        if (cancelled || !gsiId || !gsiBtnWrapRef.current) return
        gsiId.initialize({
          client_id: cleanCid,
          ux_mode: 'popup',
          callback: async (resp) => {
            if (!agreedRef.current) {
              setLocalError(
                'Centang persetujuan Syarat Penggunaan & Kebijakan Privasi terlebih dahulu.'
              )
              return
            }
            const idToken = resp?.credential
            if (!idToken) {
              setLocalError('Google tidak mengembalikan ID Token yang valid.')
              return
            }
            setLocalError(null)
            setGoogleLoading(true)
            try {
              await onGoogleLoginRef.current(true, idToken)
            } catch (err) {
              setLocalError(err?.message || 'Gagal masuk menggunakan Google.')
            } finally {
              if (!cancelled) setGoogleLoading(false)
            }
          },
        })
        const container = gsiBtnWrapRef.current
        container.innerHTML = ''
        const targetWidth = Math.max(240, Math.min(360, container.clientWidth || 320))
        gsiId.renderButton(container, {
          type: 'standard',
          theme: theme === 'dark' ? 'filled_black' : 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          logo_alignment: 'left',
          width: targetWidth,
          locale: 'id',
        })
        setGsiReady(true)
      })
      .catch(() => {
        if (!cancelled) setGsiReady(false)
      })

    return () => {
      cancelled = true
    }
  }, [googleEnabled, googleClientId, theme])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLocalError(null)
    setLocalSuccess('')
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
        await onLogin(email.trim(), password, localAgreed)
      } else if (onRegister) {
        await onRegister(name.trim(), email.trim(), password, localAgreed)
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleForgotSubmit = async (e) => {
    e.preventDefault()
    setLocalError(null)
    setLocalSuccess('')
    if (!email.trim()) {
      setLocalError('Masukkan alamat email Anda terlebih dahulu.')
      return
    }
    if (!onForgotPassword) return
    setSubmitting(true)
    try {
      const msg = await onForgotPassword(email.trim())
      setLocalSuccess(
        msg ||
          'Jika email terdaftar di VoltKu, tautan reset kata sandi telah dikirim dan berlaku 30 menit.'
      )
    } catch (err) {
      setLocalError(err?.message || 'Gagal mengirim permintaan reset kata sandi.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleResetSubmit = async (e) => {
    e.preventDefault()
    setLocalError(null)
    setLocalSuccess('')
    if (newPassword.length < 6) {
      setLocalError('Kata sandi baru minimal 6 karakter.')
      return
    }
    if (newPassword !== confirmPassword) {
      setLocalError('Konfirmasi kata sandi tidak cocok.')
      return
    }
    if (!onResetPassword || !initialResetToken) return
    setSubmitting(true)
    try {
      const msg = await onResetPassword(initialResetToken, newPassword)
      if (onClearResetToken) onClearResetToken()
      setNewPassword('')
      setConfirmPassword('')
      setPassword('')
      setAuthTab('login')
      setViewMode('auth')
      setLocalSuccess(msg || 'Kata sandi berhasil diperbarui. Silakan masuk dengan sandi baru Anda.')
    } catch (err) {
      setLocalError(err?.message || 'Gagal mengatur ulang kata sandi.')
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
      await onGoogleLogin(localAgreed)
    } catch (err) {
      setLocalError(err?.message || 'Gagal masuk menggunakan Google.')
    } finally {
      setGoogleLoading(false)
    }
  }

  const handleInputFocus = (e) => {
    const target = e.currentTarget
    if (!target || typeof target.scrollIntoView !== 'function') return
    window.setTimeout(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 240)
  }

  const displayError = localError || error
  const useWebGsi = !Capacitor.isNativePlatform() && googleEnabled && Boolean(googleClientId)

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
        {canClose && onClose && (
          <div className="native-auth-top-bar">
            <span />
            <div className="native-auth-top-right">
              <button
                type="button"
                className="btn-icon-close"
                onClick={onClose}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>
          </div>
        )}

        <div className="auth-header">
          <div className="auth-brand-hero">
            <BrandLogo
              theme={theme}
              displayMode={brandDisplay}
              appName={appName}
              variant="hero"
            />
          </div>
          <p className="auth-subtitle">{subtitle}</p>
        </div>

        {viewMode === 'forgot' && (
          <div className="auth-sub-view">
            <button
              type="button"
              className="auth-back-link"
              onClick={() => {
                setViewMode('auth')
                setLocalError(null)
                setLocalSuccess('')
              }}
            >
              <ArrowLeft size={14} />
              <span>Kembali ke Masuk</span>
            </button>

            <div className="auth-sub-panel-head">
              <span className="auth-sub-icon-box">
                <Mail size={18} />
              </span>
              <div>
                <h3 className="auth-sub-title">Lupa Kata Sandi?</h3>
                <p className="auth-sub-desc">
                  Masukkan email akun Anda. Kami akan mengirimkan tautan reset ke kotak masuk Anda.
                </p>
              </div>
            </div>

            <form onSubmit={handleForgotSubmit}>
              <div className="form-field-group">
                <label className="field-label" htmlFor="forgot-email-input">
                  Email Terdaftar
                </label>
                <input
                  type="email"
                  id="forgot-email-input"
                  className="modern-input"
                  placeholder="nama@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  autoFocus
                />
              </div>

              {displayError && <div className="feedback-msg error">{displayError}</div>}
              {localSuccess && <div className="feedback-msg success">{localSuccess}</div>}

              <button
                type="submit"
                className="btn btn-primary auth-submit-pill"
                style={{ width: '100%', padding: '12px 18px', fontSize: '15px' }}
                disabled={submitting}
              >
                <span>{submitting ? 'Mengirim Tautan...' : 'Kirim Tautan Reset'}</span>
                {!submitting && <ArrowRight size={17} />}
              </button>
            </form>
          </div>
        )}

        {viewMode === 'reset' && (
          <div className="auth-sub-view">
            <button
              type="button"
              className="auth-back-link"
              onClick={() => {
                if (onClearResetToken) onClearResetToken()
                setViewMode('auth')
                setLocalError(null)
              }}
            >
              <ArrowLeft size={14} />
              <span>Batal &amp; Kembali ke Masuk</span>
            </button>

            <div className="auth-sub-panel-head">
              <span className="auth-sub-icon-box">
                <KeyRound size={18} />
              </span>
              <div>
                <h3 className="auth-sub-title">Atur Ulang Kata Sandi</h3>
                <p className="auth-sub-desc">
                  Buat kata sandi baru minimal 6 karakter untuk akun VoltKu Anda.
                </p>
              </div>
            </div>

            <form onSubmit={handleResetSubmit}>
              <div className="form-field-group">
                <label className="field-label" htmlFor="reset-pass-input">
                  Kata Sandi Baru
                </label>
                <input
                  type="password"
                  id="reset-pass-input"
                  className="modern-input"
                  placeholder="Minimal 6 karakter"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  minLength={6}
                  required
                  autoComplete="new-password"
                  autoFocus
                />
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="reset-confirm-input">
                  Ulangi Kata Sandi Baru
                </label>
                <input
                  type="password"
                  id="reset-confirm-input"
                  className="modern-input"
                  placeholder="Ketik ulang kata sandi baru"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  minLength={6}
                  required
                  autoComplete="new-password"
                />
              </div>

              {displayError && <div className="feedback-msg error">{displayError}</div>}

              <button
                type="submit"
                className="btn btn-primary auth-submit-pill"
                style={{ width: '100%', padding: '12px 18px', fontSize: '15px' }}
                disabled={submitting}
              >
                <span>{submitting ? 'Menyimpan...' : 'Simpan Kata Sandi Baru'}</span>
                {!submitting && <ArrowRight size={17} />}
              </button>
            </form>
          </div>
        )}

        {viewMode === 'auth' && registrationEnabled && (
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
        )}

        {viewMode === 'auth' && (
          <>
        <form onSubmit={handleSubmit}>
          {authTab === 'register' && registrationEnabled && (
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
                onFocus={handleInputFocus}
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
              onFocus={handleInputFocus}
              required
              autoComplete="email"
              autoFocus={authTab === 'login' && !Capacitor.isNativePlatform()}
            />
          </div>

          <div className="form-field-group">
            <div className="auth-label-row">
              <label className="field-label" htmlFor="password-input" style={{ marginBottom: 0 }}>
                Kata Sandi
              </label>
              {authTab === 'login' && onForgotPassword && (
                <button
                  type="button"
                  className="auth-forgot-link"
                  onClick={() => {
                    setViewMode('forgot')
                    setLocalError(null)
                    setLocalSuccess('')
                  }}
                >
                  Lupa kata sandi?
                </button>
              )}
            </div>
            <input
              type="password"
              id="password-input"
              className="modern-input"
              placeholder={authTab === 'register' ? 'Minimal 6 karakter' : 'Masukkan kata sandi'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={handleInputFocus}
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
          {localSuccess && <div className="feedback-msg success">{localSuccess}</div>}

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
                : authTab === 'register' && registrationEnabled
                  ? 'Buat Akun Sekarang'
                  : 'Masuk'}
            </span>
            {!submitting && <ArrowRight size={17} />}
          </button>
        </form>

        {viewMode === 'auth' && googleEnabled && onGoogleLogin && (
          <>
            <div className="auth-divider-or">
              <span>atau</span>
            </div>

            {useWebGsi && (
              <div className={`google-gsi-wrap ${gsiReady ? 'is-ready' : 'is-hidden'}`}>
                <div ref={gsiBtnWrapRef} className="google-gsi-slot" />
                {!localAgreed && (
                  <button
                    type="button"
                    className="google-gsi-gate-overlay"
                    aria-label="Setujui ketentuan sebelum masuk dengan Google"
                    onClick={() =>
                      setLocalError(
                        'Centang persetujuan Syarat Penggunaan & Kebijakan Privasi terlebih dahulu.'
                      )
                    }
                  />
                )}
              </div>
            )}

            {(!useWebGsi || !gsiReady) && (
              <button
                type="button"
                className="google-auth-btn"
                onClick={handleGoogleClick}
                disabled={submitting || googleLoading}
              >
                <GoogleIconSvg />
                <span>
                  {googleLoading ? 'Menghubungkan ke Google...' : 'Lanjutkan dengan Google'}
                </span>
              </button>
            )}
          </>
        )}

        {viewMode === 'auth' && onTryGuest && (
          <div className="native-try-guest-wrap">
            <button type="button" className="native-try-guest-btn" onClick={onTryGuest}>
              <span className="native-try-guest-circle">
                <UserCheck size={18} />
              </span>
              <span className="native-try-guest-label">Lanjut sebagai Tamu</span>
            </button>
          </div>
        )}
          </>
        )}
      </div>
    </div>
  )
}
