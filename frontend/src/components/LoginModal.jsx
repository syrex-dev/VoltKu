import React, { useState } from 'react'
import { Lock, Zap } from 'lucide-react'

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
    <div className="modal-overlay">
      <div className="login-card">
        <div className="login-header">
          <div className="login-icon-wrap">
            <Zap className="login-icon" size={32} />
          </div>
          <h2>Monitor Listrik Pintar</h2>
          <p>Masukkan kata sandi untuk mengakses dashboard</p>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="password-input">Kata Sandi Dashboard</label>
            <div className="input-with-icon">
              <Lock size={18} className="input-icon" />
              <input
                type="password"
                id="password-input"
                placeholder="Masukkan kata sandi"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                autoFocus
              />
            </div>
          </div>
          {error && <div className="error-msg">{error}</div>}
          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? 'Memproses...' : 'Masuk ke Dashboard'}
          </button>
        </form>
      </div>
    </div>
  )
}
