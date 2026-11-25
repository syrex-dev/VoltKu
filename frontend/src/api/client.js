const DEFAULT_NATIVE_API_BASE_URL = 'https://voltku.synemax.web.id'
const CLIENT_ID_STORAGE_KEY = 'voltku_client_id'

export function isNativeApp() {
  if (typeof window === 'undefined') return false
  return Boolean(window.Capacitor?.isNativePlatform?.())
}

export function normalizeServerUrl(rawUrl) {
  const clean = String(rawUrl || '').trim().replace(/\/+$/, '')
  if (!clean) return ''
  if (!/^https?:\/\//i.test(clean)) {
    return `https://${clean}`
  }
  return clean
}

export function getApiBaseUrl() {
  if (typeof window === 'undefined') return ''
  const envBase = import.meta.env?.VITE_API_BASE_URL || ''
  if (envBase.trim()) {
    return normalizeServerUrl(envBase)
  }
  if (isNativeApp()) {
    return DEFAULT_NATIVE_API_BASE_URL
  }
  return ''
}

export function getOrCreateClientId() {
  if (typeof window === 'undefined') return 'server-client'
  try {
    let cid = localStorage.getItem(CLIENT_ID_STORAGE_KEY) || ''
    if (cid.trim().length >= 8) return cid.trim()
    const prefix = isNativeApp() ? 'apk' : 'web'
    const rand =
      typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
    cid = `${prefix}-${rand}`
    localStorage.setItem(CLIENT_ID_STORAGE_KEY, cid)
    return cid
  } catch {
    return `ephem-${Date.now().toString(36)}`
  }
}

export function buildApiUrl(endpoint) {
  if (!endpoint) return ''
  if (/^https?:\/\//i.test(endpoint)) return endpoint
  const base = getApiBaseUrl()
  if (!base) return endpoint
  return endpoint.startsWith('/') ? `${base}${endpoint}` : `${base}/${endpoint}`
}

export function getStoredUserToken() {
  return localStorage.getItem('user_token') || sessionStorage.getItem('user_token') || ''
}

export function setStoredUserToken(token) {
  if (!token) {
    localStorage.removeItem('user_token')
    sessionStorage.removeItem('user_token')
    return
  }
  localStorage.setItem('user_token', token)
  sessionStorage.setItem('user_token', token)
}

export async function apiRequest(endpoint, options = {}, token = '', onUnauthorized = null) {
  const targetUrl = buildApiUrl(endpoint)

  const fetchOptions = { ...options }
  const headers = { ...(options.headers || {}) }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (fetchOptions.body && typeof fetchOptions.body === 'object') {
    headers['Content-Type'] = 'application/json'
    fetchOptions.body = JSON.stringify(fetchOptions.body)
  }
  fetchOptions.headers = headers

  try {
    const resp = await fetch(targetUrl, fetchOptions)
    if (resp.status === 401) {
      if (onUnauthorized) onUnauthorized()
      throw new Error('Sesi telah berakhir atau kredensial tidak valid.')
    }
    if (resp.status === 429) {
      const retryAfter = resp.headers.get('Retry-After') || '30'
      const errData = await resp.json().catch(() => ({}))
      const msg =
        errData?.error?.message ||
        `Terlalu banyak percobaan. Coba lagi dalam ${retryAfter} detik.`
      throw new Error(msg)
    }

    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
      const errMsg = data?.error?.message || data?.detail || `HTTP ${resp.status}`
      throw new Error(errMsg)
    }
    return data
  } catch (err) {
    if (err?.message === 'Failed to fetch' || err?.name === 'TypeError') {
      throw new Error('Gagal terhubung ke server VoltKu. Periksa koneksi internet Anda.')
    }
    throw err
  }
}
