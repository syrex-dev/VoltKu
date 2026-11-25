import { Capacitor } from '@capacitor/core'
import { SocialLogin } from '@capgo/capacitor-social-login'

let initializedClientId = ''

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
 * Menjalankan alur Masuk dengan Google (native Credential Manager di APK / OAuth popup di Web)
 * lalu mengembalikan Google ID Token untuk diverifikasi backend VoltKu.
 */
export async function signInWithGoogleForIdToken(webClientId) {
  const cleanId = String(webClientId || '').trim()
  if (!cleanId) {
    throw new Error('Login Google belum dikonfigurasi pada server VoltKu.')
  }

  await ensureGoogleAuthInitialized(cleanId)

  // Pada stock BridgeActivity Android, jangan kirim array scopes karena sudah default & akan ditolak
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

