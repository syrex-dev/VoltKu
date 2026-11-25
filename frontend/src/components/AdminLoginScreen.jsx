import React, { useState } from 'react'
import { Shield, ArrowRight, ArrowLeft } from 'lucide-react'

export function AdminLoginScreen({ onAdminLogin, error }) {
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
          <div className="clean-app-logo">
            <Shield size={26} />
          </div>
          <span className="admin-login-pill">Portal Operator</span>
          <h2 className="auth-title">Admin VoltKu</h2>
          <p className="auth-subtitle">
            Masuk dengan kata sandi pengelola untuk mengatur tenant pengguna, inventaris unit, dan sistem.
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

