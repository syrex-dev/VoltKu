const SYNC_CHANNEL_NAME = 'voltku_sync_v1'
const SYNC_STORAGE_KEY = 'voltku_sync_pulse_v1'
const TAB_SENDER_ID = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

let sharedChannel = null

function getBroadcastChannel() {
  if (typeof window === 'undefined' || typeof window.BroadcastChannel !== 'function') {
    return null
  }
  if (!sharedChannel) {
    try {
      sharedChannel = new window.BroadcastChannel(SYNC_CHANNEL_NAME)
    } catch {
      sharedChannel = null
    }
  }
  return sharedChannel
}

/**
 * Mengirim sinyal perubahan ringan antartab (Admin <-> Publik) pada browser yang sama.
 */
export function emitSyncSignal(scope = 'all', meta = {}) {
  if (typeof window === 'undefined') return
  const payload = {
    scope,
    meta,
    sender: TAB_SENDER_ID,
    ts: Date.now(),
  }
  const ch = getBroadcastChannel()
  if (ch) {
    try {
      ch.postMessage(payload)
    } catch {
      // Abaikan jika channel tertutup
    }
  }
  try {
    window.localStorage?.setItem(SYNC_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Abaikan jika storage penuh / mode privat
  }
}

/**
 * Mendengarkan sinyal perubahan dari tab lain dan mengembalikan fungsi unsubscribe.
 */
export function subscribeSyncSignal(onSignal) {
  if (typeof window === 'undefined' || typeof onSignal !== 'function') {
    return () => {}
  }

  const handlePayload = (payload) => {
    if (!payload || payload.sender === TAB_SENDER_ID) return
    onSignal(payload)
  }

  const ch = getBroadcastChannel()
  const onMessage = (ev) => handlePayload(ev?.data)
  if (ch) {
    ch.addEventListener('message', onMessage)
  }

  const onStorage = (ev) => {
    if (ev?.key !== SYNC_STORAGE_KEY || !ev.newValue) return
    try {
      handlePayload(JSON.parse(ev.newValue))
    } catch {
      // Abaikan JSON rusak
    }
  }
  window.addEventListener('storage', onStorage)

  return () => {
    if (ch) ch.removeEventListener('message', onMessage)
    window.removeEventListener('storage', onStorage)
  }
}

