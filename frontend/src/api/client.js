const API_BASE_STORAGE_KEY = 'voltku_api_base_url'

export function isNativeApp() {
  if (typeof window === 'undefined') return false
  return Boolean(window.Capacitor?.isNativePlatform?.())
}

export function normalizeServerUrl(rawUrl) {
  const clean = String(rawUrl || '').trim().replace(/\/+$/, '')
  if (!clean) return ''
  if (!/^https?:\/\//i.test(clean)) {
    return `http://${clean}`
  }
  return clean
}

export function getApiBaseUrl() {
  if (typeof window === 'undefined') return ''
  const custom = localStorage.getItem(API_BASE_STORAGE_KEY) || ''
  if (custom.trim()) {
    return normalizeServerUrl(custom)
  }
  const envBase = import.meta.env?.VITE_API_BASE_URL || ''
  return normalizeServerUrl(envBase)
}

export function setApiBaseUrl(rawUrl) {
  const normalized = normalizeServerUrl(rawUrl)
  if (!normalized) {
    localStorage.removeItem(API_BASE_STORAGE_KEY)
    return ''
  }
  localStorage.setItem(API_BASE_STORAGE_KEY, normalized)
  return normalized
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
  const baseConfigured = Boolean(getApiBaseUrl())

  if (typeof window !== 'undefined' && window.location.protocol === 'file:' && !baseConfigured) {
    throw new Error('Aplikasi harus dibuka melalui server web atau atur URL server VoltKu.')
  }

  if (isNativeApp() && !baseConfigured && !/^https?:\/\//i.test(targetUrl)) {
    throw new Error(
      'Alamat server VoltKu belum diatur. Ketuk ikon Server untuk memasukkan IP LAN atau URL tunnel backend.'
    )
  }

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
        errData?.error?.message || `Terlalu banyak percobaan. Coba lagi dalam ${retryAfter} detik.`
      throw new Error(msg)
    }
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}))
      const msg = errData?.error?.message || `Error ${resp.status}: Permintaan gagal.`
      throw new Error(msg)
    }
    return await resp.json()
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      const destLabel = baseConfigured ? getApiBaseUrl() : 'server backend VoltKu'
      throw new Error(`Gagal terhubung ke ${destLabel}. Pastikan server aktif dan terjangkau.`)
    }
    throw err
  }
}
