import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Delete, Fingerprint, Lock, ShieldCheck } from 'lucide-react'
import { checkBiometricCapability, authenticateWithBiometric } from '../utils/biometricAuth'
import { getAppLockConfig, triggerHaptic } from '../utils/userPrefs'

const KEYPAD_DIGITS = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

export function PinKeypad({
  pinLength = 6,
  value = '',
  onChange,
  onComplete,
  status = 'idle',
  disabled = false,
  showBiometricBtn = false,
  biometricBusy = false,
  onTriggerBiometric = null,
}) {
  const pushDigit = useCallback(
    (digit) => {
      if (disabled || value.length >= pinLength) return
      triggerHaptic(8)
      const next = `${value}${digit}`.slice(0, pinLength)
      onChange?.(next)
      if (next.length === pinLength) {
        onComplete?.(next)
      }
    },
    [disabled, value, pinLength, onChange, onComplete]
  )

  const popDigit = useCallback(() => {
    if (disabled || value.length === 0) return
    triggerHaptic(6)
    onChange?.(value.slice(0, -1))
  }, [disabled, value, onChange])

  useEffect(() => {
    const onKeyDown = (e) => {
      if (disabled) return
      if (/^[0-9]$/.test(e.key)) {
        e.preventDefault()
        pushDigit(e.key)
      } else if (e.key === 'Backspace') {
        e.preventDefault()
        popDigit()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [disabled, pushDigit, popDigit])

  const dotCls = status === 'error' ? 'is-error' : status === 'success' ? 'is-success' : ''

  return (
    <div className={`pin-pad-shell ${dotCls}`}>
      <div className="pin-dots-row" aria-label={`PIN ${value.length} dari ${pinLength} digit`}>
        {Array.from({ length: pinLength }, (_, idx) => {
          const filled = idx < value.length
          return (
            <span
              key={idx}
              className={`pin-dot ${filled ? 'is-filled' : ''} ${dotCls}`}
              aria-hidden="true"
            />
          )
        })}
      </div>

      <div className="pin-keypad-grid">
        {KEYPAD_DIGITS.map((digit) => (
          <button
            key={digit}
            type="button"
            disabled={disabled}
            className="pin-key-btn num-tabular"
            onClick={() => pushDigit(digit)}
          >
            {digit}
          </button>
        ))}

        {showBiometricBtn ? (
          <button
            type="button"
            disabled={disabled || biometricBusy}
            className="pin-key-btn is-action is-biometric"
            onClick={() => onTriggerBiometric?.()}
            aria-label="Gunakan Sidik Jari"
            title="Buka dengan Sidik Jari"
          >
            <Fingerprint size={22} />
          </button>
        ) : (
          <span className="pin-key-spacer" aria-hidden="true" />
        )}

        <button
          type="button"
          disabled={disabled}
          className="pin-key-btn num-tabular"
          onClick={() => pushDigit('0')}
        >
          0
        </button>

        <button
          type="button"
          disabled={disabled || value.length === 0}
          className="pin-key-btn is-action"
          onClick={popDigit}
          aria-label="Hapus digit"
          title="Hapus"
        >
          <Delete size={20} />
        </button>
      </div>
    </div>
  )
}

export function AppLockOverlay({
  isOpen,
  currentUser = null,
  userName = 'Pengguna VoltKu',
  userEmail = '',
  onUnlock,
  onResetAndLogout,
  verifyPinFn,
  appName = 'VoltKu',
  theme = 'light',
  BrandLogoComponent = null,
}) {
  const [pinValue, setPinValue] = useState('')
  const [status, setStatus] = useState('idle')
  const [message, setMessage] = useState('Masukkan PIN 6 digit untuk membuka aplikasi')
  const [attempts, setAttempts] = useState(0)
  const [verifying, setVerifying] = useState(false)
  const [biometricBusy, setBiometricBusy] = useState(false)
  const [biometricReady, setBiometricReady] = useState(false)
  const [credentialId, setCredentialId] = useState('')
  const autoPromptedRef = useRef(false)

  const runBiometricUnlock = useCallback(
    async (credIdOverride = '') => {
      const targetCred = credIdOverride || credentialId
      setBiometricBusy(true)
      setStatus('idle')
      setMessage('Tempelkan jari pada sensor perangkat...')
      try {
        const res = await authenticateWithBiometric(targetCred)
        if (res.verified) {
          triggerHaptic(20)
          setStatus('success')
          setMessage('Sidik jari terverifikasi')
          window.setTimeout(() => {
            setPinValue('')
            setStatus('idle')
            setAttempts(0)
            onUnlock?.()
          }, 260)
          return true
        }
        setStatus('idle')
        setMessage(res.error || 'Masukkan PIN 6 digit untuk melanjutkan')
        return false
      } finally {
        setBiometricBusy(false)
      }
    },
    [credentialId, onUnlock]
  )

  useEffect(() => {
    if (!isOpen) {
      autoPromptedRef.current = false
      setPinValue('')
      setStatus('idle')
      setAttempts(0)
      return undefined
    }

    let cancelled = false
    const cfg = getAppLockConfig(currentUser)
    setPinValue('')
    setStatus('idle')
    setVerifying(false)
    setCredentialId(cfg.biometricCredentialId || '')

    checkBiometricCapability().then((cap) => {
      if (cancelled) return
      const canBio = Boolean(cfg.enabled && cfg.biometricEnabled && cap.available)
      setBiometricReady(canBio)
      if (canBio) {
        setMessage('Sentuh sidik jari atau masukkan PIN 6 digit')
        if (!autoPromptedRef.current) {
          autoPromptedRef.current = true
          window.setTimeout(() => {
            if (!cancelled) {
              runBiometricUnlock(cfg.biometricCredentialId || '')
            }
          }, 180)
        }
      } else {
        setMessage('Masukkan PIN 6 digit akun untuk membuka aplikasi')
      }
    })

    return () => {
      cancelled = true
    }
  }, [isOpen, currentUser, runBiometricUnlock])

  if (!isOpen) return null

  const handlePinComplete = async (digits) => {
    if (verifying) return
    setVerifying(true)
    try {
      const res = await verifyPinFn(digits)
      const ok = typeof res === 'boolean' ? res : Boolean(res?.verified)
      if (ok) {
        triggerHaptic(20)
        setStatus('success')
        setMessage('PIN terverifikasi')
        window.setTimeout(() => {
          setPinValue('')
          setStatus('idle')
          setAttempts(0)
          setVerifying(false)
          onUnlock?.()
        }, 240)
      } else {
        triggerHaptic(32)
        const nextAttempts = Number(res?.attempts || attempts + 1)
        setAttempts(nextAttempts)
        setStatus('error')
        setMessage(res?.error || `PIN tidak cocok (percobaan ke-${nextAttempts})`)
        window.setTimeout(() => {
          setPinValue('')
          setStatus('idle')
          setVerifying(false)
        }, 650)
      }
    } catch (err) {
      setStatus('error')
      setMessage(err?.message || 'Gagal memverifikasi PIN.')
      window.setTimeout(() => {
        setPinValue('')
        setStatus('idle')
        setVerifying(false)
      }, 650)
    }
  }

  return (
    <div
      className="app-lock-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Layar Kunci Keamanan"
    >
      <div className="app-lock-card">
        <div className="app-lock-brand">
          {BrandLogoComponent ? (
            <BrandLogoComponent
              theme={theme}
              displayMode="logo_only"
              appName={appName}
              variant="compact"
            />
          ) : (
            <span className="app-lock-brand-fallback">{appName}</span>
          )}
        </div>

        <div className={`app-lock-badge-ring ${status === 'success' ? 'is-success' : ''}`}>
          {status === 'success' ? (
            <ShieldCheck size={22} />
          ) : biometricReady ? (
            <Fingerprint size={22} />
          ) : (
            <Lock size={20} />
          )}
        </div>

        <h2 className="app-lock-title">Aplikasi Terkunci</h2>
        <p className="app-lock-user">
          {userName}
          {userEmail ? ` · ${userEmail}` : ''}
        </p>

        <div
          className={`app-lock-hint ${
            status === 'error' ? 'is-error' : status === 'success' ? 'is-success' : ''
          }`}
        >
          {message}
        </div>

        {biometricReady && (
          <button
            type="button"
            className={`app-lock-bio-pill ${biometricBusy ? 'is-busy' : ''}`}
            disabled={biometricBusy || status === 'success'}
            onClick={() => runBiometricUnlock()}
          >
            <Fingerprint size={16} />
            <span>{biometricBusy ? 'Memindai Sidik Jari...' : 'Gunakan Sidik Jari'}</span>
          </button>
        )}

        <PinKeypad
          pinLength={6}
          value={pinValue}
          onChange={setPinValue}
          onComplete={handlePinComplete}
          status={status}
          disabled={status === 'success' || verifying}
          showBiometricBtn={biometricReady}
          biometricBusy={biometricBusy}
          onTriggerBiometric={() => runBiometricUnlock()}
        />

        {onResetAndLogout && (
          <button type="button" className="app-lock-forgot-btn" onClick={onResetAndLogout}>
            Lupa PIN? Keluar &amp; masuk ulang untuk pulihkan
          </button>
        )}
      </div>
    </div>
  )
}

