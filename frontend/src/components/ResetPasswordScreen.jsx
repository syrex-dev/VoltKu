import React, { useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Mail,
  AlertTriangle,
} from 'lucide-react'
import { apiRequest, setStoredUserToken } from '../api/client'
import { BrandLogo } from './BrandLogo'

export function ResetPasswordScreen({
  initialToken = '',
  theme = 'light',
  appName = 'VoltKu',
  brandDisplay = 'logo_only',
}) {
  const [token] = useState(() => (initialToken || '').trim())
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [resetDone, setResetDone] = useState(false)

  // Request new link mode (when token missing or expired)
  const [requestMode, setRequestMode] = useState(!token)
  const [forgotEmail, setForgotEmail] = useState('')
  const [sendingLink, setSendingLink] = useState(false)
  const [linkSentMsg, setLinkSentMsg] = useState('')

  const handleSubmitReset = async (e) => {
    e.preventDefault()
    setError('')
    if (newPassword.length < 6) {
      setError('Kata sandi baru minimal 6 karakter.')
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
      setError(err.message || 'Tautan reset tidak valid atau sudah kedaluwarsa.')
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

  return (
    <div className="auth-hero-backdrop clean-auth-bg">
      <div className="auth-card-modern clean-auth-card">
        <div className="auth-header">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
            <BrandLogo
              theme={theme}
              displayMode={brandDisplay}
              appName={appName}
              variant="hero"
            />
          </div>
        </div>

        {resetDone ? (
          <div className="reset-standalone-state">
            <div className="reset-standalone-icon is-success">
              <CheckCircle2 size={28} />
            </div>
            <h2 className="auth-title" style={{ textAlign: 'center' }}>
              Kata Sandi Diperbarui
            </h2>
            <p className="auth-subtitle" style={{ textAlign: 'center', marginBottom: 18 }}>
              Kata sandi akun {appName} Anda sudah diganti. Silakan masuk kembali menggunakan kata
              sandi baru.
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
        ) : requestMode || !token ? (
          <div className="auth-sub-view">
            <div className="auth-sub-panel-head">
              <span className="auth-sub-icon-box">
                {!token ? <AlertTriangle size={18} /> : <Mail size={18} />}
              </span>
              <div>
                <h2 className="auth-sub-title">
                  {!token ? 'Tautan Reset Tidak Ditemukan' : 'Kirim Tautan Reset Baru'}
                </h2>
                <p className="auth-sub-desc">
                  Masukkan email akun {appName} Anda untuk menerima tautan pengaturan ulang kata
                  sandi baru.
                </p>
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

            {token && (
              <button
                type="button"
                className="auth-back-link"
                style={{ marginTop: 12, marginBottom: 0 }}
                onClick={() => {
                  setRequestMode(false)
                  setError('')
                }}
              >
                <ArrowLeft size={14} />
                <span>Kembali ke form kata sandi baru</span>
              </button>
            )}

            <a href="/" className="btn btn-secondary admin-back-public-link">
              <ArrowLeft size={15} />
              <span>Kembali ke Beranda {appName}</span>
            </a>
          </div>
        ) : (
          <div className="auth-sub-view">
            <div className="auth-sub-panel-head">
              <span className="auth-sub-icon-box">
                <KeyRound size={18} />
              </span>
              <div>
                <h2 className="auth-sub-title">Atur Ulang Kata Sandi</h2>
                <p className="auth-sub-desc">
                  Buat kata sandi baru minimal 6 karakter untuk akun {appName} Anda.
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmitReset}>
              <div className="form-field-group">
                <label className="field-label" htmlFor="standalone-reset-pass">
                  Kata Sandi Baru
                </label>
                <div className="admin-pass-wrap">
                  <input
                    id="standalone-reset-pass"
                    type={showPass ? 'text' : 'password'}
                    className="modern-input"
                    placeholder="Minimal 6 karakter"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    minLength={6}
                    required
                    autoComplete="new-password"
                    autoFocus
                  />
                  <button
                    type="button"
                    className="admin-pass-eye"
                    onClick={() => setShowPass((p) => !p)}
                    aria-label={showPass ? 'Sembunyikan sandi' : 'Tampilkan sandi'}
                  >
                    {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="standalone-reset-confirm">
                  Ulangi Kata Sandi Baru
                </label>
                <input
                  id="standalone-reset-confirm"
                  type={showPass ? 'text' : 'password'}
                  className="modern-input"
                  placeholder="Ketik ulang kata sandi baru"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  minLength={6}
                  required
                  autoComplete="new-password"
                />
              </div>

              {error && <div className="feedback-msg error">{error}</div>}

              <button
                type="submit"
                className="btn btn-primary auth-submit-pill"
                style={{ width: '100%', padding: '12px 18px', fontSize: 15 }}
                disabled={submitting}
              >
                <span>{submitting ? 'Menyimpan...' : 'Simpan Kata Sandi Baru'}</span>
                {!submitting && <ArrowRight size={17} />}
              </button>
            </form>

            <div className="reset-standalone-footer-links">
              <button
                type="button"
                className="auth-forgot-link"
                onClick={() => {
                  setRequestMode(true)
                  setError('')
                }}
              >
                Tautan kedaluwarsa? Minta tautan baru
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
