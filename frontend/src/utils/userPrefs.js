import { useState, useEffect, useCallback } from 'react'

import { apiRequest } from '../api/client'

const PREFS_STORAGE_KEY = 'voltku_user_prefs_v1'
const APP_LOCK_KEY = 'voltku_app_lock_v2'
const LEGACY_PATTERN_LOCK_KEY = 'voltku_pattern_lock_v1'
const FEEDBACK_LOG_KEY = 'voltku_user_feedback_v1'
const PREFS_EVENT = 'voltku:prefs-updated'

export const APP_VERSION_TAG = 'v2.5.0'
export const APP_PACKAGE_ID = 'com.voltku.energy'

export const TIMEZONE_SHORT_MAP = {
  'Asia/Jakarta': 'WIB',
  'Asia/Makassar': 'WITA',
  'Asia/Jayapura': 'WIT',
  'Asia/Singapore': 'SGT',
  UTC: 'UTC',
}

export const INDONESIAN_TIMEZONES = [
  { id: 'Asia/Jakarta', short: 'WIB', name: 'Waktu Indonesia Barat', offset: 'UTC+7' },
  { id: 'Asia/Makassar', short: 'WITA', name: 'Waktu Indonesia Tengah', offset: 'UTC+8' },
  { id: 'Asia/Jayapura', short: 'WIT', name: 'Waktu Indonesia Timur', offset: 'UTC+9' },
]

export function detectDeviceTimeZone() {
  try {
    const sysTz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''
    if (sysTz === 'Asia/Makassar' || sysTz === 'Asia/Ujung_Pandang') return 'Asia/Makassar'
    if (sysTz === 'Asia/Jayapura') return 'Asia/Jayapura'
    if (sysTz === 'Asia/Singapore' || sysTz === 'Asia/Kuala_Lumpur') return 'Asia/Singapore'
    if (sysTz === 'Asia/Jakarta' || sysTz === 'Asia/Pontianak') return 'Asia/Jakarta'
    if (sysTz === 'UTC' || sysTz === 'Etc/UTC') return 'UTC'
  } catch {
    // Abaikan jika browser tidak mengekspos resolvedOptions().timeZone
  }
  return 'Asia/Jakarta'
}

export function getTimeZoneShortLabel(tzId = 'Asia/Jakarta') {
  return TIMEZONE_SHORT_MAP[tzId] || 'WIB'
}

export const DEFAULT_USER_PREFS = {
  locale: 'id',
  timezone: detectDeviceTimeZone(),
  vibration: true,
  monthlyBudgetRp: 0,
  budgetAlertEnabled: false,
  labs: {
    proactiveAiTips: true,
    compactCards: false,
    smoothCharts: true,
    weeklyDigestReminder: true,
  },
}

export const LANGUAGE_OPTIONS = [
  {
    id: 'id',
    name: 'Bahasa Indonesia',
    subtitle: 'Bawaan Indonesia (Direkomendasikan)',
    badge: 'ID',
  },
  {
    id: 'en',
    name: 'English',
    subtitle: 'International English UI Labels',
    badge: 'EN',
  },
]

export const TIMEZONE_OPTIONS = [
  {
    id: 'Asia/Jakarta',
    zoneLabel: 'Waktu Indonesia Barat (WIB)',
    offset: 'UTC+07:00',
    defaultTag: true,
  },
  {
    id: 'Asia/Makassar',
    zoneLabel: 'Waktu Indonesia Tengah (WITA)',
    offset: 'UTC+08:00',
    defaultTag: false,
  },
  {
    id: 'Asia/Jayapura',
    zoneLabel: 'Waktu Indonesia Timur (WIT)',
    offset: 'UTC+09:00',
    defaultTag: false,
  },
  {
    id: 'Asia/Singapore',
    zoneLabel: 'Singapore / Malaysia Standard Time',
    offset: 'UTC+08:00',
    defaultTag: false,
  },
  {
    id: 'UTC',
    zoneLabel: 'Coordinated Universal Time',
    offset: 'UTC+00:00',
    defaultTag: false,
  },
]

export const VOLTKU_CHANGELOG = [
  {
    version: 'v2.5.0',
    date: '27 Nov 2026',
    badge: 'Terbaru',
    items: [
      'Arsitektur Profil multi-halaman dengan Pengaturan khusus, Ekosistem Koneksi, dan Tentang Aplikasi.',
      'Keamanan Aplikasi adaptif: PIN 6 Digit + Sidik Jari / Biometrik (menyesuaikan dukungan sensor perangkat).',
      'Pemilih Bahasa (Indonesia & English), Zona Waktu tampilan (WIB/WITA/WIT), serta getaran haptik.',
      'Menu Jadwal Laporan Telegram & Target Anggaran Listrik Bulanan + VoltKu Labs.',
    ],
  },
  {
    version: 'v2.4.2',
    date: '26 Nov 2026',
    badge: 'Stabilitas',
    items: [
      'Banner panduan instalasi interaktif Wi-Fi 2.4 GHz dan langkah pairing sensor PZEM-004T.',
      'Alur pilih paket bertahap (Pilih Paket -> Durasi -> Pembayaran QRIS/Bank/E-Wallet).',
      'Penyempurnaan posisi tombol asisten AI pada layar desktop serta grid preset daya simetris.',
    ],
  },
  {
    version: 'v2.3.0',
    date: '24 Nov 2026',
    badge: 'AI & Billing',
    items: [
      'Asisten AI Tanya VoltKu berbasis Gemini Flash dengan alat hitung biaya & proyeksi deterministik.',
      'Dukungan checkout keanggotaan Pro manual lengkap dengan upload & pratinjau bukti bayar.',
    ],
  },
  {
    version: 'v2.2.0',
    date: '20 Nov 2026',
    badge: 'Aplikasi',
    items: [
      'Integrasi Google Sign-In Web & Android Native serta notifikasi push FCM real-time.',
      'Deteksi anomali tegangan, beban puncak malam, dan lonjakan daya terhadap baseline.',
    ],
  },
]

const UI_STRINGS = {
  id: {
    navHome: 'Beranda',
    navAlerts: 'Peringatan',
    navSettings: 'Tarif & Daya',
    navLive: 'Live',
    navCharts: 'Konsumsi',
    navChartsDesktop: 'Konsumsi & Grafik',
    navAnomalies: 'Anomali',
    navDeviceSettings: 'Atur Alat',
    profileTitle: 'Profil',
    settingsTitle: 'Pengaturan',
    aboutTitle: 'Tentang Aplikasi',
    editNameTitle: 'Ubah Nama',
    passwordTitle: 'Kata Sandi',
    appLockTitle: 'PIN & Sidik Jari',
    languageTitle: 'Bahasa Antarmuka',
    timezoneTitle: 'Zona Waktu Tampilan',
    schedulesTitle: 'Jadwal Laporan & Target',
    accountDetailTitle: 'Akun VoltKu',
    ecosystemTitle: 'Ekosistem & Koneksi',
    panelsTitle: 'Panel & Laporan Saya',
    labsTitle: 'VoltKu Labs',
    helpTitle: 'Bantuan & Masukan',
    creditsTitle: 'Apresiasi & Teknologi',
    versionTitle: 'Catatan Rilis',
    channelsTitle: 'Kanal Resmi',
    logout: 'Keluar dari Akun',
    save: 'Simpan',
    saving: 'Menyimpan...',
  },
  en: {
    navHome: 'Home',
    navAlerts: 'Alerts',
    navSettings: 'Tariff & Power',
    navLive: 'Live',
    navCharts: 'Usage',
    navChartsDesktop: 'Usage & Charts',
    navAnomalies: 'Anomalies',
    navDeviceSettings: 'Device',
    profileTitle: 'Profile',
    settingsTitle: 'Settings',
    aboutTitle: 'About App',
    editNameTitle: 'Edit Name',
    passwordTitle: 'Password',
    appLockTitle: 'PIN & Biometrics',
    languageTitle: 'Language',
    timezoneTitle: 'Time Zone',
    schedulesTitle: 'Report & Budget Schedule',
    accountDetailTitle: 'VoltKu Account',
    ecosystemTitle: 'Ecosystem & Integrations',
    panelsTitle: 'My Panels & Exports',
    labsTitle: 'VoltKu Labs',
    helpTitle: 'Help & Feedback',
    creditsTitle: 'Special Thanks',
    versionTitle: 'Release Notes',
    channelsTitle: 'Official Channels',
    logout: 'Sign Out',
    save: 'Save',
    saving: 'Saving...',
  },
}

export function getUiText(locale = 'id', key) {
  const langMap = UI_STRINGS[locale === 'en' ? 'en' : 'id']
  return langMap[key] || UI_STRINGS.id[key] || key
}

function readStorageJson(key, fallback) {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return fallback
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : fallback
  } catch {
    return fallback
  }
}

function writeStorageJson(key, val) {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return
    window.localStorage.setItem(key, JSON.stringify(val))
  } catch {
    // Abaikan kegagalan storage (mis. private mode penuh)
  }
}

export function getUserPrefs() {
  const saved = readStorageJson(PREFS_STORAGE_KEY, {})
  return {
    ...DEFAULT_USER_PREFS,
    ...saved,
    labs: {
      ...DEFAULT_USER_PREFS.labs,
      ...(saved?.labs || {}),
    },
  }
}

export function updateUserPrefs(patch) {
  const current = getUserPrefs()
  const next = {
    ...current,
    ...patch,
    labs: {
      ...current.labs,
      ...(patch?.labs || {}),
    },
  }
  writeStorageJson(PREFS_STORAGE_KEY, next)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(PREFS_EVENT, { detail: next }))
  }
  return next
}

export function useUserPrefs() {
  const [prefs, setPrefs] = useState(() => getUserPrefs())

  useEffect(() => {
    const onUpdated = (e) => {
      setPrefs(e?.detail || getUserPrefs())
    }
    const onStorage = (e) => {
      if (!e || e.key === PREFS_STORAGE_KEY) {
        setPrefs(getUserPrefs())
      }
    }
    window.addEventListener(PREFS_EVENT, onUpdated)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(PREFS_EVENT, onUpdated)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  const savePrefs = useCallback((patch) => {
    const next = updateUserPrefs(patch)
    setPrefs(next)
    return next
  }, [])

  return { prefs, updatePrefs: savePrefs }
}

export function getPreferredTimeZone() {
  const tz = getUserPrefs().timezone
  const allowed = TIMEZONE_OPTIONS.some((z) => z.id === tz)
  return allowed ? tz : 'Asia/Jakarta'
}

export function triggerHaptic(durationMs = 12) {
  try {
    const { vibration } = getUserPrefs()
    if (!vibration || typeof navigator === 'undefined' || typeof navigator.vibrate !== 'function') {
      return
    }
    navigator.vibrate(durationMs)
  } catch {
    // Abaikan jika browser memblokir vibrasi
  }
}

export async function hashPinCode(pin = '', scope = 'v2') {
  const payload = `voltku:pin:${scope}:${String(pin || '').trim()}`
  try {
    if (typeof window !== 'undefined' && window.crypto?.subtle) {
      const encoded = new TextEncoder().encode(payload)
      const digest = await window.crypto.subtle.digest('SHA-256', encoded)
      return Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('')
    }
  } catch {
    // Lanjut ke fallback deterministik untuk HTTP LAN non-secure context
  }
  let h1 = 0x811c9dc5
  let h2 = 0x9e3779b9
  for (let i = 0; i < payload.length; i += 1) {
    const ch = payload.charCodeAt(i)
    h1 = Math.imul(h1 ^ ch, 0x01000193) >>> 0
    h2 = Math.imul(h2 ^ (ch + i), 0x85ebca6b) >>> 0
  }
  return `${h1.toString(16).padStart(8, '0')}${h2.toString(16).padStart(8, '0')}`
}

function generateLocalSaltHex() {
  try {
    if (typeof window !== 'undefined' && window.crypto?.getRandomValues) {
      const bytes = new Uint8Array(12)
      window.crypto.getRandomValues(bytes)
      return Array.from(bytes)
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('')
    }
  } catch {
    // fallback
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 10)}`
}

export function getAppLockConfig(currentUser = null) {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.removeItem(LEGACY_PATTERN_LOCK_KEY)
    }
  } catch {
    // ignore
  }
  const saved = readStorageJson(APP_LOCK_KEY, null)
  const uid = currentUser?.id ? Number(currentUser.id) : null
  const savedUid = saved?.userId ? Number(saved.userId) : null
  const sameOwner = !uid || !savedUid || uid === savedUid
  const scopedSaved = sameOwner ? saved : null

  const hasServerLockMeta = Boolean(currentUser && currentUser.app_lock !== undefined)
  const serverPinEnabled = hasServerLockMeta ? Boolean(currentUser.app_lock?.pin_enabled) : null
  const enabled =
    serverPinEnabled !== null
      ? serverPinEnabled
      : Boolean(scopedSaved?.enabled && (scopedSaved?.pinHash || scopedSaved?.offlineVerifier))

  return {
    userId: uid || savedUid || null,
    enabled,
    syncedWithAccount: hasServerLockMeta,
    pinHash: enabled && sameOwner ? String(scopedSaved?.pinHash || '') : '',
    offlineVerifier: enabled && sameOwner ? String(scopedSaved?.offlineVerifier || '') : '',
    offlineSalt: enabled && sameOwner ? String(scopedSaved?.offlineSalt || '') : '',
    biometricEnabled: Boolean(enabled && scopedSaved?.biometricEnabled),
    biometricCredentialId: enabled
      ? String(scopedSaved?.biometricCredentialId || '')
      : '',
    lockedUntil: currentUser?.app_lock?.locked_until || null,
    updatedAt: Number(currentUser?.app_lock?.pin_updated_at || scopedSaved?.updatedAt || 0),
  }
}

export function syncAccountPinMetadata({ userId = null, appLock = null } = {}) {
  if (!appLock) return getAppLockConfig(userId ? { id: userId } : null)
  const uid = userId ? Number(userId) : null
  if (!appLock.pin_enabled) {
    return clearAppLock()
  }
  const prev = readStorageJson(APP_LOCK_KEY, null)
  const sameOwner = !uid || !prev?.userId || Number(prev.userId) === uid
  const serverUpdatedAt = Number(appLock.pin_updated_at || 0)
  const prevUpdatedAt = Number(prev?.updatedAt || 0)
  const keepOfflineVerifier =
    Boolean(sameOwner && prev?.offlineVerifier && serverUpdatedAt > 0 && prevUpdatedAt === serverUpdatedAt)

  const record = {
    userId: uid || prev?.userId || null,
    enabled: true,
    pinHash: '',
    offlineVerifier: keepOfflineVerifier ? String(prev.offlineVerifier) : '',
    offlineSalt: keepOfflineVerifier ? String(prev.offlineSalt || '') : '',
    biometricEnabled: sameOwner ? Boolean(prev?.biometricEnabled) : false,
    biometricCredentialId: sameOwner ? String(prev?.biometricCredentialId || '') : '',
    updatedAt: serverUpdatedAt || Math.floor(Date.now() / 1000),
  }
  writeStorageJson(APP_LOCK_KEY, record)
  return getAppLockConfig({ id: uid, app_lock: appLock })
}

export async function savePinLock(pin = '', biometricOpts = null) {
  const prev = getAppLockConfig()
  const uid = biometricOpts?.userId ? Number(biometricOpts.userId) : prev.userId
  const salt = generateLocalSaltHex()
  const offlineVerifier = await hashPinCode(pin, `v3:${uid || 'local'}:${salt}`)
  const record = {
    userId: uid || null,
    enabled: true,
    pinHash: '',
    offlineVerifier,
    offlineSalt: salt,
    biometricEnabled:
      biometricOpts && typeof biometricOpts.biometricEnabled === 'boolean'
        ? biometricOpts.biometricEnabled
        : prev.biometricEnabled,
    biometricCredentialId:
      biometricOpts?.credentialId !== undefined
        ? biometricOpts.credentialId
        : prev.biometricCredentialId,
    updatedAt: Number(biometricOpts?.updatedAt || Math.floor(Date.now() / 1000)),
  }
  writeStorageJson(APP_LOCK_KEY, record)
  return getAppLockConfig(
    uid
      ? { id: uid, app_lock: { pin_enabled: true, pin_updated_at: record.updatedAt } }
      : null
  )
}

export function updateAppLockBiometric({
  userId = null,
  biometricEnabled = false,
  biometricCredentialId = '',
  appLock = null,
}) {
  const prev = getAppLockConfig(userId || appLock ? { id: userId, app_lock: appLock } : null)
  if (!prev.enabled) return prev
  const next = {
    userId: userId || prev.userId || null,
    enabled: true,
    pinHash: prev.pinHash || '',
    offlineVerifier: prev.offlineVerifier || '',
    offlineSalt: prev.offlineSalt || '',
    biometricEnabled: Boolean(biometricEnabled),
    biometricCredentialId: biometricEnabled
      ? String(biometricCredentialId || prev.biometricCredentialId || '')
      : '',
    updatedAt: prev.updatedAt || Math.floor(Date.now() / 1000),
  }
  writeStorageJson(APP_LOCK_KEY, next)
  return {
    ...prev,
    ...next,
    syncedWithAccount: prev.syncedWithAccount,
    lockedUntil: prev.lockedUntil,
  }
}

export function clearAppLock() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.removeItem(APP_LOCK_KEY)
      window.localStorage.removeItem(LEGACY_PATTERN_LOCK_KEY)
    }
  } catch {
    // ignore
  }
  return {
    userId: null,
    enabled: false,
    syncedWithAccount: false,
    pinHash: '',
    offlineVerifier: '',
    offlineSalt: '',
    biometricEnabled: false,
    biometricCredentialId: '',
    lockedUntil: null,
    updatedAt: 0,
  }
}

async function verifyLocalOfflinePin(cfg, pin) {
  if (!cfg.enabled) return true
  if (cfg.offlineVerifier && cfg.offlineSalt) {
    const candidate = await hashPinCode(pin, `v3:${cfg.userId || 'local'}:${cfg.offlineSalt}`)
    return candidate === cfg.offlineVerifier
  }
  if (cfg.pinHash) {
    const legacy = await hashPinCode(pin)
    return legacy === cfg.pinHash
  }
  return false
}

export async function verifyPinCode(pin = '', opts = null) {
  const { token = '', currentUser = null, onUnauthorized = null } = opts || {}
  const cfg = getAppLockConfig(currentUser)
  if (!cfg.enabled) return { verified: true, source: 'disabled' }

  if (token) {
    try {
      const res = await apiRequest(
        '/api/users/pin/verify',
        { method: 'POST', body: { pin: String(pin || '').trim() } },
        token,
        onUnauthorized
      )
      if (res?.verified) {
        await savePinLock(pin, {
          userId: currentUser?.id || cfg.userId,
          updatedAt: cfg.updatedAt,
          biometricEnabled: cfg.biometricEnabled,
          credentialId: cfg.biometricCredentialId,
        })
        return { verified: true, source: 'server' }
      }
      const retryAfter = Number(res?.retry_after || 0)
      const rem = Number(res?.remaining_attempts ?? 0)
      const errText =
        retryAfter > 0
          ? `Terlalu banyak percobaan salah. Tunggu ${retryAfter} detik.`
          : rem > 0
            ? `PIN tidak cocok (sisa ${rem} percobaan sebelum jeda pengaman)`
            : 'PIN tidak cocok'
      return {
        verified: false,
        source: 'server',
        attempts: Number(res?.attempts || 1),
        remainingAttempts: rem,
        retryAfter,
        lockedUntil: res?.locked_until || null,
        error: errText,
      }
    } catch (err) {
      if (err?.status && err.status >= 400 && err.status < 500) {
        return {
          verified: false,
          source: 'server',
          locked: err.status === 429,
          error: err.message || 'Verifikasi PIN ditolak oleh server.',
        }
      }
      // Network offline / server unreachable -> lanjut fallback verifikator lokal tersalt
    }
  }

  const localOk = await verifyLocalOfflinePin(cfg, pin)
  if (localOk) {
    return { verified: true, source: 'offline' }
  }
  if (!cfg.offlineVerifier && !cfg.pinHash && token) {
    return {
      verified: false,
      source: 'offline',
      error: 'Koneksi internet diperlukan untuk verifikasi PIN akun di perangkat baru ini.',
    }
  }
  return { verified: false, source: 'offline', error: 'PIN tidak cocok' }
}

export function saveUserFeedbackEntry(entry) {
  const existing = readStorageJson(FEEDBACK_LOG_KEY, { items: [] })
  const prevItems = Array.isArray(existing.items) ? existing.items : []
  const next = {
    items: [
      {
        rating: Number(entry.rating || 5),
        comment: String(entry.comment || '').trim(),
        createdAt: Math.floor(Date.now() / 1000),
      },
      ...prevItems,
    ].slice(0, 10),
  }
  writeStorageJson(FEEDBACK_LOG_KEY, next)
  return next.items[0]
}

export function getLatestUserFeedback() {
  const existing = readStorageJson(FEEDBACK_LOG_KEY, { items: [] })
  return Array.isArray(existing.items) && existing.items.length > 0 ? existing.items[0] : null
}

