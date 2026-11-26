import React, { useState, useEffect, useMemo } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Check,
  Eye,
  EyeOff,
  KeyRound,
  Mail,
  AlertTriangle,
  ShieldCheck,
  Clock,
  Info,
  LogIn,
} from 'lucide-react'
import { apiRequest, setStoredUserToken } from '../api/client'
import { BrandLogo } from './BrandLogo'

const WEAK_PASSWORDS = new Set(['123456', '12345678', 'password', 'qwerty', 'admin123', 'abcdef'])

function evaluatePasswordStrength(pw = '') {
  if (!pw) return { score: 0, label: '', tone: 'none' }
  let pts = 0
  if (pw.length >= 6) pts += 1
  if (pw.length >= 8) pts += 1
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) pts += 1
  if (/[0-9]/.test(pw) || /[^A-Za-z0-9]/.test(pw)) pts += 1
  if (WEAK_PASSWORDS.has(pw.trim().toLowerCase())) pts = 1

  if (pts <= 1) return { score: 25, label: 'Lemah', tone: 'weak' }
  if (pts === 2) return { score: 50, label: 'Cukup', tone: 'fair' }
  if (pts === 3) return { score: 78, label: 'Kuat', tone: 'good' }
  return { score: 100, label: 'Sangat Kuat', tone: 'strong' }
}

function formatRemainingMins(sec) {
  const s = Math.max(0, Number(sec) || 0)
  const m = Math.ceil(s / 60)
  if (m <= 1) return '< 1 menit'
  return `${m} menit`
}

export function ResetPasswordScreen({
  initialToken = '',
  theme = 'light',
  appName = 'VoltKu',
  brandDisplay = 'logo_only',
}) {
  const [token] = useState(() => (initialToken || '').trim())
  const [tokenCheck, setTokenCheck] = useState(() => ({
    loading: Boolean((initialToken || '').trim()),
    valid: Boolean((initialToken || '').trim()),
    reason: (initialToken || '').trim() ? '' : 'missing_or_invalid',
    emailMasked: '',
    expiresInSec: 0,
  }))

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showNewPass, setShowNewPass] = useState(false)
  const [showConfirmPass, setShowConfirmPass] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [sameAsOldNotice, setSameAsOldNotice] = useState('')
  const [resetDone, setResetDone] = useState(false)

  // Request new link mode (when token missing, used, or expired)
  const [requestMode, setRequestMode] = useState(!token)
  const [forgotEmail, setForgotEmail] = useState('')
  const [sendingLink, setSendingLink] = useState(false)
  const [linkSentMsg, setLinkSentMsg] = useState('')

  useEffect(() => {
    if (!token) return
    let active = true
    apiRequest(`/api/users/reset-password/status?token=${encodeURIComponent(token)}`)
      .then((res) => {
        if (!active) return
        if (res?.valid) {
          setTokenCheck({
            loading: false,
            valid: true,
            reason: '',
            emailMasked: res.email_masked || '',
            expiresInSec: Number(res.expires_in_seconds || 0),
          })
        } else {
          setTokenCheck({
            loading: false,
            valid: false,
            reason: res?.reason || 'invalid',
            emailMasked: '',
            expiresInSec: 0,
          })
          setRequestMode(true)
        }
      })
      .catch(() => {
        if (!active) return
        setTokenCheck((prev) => ({ ...prev, loading: false }))
      })
    return () => {
      active = false
    }
  }, [token])

  const strength = useMemo(() => evaluatePasswordStrength(newPassword), [newPassword])
  const hasMinLen = newPassword.length >= 6
  const notWeak = !WEAK_PASSWORDS.has(newPassword.trim().toLowerCase())
  const hasMatch = Boolean(newPassword && confirmPassword && newPassword === confirmPassword)

  const handleSubmitReset = async (e) => {
    e.preventDefault()
    setError('')
    setSameAsOldNotice('')
    if (!hasMinLen) {
      setError('Kata sandi baru minimal 6 karakter.')
      return
    }
    if (!notWeak) {
      setError('Kata sandi terlalu umum. Gunakan kombinasi huruf dan angka yang lebih aman.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Konfirmasi kata sandi baru tidak cocok.')
      return
    }
    setSubmitting(true)
    try {
      await apiRequest('/api/users/reset-password', {
        method: 'POST',
        body: { token, new_password: newPassword },
      })
      setStoredUserToken('')
      setResetDone(true)
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      if (err?.reason === 'same_as_old_password') {
        setSameAsOldNotice(
          err.message ||
            'Jangan sama dengan kata sandi lama Anda. Kata sandi tersebut masih aktif dan bisa langsung dipakai untuk masuk.'
        )
      } else {
        setError(err.message || 'Tautan reset tidak valid atau sudah kedaluwarsa.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleSendNewLink = async (e) => {
    e.preventDefault()
    setError('')
    setLinkSentMsg('')
    if (!forgotEmail.trim()) return
    setSendingLink(true)
    try {
      const res = await apiRequest('/api/users/forgot-password', {
        method: 'POST',
        body: { email: forgotEmail.trim() },
      })
      setLinkSentMsg(
        res?.message ||
          'Jika email terdaftar, tautan pengaturan ulang kata sandi telah dikirim ke email Anda.'
      )
    } catch (err) {
      setError(err.message || 'Gagal mengirim tautan reset kata sandi.')
    } finally {
      setSendingLink(false)
    }
  }

  const expiredOrUsedHeading =
    tokenCheck.reason === 'used'
      ? 'Tautan Sudah Pernah Dipakai'
      : tokenCheck.reason === 'expired'
        ? 'Tautan Reset Kedaluwarsa'
        : !token
          ? 'Tautan Reset Tidak Ditemukan'
          : 'Tautan Reset Tidak Valid'

  const expiredOrUsedDesc =
    tokenCheck.reason === 'used'
      ? 'Tautan reset ini hanya berlaku sekali pakai dan sudah digunakan sebelumnya. Minta tautan baru di bawah ini bila masih perlu.'
      : tokenCheck.reason === 'expired'
        ? 'Batas waktu 30 menit untuk tautan reset ini telah habis. Masukkan email Anda untuk mengirim tautan baru.'
        : `Masukkan alamat email akun ${appName} Anda untuk menerima tautan pengaturan ulang kata sandi baru.`

  return (
    <div className="auth-hero-backdrop clean-auth-bg reset-page-wrap">
      <div className="auth-card-modern clean-auth-card reset-page-card">
        <div className="auth-header reset-page-brand-head">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
            <BrandLogo
              theme={theme}
              displayMode={brandDisplay}
              appName={appName}
              variant="hero"
            />
          </div>
          <span className="reset-security-pill">Keamanan Akun</span>
        </div>

        {resetDone ? (
          <div className="reset-standalone-state">
            <div className="reset-standalone-icon is-success">
              <CheckCircle2 size={30} />
            </div>
            <h1 className="auth-title" style={{ textAlign: 'center' }}>
              Kata Sandi Diperbarui
            </h1>
            <p className="auth-subtitle" style={{ textAlign: 'center', marginBottom: 18 }}>
              Kata sandi akun {appName} Anda sudah berhasil diganti. Silakan masuk kembali
              menggunakan kata sandi baru Anda.
            </p>
            <a
              href="/?open_login=1"
              className="btn btn-primary auth-submit-pill"
              style={{ width: '100%', padding: '12px 18px', fontSize: 15 }}
            >
              <span>Masuk ke {appName}</span>
              <ArrowRight size={17} />
            </a>
          </div>
        ) : requestMode || !tokenCheck.valid ? (
          <div className="auth-sub-view">
            <div className="auth-sub-panel-head">
              <span className={`auth-sub-icon-box ${!tokenCheck.valid && token ? 'is-warn' : ''}`}>
                {!tokenCheck.valid ? <AlertTriangle size={18} /> : <Mail size={18} />}
              </span>
              <div>
                <h1 className="auth-sub-title">
                  {!tokenCheck.valid ? expiredOrUsedHeading : 'Kirim Tautan Reset Baru'}
                </h1>
                <p className="auth-sub-desc">{expiredOrUsedDesc}</p>
              </div>
            </div>

            <form onSubmit={handleSendNewLink}>
              <div className="form-field-group">
                <label className="field-label" htmlFor="standalone-forgot-email">
                  Email Akun
                </label>
                <input
                  id="standalone-forgot-email"
                  type="email"
                  className="modern-input"
                  placeholder="nama@email.com"
                  value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  required
                  autoComplete="email"
                  autoFocus
                />
              </div>

              {error && <div className="feedback-msg error">{error}</div>}
              {linkSentMsg && <div className="feedback-msg success">{linkSentMsg}</div>}

              <button
                type="submit"
                className="btn btn-primary auth-submit-pill"
                style={{ width: '100%', padding: '12px 18px', fontSize: 15 }}
                disabled={sendingLink}
              >
                <span>{sendingLink ? 'Mengirim Tautan...' : 'Kirim Tautan Reset'}</span>
                {!sendingLink && <ArrowRight size={17} />}
              </button>
            </form>

            {token && tokenCheck.valid && (
              <button
                type="button"
                className="auth-back-link"
                style={{ marginTop: 14, marginBottom: 0 }}
                onClick={() => {
                  setRequestMode(false)
                  setError('')
                }}
              >
                <ArrowLeft size={14} />
                <span>Kembali ke form kata sandi baru</span>
              </button>
            )}

            <div className="reset-standalone-footer-bar">
              <a href="/?open_login=1" className="auth-forgot-link" style={{ textDecoration: 'none' }}>
                Halaman Masuk
              </a>
              <a href="/" className="auth-forgot-link" style={{ textDecoration: 'none' }}>
                Beranda {appName}
              </a>
            </div>
          </div>
        ) : (
          <div className="auth-sub-view">
            <div className="auth-sub-panel-head">
              <span className="auth-sub-icon-box">
                <KeyRound size={18} />
              </span>
              <div>
                <h1 className="auth-sub-title">Atur Ulang Kata Sandi</h1>
                <p className="auth-sub-desc">
                  Buat kata sandi baru yang berbeda dari kata sandi sebelumnya.
                </p>
              </div>
            </div>

            {(tokenCheck.emailMasked || tokenCheck.expiresInSec > 0) && (
              <div className="reset-account-meta-bar">
                <span className="reset-account-chip">
                  <ShieldCheck size={13} />
                  <span>{tokenCheck.emailMasked || 'Tautan Terverifikasi'}</span>
                </span>
                {tokenCheck.expiresInSec > 0 && (
                  <span className="reset-expiry-chip num-tabular">
                    <Clock size={12} />
                    <span>Berlaku {formatRemainingMins(tokenCheck.expiresInSec)}</span>
                  </span>
                )}
              </div>
            )}

            {sameAsOldNotice && (
              <div className="reset-old-pass-alert" role="alert">
                <div className="reset-old-pass-head">
                  <Info size={16} />
                  <span>Jangan sama dengan kata sandi lama</span>
                </div>
                <p className="reset-old-pass-desc">{sameAsOldNotice}</p>
                <div className="reset-old-pass-actions">
                  <a href="/?open_login=1" className="btn btn-primary btn-compact">
                    <LogIn size={14} />
                    <span>Langsung Masuk Pakai Sandi Ini</span>
                  </a>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmitReset}>
              <div className="form-field-group">
                <label className="field-label" htmlFor="standalone-reset-pass">
                  Kata Sandi Baru
                </label>
                <div className="admin-pass-wrap">
                  <input
                    id="standalone-reset-pass"
                    type={showNewPass ? 'text' : 'password'}
                    className="modern-input"
                    placeholder="Minimal 6 karakter"
                    value={newPassword}
                    onChange={(e) => {
                      setNewPassword(e.target.value)
                      if (sameAsOldNotice) setSameAsOldNotice('')
                      if (error) setError('')
                    }}
                    minLength={6}
                    required
                    autoComplete="new-password"
                    autoFocus
                  />
                  <button
                    type="button"
                    className="admin-pass-eye"
                    onClick={() => setShowNewPass((p) => !p)}
                    aria-label={showNewPass ? 'Sembunyikan sandi' : 'Tampilkan sandi'}
                  >
                    {showNewPass ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>

                {newPassword.length > 0 && (
                  <div className="reset-strength-box">
                    <div className="reset-strength-track">
                      <div
                        className={`reset-strength-fill is-${strength.tone}`}
                        style={{ width: `${strength.score}%` }}
                      />
                    </div>
                    <span className={`reset-strength-label is-${strength.tone}`}>
                      {strength.label}
                    </span>
                  </div>
                )}
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="standalone-reset-confirm">
                  Ulangi Kata Sandi Baru
                </label>
                <div className="admin-pass-wrap">
                  <input
                    id="standalone-reset-confirm"
                    type={showConfirmPass ? 'text' : 'password'}
                    className="modern-input"
                    placeholder="Ketik ulang kata sandi baru"
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value)
                      if (error) setError('')
                    }}
                    minLength={6}
                    required
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="admin-pass-eye"
                    onClick={() => setShowConfirmPass((p) => !p)}
                    aria-label={showConfirmPass ? 'Sembunyikan konfirmasi' : 'Tampilkan konfirmasi'}
                  >
                    {showConfirmPass ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div className="reset-rules-row">
                <span className={`reset-rule-item ${hasMinLen ? 'ok' : ''}`}>
                  <Check size={12} /> Minimal 6 karakter
                </span>
                <span className={`reset-rule-item ${newPassword && notWeak ? 'ok' : ''}`}>
                  <Check size={12} /> Bukan sandi umum
                </span>
                <span className={`reset-rule-item ${hasMatch ? 'ok' : ''}`}>
                  <Check size={12} /> Konfirmasi cocok
                </span>
              </div>

              {error && <div className="feedback-msg error">{error}</div>}

              <button
                type="submit"
                className="btn btn-primary auth-submit-pill"
                style={{ width: '100%', padding: '12px 18px', fontSize: 15, marginTop: 4 }}
                disabled={submitting || tokenCheck.loading}
              >
                <span>{submitting ? 'Menyimpan...' : 'Simpan Kata Sandi Baru'}</span>
                {!submitting && <ArrowRight size={17} />}
              </button>
            </form>

            <div className="reset-standalone-footer-bar">
              <button
                type="button"
                className="auth-forgot-link"
                onClick={() => {
                  setRequestMode(true)
                  setError('')
                }}
              >
                Minta tautan baru
              </button>
              <a href="/" className="auth-forgot-link" style={{ textDecoration: 'none' }}>
                Beranda {appName}
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
