import React, { useState, useEffect } from 'react'
import { X, Server, CheckCircle2, AlertCircle, RotateCcw, Loader2 } from 'lucide-react'
import { getApiBaseUrl, setApiBaseUrl, normalizeServerUrl, isNativeApp } from '../api/client'

export function ServerConfigModal({ isOpen, onClose, onSaved }) {
  const [serverInput, setServerInput] = useState('')
  const [testing, setTesting] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)

  useEffect(() => {
    if (isOpen) {
      setServerInput(getApiBaseUrl())
      setStatusMsg(null)
    }
  }, [isOpen])

  if (!isOpen) return null

  const nativeMode = isNativeApp()

  const handleTest = async () => {
    const clean = normalizeServerUrl(serverInput)
    const testTarget = clean ? `${clean}/healthz` : '/healthz'
    setTesting(true)
    setStatusMsg(null)
    try {
      const resp = await fetch(testTarget, { method: 'GET' })
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`)
      }
      const data = await resp.json()
      if (data?.status === 'ok') {
        setStatusMsg({
          type: 'success',
          text: clean
            ? `Terhubung ke server VoltKu (${clean}).`
            : 'Terhubung ke server Web saat ini.',
        })
      } else {
        throw new Error('Respons tidak dikenali.')
      }
    } catch (err) {
      setStatusMsg({
        type: 'error',
        text: `Gagal terhubung ke ${clean || 'server'}: ${err.message || 'Timeout'}`,
      })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = (e) => {
    e.preventDefault()
    const saved = setApiBaseUrl(serverInput)
    if (onSaved) onSaved(saved)
    if (onClose) onClose()
  }

  const handleReset = () => {
    setApiBaseUrl('')
    setServerInput('')
    setStatusMsg({ type: 'success', text: 'Dikembalikan ke mode otomatis (origin web).' })
    if (onSaved) onSaved('')
  }

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div className="modal-dialog-modern" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header-modern">
          <div className="modal-title-group">
            <Server size={20} className="modal-title-icon" />
            <div>
              <h3 className="modal-title-text">Alamat Server Backend</h3>
              <div className="wizard-subtitle">
                {nativeMode
                  ? 'Wajib diisi untuk aplikasi Android (.apk)'
                  : 'Opsional (otomatis di Web)'}
              </div>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSave}>
          <div className="form-field-group">
            <label className="field-label" htmlFor="voltku-server-url-input">
              URL Server VoltKu (LAN atau Remote Tunnel)
            </label>
            <input
              id="voltku-server-url-input"
              type="text"
              className="modern-input"
              placeholder="Contoh: https://voltku-anda.trycloudflare.com"
              value={serverInput}
              onChange={(e) => setServerInput(e.target.value)}
            />
            <small className="field-hint">
              Bisa berupa IP rumah (<code>http://192.168.1.10:8000</code>) atau URL HTTPS
              dari <code>buka_akses_luar_rumah.bat</code>. Kosongkan jika dibuka di browser Web.
            </small>
          </div>

          {statusMsg && (
            <div className={`feedback-msg ${statusMsg.type === 'error' ? 'error' : 'success'}`}>
              {statusMsg.type === 'error' ? (
                <AlertCircle size={15} style={{ flexShrink: 0 }} />
              ) : (
                <CheckCircle2 size={15} style={{ flexShrink: 0 }} />
              )}
              <span>{statusMsg.text}</span>
            </div>
          )}

          <div className="server-modal-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleTest}
              disabled={testing}
            >
              {testing ? <Loader2 size={15} className="spin" /> : null}
              <span>{testing ? 'Menguji...' : 'Tes Koneksi'}</span>
            </button>

            {!nativeMode && serverInput && (
              <button type="button" className="btn btn-secondary" onClick={handleReset}>
                <RotateCcw size={15} />
                <span>Otomatis</span>
              </button>
            )}

            <button type="submit" className="btn btn-primary" style={{ marginLeft: 'auto' }}>
              Simpan
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

