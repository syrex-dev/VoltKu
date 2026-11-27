import { Capacitor, registerPlugin } from '@capacitor/core'

const VoltKuBiometric = Capacitor.isNativePlatform()
  ? registerPlugin('VoltKuBiometric')
  : null

function getRandomChallengeBytes(len = 32) {
  const bytes = new Uint8Array(len)
  if (typeof window !== 'undefined' && window.crypto?.getRandomValues) {
    window.crypto.getRandomValues(bytes)
    return bytes
  }
  for (let i = 0; i < len; i += 1) {
    bytes[i] = Math.floor(Math.random() * 256)
  }
  return bytes
}

function bytesToBase64Url(buf) {
  const arr = new Uint8Array(buf)
  let str = ''
  for (let i = 0; i < arr.length; i += 1) {
    str += String.fromCharCode(arr[i])
  }
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64UrlToBytes(b64u) {
  const b64 = String(b64u || '').replace(/-/g, '+').replace(/_/g, '/')
  const pad = b64.length % 4 === 0 ? '' : '='.repeat(4 - (b64.length % 4))
  const raw = atob(b64 + pad)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) {
    out[i] = raw.charCodeAt(i)
  }
  return out
}

/**
 * Periksa dukungan sensor sidik jari / biometrik pada perangkat (Android Native via
 * AndroidX BiometricPrompt, atau Web Browser via WebAuthn Platform Authenticator).
 */
export async function checkBiometricCapability() {
  if (Capacitor.isNativePlatform() && VoltKuBiometric) {
    try {
      const res = await VoltKuBiometric.isAvailable()
      return {
        available: Boolean(res?.available),
        status: res?.status || (res?.available ? 'ready' : 'unavailable'),
        reason: res?.reason || '',
        platform: 'android',
      }
    } catch {
      return {
        available: false,
        status: 'unavailable',
        reason: 'Sensor sidik jari tidak tersedia di perangkat ini.',
        platform: 'android',
      }
    }
  }

  if (typeof window === 'undefined') {
    return {
      available: false,
      status: 'unavailable',
      reason: 'Lingkungan tidak mendukung sensor biometrik.',
      platform: 'web',
    }
  }

  if (!window.isSecureContext) {
    return {
      available: false,
      status: 'insecure_context',
      reason: 'Sidik jari browser membutuhkan koneksi HTTPS aman; silakan gunakan PIN 6 digit.',
      platform: 'web',
    }
  }

  if (
    typeof window.PublicKeyCredential === 'undefined' ||
    typeof window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable !== 'function'
  ) {
    return {
      available: false,
      status: 'no_hardware',
      reason: 'Browser / perangkat ini tidak mendukung autentikasi sidik jari; gunakan PIN 6 digit.',
      platform: 'web',
    }
  }

  try {
    const ok = await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
    if (ok) {
      return {
        available: true,
        status: 'ready',
        reason: 'Autentikasi biometrik perangkat siap digunakan.',
        platform: 'web',
      }
    }
    return {
      available: false,
      status: 'none_enrolled',
      reason: 'Perangkat tidak memiliki sensor sidik jari aktif atau biometrik belum disiapkan.',
      platform: 'web',
    }
  } catch {
    return {
      available: false,
      status: 'unavailable',
      reason: 'Tidak dapat memverifikasi dukungan sidik jari; gunakan PIN 6 digit.',
      platform: 'web',
    }
  }
}

/**
 * Daftarkan sidik jari / biometrik lokal agar bisa digunakan untuk membuka Kunci Aplikasi.
 * Di Android langsung memverifikasi BiometricPrompt OS; di Web membuat WebAuthn platform credential.
 */
export async function enrollBiometricUnlock(userLabel = 'Pengguna VoltKu') {
  if (Capacitor.isNativePlatform() && VoltKuBiometric) {
    const res = await VoltKuBiometric.authenticate({
      title: 'Aktifkan Sidik Jari VoltKu',
      subtitle: 'Sentuh sensor sidik jari untuk mengonfirmasi',
      negativeText: 'Batal',
    })
    return {
      ok: Boolean(res?.verified),
      credentialId: res?.verified ? 'android_native_biometric' : '',
      message: res?.verified
        ? 'Sidik jari berhasil diaktifkan.'
        : res?.error || 'Verifikasi sidik jari dibatalkan.',
    }
  }

  try {
    const hostname = window.location.hostname || 'localhost'
    const cred = await navigator.credentials.create({
      publicKey: {
        challenge: getRandomChallengeBytes(32),
        rp: { name: 'VoltKu Smart Energy', id: hostname },
        user: {
          id: getRandomChallengeBytes(16),
          name: userLabel,
          displayName: userLabel,
        },
        pubKeyCredParams: [
          { type: 'public-key', alg: -7 },
          { type: 'public-key', alg: -257 },
        ],
        authenticatorSelection: {
          authenticatorAttachment: 'platform',
          userVerification: 'required',
        },
        timeout: 45000,
        attestation: 'none',
      },
    })
    if (!cred?.rawId) {
      return { ok: false, credentialId: '', message: 'Registrasi biometrik tidak selesai.' }
    }
    return {
      ok: true,
      credentialId: bytesToBase64Url(cred.rawId),
      message: 'Sidik jari / biometrik perangkat aktif!',
    }
  } catch (err) {
    const aborted = err?.name === 'NotAllowedError' || err?.name === 'AbortError'
    return {
      ok: false,
      credentialId: '',
      message: aborted
        ? 'Verifikasi biometrik dibatalkan atau belum tersedia di perangkat ini.'
        : 'Perangkat tidak dapat mengaktifkan biometrik; gunakan PIN 6 digit.',
    }
  }
}

/**
 * Jalankan verifikasi sidik jari / biometrik saat membuka Kunci Aplikasi.
 */
export async function authenticateWithBiometric(credentialId = '') {
  if (Capacitor.isNativePlatform() && VoltKuBiometric) {
    try {
      const res = await VoltKuBiometric.authenticate({
        title: 'Buka Kunci VoltKu',
        subtitle: 'Sentuh sensor sidik jari untuk masuk ke aplikasi',
        negativeText: 'Gunakan PIN',
      })
      return {
        verified: Boolean(res?.verified),
        cancelled: Boolean(res?.cancelled),
        error: res?.error || '',
      }
    } catch (err) {
      return {
        verified: false,
        cancelled: false,
        error: err?.message || 'Gagal membaca sidik jari.',
      }
    }
  }

  if (!credentialId || typeof navigator === 'undefined' || !navigator.credentials?.get) {
    return { verified: false, cancelled: false, error: 'Gunakan PIN 6 digit Anda.' }
  }

  try {
    const assertion = await navigator.credentials.get({
      publicKey: {
        challenge: getRandomChallengeBytes(32),
        allowCredentials: [
          {
            id: base64UrlToBytes(credentialId),
            type: 'public-key',
            transports: ['internal'],
          },
        ],
        userVerification: 'required',
        timeout: 45000,
      },
    })
    return { verified: Boolean(assertion?.rawId), cancelled: false, error: '' }
  } catch (err) {
    const cancelled = err?.name === 'NotAllowedError' || err?.name === 'AbortError'
    return {
      verified: false,
      cancelled,
      error: cancelled ? 'Verifikasi dibatalkan — masukkan PIN.' : 'Sidik jari gagal, gunakan PIN.',
    }
  }
}

