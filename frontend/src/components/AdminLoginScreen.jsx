import React, { useState } from 'react'
import { ArrowRight, ArrowLeft } from 'lucide-react'
import { BrandLogo } from './BrandLogo'

export function AdminLoginScreen({
  onAdminLogin,
  error,
  theme = 'light',
  appName = 'VoltKu',
}) {
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!password.trim()) return
    setSubmitting(true)
    try {
      await onAdminLogin(password)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-hero-backdrop clean-auth-bg">
      <div className="auth-card-modern clean-auth-card">
        <div className="auth-header">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
            <BrandLogo theme={theme} appName={appName} displayMode="logo_only" variant="hero" />
          </div>
          <span className="admin-login-pill">Portal Pengelola</span>
          <h2 className="auth-title">Panel Admin {appName}</h2>
          <p className="auth-subtitle">
            Masuk dengan kata sandi pengelola untuk mengatur pengguna, inventaris unit, serta kebijakan aplikasi.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-field-group">
            <label className="field-label" htmlFor="admin-password-input">
              Kata Sandi Admin
            </label>
            <input
              type="password"
              id="admin-password-input"
              className="modern-input"
              placeholder="Masukkan kata sandi admin"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              autoFocus
            />
          </div>

          {error && <div className="feedback-msg error">{error}</div>}

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', padding: '12px', marginTop: 8, fontSize: 15 }}
            disabled={submitting}
          >
            <span>{submitting ? 'Memeriksa...' : 'Masuk ke Panel Admin'}</span>
            <ArrowRight size={17} />
          </button>

          <a href="/" className="btn btn-secondary admin-back-public-link">
            <ArrowLeft size={15} />
            <span>Kembali ke Halaman Pengguna</span>
          </a>
        </form>
      </div>
    </div>
  )
}
