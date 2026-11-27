import React, { useState, useMemo, useEffect } from 'react'
import {
  Check,
  ChevronRight,
  Lock,
  Unlock,
  KeyRound,
  Eye,
  EyeOff,
  Search,
  Globe,
  Clock,
  Fingerprint,
  Cpu,
  Wifi,
  BellRing,
  Zap,
  ShieldCheck,
  MessageCircle,
  Send,
  Mail,
  BookOpen,
  Compass,
  Star,
  Copy,
  ExternalLink,
  Award,
  Activity,
  RotateCcw,
  Wallet,
  CalendarClock,
  Info,
  LogOut,
  Plus,
  X,
} from 'lucide-react'
import { BrandLogo } from './BrandLogo'
import { PinKeypad } from './AppLockSecurity'
import { EnergyAssistantIcon, TierShieldIcon } from './VoltKuIcons'
import { apiRequest } from '../api/client'
import { emitSyncSignal } from '../utils/liveSync'
import {
  formatNum,
  formatRp,
  formatDateTimeWIB,
  getPreferredTimeZoneTag,
} from '../utils/formatters'
import {
  checkBiometricCapability,
  enrollBiometricUnlock,
} from '../utils/biometricAuth'
import {
  APP_PACKAGE_ID,
  APP_VERSION_TAG,
  LANGUAGE_OPTIONS,
  TIMEZONE_OPTIONS,
  VOLTKU_CHANGELOG,
  clearAppLock,
  getAppLockConfig,
  getLatestUserFeedback,
  getPreferredTimeZone,
  getTimeZoneShortLabel,
  savePinLock,
  saveUserFeedbackEntry,
  triggerHaptic,
  updateAppLockBiometric,
  verifyPinCode,
} from '../utils/userPrefs'

export function EditNameSubView({
  editName,
  onChangeName,
  feedback,
  locale,
  onSubmit,
}) {
  return (
    <form id="profile-edit-name-form" onSubmit={onSubmit} className="profile-subview-stack">
      {feedback && (
        <div className={`feedback-msg ${feedback.type === 'error' ? 'error' : 'success'}`}>
          {feedback.text}
        </div>
      )}

      <div className="profile-ref-card-group profile-single-input-card">
        <label className="profile-inline-field-label" htmlFor="prof-sub-name-input">
          {locale === 'en' ? 'Name' : 'Nama'}
        </label>
        <input
          id="prof-sub-name-input"
          type="text"
          className="profile-borderless-input"
          placeholder={locale === 'en' ? 'Enter display name' : 'Masukkan nama tampilan'}
          value={editName}
          onChange={(e) => onChangeName(e.target.value)}
          minLength={2}
          maxLength={100}
          required
          autoFocus
        />
        {editName && (
          <button
            type="button"
            className="profile-clear-inline-btn"
            onClick={() => onChangeName('')}
            aria-label="Hapus teks"
          >
            <X size={15} />
          </button>
        )}
      </div>

      <p className="profile-subview-footnote">
        {locale === 'en'
          ? 'This name appears on your account header, reports, and device ownership info.'
          : 'Nama ini tampil di header profil, riwayat tagihan, dan identifikasi pemilik panel.'}
      </p>
    </form>
  )
}

export function PasswordSubView({
  hasLocalPassword,
  currentPassword,
  setCurrentPassword,
  newPassword,
  setNewPassword,
  confirmPassword,
  setConfirmPassword,
  showPasswords,
  setShowPasswords,
  saving,
  feedback,
  onSubmit,
}) {
  return (
    <form onSubmit={onSubmit} className="profile-subview-stack">
      {feedback && (
        <div className={`feedback-msg ${feedback.type === 'error' ? 'error' : 'success'}`}>
          {feedback.text}
        </div>
      )}

      <div className="profile-ref-card-group profile-card-padded">
        <div className="profile-account-sec-head" style={{ marginBottom: 6 }}>
          <KeyRound size={15} />
          <span>{hasLocalPassword ? 'Perbarui Kata Sandi Masuk' : 'Tambah Kata Sandi Lokal'}</span>
          <button
            type="button"
            className="profile-account-eye-btn"
            onClick={() => setShowPasswords((p) => !p)}
            aria-label={showPasswords ? 'Sembunyikan sandi' : 'Tampilkan sandi'}
          >
            {showPasswords ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>

        {!hasLocalPassword && (
          <p className="profile-subcard-hint" style={{ margin: '0 0 8px' }}>
            Akun ini terhubung lewat Google. Tambahkan kata sandi lokal agar tetap bisa masuk
            memakai email kapan saja.
          </p>
        )}

        <div className="profile-account-form">
          {hasLocalPassword && (
            <input
              type={showPasswords ? 'text' : 'password'}
              className="modern-input"
              placeholder="Kata sandi saat ini"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          )}
          <input
            type={showPasswords ? 'text' : 'password'}
            className="modern-input"
            placeholder="Kata sandi baru (minimal 6 karakter)"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={6}
            autoComplete="new-password"
            required
          />
          <input
            type={showPasswords ? 'text' : 'password'}
            className="modern-input"
            placeholder="Ulangi kata sandi baru"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            minLength={6}
            autoComplete="new-password"
            required
          />
          <button type="submit" className="btn btn-primary profile-save-pw-btn" disabled={saving}>
            <KeyRound size={15} />
            <span>
              {saving ? 'Menyimpan...' : hasLocalPassword ? 'Simpan Kata Sandi' : 'Buat Kata Sandi'}
            </span>
          </button>
        </div>
      </div>
    </form>
  )
}

export function AppLockSubView({
  currentUser,
  token = '',
  onLogout,
  onUserUpdated,
  onLockChanged,
  onTestLockScreen,
}) {
  const [lockCfg, setLockCfg] = useState(() => getAppLockConfig(currentUser))
  const [bioCap, setBioCap] = useState({ available: false, status: 'checking', reason: 'Memeriksa dukungan sensor perangkat...' })
  // 'overview' | 'verify_current_for_change' | 'create_step1' | 'create_step2' | 'verify_disable'
  const [mode, setMode] = useState(() => (lockCfg.enabled ? 'overview' : 'create_step1'))
  const [pinInput, setPinInput] = useState('')
  const [verifiedCurrentPin, setVerifiedCurrentPin] = useState('')
  const [draftPin, setDraftPin] = useState('')
  const [padStatus, setPadStatus] = useState('idle')
  const [pinBusy, setPinBusy] = useState(false)
  const [bioBusy, setBioBusy] = useState(false)
  const [showDisableByPassword, setShowDisableByPassword] = useState(false)
  const [disableAccountPassword, setDisableAccountPassword] = useState('')
  const [hintText, setHintText] = useState(() =>
    lockCfg.enabled
      ? 'PIN keamanan 6 digit aktif & tersinkron ke seluruh perangkat akun Anda.'
      : 'Buat PIN 6 digit sebagai kunci pengaman akun di APK maupun Web.'
  )

  useEffect(() => {
    const synced = getAppLockConfig(currentUser)
    setLockCfg(synced)
  }, [currentUser])

  useEffect(() => {
    let cancelled = false
    checkBiometricCapability().then((cap) => {
      if (!cancelled) setBioCap(cap)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const applyServerAppLock = async (appLockMeta, rawPin = '') => {
    let nextCfg
    if (appLockMeta?.pin_enabled && rawPin) {
      nextCfg = await savePinLock(rawPin, {
        userId: currentUser?.id,
        updatedAt: appLockMeta.pin_updated_at,
      })
    } else if (!appLockMeta?.pin_enabled) {
      nextCfg = clearAppLock()
    } else {
      nextCfg = getAppLockConfig({ ...currentUser, app_lock: appLockMeta })
    }
    setLockCfg(nextCfg)
    if (currentUser && onUserUpdated) {
      onUserUpdated({ ...currentUser, app_lock: appLockMeta })
    }
    onLockChanged?.(nextCfg)
    emitSyncSignal('user', { source: 'app-pin-updated' })
    return nextCfg
  }

  const handlePinComplete = async (digits) => {
    if (pinBusy) return

    if (mode === 'verify_current_for_change') {
      setPinBusy(true)
      try {
        const res = await verifyPinCode(digits, { token, currentUser, onUnauthorized: onLogout })
        const ok = typeof res === 'boolean' ? res : Boolean(res?.verified)
        if (!ok) {
          setPadStatus('error')
          setHintText(res?.error || 'PIN aktif tidak cocok. Masukkan PIN saat ini.')
          window.setTimeout(() => {
            setPadStatus('idle')
            setPinInput('')
            setPinBusy(false)
          }, 650)
          return
        }
        setVerifiedCurrentPin(digits)
        setPinInput('')
        setMode('create_step1')
        setPadStatus('success')
        setHintText('PIN lama terverifikasi. Sekarang masukkan PIN 6 digit baru.')
        window.setTimeout(() => {
          setPadStatus('idle')
          setPinBusy(false)
        }, 350)
      } catch (err) {
        setPadStatus('error')
        setHintText(err?.message || 'Gagal memverifikasi PIN saat ini.')
        window.setTimeout(() => {
          setPadStatus('idle')
          setPinInput('')
          setPinBusy(false)
        }, 650)
      }
      return
    }

    if (mode === 'create_step1') {
      setDraftPin(digits)
      setPinInput('')
      setMode('create_step2')
      setPadStatus('success')
      setHintText('Masukkan ulang PIN 6 digit yang sama untuk konfirmasi.')
      window.setTimeout(() => setPadStatus('idle'), 350)
      return
    }

    if (mode === 'create_step2') {
      if (digits !== draftPin) {
        setPadStatus('error')
        setHintText('PIN konfirmasi tidak cocok. Ulangi buat PIN baru.')
        window.setTimeout(() => {
          setPadStatus('idle')
          setPinInput('')
          setDraftPin('')
          setMode('create_step1')
          setHintText('Masukkan PIN 6 digit baru untuk keamanan akun.')
        }, 650)
        return
      }
      setPinBusy(true)
      try {
        let savedMeta = { pin_enabled: true, pin_updated_at: Math.floor(Date.now() / 1000) }
        if (token) {
          const res = await apiRequest(
            '/api/users/pin',
            {
              method: 'POST',
              body: {
                new_pin: digits,
                current_pin: verifiedCurrentPin || null,
              },
            },
            token,
            onLogout
          )
          if (res?.app_lock) savedMeta = res.app_lock
        }
        await applyServerAppLock(savedMeta, digits)
        triggerHaptic(22)
        setPinInput('')
        setDraftPin('')
        setVerifiedCurrentPin('')
        setMode('overview')
        setPadStatus('success')
        setHintText(
          bioCap.available
            ? 'PIN 6 digit aktif & tersinkron! Anda dapat menyalakan Sidik Jari di bawah.'
            : 'PIN 6 digit aktif & otomatis tersinkron ke seluruh perangkat akun Anda!'
        )
        window.setTimeout(() => {
          setPadStatus('idle')
          setPinBusy(false)
        }, 450)
      } catch (err) {
        setPadStatus('error')
        setHintText(err?.message || 'PIN gagal disimpan. Hindari pola angka lemah seperti 123456.')
        window.setTimeout(() => {
          setPadStatus('idle')
          setPinInput('')
          setDraftPin('')
          setMode('create_step1')
          setPinBusy(false)
        }, 900)
      }
      return
    }

    if (mode === 'verify_disable') {
      setPinBusy(true)
      try {
        if (token) {
          const res = await apiRequest(
            '/api/users/pin/disable',
            { method: 'POST', body: { current_pin: digits } },
            token,
            onLogout
          )
          await applyServerAppLock(res?.app_lock || { pin_enabled: false, pin_updated_at: 0 })
        } else {
          const res = await verifyPinCode(digits, { currentUser })
          const ok = typeof res === 'boolean' ? res : Boolean(res?.verified)
          if (!ok) throw new Error('PIN salah.')
          await applyServerAppLock({ pin_enabled: false, pin_updated_at: 0 })
        }
        triggerHaptic(18)
        setPinInput('')
        setDraftPin('')
        setVerifiedCurrentPin('')
        setShowDisableByPassword(false)
        setDisableAccountPassword('')
        setMode('create_step1')
        setHintText('Kunci keamanan dinonaktifkan di semua perangkat. Buat PIN kapan saja untuk mengaktifkan.')
      } catch (err) {
        setPadStatus('error')
        setHintText(err?.message || 'PIN salah. Masukkan PIN aktif untuk menonaktifkan kunci.')
        window.setTimeout(() => {
          setPadStatus('idle')
          setPinInput('')
        }, 650)
      } finally {
        setPinBusy(false)
      }
    }
  }

  const handleDisableWithPassword = async (e) => {
    e.preventDefault()
    if (!token || !disableAccountPassword || pinBusy) return
    setPinBusy(true)
    try {
      const res = await apiRequest(
        '/api/users/pin/disable',
        { method: 'POST', body: { account_password: disableAccountPassword } },
        token,
        onLogout
      )
      await applyServerAppLock(res?.app_lock || { pin_enabled: false, pin_updated_at: 0 })
      triggerHaptic(18)
      setPinInput('')
      setDraftPin('')
      setShowDisableByPassword(false)
      setDisableAccountPassword('')
      setMode('create_step1')
      setHintText('PIN berhasil dinonaktifkan memakai kata sandi akun.')
    } catch (err) {
      setPadStatus('error')
      setHintText(err?.message || 'Kata sandi akun salah.')
    } finally {
      setPinBusy(false)
    }
  }

  const handleToggleBiometric = async () => {
    if (!lockCfg.enabled) return
    if (lockCfg.biometricEnabled) {
      const next = updateAppLockBiometric({
        userId: currentUser?.id,
        biometricEnabled: false,
        biometricCredentialId: '',
        appLock: currentUser?.app_lock,
      })
      triggerHaptic(12)
      setLockCfg(next)
      setHintText('Kunci sidik jari dimatikan; akun tetap aman dengan PIN 6 digit tersinkron.')
      onLockChanged?.(next)
      return
    }

    if (!bioCap.available) {
      setHintText(bioCap.reason || 'Sensor sidik jari belum siap pada perangkat ini.')
      return
    }

    setBioBusy(true)
    try {
      const res = await enrollBiometricUnlock(currentUser?.email || currentUser?.name || 'VoltKu')
      if (res.ok) {
        const next = updateAppLockBiometric({
          userId: currentUser?.id,
          biometricEnabled: true,
          biometricCredentialId: res.credentialId,
          appLock: currentUser?.app_lock,
        })
        triggerHaptic(20)
        setLockCfg(next)
        setHintText('Sidik jari perangkat ini aktif mendampingi PIN 6 digit!')
        onLockChanged?.(next)
      } else {
        setHintText(res.message || 'Sidik jari tidak jadi diaktifkan.')
      }
    } finally {
      setBioBusy(false)
    }
  }

  return (
    <div className="profile-subview-stack">
      <div className="profile-ref-card-group profile-card-padded">
        <div className="profile-pattern-head-row">
          <div className={`profile-ref-row-icon ${lockCfg.enabled ? 'is-emerald' : 'is-slate'}`}>
            {lockCfg.enabled ? <Lock size={17} /> : <Unlock size={17} />}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="profile-ref-row-title">PIN &amp; Sidik Jari Aplikasi</div>
            <div className="profile-ref-row-sub">
              {lockCfg.enabled
                ? lockCfg.biometricEnabled && bioCap.available
                  ? 'Aktif · PIN tersinkron akun + Sidik Jari (perangkat ini)'
                  : 'Aktif · PIN 6 Digit tersinkron ke semua perangkat (PBKDF2)'
                : 'Nonaktif · Lindungi akses akun di APK & Web'}
            </div>
          </div>
          <span className={`profile-ref-badge ${lockCfg.enabled ? 'is-emerald' : 'is-neutral'}`}>
            {lockCfg.enabled ? 'Aktif' : 'Off'}
          </span>
        </div>

        <div className={`profile-bio-cap-banner ${bioCap.available ? 'is-ready' : 'is-pin-only'}`}>
          {bioCap.available ? <Fingerprint size={15} /> : <ShieldCheck size={15} />}
          <span>
            {bioCap.available
              ? lockCfg.enabled && !lockCfg.biometricEnabled
                ? 'PIN Anda sudah tersinkron dari akun. Aktifkan sakelar Sidik Jari di bawah khusus untuk perangkat ini.'
                : bioCap.reason
              : bioCap.reason ||
                'Sensor sidik jari tidak tersedia di perangkat ini — otomatis menggunakan PIN 6 digit tersinkron.'}
          </span>
        </div>
      </div>

      {mode === 'overview' && lockCfg.enabled ? (
        <div className="profile-ref-card-group">
          <button
            type="button"
            role="switch"
            aria-checked={Boolean(lockCfg.biometricEnabled && bioCap.available)}
            disabled={!bioCap.available || bioBusy}
            className="profile-ref-row"
            onClick={handleToggleBiometric}
          >
            <span className={`profile-ref-row-icon ${bioCap.available ? 'is-emerald' : 'is-slate'}`}>
              <Fingerprint size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Buka dengan Sidik Jari (Perangkat Ini)</span>
              <span className="profile-ref-row-sub">
                {bioCap.available
                  ? bioBusy
                    ? 'Memverifikasi sensor sidik jari...'
                    : 'Sidik jari diaktifkan per perangkat; PIN tetap tersinkron di semua perangkat'
                  : 'Perangkat belum mendukung sidik jari — otomatis memakai PIN tersinkron'}
              </span>
            </span>
            <span
              className={`profile-theme-switch ${
                lockCfg.biometricEnabled && bioCap.available ? 'is-on' : ''
              }`}
              aria-hidden="true"
            >
              <span className="profile-theme-knob" />
            </span>
          </button>

          <button
            type="button"
            className="profile-ref-row"
            onClick={() => {
              setPinInput('')
              setDraftPin('')
              setVerifiedCurrentPin('')
              setMode('verify_current_for_change')
              setHintText('Masukkan PIN 6 digit yang sedang aktif saat ini.')
            }}
          >
            <span className="profile-ref-row-icon is-blue">
              <KeyRound size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Ubah PIN 6 Digit</span>
              <span className="profile-ref-row-sub">Perbarui PIN rahasia (tersinkron ke semua perangkat)</span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </button>

          {onTestLockScreen && (
            <button type="button" className="profile-ref-row" onClick={onTestLockScreen}>
              <span className="profile-ref-row-icon is-indigo">
                <Lock size={17} />
              </span>
              <span className="profile-ref-row-text">
                <span className="profile-ref-row-title">Kunci Aplikasi Sekarang</span>
                <span className="profile-ref-row-sub">
                  {lockCfg.biometricEnabled && bioCap.available
                    ? 'Uji layar kunci Sidik Jari & PIN'
                    : 'Uji layar kunci PIN 6 Digit'}
                </span>
              </span>
              <ChevronRight size={16} className="profile-ref-chevron" />
            </button>
          )}

          <button
            type="button"
            className="profile-ref-row"
            onClick={() => {
              setPinInput('')
              setShowDisableByPassword(false)
              setDisableAccountPassword('')
              setMode('verify_disable')
              setHintText('Masukkan PIN aktif untuk menonaktifkan kunci keamanan akun.')
            }}
          >
            <span className="profile-ref-row-icon is-amber">
              <Unlock size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Nonaktifkan Kunci Keamanan</span>
              <span className="profile-ref-row-sub">Memerlukan verifikasi PIN atau kata sandi akun</span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </button>
        </div>
      ) : (
        <div className="profile-ref-card-group profile-pattern-board-card">
          <h4 className="profile-pattern-stage-title">
            {mode === 'verify_disable'
              ? 'Verifikasi Nonaktifkan PIN'
              : mode === 'verify_current_for_change'
                ? 'Verifikasi PIN Saat Ini'
                : mode === 'create_step2'
                  ? 'Konfirmasi PIN 6 Digit'
                  : 'Buat PIN 6 Digit'}
          </h4>
          <p className={`profile-pattern-stage-sub ${padStatus === 'error' ? 'is-error' : ''}`}>
            {hintText}
          </p>

          {!showDisableByPassword ? (
            <PinKeypad
              pinLength={6}
              value={pinInput}
              onChange={setPinInput}
              onComplete={handlePinComplete}
              status={padStatus}
              disabled={padStatus === 'success' || pinBusy}
              showBiometricBtn={false}
            />
          ) : (
            <form onSubmit={handleDisableWithPassword} style={{ width: '100%', maxWidth: 300 }}>
              <input
                type="password"
                className="modern-input"
                placeholder="Masukkan kata sandi akun..."
                value={disableAccountPassword}
                onChange={(e) => setDisableAccountPassword(e.target.value)}
                required
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={pinBusy || !disableAccountPassword}
                style={{ width: '100%', marginTop: 10 }}
              >
                {pinBusy ? 'Memverifikasi...' : 'Matikan PIN'}
              </button>
            </form>
          )}

          <div className="profile-pattern-board-actions">
            {mode === 'verify_disable' && currentUser?.has_local_password !== false && token && (
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                onClick={() => {
                  setShowDisableByPassword((p) => !p)
                  setPadStatus('idle')
                  setHintText(
                    !showDisableByPassword
                      ? 'Masukkan kata sandi login akun untuk mematikan PIN.'
                      : 'Masukkan PIN aktif untuk menonaktifkan kunci keamanan akun.'
                  )
                }}
              >
                <span>{showDisableByPassword ? 'Pakai PIN' : 'Lupa PIN? Pakai Kata Sandi'}</span>
              </button>
            )}
            {(mode === 'create_step2' || (lockCfg.enabled && mode !== 'overview')) && (
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                onClick={() => {
                  setPinInput('')
                  setDraftPin('')
                  setVerifiedCurrentPin('')
                  setShowDisableByPassword(false)
                  setDisableAccountPassword('')
                  setPadStatus('idle')
                  if (lockCfg.enabled) {
                    setMode('overview')
                    setHintText('PIN keamanan 6 digit aktif & tersinkron ke seluruh perangkat akun Anda.')
                  } else {
                    setMode('create_step1')
                    setHintText('Buat PIN 6 digit sebagai kunci pengaman akun di APK maupun Web.')
                  }
                }}
              >
                <RotateCcw size={13} />
                <span>{lockCfg.enabled ? 'Batal' : 'Ulangi'}</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function LanguageSubView({ prefs, updatePrefs }) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return LANGUAGE_OPTIONS
    return LANGUAGE_OPTIONS.filter(
      (item) => item.name.toLowerCase().includes(q) || item.subtitle.toLowerCase().includes(q)
    )
  }, [query])

  return (
    <div className="profile-subview-stack">
      <div className="profile-search-box">
        <Search size={15} className="profile-search-ico" />
        <input
          type="text"
          className="profile-search-input"
          placeholder="Cari bahasa..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <button
            type="button"
            className="profile-clear-inline-btn"
            onClick={() => setQuery('')}
            aria-label="Hapus pencarian"
          >
            <X size={14} />
          </button>
        )}
      </div>

      <div className="profile-ref-card-group">
        {filtered.length === 0 ? (
          <div className="profile-empty-subnote">Bahasa tidak ditemukan.</div>
        ) : (
          filtered.map((lang) => {
            const active = prefs.locale === lang.id
            return (
              <button
                key={lang.id}
                type="button"
                className="profile-ref-row"
                onClick={() => {
                  triggerHaptic(12)
                  updatePrefs({ locale: lang.id })
                }}
              >
                <span className={`profile-lang-badge ${active ? 'is-active' : ''}`}>
                  {lang.badge}
                </span>
                <span className="profile-ref-row-text">
                  <span className="profile-ref-row-title">{lang.name}</span>
                  <span className="profile-ref-row-sub">{lang.subtitle}</span>
                </span>
                {active && <Check size={17} className="profile-check-icon" />}
              </button>
            )
          })
        )}
      </div>

      <p className="profile-subview-footnote">
        Pilihan bahasa langsung memperbarui label menu Profil, Pengaturan, dan tab navigasi utama.
      </p>
    </div>
  )
}

export function TimeZoneSubView({ prefs, updatePrefs, onSyncServerTimezone }) {
  const [query, setQuery] = useState('')
  const [clockMs, setClockMs] = useState(() => Date.now())

  React.useEffect(() => {
    const timerId = window.setInterval(() => {
      setClockMs(Date.now())
    }, 15000)
    return () => window.clearInterval(timerId)
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return TIMEZONE_OPTIONS
    return TIMEZONE_OPTIONS.filter(
      (z) =>
        z.id.toLowerCase().includes(q) ||
        z.zoneLabel.toLowerCase().includes(q) ||
        z.offset.toLowerCase().includes(q)
    )
  }, [query])

  const liveClockPreview = useMemo(() => {
    try {
      return new Intl.DateTimeFormat('id-ID', {
        timeZone: prefs.timezone || 'Asia/Jakarta',
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(clockMs))
    } catch {
      return '-'
    }
  }, [prefs.timezone, clockMs])

  return (
    <div className="profile-subview-stack">
      <div className="profile-tz-preview-banner">
        <Clock size={15} />
        <span>Waktu saat ini ({prefs.timezone}):</span>
        <strong className="num-tabular">{liveClockPreview}</strong>
      </div>

      <div className="profile-search-box">
        <Search size={15} className="profile-search-ico" />
        <input
          type="text"
          className="profile-search-input"
          placeholder="Cari zona waktu (mis. Jakarta, Makassar)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <button
            type="button"
            className="profile-clear-inline-btn"
            onClick={() => setQuery('')}
            aria-label="Hapus pencarian"
          >
            <X size={14} />
          </button>
        )}
      </div>

      <div className="profile-ref-card-group">
        {filtered.length === 0 ? (
          <div className="profile-empty-subnote">Zona waktu tidak ditemukan.</div>
        ) : (
          filtered.map((zone) => {
            const active = prefs.timezone === zone.id
            return (
              <button
                key={zone.id}
                type="button"
                className="profile-ref-row"
                onClick={() => {
                  triggerHaptic(12)
                  updatePrefs({ timezone: zone.id })
                  onSyncServerTimezone?.(zone.id)
                }}
              >
                <span className="profile-ref-row-icon is-sky">
                  <Globe size={16} />
                </span>
                <span className="profile-ref-row-text">
                  <span className="profile-ref-row-title">{zone.zoneLabel}</span>
                  <span className="profile-ref-row-sub num-tabular">
                    {zone.id} · {zone.offset}
                  </span>
                </span>
                {zone.defaultTag && !active && (
                  <span className="profile-ref-badge is-neutral">Default</span>
                )}
                {active && <Check size={17} className="profile-check-icon" />}
              </button>
            )
          })
        )}
      </div>

      <p className="profile-subview-footnote">
        Server menyimpan data dalam standar UTC dan menampilkan laporan maupun jadwal rekap harian
        sesuai zona waktu wilayah pilihan Anda (WIB / WITA / WIT).
      </p>
    </div>
  )
}

export function SchedulesBudgetSubView({
  settings,
  onSaveSettings,
  prefs,
  updatePrefs,
}) {
  const [reportEnabled, setReportEnabled] = useState(() => settings?.report_enabled !== false)
  const [reportHour, setReportHour] = useState(() => Number(settings?.report_hour ?? 21))
  const activeTzId = settings?.report_timezone || prefs.timezone || 'Asia/Jakarta'
  const activeTzShort = getTimeZoneShortLabel(activeTzId)
  const [savingServer, setSavingServer] = useState(false)
  const [budgetRp, setBudgetRp] = useState(() => String(prefs.monthlyBudgetRp || ''))
  const [budgetEnabled, setBudgetEnabled] = useState(() => Boolean(prefs.budgetAlertEnabled))
  const [msg, setMsg] = useState(null)

  const handleSaveServerSchedule = async (e) => {
    e.preventDefault()
    if (!onSaveSettings) return
    setSavingServer(true)
    setMsg(null)
    try {
      await onSaveSettings({
        report_enabled: Boolean(reportEnabled),
        report_hour: Number(reportHour),
        report_timezone: prefs.timezone || activeTzId,
      })
      triggerHaptic(16)
      setMsg({
        type: 'success',
        text: `Jadwal laporan harian (${activeTzShort}) berhasil disimpan ke akun Anda.`,
      })
    } catch (err) {
      setMsg({ type: 'error', text: err?.message || 'Gagal menyimpan jadwal laporan.' })
    } finally {
      setSavingServer(false)
    }
  }

  const handleApplyBudget = (nextBudgetVal, nextEnabled = budgetEnabled) => {
    const clean = Math.max(0, Math.min(100_000_000, parseInt(nextBudgetVal || '0', 10) || 0))
    setBudgetRp(clean > 0 ? String(clean) : '')
    setBudgetEnabled(Boolean(nextEnabled && clean > 0))
    updatePrefs({
      monthlyBudgetRp: clean,
      budgetAlertEnabled: Boolean(nextEnabled && clean > 0),
    })
    triggerHaptic(12)
    setMsg({
      type: 'success',
      text:
        clean > 0
          ? `Target anggaran bulanan disetel ke ${formatRp(clean)}.`
          : 'Target anggaran bulanan dinonaktifkan.',
    })
  }

  return (
    <div className="profile-subview-stack">
      {msg && (
        <div className={`feedback-msg ${msg.type === 'error' ? 'error' : 'success'}`}>
          {msg.text}
        </div>
      )}

      <form onSubmit={handleSaveServerSchedule} className="profile-ref-card-group profile-card-padded">
        <div className="profile-pattern-head-row" style={{ marginBottom: 12 }}>
          <div className="profile-ref-row-icon is-amber">
            <CalendarClock size={17} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="profile-ref-row-title">Laporan Energi Harian</div>
            <div className="profile-ref-row-sub">
              Ringkasan kWh &amp; estimasi biaya otomatis setiap hari
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={reportEnabled}
            className="profile-switch-btn-reset"
            onClick={() => {
              triggerHaptic(10)
              setReportEnabled((p) => !p)
            }}
          >
            <span className={`profile-theme-switch ${reportEnabled ? 'is-on' : ''}`}>
              <span className="profile-theme-knob" />
            </span>
          </button>
        </div>

        <label className="profile-subcard-label" style={{ display: 'block', marginBottom: 8 }}>
          Jam Pengiriman ({activeTzShort})
        </label>
        <div className="profile-hour-chip-grid">
          {[6, 8, 12, 18, 20, 21, 22, 23].map((hr) => (
            <button
              key={hr}
              type="button"
              disabled={!reportEnabled}
              className={`profile-hour-chip num-tabular ${Number(reportHour) === hr ? 'active' : ''}`}
              onClick={() => {
                triggerHaptic(8)
                setReportHour(hr)
              }}
            >
              {String(hr).padStart(2, '0')}:00
            </button>
          ))}
        </div>

        <button
          type="submit"
          className="btn btn-primary profile-save-pw-btn"
          style={{ marginTop: 12 }}
          disabled={savingServer || !onSaveSettings}
        >
          <CalendarClock size={15} />
          <span>{savingServer ? 'Menyimpan...' : 'Simpan Jadwal Laporan'}</span>
        </button>
      </form>

      <div className="profile-ref-card-group profile-card-padded">
        <div className="profile-pattern-head-row" style={{ marginBottom: 10 }}>
          <div className="profile-ref-row-icon is-emerald">
            <Wallet size={17} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="profile-ref-row-title">Target Anggaran Listrik Bulanan</div>
            <div className="profile-ref-row-sub">
              Batas pantau pengeluaran tagihan rumah bulan berjalan
            </div>
          </div>
        </div>

        <div className="profile-hour-chip-grid" style={{ marginBottom: 10 }}>
          {[300000, 500000, 1000000, 2000000].map((preset) => (
            <button
              key={preset}
              type="button"
              className={`profile-hour-chip num-tabular ${Number(budgetRp) === preset ? 'active' : ''}`}
              onClick={() => handleApplyBudget(preset, true)}
            >
              {preset >= 1000000 ? `Rp ${preset / 1000000} jt` : `Rp ${preset / 1000} rb`}
            </button>
          ))}
        </div>

        <div className="profile-account-inline-row">
          <input
            type="number"
            min="0"
            step="10000"
            className="modern-input num-tabular"
            placeholder="Nominal target (Rp)"
            value={budgetRp}
            onChange={(e) => setBudgetRp(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            onClick={() => handleApplyBudget(budgetRp, Number(budgetRp) > 0)}
          >
            Tetapkan
          </button>
        </div>

        {Number(prefs.monthlyBudgetRp || 0) > 0 && (
          <div className="profile-budget-active-bar">
            <span>
              Target aktif: <strong className="num-tabular">{formatRp(prefs.monthlyBudgetRp)}</strong>
            </span>
            <button
              type="button"
              className="profile-inline-link-btn"
              onClick={() => handleApplyBudget(0, false)}
            >
              Nonaktifkan
            </button>
          </div>
        )}
      </div>

      <p className="profile-subview-footnote">
        Sesuai prinsip keselamatan VoltKu, menu jadwal hanya mengatur pelaporan &amp; target anggaran
        (pemantauan read-only) tanpa memutus sakelar beban AC jarak jauh.
      </p>
    </div>
  )
}

export function SettingsSubView({
  currentUser,
  prefs,
  updatePrefs,
  lockCfg,
  theme = 'light',
  onToggleTheme,
  onNavigate,
  onLogout,
  onClose,
}) {
  const activeLang = LANGUAGE_OPTIONS.find((l) => l.id === prefs.locale) || LANGUAGE_OPTIONS[0]
  const activeTz = TIMEZONE_OPTIONS.find((z) => z.id === prefs.timezone) || TIMEZONE_OPTIONS[0]

  return (
    <div className="profile-subview-stack">
      <div className="profile-ref-card-group">
        <button type="button" className="profile-ref-row" onClick={() => onNavigate('edit-name')}>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Ubah Nama Tampilan</span>
          </span>
          <span className="profile-ref-value-muted">{currentUser?.name || '-'}</span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>

        <button type="button" className="profile-ref-row" onClick={() => onNavigate('password')}>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Kata Sandi</span>
          </span>
          <span className="profile-ref-value-muted">
            {currentUser?.has_local_password === false ? 'Tambah Sandi' : 'Terpasang'}
          </span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>

        <button type="button" className="profile-ref-row" onClick={() => onNavigate('app-lock')}>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">PIN &amp; Sidik Jari</span>
          </span>
          <span className={`profile-ref-badge ${lockCfg.enabled ? 'is-emerald' : 'is-neutral'}`}>
            {lockCfg.enabled
              ? lockCfg.biometricEnabled
                ? 'PIN + Sidik Jari'
                : 'PIN Aktif'
              : 'Off'}
          </span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>

        <button type="button" className="profile-ref-row" onClick={() => onNavigate('language')}>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Bahasa</span>
          </span>
          <span className="profile-ref-value-muted">{activeLang.name}</span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>

        <button type="button" className="profile-ref-row" onClick={() => onNavigate('timezone')}>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Zona Waktu</span>
          </span>
          <span className="profile-ref-value-muted num-tabular">{activeTz.id}</span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>

        {onToggleTheme && (
          <button
            type="button"
            role="switch"
            aria-checked={theme === 'dark'}
            className="profile-ref-row"
            onClick={() => {
              triggerHaptic(12)
              onToggleTheme()
            }}
          >
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Mode Gelap</span>
              <span className="profile-ref-row-sub">
                Saat ini: {theme === 'dark' ? 'Tema Gelap' : 'Tema Terang'}
              </span>
            </span>
            <span
              className={`profile-theme-switch ${theme === 'dark' ? 'is-on' : ''}`}
              aria-hidden="true"
            >
              <span className="profile-theme-knob" />
            </span>
          </button>
        )}

        <button
          type="button"
          role="switch"
          aria-checked={Boolean(prefs.vibration)}
          className="profile-ref-row"
          onClick={() => {
            const nextVal = !prefs.vibration
            updatePrefs({ vibration: nextVal })
            if (nextVal && typeof navigator !== 'undefined' && navigator.vibrate) {
              navigator.vibrate(15)
            }
          }}
        >
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Getaran Sentuhan</span>
            <span className="profile-ref-row-sub">Umpan balik haptik ringan pada tombol</span>
          </span>
          <span
            className={`profile-theme-switch ${prefs.vibration ? 'is-on' : ''}`}
            aria-hidden="true"
          >
            <span className="profile-theme-knob" />
          </span>
        </button>
      </div>

      <div className="profile-info-hint-row">
        <Info size={14} />
        <span>
          Jadwal laporan Telegram, target anggaran &amp; detail akun dapat diakses langsung dari
          halaman utama <strong>Profil</strong>.
        </span>
      </div>

      {onLogout && (
        <button
          type="button"
          className="profile-logout-btn"
          onClick={() => {
            onClose()
            onLogout()
          }}
        >
          <LogOut size={15} />
          <span>Keluar dari Akun</span>
        </button>
      )}
    </div>
  )
}

export function AccountDetailSubView({
  currentUser,
  onOpenTerms,
  onNavigate,
  onResetPrefs,
}) {
  const [resetMsg, setResetMsg] = useState('')
  const providerLabel =
    currentUser?.auth_provider === 'both'
      ? 'Google & Kata Sandi Lokal'
      : currentUser?.auth_provider === 'google'
        ? 'Akun Google'
        : 'Email & Kata Sandi'

  return (
    <div className="profile-subview-stack">
      {resetMsg && <div className="feedback-msg success">{resetMsg}</div>}

      <div className="profile-ref-card-group">
        <div className="profile-detail-kv-row">
          <span>ID Akun</span>
          <strong className="num-tabular">#{currentUser?.id ?? '-'}</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Nama Tampilan</span>
          <strong>{currentUser?.name || '-'}</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Email Terdaftar</span>
          <strong>{currentUser?.email || '-'}</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Metode Masuk</span>
          <strong>{providerLabel}</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Paket Aktif</span>
          <strong>{currentUser?.plan?.plan_name || 'VoltKu Gratis'}</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Versi Syarat Disetujui</span>
          <strong className="num-tabular">{currentUser?.terms_version_accepted || '-'}</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Terdaftar Sejak</span>
          <strong className="num-tabular">
            {currentUser?.created_at ? formatDateTimeWIB(currentUser.created_at) : '-'}
          </strong>
        </div>
      </div>

      <div className="profile-ref-card-group">
        <button type="button" className="profile-ref-row" onClick={() => onNavigate('edit-name')}>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Ubah Nama Tampilan</span>
          </span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>
        <button type="button" className="profile-ref-row" onClick={() => onNavigate('password')}>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Kelola Kata Sandi Login</span>
          </span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>
        {onOpenTerms && (
          <button
            type="button"
            className="profile-ref-row"
            onClick={() => onOpenTerms('privacy')}
          >
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Kebijakan Privasi Data Akun</span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </button>
        )}
      </div>

      <button
        type="button"
        className="btn btn-secondary"
        style={{ width: '100%', justifyContent: 'center' }}
        onClick={() => {
          onResetPrefs()
          setResetMsg('Preferensi tampilan lokal (bahasa, zona waktu, labs) dikembalikan ke default.')
        }}
      >
        <RotateCcw size={14} />
        <span>Kembalikan Preferensi Lokal ke Default</span>
      </button>
    </div>
  )
}

export function EcosystemSubView({
  devices = [],
  isDeviceOnlineFn,
  settings,
  onOpenAiChat,
  onNavigate,
}) {
  const onlineCount = devices.filter((d) =>
    isDeviceOnlineFn ? isDeviceOnlineFn(d) : d.status === 'online'
  ).length
  const notifPermission =
    typeof window !== 'undefined' && typeof Notification !== 'undefined'
      ? Notification.permission
      : 'default'

  return (
    <div className="profile-subview-stack">
      <div className="profile-eco-banner">
        <Cpu size={20} />
        <div>
          <strong>Ekosistem Energi VoltKu</strong>
          <p>
            Seluruh modul telemetri, bot peringatan, dan kecerdasan buatan bekerja terpadu dalam
            satu akun.
          </p>
        </div>
      </div>

      <div className="profile-ref-card-group">
        <div className="profile-eco-card-row">
          <span className="profile-ref-row-icon is-blue">
            <Wifi size={17} />
          </span>
          <div className="profile-ref-row-text">
            <span className="profile-ref-row-title">Sensor ESP32 &amp; MQTT TLS</span>
            <span className="profile-ref-row-sub">
              {devices.length === 0
                ? 'Belum ada panel tertaut ke akun Anda'
                : `${onlineCount} dari ${devices.length} panel sedang mengirim telemetri`}
            </span>
          </div>
          <span className={`profile-ref-badge ${onlineCount > 0 ? 'is-emerald' : 'is-neutral'}`}>
            {onlineCount > 0 ? 'Terhubung' : 'Siaga'}
          </span>
        </div>

        <div className="profile-eco-card-row">
          <span className="profile-ref-row-icon is-indigo">
            <EnergyAssistantIcon size={17} />
          </span>
          <div className="profile-ref-row-text">
            <span className="profile-ref-row-title">Asisten Energi VoltKu</span>
            <span className="profile-ref-row-sub">
              Analisa konsumsi kWh &amp; proyeksi tagihan berbasis data meteran
            </span>
          </div>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            onClick={onOpenAiChat}
          >
            Buka
          </button>
        </div>

        <div className="profile-eco-card-row">
          <span className="profile-ref-row-icon is-amber">
            <BellRing size={17} />
          </span>
          <div className="profile-ref-row-text">
            <span className="profile-ref-row-title">Notifikasi Push &amp; Anomali L1–L3</span>
            <span className="profile-ref-row-sub">
              Status izin perangkat:{' '}
              {notifPermission === 'granted'
                ? 'Diizinkan'
                : notifPermission === 'denied'
                  ? 'Diblokir browser'
                  : 'Default'}
            </span>
          </div>
          <span
            className={`profile-ref-badge ${notifPermission === 'granted' ? 'is-emerald' : 'is-neutral'}`}
          >
            {notifPermission === 'granted' ? 'Aktif' : 'FCM'}
          </span>
        </div>

        <button
          type="button"
          className="profile-ref-row"
          onClick={() => onNavigate('schedules')}
        >
          <span className="profile-ref-row-icon is-sky">
            <Send size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Bot Laporan Harian</span>
            <span className="profile-ref-row-sub">
              {settings?.report_enabled === false
                ? 'Laporan harian sedang dimatikan'
                : `Dijadwalkan pukul ${String(settings?.report_hour ?? 21).padStart(2, '0')}:00 ${getPreferredTimeZoneTag()}`}
            </span>
          </span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>
      </div>
    </div>
  )
}

export function MyPanelsSubView({
  devices = [],
  userPlan,
  isDeviceOnlineFn,
  onSelectDevice,
  onOpenAddDevice,
  onClose,
}) {
  const maxDevices = userPlan?.limits?.max_devices ?? 1

  return (
    <div className="profile-subview-stack">
      <div className="profile-panels-quota-bar">
        <span>
          Panel Tertaut:{' '}
          <strong className="num-tabular">
            {devices.length}/{maxDevices < 0 ? '∞' : maxDevices}
          </strong>
        </span>
        {onOpenAddDevice && (
          <button
            type="button"
            className="btn btn-primary btn-compact"
            onClick={() => {
              onClose()
              onOpenAddDevice()
            }}
          >
            <Plus size={14} />
            <span>Tambah Panel</span>
          </button>
        )}
      </div>

      {devices.length === 0 ? (
        <div className="profile-ref-card-group profile-card-padded" style={{ textAlign: 'center' }}>
          <Cpu size={28} style={{ color: '#1677ff', margin: '4px auto 8px' }} />
          <div className="profile-ref-row-title">Belum Ada Panel Listrik</div>
          <p className="profile-subcard-hint" style={{ margin: '4px 0 12px' }}>
            Tautkan sensor PZEM-004T Anda dengan memindai barcode perangkat atau memasukkan Device ID.
          </p>
        </div>
      ) : (
        <div className="profile-ref-card-group">
          {devices.map((dev) => {
            const online = isDeviceOnlineFn ? isDeviceOnlineFn(dev) : dev.status === 'online'
            const watts = dev.latest && typeof dev.latest.p === 'number' ? dev.latest.p : null
            return (
              <button
                key={dev.id}
                type="button"
                className="profile-ref-row"
                onClick={() => {
                  onClose()
                  onSelectDevice?.(dev.id)
                }}
              >
                <span className={`panel-status-dot ${online ? 'online' : 'offline'}`} />
                <span className="profile-ref-row-text">
                  <span className="profile-ref-row-title">{dev.name || dev.id}</span>
                  <span className="profile-ref-row-sub">
                    {dev.location || 'Panel Utama'} · MCB {dev.mcb_watt} W ·{' '}
                    {online ? 'Online' : 'Offline'}
                  </span>
                </span>
                <span className="profile-ref-value-muted num-tabular">
                  {watts !== null ? `${formatNum(watts, 0)} W` : '-'}
                </span>
                <ChevronRight size={16} className="profile-ref-chevron" />
              </button>
            )
          })}
        </div>
      )}

      <p className="profile-subview-footnote">
        Seluruh panel di akun Anda terisolasi privat per tenant dan tidak dapat dilihat akun
        pengguna lain.
      </p>
    </div>
  )
}

export function LabsSubView({ prefs, updatePrefs, isPro }) {
  const labs = prefs.labs || {}
  const toggleLab = (key) => {
    triggerHaptic(12)
    updatePrefs({ labs: { ...labs, [key]: !labs[key] } })
  }

  return (
    <div className="profile-subview-stack">
      <div className="profile-ref-card-group">
        <button
          type="button"
          role="switch"
          aria-checked={Boolean(labs.proactiveAiTips)}
          className="profile-ref-row"
          onClick={() => toggleLab('proactiveAiTips')}
        >
          <span className="profile-ref-row-icon is-amber">
            <EnergyAssistantIcon size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">
              Wawasan AI Proaktif{' '}
              <span className="profile-mini-gold-tag">{isPro ? 'Pro' : 'Beta'}</span>
            </span>
            <span className="profile-ref-row-sub">
              Tampilkan pintasan tips efisiensi beban pada beranda dan asisten AI
            </span>
          </span>
          <span
            className={`profile-theme-switch ${labs.proactiveAiTips ? 'is-on' : ''}`}
            aria-hidden="true"
          >
            <span className="profile-theme-knob" />
          </span>
        </button>

        <button
          type="button"
          role="switch"
          aria-checked={Boolean(labs.compactCards)}
          className="profile-ref-row"
          onClick={() => toggleLab('compactCards')}
        >
          <span className="profile-ref-row-icon is-emerald">
            <Activity size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Mode Kartu Padat</span>
            <span className="profile-ref-row-sub">
              Menampilkan lebih banyak panel ringkas pada layar ponsel
            </span>
          </span>
          <span
            className={`profile-theme-switch ${labs.compactCards ? 'is-on' : ''}`}
            aria-hidden="true"
          >
            <span className="profile-theme-knob" />
          </span>
        </button>

        <button
          type="button"
          role="switch"
          aria-checked={Boolean(labs.weeklyDigestReminder)}
          className="profile-ref-row"
          onClick={() => toggleLab('weeklyDigestReminder')}
        >
          <span className="profile-ref-row-icon is-teal">
            <CalendarClock size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Pengingat Evaluasi Mingguan</span>
            <span className="profile-ref-row-sub">
              Highlight perbandingan beban puncak antar minggu di beranda
            </span>
          </span>
          <span
            className={`profile-theme-switch ${labs.weeklyDigestReminder ? 'is-on' : ''}`}
            aria-hidden="true"
          >
            <span className="profile-theme-knob" />
          </span>
        </button>
      </div>
    </div>
  )
}

export function HelpSupportSubView({
  waHref,
  tgHandle,
  supportEmail,
  onOpenUsageGuide,
  onReplayTour,
  onClose,
  onOpenRateModal,
}) {
  return (
    <div className="profile-subview-stack">
      <div className="profile-ref-card-group">
        {onOpenUsageGuide && (
          <button
            type="button"
            className="profile-ref-row"
            onClick={() => {
              onClose()
              onOpenUsageGuide()
            }}
          >
            <span className="profile-ref-row-icon is-blue">
              <BookOpen size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Cara Pemakaian &amp; Koneksi Wi-Fi</span>
              <span className="profile-ref-row-sub">
                Panduan 5 langkah pasang alat &amp; scan barcode
              </span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </button>
        )}

        {onReplayTour && (
          <button
            type="button"
            className="profile-ref-row"
            onClick={() => {
              onClose()
              onReplayTour()
            }}
          >
            <span className="profile-ref-row-icon is-emerald">
              <Compass size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Panduan Awal Aplikasi</span>
              <span className="profile-ref-row-sub">Putar ulang tur interaktif dashboard</span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </button>
        )}

        <button type="button" className="profile-ref-row" onClick={onOpenRateModal}>
          <span className="profile-ref-row-icon is-amber">
            <Star size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Kirim Masukan &amp; Penilaian</span>
            <span className="profile-ref-row-sub">Bagikan pengalaman atau usulkan fitur baru</span>
          </span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>
      </div>

      <div className="profile-ref-card-group">
        {waHref && (
          <a href={waHref} target="_blank" rel="noreferrer" className="profile-ref-row">
            <span className="profile-ref-row-icon is-emerald">
              <MessageCircle size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">WhatsApp Bantuan Admin</span>
            </span>
            <span className="profile-ref-badge is-emerald">Chat</span>
            <ExternalLink size={14} className="profile-ref-chevron" />
          </a>
        )}
        {tgHandle && (
          <a
            href={`https://t.me/${tgHandle}`}
            target="_blank"
            rel="noreferrer"
            className="profile-ref-row"
          >
            <span className="profile-ref-row-icon is-sky">
              <Send size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Telegram Dukungan</span>
            </span>
            <span className="profile-ref-badge is-neutral">@{tgHandle}</span>
            <ExternalLink size={14} className="profile-ref-chevron" />
          </a>
        )}
        {supportEmail && (
          <a href={`mailto:${supportEmail}`} className="profile-ref-row">
            <span className="profile-ref-row-icon is-blue">
              <Mail size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Email Resmi Dukungan</span>
              <span className="profile-ref-row-sub">{supportEmail}</span>
            </span>
            <ExternalLink size={14} className="profile-ref-chevron" />
          </a>
        )}
        {!waHref && !tgHandle && !supportEmail && (
          <div className="profile-empty-subnote">
            Kontak dukungan belum ditambahkan oleh pengelola di Panel Admin.
          </div>
        )}
      </div>
    </div>
  )
}

export function CreditsSubView({ appName }) {
  return (
    <div className="profile-subview-stack">
      <div className="profile-about-hero" style={{ gap: 8 }}>
        <div className="profile-eco-banner" style={{ margin: 0, padding: 0, background: 'transparent', border: 'none' }}>
          <Award size={22} style={{ color: '#f59e0b' }} />
          <div>
            <strong>Apresiasi Khusus &amp; Teknologi</strong>
            <p>
              Terima kasih kepada pengguna awal dan penguji lapangan yang membantu menyempurnakan
              akurasi deteksi anomali &amp; kenyamanan {appName}.
            </p>
          </div>
        </div>
      </div>

      <div className="profile-ref-card-group">
        <div className="profile-detail-kv-row">
          <span>Arsitektur Telemetry</span>
          <strong>ESP32 + Sensor PZEM-004T</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Protokol Transportasi</span>
          <strong>MQTT TLS + FastAPI REST</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Komputasi Biaya</span>
          <strong>Exact Decimal (ROUND_HALF_UP)</strong>
        </div>
        <div className="profile-detail-kv-row">
          <span>Analitik &amp; Asisten</span>
          <strong>Detektor L1–L3 &amp; Gemini Flash</strong>
        </div>
      </div>
    </div>
  )
}

export function AboutHubSubView({
  appName,
  appConfig = {},
  waHref,
  tgHandle,
  supportEmail,
  onNavigate,
  onOpenTerms,
}) {
  const versionLabel = appConfig?.app_release?.version || APP_VERSION_TAG
  return (
    <div className="profile-subview-stack profile-about-hub-layout">
      <div className="profile-ref-card-group">
        <button type="button" className="profile-ref-row" onClick={() => onNavigate('about-detail')}>
          <span className="profile-ref-row-icon is-blue">
            <Info size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Tentang {appName}</span>
          </span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>

        <button type="button" className="profile-ref-row" onClick={() => onNavigate('changelog')}>
          <span className="profile-ref-row-icon is-emerald">
            <Zap size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Versi Aplikasi</span>
          </span>
          <span className="profile-ref-value-muted num-tabular">{versionLabel}</span>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>

        <button type="button" className="profile-ref-row" onClick={() => onNavigate('channels')}>
          <span className="profile-ref-row-icon is-sky">
            <Globe size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Kanal Resmi</span>
          </span>
          <div className="profile-mini-social-dots" aria-hidden="true">
            {waHref && <span className="dot-wa">WA</span>}
            {tgHandle && <span className="dot-tg">TG</span>}
            {supportEmail && <span className="dot-em">@</span>}
          </div>
          <ChevronRight size={16} className="profile-ref-chevron" />
        </button>
      </div>

      {onOpenTerms && (
        <div className="profile-about-legal-footer">
          <button type="button" onClick={() => onOpenTerms('terms')}>
            &lt;Syarat Penggunaan&gt;
          </button>
          <button type="button" onClick={() => onOpenTerms('privacy')}>
            &lt;Kebijakan Privasi&gt;
          </button>
        </div>
      )}
    </div>
  )
}

export function AboutDetailSubView({ appName, appTagline, appConfig = {}, theme, onOpenTerms }) {
  const versionLabel = appConfig?.app_release?.version || APP_VERSION_TAG
  return (
    <div className="profile-subview-stack">
      <div className="profile-about-card profile-about-full-page">
        <div className="profile-about-showcase-art">
          <svg viewBox="0 0 260 112" className="profile-showcase-svg" aria-hidden="true">
            <defs>
              <linearGradient id="vkNodeGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#1677ff" />
                <stop offset="100%" stopColor="#0ea5e9" />
              </linearGradient>
            </defs>
            <path d="M56 56 H204" stroke="#93c5fd" strokeWidth="2.5" strokeDasharray="5 4" />
            <rect x="20" y="34" width="48" height="44" rx="12" className="vk-art-box" />
            <path d="M45 45 L39 57 H46 L43 67 L53 53 H46 Z" fill="#1677ff" />
            <rect x="98" y="22" width="64" height="68" rx="16" fill="url(#vkNodeGrad)" />
            <path d="M133 38 L123 56 H131 L127 74 L141 53 H132 Z" fill="#ffffff" />
            <rect x="192" y="34" width="48" height="44" rx="12" className="vk-art-box" />
            <circle cx="216" cy="56" r="10" fill="rgba(16,185,129,0.18)" />
            <path d="M211 56 L215 60 L222 52" fill="none" stroke="#10b981" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        <div className="profile-about-hero">
          <div className="profile-about-brand">
            <BrandLogo theme={theme} displayMode="logo_only" appName={appName} variant="compact" />
          </div>
          <p className="profile-about-tagline">{appTagline}</p>
        </div>

        <div className="profile-about-features">
          <div className="profile-about-feat-row">
            <span className="profile-about-feat-ico is-blue">
              <Activity size={14} />
            </span>
            <div>
              <strong>Pantau Daya Real-Time</strong>
              <span>Tegangan, arus, watt, PF, frekuensi &amp; beban MCB secara langsung.</span>
            </div>
          </div>
          <div className="profile-about-feat-row">
            <span className="profile-about-feat-ico is-amber">
              <Zap size={14} />
            </span>
            <div>
              <strong>Hitung Tarif &amp; Proyeksi PLN</strong>
              <span>Estimasi biaya presisi Decimal, grafik historis &amp; proyeksi akhir bulan.</span>
            </div>
          </div>
          <div className="profile-about-feat-row">
            <span className="profile-about-feat-ico is-emerald">
              <TierShieldIcon size={14} />
            </span>
            <div>
              <strong>Asisten AI &amp; Deteksi Anomali</strong>
              <span>Peringatan dini lonjakan daya, tegangan tak stabil &amp; analisa AI.</span>
            </div>
          </div>
          <div className="profile-about-feat-row">
            <span className="profile-about-feat-ico is-indigo">
              <ShieldCheck size={14} />
            </span>
            <div>
              <strong>Koneksi Terenkripsi</strong>
              <span>Komunikasi HTTPS, JWT &amp; MQTT TLS dengan akses terisolasi per akun.</span>
            </div>
          </div>
        </div>

        <div className="profile-about-specs">
          <div className="profile-about-spec-item">
            <Cpu size={13} />
            <span>Hardware: Smart Panel / PZEM-004T</span>
          </div>
          <div className="profile-about-spec-item">
            <Clock size={13} />
            <span>
              Zona Waktu: {getPreferredTimeZone()} ({getPreferredTimeZoneTag()})
            </span>
          </div>
        </div>

        <div className="profile-about-footer">
          <span className="profile-about-pkg num-tabular">
            {APP_PACKAGE_ID} · {versionLabel}
          </span>
          {onOpenTerms && (
            <div className="profile-about-legal-links">
              <button type="button" onClick={() => onOpenTerms('terms')}>
                Syarat
              </button>
              <span>·</span>
              <button type="button" onClick={() => onOpenTerms('privacy')}>
                Privasi
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function ChangelogSubView({ appConfig = {} }) {
  const release = appConfig?.app_release
  const versionLabel = release?.version || APP_VERSION_TAG
  const apkUrl = (release?.apk_download_url || '').trim()
  const releaseNotes = (release?.release_notes || '').trim()
  const changelogItems =
    Array.isArray(release?.changelog) && release.changelog.length > 0
      ? release.changelog
      : VOLTKU_CHANGELOG

  return (
    <div className="profile-subview-stack">
      {(apkUrl || releaseNotes) && (
        <div className="profile-ref-card-group profile-card-padded">
          <div className="profile-changelog-head">
            <strong className="num-tabular">{versionLabel}</strong>
            <span className="profile-ref-badge is-blue">Rilis Resmi</span>
          </div>
          {releaseNotes && (
            <p className="profile-subcard-hint" style={{ margin: '6px 0 10px' }}>
              {releaseNotes}
            </p>
          )}
          {apkUrl && (
            <a
              href={apkUrl}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary btn-compact profile-apk-download-btn"
            >
              <ExternalLink size={14} />
              <span>Unduh APK Android ({versionLabel})</span>
            </a>
          )}
        </div>
      )}

      {changelogItems.map((rel) => (
        <div key={rel.version} className="profile-ref-card-group profile-card-padded">
          <div className="profile-changelog-head">
            <strong className="num-tabular">{rel.version}</strong>
            <span className="profile-ref-badge is-blue">{rel.badge}</span>
            <span className="profile-changelog-date">{rel.date}</span>
          </div>
          <ul className="profile-changelog-list">
            {(rel.items || []).map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

export function OfficialChannelsSubView({ waHref, tgHandle, supportEmail, appName }) {
  const [copiedUrl, setCopiedUrl] = useState('')
  const portalUrl = typeof window !== 'undefined' ? window.location.origin : 'https://voltku.synemax.web.id'

  const handleCopy = async (val) => {
    try {
      await navigator.clipboard.writeText(val)
      triggerHaptic(10)
      setCopiedUrl(val)
      window.setTimeout(() => setCopiedUrl(''), 1800)
    } catch {
      // ignore
    }
  }

  return (
    <div className="profile-subview-stack">
      <div className="profile-ref-card-group">
        {waHref && (
          <a href={waHref} target="_blank" rel="noreferrer" className="profile-ref-row">
            <span className="profile-ref-row-icon is-emerald">
              <MessageCircle size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">WhatsApp Resmi {appName}</span>
              <span className="profile-ref-row-sub">Konsultasi alat &amp; konfirmasi paket</span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </a>
        )}
        {tgHandle && (
          <a
            href={`https://t.me/${tgHandle}`}
            target="_blank"
            rel="noreferrer"
            className="profile-ref-row"
          >
            <span className="profile-ref-row-icon is-sky">
              <Send size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">Telegram @{tgHandle}</span>
              <span className="profile-ref-row-sub">Pembaruan &amp; bantuan teknis cepat</span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </a>
        )}
        {supportEmail && (
          <a href={`mailto:${supportEmail}`} className="profile-ref-row">
            <span className="profile-ref-row-icon is-blue">
              <Mail size={17} />
            </span>
            <span className="profile-ref-row-text">
              <span className="profile-ref-row-title">{supportEmail}</span>
              <span className="profile-ref-row-sub">Email dukungan pelanggan</span>
            </span>
            <ChevronRight size={16} className="profile-ref-chevron" />
          </a>
        )}
        <button
          type="button"
          className="profile-ref-row"
          onClick={() => handleCopy(portalUrl)}
        >
          <span className="profile-ref-row-icon is-indigo">
            <Globe size={17} />
          </span>
          <span className="profile-ref-row-text">
            <span className="profile-ref-row-title">Portal Web {appName}</span>
            <span className="profile-ref-row-sub num-tabular">{portalUrl}</span>
          </span>
          <span className="profile-ref-badge is-neutral">
            {copiedUrl === portalUrl ? 'Disalin' : <Copy size={12} />}
          </span>
        </button>
      </div>
    </div>
  )
}

export function RateFeedbackModal({
  isOpen,
  onClose,
  token = '',
  onUnauthorized,
  appName,
  waHref,
  supportEmail,
}) {
  const existing = getLatestUserFeedback()
  const [rating, setRating] = useState(existing?.rating || 5)
  const [category, setCategory] = useState('feedback')
  const [comment, setComment] = useState(existing?.comment || '')
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitErr, setSubmitErr] = useState('')
  const [serverHistory, setServerHistory] = useState([])

  useEffect(() => {
    if (!isOpen || !token) return undefined
    let cancelled = false
    apiRequest('/api/users/feedback?limit=3', {}, token, onUnauthorized)
      .then((rows) => {
        if (!cancelled && Array.isArray(rows)) {
          setServerHistory(rows)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [isOpen, token, onUnauthorized])

  if (!isOpen) return null

  const ratingLabels = {
    1: 'Perlu banyak perbaikan',
    2: 'Kurang nyaman',
    3: 'Cukup baik',
    4: 'Sangat membantu',
    5: 'Luar biasa memuaskan!',
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSubmitErr('')
    saveUserFeedbackEntry({ rating, comment, category })
    if (token) {
      setSubmitting(true)
      try {
        const created = await apiRequest(
          '/api/users/feedback',
          {
            method: 'POST',
            body: { rating, category, comment: comment.trim() || null },
          },
          token,
          onUnauthorized
        )
        if (created) {
          setServerHistory((prev) => [created, ...prev.slice(0, 2)])
        }
      } catch (err) {
        setSubmitErr(err.message || 'Gagal mengirim masukan ke server.')
        setSubmitting(false)
        return
      } finally {
        setSubmitting(false)
      }
    }
    triggerHaptic(18)
    setSubmitted(true)
  }

  const mailtoFeedback = supportEmail
    ? `mailto:${supportEmail}?subject=${encodeURIComponent(
        `Ulasan ${appName} (${rating}/5 Bintang)`
      )}&body=${encodeURIComponent(comment || `Nilai ${rating}/5 untuk ${appName}.`)}`
    : ''

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 1300 }}>
      <div className="profile-rate-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="profile-rate-stars-header">
          <div className="profile-rate-ribbon">
            <Award size={18} />
            <span>Dukungan Pengguna {appName}</span>
          </div>
        </div>

        {submitted ? (
          <div className="profile-rate-done-body">
            <h4>Terima Kasih atas Penilaian Anda!</h4>
            <p>
              Ulasan <strong>{rating}/5 bintang</strong> Anda telah dicatat. Masukan Anda membantu
              kami terus mengembangkan {appName}.
            </p>
            <div className="profile-rate-split-actions">
              {(waHref || mailtoFeedback) && (
                <a
                  href={
                    waHref
                      ? `${waHref}?text=${encodeURIComponent(
                          `Halo Admin ${appName}, ulasan saya (${rating}/5): ${comment || 'Mantap!'}`
                        )}`
                      : mailtoFeedback
                  }
                  target="_blank"
                  rel="noreferrer"
                  className="profile-rate-split-btn"
                >
                  Kirim ke Admin
                </a>
              )}
              <button
                type="button"
                className="profile-rate-split-btn is-primary"
                onClick={() => {
                  setSubmitted(false)
                  onClose()
                }}
              >
                Selesai
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSave} className="profile-rate-form">
            <p className="profile-rate-prompt">
              Jika Anda menyukai {appName}, beri bintang &amp; saran agar pemantauan listrik makin
              baik:
            </p>
            <div className="profile-rate-stars-row" role="radiogroup" aria-label="Beri bintang 1 hingga 5">
              {[1, 2, 3, 4, 5].map((starVal) => (
                <button
                  key={starVal}
                  type="button"
                  className={`profile-rate-star-btn ${starVal <= rating ? 'active' : ''}`}
                  onClick={() => {
                    triggerHaptic(10)
                    setRating(starVal)
                  }}
                  aria-label={`${starVal} bintang`}
                >
                  <Star size={24} fill={starVal <= rating ? '#f59e0b' : 'none'} />
                </button>
              ))}
            </div>
            <div className="profile-rate-caption">{ratingLabels[rating]}</div>

            <div className="profile-rate-cat-row" role="radiogroup" aria-label="Kategori masukan">
              {[
                { id: 'feedback', label: 'Ulasan' },
                { id: 'bug', label: 'Lapor Bug' },
                { id: 'feature', label: 'Usul Fitur' },
              ].map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`profile-rate-cat-pill ${category === c.id ? 'active' : ''}`}
                  onClick={() => setCategory(c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>

            <textarea
              rows={3}
              className="modern-input"
              placeholder={
                category === 'bug'
                  ? 'Jelaskan kendala yang dialami agar tim segera perbaiki...'
                  : 'Tulis saran fitur atau masukan Anda (opsional)...'
              }
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              maxLength={400}
            />

            {submitErr && (
              <p className="feedback-msg error" style={{ margin: 0 }}>
                {submitErr}
              </p>
            )}

            {serverHistory.length > 0 && (
              <div className="profile-rate-history">
                <div className="profile-rate-history-head">Riwayat Kiriman Anda</div>
                {serverHistory.slice(0, 2).map((fb) => (
                  <div key={fb.id} className="profile-rate-history-item">
                    <div className="profile-rate-history-meta">
                      <span>
                        {'★'.repeat(fb.rating || 5)} ·{' '}
                        {fb.status === 'resolved'
                          ? 'Selesai'
                          : fb.status === 'reviewed'
                          ? 'Ditinjau'
                          : 'Terkirim'}
                      </span>
                      <span className="num-tabular">{formatDateTimeWIB(fb.created_at)}</span>
                    </div>
                    {fb.admin_reply && (
                      <div className="profile-rate-admin-reply">
                        <strong>Balasan Admin:</strong> {fb.admin_reply}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="profile-rate-split-actions">
              <button type="button" className="profile-rate-split-btn" onClick={onClose}>
                Tutup
              </button>
              <button type="submit" className="profile-rate-split-btn is-primary" disabled={submitting}>
                {submitting ? 'Mengirim...' : 'Kirim Nilai'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

