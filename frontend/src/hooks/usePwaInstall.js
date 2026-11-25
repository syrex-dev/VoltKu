import { useEffect, useState } from 'react'

let globalDeferredPrompt = null
const promptListeners = new Set()

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    globalDeferredPrompt = e
    promptListeners.forEach((fn) => fn(globalDeferredPrompt))
  })

  window.addEventListener('appinstalled', () => {
    globalDeferredPrompt = null
    promptListeners.forEach((fn) => fn(null))
  })
}

export function detectPlatform() {
  if (typeof navigator === 'undefined') return 'desktop'
  const ua = navigator.userAgent || ''
  if (/iphone|ipad|ipod/i.test(ua)) return 'ios'
  if (/android/i.test(ua)) return 'android'
  return 'desktop'
}

export function checkStandaloneMode() {
  if (typeof window === 'undefined') return false
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  )
}

export function usePwaInstall() {
  const [deferredPrompt, setDeferredPrompt] = useState(globalDeferredPrompt)
  const [isInstalled, setIsInstalled] = useState(() => checkStandaloneMode())
  const [platform] = useState(() => detectPlatform())

  useEffect(() => {
    const updatePrompt = (p) => setDeferredPrompt(p)
    promptListeners.add(updatePrompt)

    const onDisplayChange = () => {
      setIsInstalled(checkStandaloneMode())
    }
    const onInstalled = () => {
      setIsInstalled(true)
      setDeferredPrompt(null)
      globalDeferredPrompt = null
    }

    const mq = window.matchMedia('(display-mode: standalone)')
    mq.addEventListener?.('change', onDisplayChange)
    window.addEventListener('appinstalled', onInstalled)

    return () => {
      promptListeners.delete(updatePrompt)
      mq.removeEventListener?.('change', onDisplayChange)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  const install = async () => {
    if (!deferredPrompt) return 'manual'
    try {
      await deferredPrompt.prompt()
      const choice = await deferredPrompt.userChoice
      if (choice.outcome === 'accepted') {
        globalDeferredPrompt = null
        setDeferredPrompt(null)
        setIsInstalled(true)
      }
      return choice.outcome
    } catch {
      return 'dismissed'
    }
  }

  return {
    canInstall: Boolean(deferredPrompt) && !isInstalled,
    isInstalled,
    isIos: platform === 'ios',
    platform,
    install,
  }
}
