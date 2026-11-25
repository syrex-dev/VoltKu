import { Capacitor } from '@capacitor/core'
import { SocialLogin } from '@capgo/capacitor-social-login'

let initializedClientId = ''
let gsiLoadPromise = null

const GOOGLE_REDIRECT_PENDING_KEY = 'voltku_google_oauth_pending'

/**
 * Muat skrip resmi Google Identity Services (GSI) untuk Web agar login popup
 * tidak membutuhkan redirect_uri khusus (cukup Authorized JavaScript origins)
 * dan tidak diblokir popup blocker karena klik terjadi langsung di tombol Google.
 */
export function loadGoogleGsiScript() {
  if (typeof window === 'undefined' || Capacitor.isNativePlatform()) {
    return Promise.resolve(null)
  }
  if (window.google?.accounts?.id) {
    return Promise.resolve(window.google.accounts.id)
  }
  if (gsiLoadPromise) return gsiLoadPromise

  gsiLoadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-voltku-gsi="1"]')
    if (existing) {
      existing.addEventListener('load', () => resolve(window.google?.accounts?.id || null))
      existing.addEventListener('error', () => {
        gsiLoadPromise = null
        reject(new Error('Gagal memuat Google Sign-In.'))
      })
      return
    }
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.dataset.voltkuGsi = '1'
    script.onload = () => resolve(window.google?.accounts?.id || null)
    script.onerror = () => {
      gsiLoadPromise = null
      reject(new Error('Gagal memuat Google Sign-In.'))
    }
    document.head.appendChild(script)
  })
  return gsiLoadPromise
}

/**
 * Inisialisasi Google Sign-In lintas Web dan Android APK menggunakan Client ID dari backend.
 */
export async function ensureGoogleAuthInitialized(webClientId) {
  const cleanId = String(webClientId || '').trim()
  if (!cleanId) return false
  if (initializedClientId === cleanId) return true

  const googleInitConfig = {
    webClientId: cleanId,
    mode: 'online',
    skipAuthOnlyAuthorizationAfterSignIn: true,
  }
  if (!Capacitor.isNativePlatform() && typeof window !== 'undefined') {
    googleInitConfig.redirectUrl = `${window.location.origin}/`
  }

  await SocialLogin.initialize({
    google: googleInitConfig,
  })
  initializedClientId = cleanId
  return true
}

/**
 * Fallback redirect tab yang sama jika popup diblokir browser seluler / PWA.
 */
export function startGoogleRedirectLogin(webClientId) {
  const cleanId = String(webClientId || '').trim()
  if (!cleanId || typeof window === 'undefined') return

  const nonce = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
  try {
    sessionStorage.setItem(GOOGLE_REDIRECT_PENDING_KEY, nonce)
  } catch {
    // Abaikan jika sessionStorage tidak tersedia
  }

  const params = new URLSearchParams({
    client_id: cleanId,
    redirect_uri: `${window.location.origin}/`,
    response_type: 'id_token',
    scope: 'openid email profile',
    nonce,
    prompt: 'select_account',
  })
  window.location.assign(`https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`)
}

/**
 * Ambil id_token jika baru saja kembali dari same-tab OAuth redirect fallback.
 */
export function consumeGoogleRedirectFromHash() {
  if (typeof window === 'undefined' || !window.location.hash) return null
  const rawHash = window.location.hash.replace(/^#/, '')
  const params = new URLSearchParams(rawHash)
  const idToken = params.get('id_token')
  const oauthError = params.get('error')
  if (!idToken && !oauthError) return null

  let pending = false
  try {
    pending = Boolean(sessionStorage.getItem(GOOGLE_REDIRECT_PENDING_KEY))
    sessionStorage.removeItem(GOOGLE_REDIRECT_PENDING_KEY)
  } catch {
    pending = false
  }
  if (!pending) return null

  try {
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
  } catch {
    // Abaikan
  }

  if (oauthError) {
    return { error: params.get('error_description') || oauthError }
  }
  return { idToken }
}

/**
 * Menjalankan alur Masuk dengan Google (native Credential Manager di APK / OAuth popup di Web
 * dengan fallback redirect tab yang sama bila popup diblokir browser).
 */
export async function signInWithGoogleForIdToken(webClientId) {
  const cleanId = String(webClientId || '').trim()
  if (!cleanId) {
    throw new Error('Login Google belum dikonfigurasi pada server VoltKu.')
  }

  await ensureGoogleAuthInitialized(cleanId)

  const loginOptions = Capacitor.isNativePlatform()
    ? { style: 'standard' }
    : { scopes: ['profile', 'email'], prompt: 'select_account' }

  try {
    const response = await SocialLogin.login({
      provider: 'google',
      options: loginOptions,
    })
    const idToken = response?.result?.idToken
    if (!idToken) {
      throw new Error('Google tidak mengembalikan ID Token yang valid.')
    }
    return idToken
  } catch (err) {
    const rawMsg = String(err?.message || err?.code || '').toLowerCase()
    if (!Capacitor.isNativePlatform() && rawMsg.includes('popup')) {
      startGoogleRedirectLogin(cleanId)
      return null
    }
    if (
      err?.code === 'USER_CANCELLED' ||
      rawMsg.includes('cancel') ||
      rawMsg.includes('closed')
    ) {
      throw new Error('Login Google dibatalkan.')
    }
    throw err
  }
}

export async function signOutGoogleIfInitialized() {
  if (!initializedClientId) return
  try {
    await SocialLogin.logout({ provider: 'google' })
  } catch {
    // Abaikan jika sesi Google native sudah kosong
  }
}
