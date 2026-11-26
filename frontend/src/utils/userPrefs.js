import { useState, useEffect, useCallback } from 'react'

const PREFS_STORAGE_KEY = 'voltku_user_prefs_v1'
const PATTERN_LOCK_KEY = 'voltku_pattern_lock_v1'
const FEEDBACK_LOG_KEY = 'voltku_user_feedback_v1'
const PREFS_EVENT = 'voltku:prefs-updated'

export const APP_VERSION_TAG = 'v2.5.0'
export const APP_PACKAGE_ID = 'com.voltku.energy'

export const DEFAULT_USER_PREFS = {
  locale: 'id',
  timezone: 'Asia/Jakarta',
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
      'Tambahan Kunci Pola Aplikasi 3x3 (terhash SHA-256 lokal) untuk proteksi privasi ekstra.',
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
    navSettings: 'Setelan',
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
    patternTitle: 'Kunci Pola Aplikasi',
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
    navSettings: 'Settings',
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
    patternTitle: 'Pattern Lock',
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

export async function hashPatternSequence(nodes = []) {
  const payload = `voltku:pattern:v1:${nodes.join('-')}`
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

export function getPatternLockConfig() {
  const saved = readStorageJson(PATTERN_LOCK_KEY, null)
  if (!saved || !saved.hash) {
    return { enabled: false, hash: '', updatedAt: 0 }
  }
  return {
    enabled: Boolean(saved.enabled),
    hash: String(saved.hash),
    updatedAt: Number(saved.updatedAt || 0),
  }
}

export async function savePatternLock(nodes = []) {
  const hash = await hashPatternSequence(nodes)
  const record = {
    enabled: true,
    hash,
    updatedAt: Math.floor(Date.now() / 1000),
  }
  writeStorageJson(PATTERN_LOCK_KEY, record)
  return record
}

export function clearPatternLock() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.removeItem(PATTERN_LOCK_KEY)
    }
  } catch {
    // ignore
  }
  return { enabled: false, hash: '', updatedAt: 0 }
}

export async function verifyPatternLock(nodes = []) {
  const cfg = getPatternLockConfig()
  if (!cfg.enabled || !cfg.hash) return true
  const candidate = await hashPatternSequence(nodes)
  return candidate === cfg.hash
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

