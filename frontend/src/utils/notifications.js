import { Capacitor, registerPlugin } from '@capacitor/core'
import { PushNotifications } from '@capacitor/push-notifications'
import { LocalNotifications } from '@capacitor/local-notifications'
import { apiRequest, getApiBaseUrl, isNativeApp } from '../api/client'

const VoltKuPushBridge = registerPlugin('VoltKuPushBridge')
const ANDROID_CHANNEL_ID = 'voltku_alerts'
const PUSH_TOKEN_CACHE_KEY = 'voltku_fcm_push_token'
const LAST_SEEN_NOTIF_KEY = 'voltku_last_seen_notif_id'

let activeListeners = []
let fcmInitializedForToken = ''

export function getLastSeenNotificationId() {
  const raw = Number(localStorage.getItem(LAST_SEEN_NOTIF_KEY) || 0)
  return Number.isFinite(raw) && raw > 0 ? raw : 0
}

export function setLastSeenNotificationId(id) {
  const num = Number(id || 0)
  if (Number.isFinite(num) && num > getLastSeenNotificationId()) {
    localStorage.setItem(LAST_SEEN_NOTIF_KEY, String(num))
  }
}

export async function ensureAndroidNotificationChannel() {
  if (!isNativeApp() || Capacitor.getPlatform() !== 'android') return
  try {
    await LocalNotifications.createChannel({
      id: ANDROID_CHANNEL_ID,
      name: 'Peringatan Listrik VoltKu',
      description: 'Notifikasi beban tinggi, tegangan ekstrem, & info tagihan.',
      importance: 5,
      visibility: 1,
      sound: 'default',
      vibration: true,
      lights: true,
      lightColor: '#0284c7',
    })
  } catch {
    // Abaikan di platform non-Android atau SDK lama
  }
}

export async function showLocalBannerNotification(item) {
  if (!item || !item.title) return
  const notifId = Number(item.id ? (item.id % 100000) + 100000 : Date.now() % 100000)

  if (isNativeApp()) {
    try {
      await ensureAndroidNotificationChannel()
      await LocalNotifications.schedule({
        notifications: [
          {
            id: notifId,
            title: item.title,
            body: item.body || '',
            channelId: ANDROID_CHANNEL_ID,
            smallIcon: 'ic_launcher',
            extra: item.data || (item.device_id ? { device_id: item.device_id } : {}),
          },
        ],
      })
      return
    } catch {
      // Lanjut fallback jika izin belum diberikan
    }
  }

  if (typeof window !== 'undefined' && 'Notification' in window) {
    if (window.Notification.permission === 'granted') {
      try {
        new window.Notification(item.title, {
          body: item.body || '',
          tag: `voltku-${item.id || Date.now()}`,
        })
      } catch {
        // Ignore browser notification errors
      }
    }
  }
}

export async function syncNativeWorkerSession(userToken, latestId = 0) {
  if (!isNativeApp() || Capacitor.getPlatform() !== 'android') return
  try {
    const apiBaseUrl = getApiBaseUrl()
    await VoltKuPushBridge.syncSession({
      apiBaseUrl,
      token: userToken || '',
      lastSeenId: Number(latestId || getLastSeenNotificationId() || 0),
    })
  } catch {
    // Plugin native belum terpasang di lingkungan web/test
  }
}

async function cleanupPushListeners() {
  while (activeListeners.length > 0) {
    const handle = activeListeners.pop()
    try {
      await handle?.remove?.()
    } catch {
      // ignore
    }
  }
}

export async function registerDeviceNotifications(userToken, callbacks = {}) {
  if (!userToken) return
  await syncNativeWorkerSession(userToken)

  if (isNativeApp()) {
    try {
      await ensureAndroidNotificationChannel()
      const localPerm = await LocalNotifications.checkPermissions()
      if (localPerm.display !== 'granted') {
        await LocalNotifications.requestPermissions()
      }

      if (fcmInitializedForToken !== userToken) {
        await cleanupPushListeners()
        fcmInitializedForToken = userToken

        const regHandle = await PushNotifications.addListener('registration', async (tok) => {
          const fcmVal = tok?.value?.trim()
          if (!fcmVal) return
          localStorage.setItem(PUSH_TOKEN_CACHE_KEY, fcmVal)
          try {
            await apiRequest(
              '/api/users/push-token',
              {
                method: 'POST',
                body: {
                  token: fcmVal,
                  platform: Capacitor.getPlatform() === 'ios' ? 'ios' : 'android',
                  device_label: `VoltKu ${Capacitor.getPlatform()}`,
                },
              },
              userToken
            )
          } catch {
            // Akan dicoba ulang pada sesi berikutnya
          }
        })
        activeListeners.push(regHandle)

        const fgHandle = await PushNotifications.addListener('pushNotificationReceived', async (pn) => {
          await showLocalBannerNotification({
            id: Date.now(),
            title: pn.title || 'VoltKu',
            body: pn.body || '',
            data: pn.data || {},
          })
          callbacks.onPushReceived?.(pn)
        })
        activeListeners.push(fgHandle)

        const tapHandle = await PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
          const devId = action?.notification?.data?.device_id
          callbacks.onNotificationTap?.(devId || '')
        })
        activeListeners.push(tapHandle)

        const localTapHandle = await LocalNotifications.addListener('localNotificationActionPerformed', (action) => {
          const devId = action?.notification?.extra?.device_id
          callbacks.onNotificationTap?.(devId || '')
        })
        activeListeners.push(localTapHandle)
      }

      const pushPerm = await PushNotifications.checkPermissions()
      let granted = pushPerm.receive === 'granted'
      if (!granted) {
        const asked = await PushNotifications.requestPermissions()
        granted = asked.receive === 'granted'
      }
      if (granted) {
        // Aman bila Firebase google-services.json belum dipasang: hanya reject halus
        await PushNotifications.register().catch(() => {})
      }
    } catch {
      // Tetap mengandalkan LocalNotifications + WorkManager fallback bila FCM belum dikonfigurasi
    }
  } else if (typeof window !== 'undefined' && 'Notification' in window) {
    if (window.Notification.permission === 'default') {
      // Jangan memblokir; minta secara halus jika user mengizinkan
      window.Notification.requestPermission().catch(() => {})
    }
  }
}

export async function unregisterDeviceNotifications(userToken) {
  fcmInitializedForToken = ''
  await cleanupPushListeners()
  await syncNativeWorkerSession('')

  const cached = localStorage.getItem(PUSH_TOKEN_CACHE_KEY) || ''
  if (cached && userToken) {
    try {
      await apiRequest(
        `/api/users/push-token?token=${encodeURIComponent(cached)}`,
        { method: 'DELETE' },
        userToken
      )
    } catch {
      // Abaikan error jaringan saat logout
    }
  }
  localStorage.removeItem(PUSH_TOKEN_CACHE_KEY)
}

export async function fetchAndNotifyNewInboxItems(userToken, { notifyNew = true } = {}) {
  if (!userToken) return null
  const prevSeen = getLastSeenNotificationId()
  const data = await apiRequest('/api/users/notifications?limit=25', {}, userToken)
  const items = Array.isArray(data?.items) ? data.items : []
  const latestId = Number(data?.latest_id || 0)

  if (notifyNew && prevSeen > 0 && items.length > 0) {
    const freshUnread = items
      .filter((it) => !it.is_read && Number(it.id) > prevSeen)
      .sort((a, b) => Number(a.id) - Number(b.id))
    for (const notif of freshUnread.slice(-3)) {
      await showLocalBannerNotification(notif)
    }
  }

  if (latestId > prevSeen) {
    setLastSeenNotificationId(latestId)
    await syncNativeWorkerSession(userToken, latestId)
  }

  return data
}

