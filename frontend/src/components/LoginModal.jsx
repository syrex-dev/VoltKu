import React, { useState } from 'react'
import { Lock, Zap, ArrowRight } from 'lucide-react'

export function LoginModal({ onLogin, error }) {
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!password.trim()) return
    setSubmitting(true)
    try {
      await onLogin(password)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-hero-backdrop">
      <div className="auth-card-modern">
        <div className="auth-header">
          <div className="auth-icon-halo">
            <Zap size={28} />
          </div>
          <h2 className="auth-title">Monitor Listrik Pintar</h2>
          <p className="auth-subtitle">Sistem Monitoring Energi IoT & Deteksi Anomali AI</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-field-group">
            <label className="field-label" htmlFor="password-input">
              Kata Sandi Dashboard
            </label>
            <div className="input-affix-wrap">
              <input
                type="password"
                id="password-input"
                className="modern-input"
                placeholder="Masukkan kata sandi otorisasi"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                autoFocus
              />
            </div>
          </div>

          {error && <div className="feedback-msg error">{error}</div>}

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', padding: '11px', marginTop: 8 }}
            disabled={submitting}
          >
            <span>{submitting ? 'Memverifikasi...' : 'Buka Dashboard'}</span>
            <ArrowRight size={16} />
          </button>
        </form>
      </div>
    </div>
  )
}
