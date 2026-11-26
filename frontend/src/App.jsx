import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Capacitor } from '@capacitor/core'
import { App as CapApp } from '@capacitor/app'
import { StatusBar, Style } from '@capacitor/status-bar'
import {
  apiRequest,
  buildApiUrl,
  getOrCreateClientId,
  getStoredUserToken,
  setStoredUserToken,
  isNativeApp,
} from './api/client'
import {
  consumeGoogleRedirectFromHash,
  ensureGoogleAuthInitialized,
  signInWithGoogleForIdToken,
  signOutGoogleIfInitialized,
} from './utils/googleAuth'
import { Header } from './components/Header'
import { LoginModal } from './components/LoginModal'
import { AdminLoginScreen } from './components/AdminLoginScreen'
import { HomeDevicesView } from './components/HomeDevicesView'
import { WarningBanner } from './components/WarningBanner'
import { RealtimeTelemetry } from './components/RealtimeTelemetry'
import { EnergyMetrics } from './components/EnergyMetrics'
import { PowerChart } from './components/PowerChart'
import { DailyChart } from './components/DailyChart'
import { AnomaliesList } from './components/AnomaliesList'
import { SettingsView } from './components/SettingsView'
import { BottomNav } from './components/BottomNav'
import { AddDeviceModal } from './components/AddDeviceModal'
import { PwaInstallPrompt } from './components/PwaInstallPrompt'
import { AdminPanel } from './components/AdminPanel'
import { TermsAgreementModal } from './components/TermsAgreementModal'
import { OnboardingTour } from './components/OnboardingTour'
import { UsageGuideModal } from './components/UsageGuideModal'
import { PlanUpgradeModal } from './components/PlanUpgradeModal'
import { ProfileModal } from './components/ProfileModal'
import { ResetPasswordScreen } from './components/ResetPasswordScreen'
import { AiChatWidget } from './components/AiChatWidget'
import { BrandLogo } from './components/BrandLogo'
import { AppLockOverlay } from './components/PatternLockGrid'
import {
  clearPatternLock,
  getPatternLockConfig,
  useUserPrefs,
  verifyPatternLock,
} from './utils/userPrefs'
import {
  fetchAndNotifyNewInboxItems,
  registerDeviceNotifications,
  unregisterDeviceNotifications,
} from './utils/notifications'

const DEFAULT_LOGIN_SUBTITLE = 'Pantau listrik rumah lebih tenang dan akurat'
const DEFAULT_TERMS_VERSION = '2026-11-v1'
const TERMS_STORAGE_KEY = 'voltku_terms_accepted_version'
const WELCOME_SEEN_KEY = 'voltku_welcome_seen'
const TOUR_COMPLETED_KEY = 'voltku_tour_completed_v1'
const THEME_MANUAL_KEY = 'voltku_theme_manual'

const DEFAULT_APP_CONFIG = {
  app_name: 'VoltKu',
  app_tagline: DEFAULT_LOGIN_SUBTITLE,
  navbar_brand_display: 'logo_only',
  announcement_active: false,
  announcement_text: '',
  announcement_url: '',
  default_theme: 'light',
  onboarding_enabled: true,
  onboarding_steps: null,
  public_read_enabled: true,
  registration_enabled: true,
  google_enabled: false,
  google_auth_enabled: true,
  google_client_id: null,
  google_android_client_id: null,
  require_terms_consent: true,
  terms_version: DEFAULT_TERMS_VERSION,
  legal_updated_at: '25 November 2026',
  terms_title: 'Syarat & Ketentuan Layanan',
  terms_content: '',
  privacy_title: 'Kebijakan Privasi',
  privacy_content: '',
  support_whatsapp: '',
  support_telegram: '',
  support_email: '',
}

const isDeviceOnlineHelper = (dev, overrideLastTs = null) => {
  if (!dev) return false
  const nowSec = Math.floor(Date.now() / 1000)
  const ts = overrideLastTs || dev.last_seen_at || dev.last_data_ts
  const isRecent = ts ? nowSec - ts <= 120 : false
  return dev.status === 'online' && isRecent
}

function resolveDefaultTheme(defaultTheme = 'light') {
  if (defaultTheme === 'dark' || defaultTheme === 'light') return defaultTheme
  if (
    defaultTheme === 'system' &&
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches
  ) {
    return 'dark'
  }
  return 'light'
}

function useThemePreference(serverDefaultTheme = 'light') {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')

  useEffect(() => {
    if (!localStorage.getItem(THEME_MANUAL_KEY) && serverDefaultTheme) {
      const next = resolveDefaultTheme(serverDefaultTheme)
      setTheme(next)
    }
  }, [serverDefaultTheme])

  useEffect(() => {
    const isDark = theme === 'dark'
    const pageBg = isDark ? '#0d1117' : '#f4f6f9'
    const barBg = isDark ? '#0d1117' : '#ffffff'
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.style.colorScheme = theme
    document.documentElement.style.backgroundColor = pageBg
    if (document.body) {
      document.body.style.backgroundColor = pageBg
    }
    localStorage.setItem('theme', theme)
    const themeMeta = document.getElementById('app-theme-color')
    if (themeMeta) {
      themeMeta.setAttribute('content', barBg)
    }
    const colorSchemeMeta = document.getElementById('app-color-scheme')
    if (colorSchemeMeta) {
      colorSchemeMeta.setAttribute('content', theme)
    }
    const appleStatusMeta = document.getElementById('apple-status-bar-style')
    if (appleStatusMeta) {
      appleStatusMeta.setAttribute('content', isDark ? 'black-translucent' : 'default')
    }
    if (Capacitor.isNativePlatform()) {
      StatusBar.setStyle({ style: isDark ? Style.Dark : Style.Light }).catch(() => {})
      StatusBar.setBackgroundColor({ color: barBg }).catch(() => {})
    }
  }, [theme])

  const toggleTheme = useCallback(() => {
    localStorage.setItem(THEME_MANUAL_KEY, '1')
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggleTheme }
}

/**
 * Portal Khusus Operator Admin (/admin) — terpisah penuh dari UI Customer / Publik.
 */
function AdminPortalRoot() {
  const { theme, toggleTheme } = useThemePreference('light')
  const [adminToken, setAdminToken] = useState(
    () => sessionStorage.getItem('admin_token') || ''
  )
  const [adminLoginError, setAdminLoginError] = useState(null)
  const [isAddDeviceOpen, setIsAddDeviceOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const handleAdminLogout = useCallback(() => {
    setAdminToken('')
    sessionStorage.removeItem('admin_token')
  }, [])

  const handleAdminLogin = async (password) => {
    setAdminLoginError(null)
    try {
      const data = await apiRequest('/api/admin/login', {
        method: 'POST',
        body: { password },
      })
      setAdminToken(data.token)
      sessionStorage.setItem('admin_token', data.token)
    } catch (err) {
      setAdminLoginError(err.message || 'Kata sandi admin salah.')
    }
  }

  if (!adminToken) {
    return (
      <>
        <AdminLoginScreen
          onAdminLogin={handleAdminLogin}
          error={adminLoginError}
          theme={theme}
        />
        <PwaInstallPrompt hasBottomNav={false} />
      </>
    )
  }

  return (
    <>
      <AdminPanel
        token={adminToken}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenAddDevice={() => setIsAddDeviceOpen(true)}
        onLogout={handleAdminLogout}
        refreshSignal={refreshKey}
      />

      <AddDeviceModal
        isOpen={isAddDeviceOpen}
        onClose={() => setIsAddDeviceOpen(false)}
        token={adminToken}
        existingDevices={[]}
        onLogout={handleAdminLogout}
        onDeviceAdded={() => setRefreshKey((k) => k + 1)}
      />
    </>
  )
}

/**
 * Portal Pelanggan & Publik (/) — Multi-tenant & Mode Demo Tanpa Login (tanpa kontrol Admin).
 */
function CustomerPortalRoot() {
  const [publicAppConfig, setPublicAppConfig] = useState(DEFAULT_APP_CONFIG)
  const { theme, toggleTheme } = useThemePreference(publicAppConfig.default_theme)
  const { prefs } = useUserPrefs()
  const [isAppLocked, setIsAppLocked] = useState(() =>
    Boolean(getStoredUserToken() && getPatternLockConfig().enabled)
  )

  const [userToken, setUserToken] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const tokenFromUrl = urlParams.get('token')
    if (tokenFromUrl) {
      setStoredUserToken(tokenFromUrl)
      window.history.replaceState({}, document.title, window.location.pathname)
      return tokenFromUrl
    }
    return getStoredUserToken()
  })
  const [showLoginModal, setShowLoginModal] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.get('open_login') === '1') {
      urlParams.delete('open_login')
      const qs = urlParams.toString()
      window.history.replaceState(
        {},
        document.title,
        qs ? `${window.location.pathname}?${qs}` : window.location.pathname
      )
      return true
    }
    return false
  })
  const [currentUser, setCurrentUser] = useState(null)
  const [loginError, setLoginError] = useState(null)
  const [publicReadEnabled, setPublicReadEnabled] = useState(true)
  const [accessChecked, setAccessChecked] = useState(false)
  const [acceptedTermsVersion, setAcceptedTermsVersion] = useState(
    () => localStorage.getItem(TERMS_STORAGE_KEY) || ''
  )
  const [submittingConsent, setSubmittingConsent] = useState(false)
  const [termsDeclined, setTermsDeclined] = useState(false)
  const [termsReaderDoc, setTermsReaderDoc] = useState(null)
  const [welcomeSeen, setWelcomeSeen] = useState(
    () => localStorage.getItem(WELCOME_SEEN_KEY) === '1'
  )
  const [showTour, setShowTour] = useState(false)
  const [loginModalSubtitle, setLoginModalSubtitle] = useState('')
  const [pendingAddDevice, setPendingAddDevice] = useState(false)

  const [activeTab, setActiveTab] = useState('home')
  const [activeRoom, setActiveRoom] = useState('Semua')

  const [devices, setDevices] = useState([])
  const [activeDeviceId, setActiveDeviceId] = useState('')
  const [settings, setSettings] = useState(null)
  const [latestData, setLatestData] = useState(null)
  const [todaySummary, setTodaySummary] = useState(null)
  const [weekSummary, setWeekSummary] = useState(null)
  const [monthSummary, setMonthSummary] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [globalAnomalies, setGlobalAnomalies] = useState([])
  const [deviceAnomalies, setDeviceAnomalies] = useState([])
  const [powerPoints, setPowerPoints] = useState([])
  const [powerRange, setPowerRange] = useState('5h')
  const [dailyPoints, setDailyPoints] = useState([])
  const [exportingCsv, setExportingCsv] = useState(false)

  const [isAddDeviceOpen, setIsAddDeviceOpen] = useState(false)
  const [showUsageGuide, setShowUsageGuide] = useState(false)
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false)
  const [planModalReason, setPlanModalReason] = useState('')
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false)
  const [userNotifications, setUserNotifications] = useState([])
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0)

  const homePollRef = useRef(null)
  const pollTimerRef = useRef(null)
  const chartTimerRef = useRef(null)

  const activeTermsVersion = publicAppConfig.terms_version || DEFAULT_TERMS_VERSION
  const consentRequired = publicAppConfig.require_terms_consent !== false
  const isAuthenticated = Boolean(userToken)

  const needsGuestTermsAgreement =
    consentRequired && !isAuthenticated && acceptedTermsVersion !== activeTermsVersion
  const needsUserReconsent =
    consentRequired && isAuthenticated && Boolean(currentUser?.needs_terms_reconsent)
  const needsTermsAgreement = needsGuestTermsAgreement || needsUserReconsent
  const isTermsUpdate =
    needsUserReconsent || (Boolean(acceptedTermsVersion) && needsGuestTermsAgreement)

  const showWelcomeGate = !needsTermsAgreement && !termsDeclined && !userToken && !welcomeSeen
  const canReadDashboard = isAuthenticated || (accessChecked && publicReadEnabled)

  const appName = publicAppConfig.app_name || 'VoltKu'
  const effectiveLoginSubtitle =
    loginModalSubtitle || publicAppConfig.app_tagline || DEFAULT_LOGIN_SUBTITLE

  useEffect(() => {
    document.title = appName
  }, [appName])

  const checkPublicAccess = useCallback(async () => {
    try {
      const [appCfgRes, accessRes, oauthRes] = await Promise.all([
        apiRequest('/api/public/app-config').catch(() => null),
        apiRequest('/api/public/access').catch(() => null),
        apiRequest('/api/users/oauth-config').catch(() => null),
      ])

      if (appCfgRes) {
        setPublicAppConfig((prev) => ({ ...prev, ...appCfgRes }))
        if (typeof appCfgRes.public_read_enabled === 'boolean') {
          setPublicReadEnabled(appCfgRes.public_read_enabled)
        }
      } else {
        if (accessRes && typeof accessRes.public_read_enabled === 'boolean') {
          setPublicReadEnabled(accessRes.public_read_enabled)
        }
        if (oauthRes) {
          setPublicAppConfig((prev) => ({ ...prev, ...oauthRes }))
        }
      }
    } finally {
      setAccessChecked(true)
    }
  }, [])

  useEffect(() => {
    checkPublicAccess()
  }, [checkPublicAccess])

  const completeOnboardingSession = useCallback(
    (tokenVal, userObj) => {
      setUserToken(tokenVal)
      setStoredUserToken(tokenVal)
      setCurrentUser(userObj || null)
      if (userObj?.terms_version_accepted) {
        localStorage.setItem(TERMS_STORAGE_KEY, userObj.terms_version_accepted)
        setAcceptedTermsVersion(userObj.terms_version_accepted)
      }
      localStorage.setItem(WELCOME_SEEN_KEY, '1')
      setWelcomeSeen(true)
      setShowLoginModal(false)
      setLoginModalSubtitle('')
      setIsAppLocked(false)
      setActiveDeviceId('')
      setActiveTab('home')
    },
    []
  )

  const handleLogout = useCallback(() => {
    unregisterDeviceNotifications(userToken).catch(() => {})
    setUserToken('')
    setCurrentUser(null)
    setStoredUserToken('')
    setIsAppLocked(false)
    setUserNotifications([])
    setUnreadNotificationCount(0)
    signOutGoogleIfInitialized()
    setShowLoginModal(false)
    setActiveDeviceId('')
    setLatestData(null)
    setTodaySummary(null)
    setActiveTab('home')
    checkPublicAccess()
  }, [checkPublicAccess, userToken])

  const handleUnauthorized = useCallback(() => {
    if (userToken) {
      handleLogout()
    } else {
      setPublicReadEnabled(false)
    }
  }, [userToken, handleLogout])

  const refreshCurrentUser = useCallback(async () => {
    if (!userToken) return
    try {
      const profile = await apiRequest('/api/users/me', {}, userToken, handleUnauthorized)
      if (profile?.role === 'admin') {
        handleLogout()
        return
      }
      setCurrentUser(profile)
      if (profile?.terms_version_accepted) {
        localStorage.setItem(TERMS_STORAGE_KEY, profile.terms_version_accepted)
        setAcceptedTermsVersion(profile.terms_version_accepted)
      }
    } catch {
      setCurrentUser(null)
    }
  }, [userToken, handleUnauthorized, handleLogout])

  useEffect(() => {
    if (!userToken) {
      setCurrentUser(null)
      return
    }
    refreshCurrentUser()
  }, [userToken, refreshCurrentUser])

  const maybeTriggerOnboarding = useCallback(() => {
    if (
      publicAppConfig.onboarding_enabled !== false &&
      localStorage.getItem(TOUR_COMPLETED_KEY) !== '1'
    ) {
      setShowTour(true)
    }
  }, [publicAppConfig.onboarding_enabled])

  const handleUserLogin = async (email, password, acceptTerms = true) => {
    setLoginError(null)
    try {
      const data = await apiRequest('/api/users/login', {
        method: 'POST',
        body: {
          email,
          password,
          accept_terms: Boolean(acceptTerms),
          accepted_terms_version: activeTermsVersion,
          client_id: getOrCreateClientId(),
        },
      })
      completeOnboardingSession(data.token, data.user)
      if (pendingAddDevice) {
        setPendingAddDevice(false)
        setIsAddDeviceOpen(true)
      } else {
        maybeTriggerOnboarding()
      }
    } catch (err) {
      setLoginError(err.message || 'Email atau kata sandi salah.')
    }
  }

  const handleUserRegister = async (name, email, password, acceptTerms = true) => {
    setLoginError(null)
    try {
      const data = await apiRequest('/api/users/register', {
        method: 'POST',
        body: {
          name,
          email,
          password,
          accept_terms: Boolean(acceptTerms),
          accepted_terms_version: activeTermsVersion,
          client_id: getOrCreateClientId(),
        },
      })
      completeOnboardingSession(data.token, data.user)
      if (pendingAddDevice) {
        setPendingAddDevice(false)
        setIsAddDeviceOpen(true)
      } else {
        maybeTriggerOnboarding()
      }
    } catch (err) {
      setLoginError(err.message || 'Pendaftaran akun gagal.')
    }
  }

  const handleForgotPassword = async (email) => {
    const data = await apiRequest('/api/users/forgot-password', {
      method: 'POST',
      body: { email },
    })
    return data?.message || ''
  }

  const handleGoogleLogin = useCallback(
    async (acceptTerms = true, preObtainedIdToken = null) => {
      setLoginError(null)
      const cid =
        publicAppConfig.google_client_id || publicAppConfig.google_android_client_id
      if (!preObtainedIdToken && (!cid || !publicAppConfig.google_enabled)) {
        throw new Error('Masuk dengan Google sedang tidak tersedia saat ini.')
      }
      const idToken = preObtainedIdToken || (await signInWithGoogleForIdToken(cid))
      if (!idToken) {
        // Sedang dialihkan ke halaman OAuth same-tab (redirect fallback)
        return
      }
      const data = await apiRequest('/api/users/google', {
        method: 'POST',
        body: {
          id_token: idToken,
          accept_terms: Boolean(acceptTerms),
          accepted_terms_version: activeTermsVersion,
          client_id: getOrCreateClientId(),
        },
      })
      completeOnboardingSession(data.token, data.user)
      if (pendingAddDevice) {
        setPendingAddDevice(false)
        setIsAddDeviceOpen(true)
      } else {
        maybeTriggerOnboarding()
      }
    },
    [
      activeTermsVersion,
      completeOnboardingSession,
      maybeTriggerOnboarding,
      pendingAddDevice,
      publicAppConfig.google_android_client_id,
      publicAppConfig.google_client_id,
      publicAppConfig.google_enabled,
    ]
  )

  useEffect(() => {
    const cid = publicAppConfig.google_client_id || publicAppConfig.google_android_client_id
    if (publicAppConfig.google_enabled && cid) {
      ensureGoogleAuthInitialized(cid).catch(() => {})
    }
  }, [
    publicAppConfig.google_enabled,
    publicAppConfig.google_client_id,
    publicAppConfig.google_android_client_id,
  ])

  useEffect(() => {
    const redirectResult = consumeGoogleRedirectFromHash()
    if (!redirectResult) return
    if (redirectResult.error) {
      setLoginError(redirectResult.error)
      setShowLoginModal(true)
      return
    }
    if (redirectResult.idToken) {
      handleGoogleLogin(true, redirectResult.idToken).catch((err) => {
        setLoginError(err?.message || 'Gagal masuk menggunakan Google.')
        setShowLoginModal(true)
      })
    }
  }, [handleGoogleLogin])

  useEffect(() => {
    if (!userToken) {
      setUserNotifications([])
      setUnreadNotificationCount(0)
      return undefined
    }
    let cancelled = false

    const loadInbox = async (notifyNew) => {
      try {
        const res = await fetchAndNotifyNewInboxItems(userToken, { notifyNew })
        if (!cancelled && res) {
          setUserNotifications(Array.isArray(res.items) ? res.items : [])
          setUnreadNotificationCount(Number(res.unread_count || 0))
        }
      } catch {
        // Abaikan error sementara saat polling
      }
    }

    registerDeviceNotifications(userToken, {
      onPushReceived: () => loadInbox(false),
      onNotificationTap: (devId) => {
        loadInbox(false)
        if (devId) {
          setActiveDeviceId(devId)
          setActiveTab('anomalies')
        }
      },
    })

    loadInbox(false)
    const timer = setInterval(() => loadInbox(true), 30000)
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        loadInbox(true)
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      cancelled = true
      clearInterval(timer)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [userToken])

  const handleMarkNotificationRead = useCallback(
    async (notificationId = null) => {
      if (!userToken) return
      try {
        await apiRequest(
          '/api/users/notifications/read',
          {
            method: 'POST',
            body: notificationId ? { notification_id: notificationId } : {},
          },
          userToken,
          handleUnauthorized
        )
        setUserNotifications((prev) =>
          prev.map((it) =>
            !notificationId || it.id === notificationId ? { ...it, is_read: true } : it
          )
        )
        setUnreadNotificationCount((prev) =>
          notificationId ? Math.max(0, prev - 1) : 0
        )
      } catch {
        // ignore
      }
    },
    [userToken, handleUnauthorized]
  )

  const handleSelectNotification = useCallback(
    (item) => {
      if (!item) return
      if (item.category === 'billing') {
        setIsPlanModalOpen(true)
        return
      }
      if (item.device_id) {
        setActiveDeviceId(item.device_id)
        setActiveTab('anomalies')
      } else {
        setActiveDeviceId('')
        setActiveTab('alerts')
      }
    },
    []
  )

  const handleAgreeTerms = async () => {
    setSubmittingConsent(true)
    const clientId = getOrCreateClientId()
    try {
      if (userToken) {
        const updatedUser = await apiRequest(
          '/api/users/terms-consent',
          {
            method: 'POST',
            body: {
              accepted: true,
              terms_version: activeTermsVersion,
              client_id: clientId,
            },
          },
          userToken,
          handleUnauthorized
        )
        setCurrentUser(updatedUser)
      } else {
        await apiRequest('/api/public/terms-consent', {
          method: 'POST',
          body: {
            accepted: true,
            terms_version: activeTermsVersion,
            client_id: clientId,
          },
        }).catch(() => null)
      }
      localStorage.setItem(TERMS_STORAGE_KEY, activeTermsVersion)
      setAcceptedTermsVersion(activeTermsVersion)
      setTermsDeclined(false)
      setTermsReaderDoc(null)
    } finally {
      setSubmittingConsent(false)
    }
  }

  const handleDeclineTerms = () => {
    if (isNativeApp()) {
      CapApp.exitApp().catch(() => {})
      return
    }
    setTermsDeclined(true)
  }

  const handleEnterGuestMode = () => {
    localStorage.setItem(WELCOME_SEEN_KEY, '1')
    setWelcomeSeen(true)
    setShowLoginModal(false)
    setPendingAddDevice(false)
    maybeTriggerOnboarding()
  }

  const finishTour = () => {
    localStorage.setItem(TOUR_COMPLETED_KEY, '1')
    setShowTour(false)
  }

  const readBase = userToken ? '/api' : '/api/public'

  const loadSettings = useCallback(async () => {
    if (!canReadDashboard) return
    try {
      const data = await apiRequest(`${readBase}/settings`, {}, userToken, handleUnauthorized)
      setSettings(data)
    } catch (err) {
      console.error('Gagal memuat pengaturan:', err)
    }
  }, [canReadDashboard, readBase, userToken, handleUnauthorized])

  const loadDevicesAndAlerts = useCallback(async () => {
    if (!canReadDashboard) return
    try {
      const [devs, allAlerts] = await Promise.all([
        apiRequest(`${readBase}/devices?include_latest=true`, {}, userToken, handleUnauthorized),
        apiRequest(`${readBase}/anomalies`, {}, userToken, handleUnauthorized).catch(() => []),
      ])
      setDevices(devs || [])
      setGlobalAnomalies(allAlerts || [])
      setActiveDeviceId((prev) => {
        if (prev && !(devs || []).some((d) => d.id === prev)) {
          return ''
        }
        return prev
      })
    } catch (err) {
      console.error('Gagal memuat daftar perangkat:', err)
    }
  }, [canReadDashboard, readBase, userToken, handleUnauthorized])

  const rooms = useMemo(() => {
    const locSet = new Set()
    let hasUnassigned = false
    devices.forEach((d) => {
      const loc = (d.location || '').trim()
      if (loc) locSet.add(loc)
      else hasUnassigned = true
    })
    const list = ['Semua', ...Array.from(locSet)]
    if (hasUnassigned && locSet.size > 0) {
      list.push('Lainnya')
    }
    return list
  }, [devices])

  const deviceNamesById = useMemo(() => {
    const map = {}
    devices.forEach((d) => {
      map[d.id] = d.name || d.id
    })
    return map
  }, [devices])

  useEffect(() => {
    if (!rooms.includes(activeRoom)) {
      setActiveRoom('Semua')
    }
  }, [rooms, activeRoom])

  const pollLatest = useCallback(async () => {
    if (!canReadDashboard || !activeDeviceId) return

    try {
      const latest = await apiRequest(
        `${readBase}/devices/${activeDeviceId}/latest`,
        {},
        userToken,
        handleUnauthorized
      )
      if (latest) setLatestData(latest)
    } catch {
      setLatestData(null)
    }

    try {
      const today = await apiRequest(
        `${readBase}/devices/${activeDeviceId}/summary?range=today`,
        {},
        userToken,
        handleUnauthorized
      )
      setTodaySummary(today)
    } catch {
      setTodaySummary(null)
    }
  }, [canReadDashboard, readBase, activeDeviceId, userToken, handleUnauthorized])

  const userPlan = isAuthenticated ? currentUser?.plan || null : null
  const freemiumActive = Boolean(isAuthenticated && userPlan?.freemium_enabled !== false)
  const historyDaysLimit = freemiumActive
    ? userPlan?.limits?.history_days ?? 3
    : 366
  const forecastEnabled = !freemiumActive || Boolean(userPlan?.limits?.forecast_enabled)
  const exportEnabled = !freemiumActive || Boolean(userPlan?.limits?.export_enabled)

  const openPlanModal = useCallback((reason = '') => {
    setPlanModalReason(reason || '')
    setIsPlanModalOpen(true)
  }, [])

  const loadPeriodicData = useCallback(async () => {
    if (!canReadDashboard || !activeDeviceId) return
    try {
      const [week, month, fc, anoms] = await Promise.all([
        apiRequest(
          `${readBase}/devices/${activeDeviceId}/summary?range=week`,
          {},
          userToken,
          handleUnauthorized
        ).catch(() => null),
        apiRequest(
          `${readBase}/devices/${activeDeviceId}/summary?range=month`,
          {},
          userToken,
          handleUnauthorized
        ).catch(() => null),
        forecastEnabled
          ? apiRequest(
              `${readBase}/devices/${activeDeviceId}/forecast`,
              {},
              userToken,
              handleUnauthorized
            ).catch(() => null)
          : Promise.resolve(null),
        apiRequest(
          `${readBase}/anomalies?device_id=${activeDeviceId}`,
          {},
          userToken,
          handleUnauthorized
        ).catch(() => []),
      ])
      setWeekSummary(week)
      setMonthSummary(month)
      setForecast(fc)
      setDeviceAnomalies(anoms || [])
    } catch (err) {
      console.error('Gagal memuat data periodik:', err)
    }
  }, [
    canReadDashboard,
    readBase,
    activeDeviceId,
    userToken,
    handleUnauthorized,
    forecastEnabled,
  ])

  const loadPowerChart = useCallback(
    async (rangeVal) => {
      if (!canReadDashboard || !activeDeviceId) return
      const nowSec = Math.floor(Date.now() / 1000)
      let dur = 5 * 3600
      if (rangeVal === '24h') dur = 24 * 3600
      else if (rangeVal === '3d') dur = 3 * 86400
      else if (rangeVal === '7d') dur = 7 * 86400
      else if (rangeVal === '30d') dur = 30 * 86400
      const fromTs = nowSec - dur

      try {
        const res = await apiRequest(
          `${readBase}/devices/${activeDeviceId}/series?from=${fromTs}&to=${nowSec}&resolution=auto`,
          {},
          userToken,
          handleUnauthorized
        )
        setPowerPoints(res?.points || [])
      } catch {
        setPowerPoints([])
      }
    },
    [canReadDashboard, readBase, activeDeviceId, userToken, handleUnauthorized]
  )

  const loadDailyChart = useCallback(async () => {
    if (!canReadDashboard || !activeDeviceId) return
    const nowSec = Math.floor(Date.now() / 1000)
    const dailyWindowDays = Math.min(historyDaysLimit, 14)
    const fromTs = nowSec - dailyWindowDays * 86400
    try {
      const res = await apiRequest(
        `${readBase}/devices/${activeDeviceId}/series?from=${fromTs}&to=${nowSec}&resolution=1d`,
        {},
        userToken,
        handleUnauthorized
      )
      setDailyPoints(res?.points || [])
    } catch {
      setDailyPoints([])
    }
  }, [canReadDashboard, readBase, activeDeviceId, userToken, handleUnauthorized, historyDaysLimit])

  useEffect(() => {
    if (!canReadDashboard) {
      setDevices([])
      setGlobalAnomalies([])
      clearInterval(homePollRef.current)
      return
    }
    loadSettings()
    loadDevicesAndAlerts()
    clearInterval(homePollRef.current)
    homePollRef.current = setInterval(loadDevicesAndAlerts, 15000)
    return () => clearInterval(homePollRef.current)
  }, [canReadDashboard, loadSettings, loadDevicesAndAlerts])

  useEffect(() => {
    if (!canReadDashboard || !activeDeviceId) {
      clearInterval(pollTimerRef.current)
      clearInterval(chartTimerRef.current)
      return
    }

    const startIntervals = () => {
      clearInterval(pollTimerRef.current)
      clearInterval(chartTimerRef.current)
      pollLatest()
      loadPeriodicData()
      loadPowerChart(powerRange)
      loadDailyChart()

      pollTimerRef.current = setInterval(pollLatest, 5000)
      chartTimerRef.current = setInterval(() => {
        loadPeriodicData()
        loadPowerChart(powerRange)
        loadDailyChart()
      }, 60000)
    }

    const stopIntervals = () => {
      clearInterval(pollTimerRef.current)
      clearInterval(chartTimerRef.current)
    }

    const handleVisibility = () => {
      if (document.visibilityState === 'hidden') stopIntervals()
      else startIntervals()
    }

    startIntervals()
    document.addEventListener('visibilitychange', handleVisibility)
    return () => {
      stopIntervals()
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [
    canReadDashboard,
    activeDeviceId,
    powerRange,
    pollLatest,
    loadPeriodicData,
    loadPowerChart,
    loadDailyChart,
  ])

  const handleSaveSettings = async (payload) => {
    if (!userToken) {
      setShowLoginModal(true)
      throw new Error('Silakan masuk atau daftar akun terlebih dahulu.')
    }
    const updated = await apiRequest(
      '/api/settings',
      { method: 'PATCH', body: payload },
      userToken,
      handleUnauthorized
    )
    setSettings(updated)
    if (activeDeviceId) loadPeriodicData()
  }

  const handleOpenDeviceDetail = (deviceId) => {
    setActiveDeviceId(deviceId)
    setLatestData(null)
    setTodaySummary(null)
    setWeekSummary(null)
    setMonthSummary(null)
    setForecast(null)
    setPowerPoints([])
    setDailyPoints([])
    setDeviceAnomalies([])
    setActiveTab('live')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSwitchDevice = (deviceId) => {
    if (!deviceId || deviceId === activeDeviceId) return
    setActiveDeviceId(deviceId)
    setLatestData(null)
    setTodaySummary(null)
    setWeekSummary(null)
    setMonthSummary(null)
    setForecast(null)
    setPowerPoints([])
    setDailyPoints([])
    setDeviceAnomalies([])
    if (!activeDevice) {
      setActiveTab('live')
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleRequestAddDevice = () => {
    if (!isAuthenticated) {
      setPendingAddDevice(true)
      setLoginError(null)
      setLoginModalSubtitle(
        'Masuk atau daftar akun terlebih dahulu untuk menambahkan panel listrik baru.'
      )
      setShowLoginModal(true)
      return
    }
    const maxDev = userPlan?.limits?.max_devices
    if (freemiumActive && typeof maxDev === 'number' && maxDev >= 0 && devices.length >= maxDev) {
      openPlanModal(
        `Kuota panel paket ${userPlan?.plan_name || 'Gratis'} sudah penuh (${devices.length}/${maxDev} panel). Upgrade ke ${publicAppConfig?.plans?.pro?.name || 'VoltKu Pro'} untuk menambah panel lagi.`
      )
      return
    }
    setIsAddDeviceOpen(true)
  }

  const handleExportDeviceCsv = async () => {
    if (!activeDeviceId || exportingCsv) return
    if (!userToken && !canReadDashboard) {
      setLoginError(null)
      setLoginModalSubtitle('Masuk ke akun Anda untuk mengunduh laporan CSV.')
      setShowLoginModal(true)
      return
    }
    if (isAuthenticated && !exportEnabled) {
      openPlanModal('Ekspor laporan konsumsi CSV tersedia pada paket VoltKu Pro.')
      return
    }

    setExportingCsv(true)
    try {
      const targetEndpoint = `${readBase}/devices/${encodeURIComponent(activeDeviceId)}/export?days=30`
      const headers = userToken ? { Authorization: `Bearer ${userToken}` } : {}
      const resp = await fetch(buildApiUrl(targetEndpoint), { headers })

      if (resp.status === 401) {
        if (userToken) {
          handleUnauthorized()
        } else {
          setLoginError(null)
          setLoginModalSubtitle('Masuk ke akun Anda untuk mengunduh laporan CSV.')
          setShowLoginModal(true)
        }
        return
      }
      if (resp.status === 403) {
        const errBody = await resp.json().catch(() => ({}))
        const msg =
          errBody?.error?.message || 'Ekspor laporan konsumsi CSV tersedia pada paket VoltKu Pro.'
        if (isAuthenticated) {
          openPlanModal(msg)
        } else {
          alert(msg)
        }
        return
      }
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}))
        throw new Error(errBody?.error?.message || 'Gagal mengunduh laporan CSV.')
      }

      const disposition = resp.headers.get('Content-Disposition') || ''
      const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/i)
      const fallbackName = `voltku-${String(activeDeviceId).replace(/[^A-Za-z0-9_-]/g, '_')}-30d.csv`
      const filename = filenameMatch?.[1]?.trim() || fallbackName

      const blob = await resp.blob()
      if (isNativeApp()) {
        const csvFile = new File([blob], filename, { type: 'text/csv;charset=utf-8' })
        if (
          typeof navigator !== 'undefined' &&
          typeof navigator.share === 'function' &&
          (!navigator.canShare || navigator.canShare({ files: [csvFile] }))
        ) {
          try {
            await navigator.share({
              files: [csvFile],
              title: filename,
              text: 'Laporan Konsumsi Listrik Harian VoltKu',
            })
            return
          } catch (shareErr) {
            if (shareErr?.name === 'AbortError') return
          }
        }
        const csvText = await blob.text()
        const a = document.createElement('a')
        a.href = `data:text/csv;charset=utf-8,${encodeURIComponent(csvText)}`
        a.download = filename
        a.style.display = 'none'
        document.body.appendChild(a)
        a.click()
        a.remove()
        return
      }

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1500)
    } catch (err) {
      alert(err?.message || 'Gagal mengunduh laporan CSV.')
    } finally {
      setExportingCsv(false)
    }
  }

  const handleTabChange = (nextTab) => {
    if (nextTab === 'home') {
      setActiveDeviceId('')
      setActiveTab('home')
      loadDevicesAndAlerts()
    } else if (nextTab === 'alerts' || nextTab === 'settings') {
      setActiveDeviceId('')
      setActiveTab(nextTab)
    } else {
      setActiveTab(nextTab)
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const activeDevice = devices.find((d) => d.id === activeDeviceId)
  const isDeviceScope = Boolean(activeDevice)
  const activeDeviceOnline = isDeviceOnlineHelper(activeDevice, latestData?.ts)
  const tariffNum = settings?.tariff_sen ? settings.tariff_sen / 100 : 1444.7

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return undefined
    let handleRef = null
    CapApp.addListener('backButton', () => {
      if (termsReaderDoc) {
        setTermsReaderDoc(null)
      } else if (isPlanModalOpen) {
        setIsPlanModalOpen(false)
      } else if (isProfileModalOpen) {
        setIsProfileModalOpen(false)
      } else if (showTour) {
        finishTour()
      } else if (isAddDeviceOpen) {
        setIsAddDeviceOpen(false)
      } else if (showLoginModal) {
        setShowLoginModal(false)
        setPendingAddDevice(false)
      } else if (activeDeviceId) {
        setActiveDeviceId('')
        setActiveTab('home')
      } else if (activeTab !== 'home') {
        setActiveTab('home')
      } else {
        CapApp.exitApp().catch(() => {})
      }
    }).then((h) => {
      handleRef = h
    })
    return () => {
      if (handleRef && handleRef.remove) {
        handleRef.remove()
      }
    }
  }, [
    termsReaderDoc,
    isPlanModalOpen,
    isProfileModalOpen,
    showTour,
    isAddDeviceOpen,
    showLoginModal,
    activeDeviceId,
    activeTab,
  ])

  if (!userToken && !accessChecked) {
    return null
  }

  if (termsDeclined && needsTermsAgreement) {
    return (
      <div className="auth-hero-backdrop clean-auth-bg">
        <div className="auth-card-modern clean-auth-card" style={{ textAlign: 'center' }}>
          <h2 className="auth-title">Persetujuan Diperlukan</h2>
          <p className="auth-subtitle" style={{ marginTop: 10 }}>
            Untuk melindungi data kelistrikan dan akun Anda, silakan tinjau dan setujui
            Syarat Penggunaan &amp; Kebijakan Privasi {appName}.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            style={{ width: '100%', marginTop: 18 }}
            onClick={() => setTermsDeclined(false)}
          >
            Tinjau Syarat &amp; Privasi
          </button>
        </div>
      </div>
    )
  }

  if (needsTermsAgreement) {
    return (
      <>
        <div className="auth-hero-backdrop clean-auth-bg" />
        <TermsAgreementModal
          isOpen
          isUpdate={isTermsUpdate}
          submitting={submittingConsent}
          termsVersion={activeTermsVersion}
          legalUpdatedAt={publicAppConfig.legal_updated_at}
          appName={appName}
          termsTitle={publicAppConfig.terms_title}
          termsContent={publicAppConfig.terms_content}
          privacyTitle={publicAppConfig.privacy_title}
          privacyContent={publicAppConfig.privacy_content}
          onAgree={handleAgreeTerms}
          onDecline={handleDeclineTerms}
        />
      </>
    )
  }

  if (showWelcomeGate || (!userToken && !publicReadEnabled)) {
    return (
      <>
        <LoginModal
          onLogin={handleUserLogin}
          onRegister={handleUserRegister}
          onGoogleLogin={handleGoogleLogin}
          onForgotPassword={handleForgotPassword}
          googleEnabled={publicAppConfig.google_enabled}
          googleClientId={publicAppConfig.google_client_id || publicAppConfig.google_android_client_id}
          registrationEnabled={publicAppConfig.registration_enabled !== false}
          termsAccepted={!needsTermsAgreement}
          onOpenTerms={(docType) => setTermsReaderDoc(docType || 'terms')}
          onTryGuest={publicReadEnabled ? handleEnterGuestMode : undefined}
          error={loginError}
          canClose={false}
          theme={theme}
          appName={appName}
          brandDisplay={publicAppConfig.navbar_brand_display}
          subtitle={effectiveLoginSubtitle}
        />
        <TermsAgreementModal
          isOpen={Boolean(termsReaderDoc)}
          readOnly
          initialDoc={termsReaderDoc}
          termsVersion={activeTermsVersion}
          legalUpdatedAt={publicAppConfig.legal_updated_at}
          appName={appName}
          termsTitle={publicAppConfig.terms_title}
          termsContent={publicAppConfig.terms_content}
          privacyTitle={publicAppConfig.privacy_title}
          privacyContent={publicAppConfig.privacy_content}
          onClose={() => setTermsReaderDoc(null)}
        />
        <PwaInstallPrompt hasBottomNav={false} appName={appName} />
      </>
    )
  }

  const hasForegroundOverlay =
    (showLoginModal && !userToken) ||
    (isAuthenticated && isAppLocked) ||
    (isAuthenticated && isAddDeviceOpen) ||
    showUsageGuide ||
    isPlanModalOpen ||
    (isAuthenticated && isProfileModalOpen) ||
    Boolean(termsReaderDoc) ||
    (showTour && !isDeviceScope && activeTab === 'home')

  return (
    <div
      className={`app-layout ${hasForegroundOverlay ? 'has-modal-open' : ''} ${
        prefs.labs?.compactCards ? 'app-compact-cards' : ''
      }`}
    >
      <Header
        activeTab={activeTab}
        onTabChange={handleTabChange}
        isDeviceScope={isDeviceScope}
        activeDevice={activeDevice}
        devices={devices}
        onSelectDevice={handleSwitchDevice}
        onOpenAddDevice={handleRequestAddDevice}
        isDeviceOnlineFn={(d) => isDeviceOnlineHelper(d)}
        deviceAnomalyCount={deviceAnomalies.length}
        globalAnomalyCount={globalAnomalies.length}
        theme={theme}
        isAuthenticated={isAuthenticated}
        currentUser={currentUser}
        onOpenLogin={() => {
          setPendingAddDevice(false)
          setLoginError(null)
          setLoginModalSubtitle('')
          setShowLoginModal(true)
        }}
        onOpenProfile={() => setIsProfileModalOpen(true)}
        appConfig={publicAppConfig}
        notifications={userNotifications}
        unreadNotificationCount={unreadNotificationCount}
        onMarkNotificationRead={handleMarkNotificationRead}
        onSelectNotification={handleSelectNotification}
      />

      <main className="container main-content-wrap has-bottom-nav">
        {!isDeviceScope && activeTab === 'home' && (
          <HomeDevicesView
            devices={devices}
            rooms={rooms}
            activeRoom={activeRoom}
            onSelectRoom={setActiveRoom}
            onSelectDevice={handleOpenDeviceDetail}
            onOpenAddDevice={handleRequestAddDevice}
            onOpenUsageGuide={() => setShowUsageGuide(true)}
            isDeviceOnlineFn={(d) => isDeviceOnlineHelper(d)}
            isAuthenticated={isAuthenticated}
            currentUser={currentUser}
            appConfig={publicAppConfig}
            onOpenPlanModal={openPlanModal}
            onOpenSettings={() => handleTabChange('settings')}
            onOpenAlerts={() => handleTabChange('alerts')}
            onOpenLogin={() => {
              setPendingAddDevice(false)
              setLoginError(null)
              setLoginModalSubtitle('')
              setShowLoginModal(true)
            }}
          />
        )}

        {!isDeviceScope && activeTab === 'alerts' && (
          <div className="tab-pane-fade">
            <AnomaliesList
              anomalies={globalAnomalies}
              showDeviceLabel
              deviceNamesById={deviceNamesById}
            />
          </div>
        )}

        {!isDeviceScope && activeTab === 'settings' && (
          <div className="tab-pane-fade">
            <SettingsView
              mode="global"
              settings={settings}
              token={userToken}
              isAuthenticated={isAuthenticated}
              currentUser={currentUser}
              theme={theme}
              onToggleTheme={toggleTheme}
              onSave={handleSaveSettings}
              onOpenLogin={() => {
                setPendingAddDevice(false)
                setLoginError(null)
                setLoginModalSubtitle('')
                setShowLoginModal(true)
              }}
              onLogout={handleLogout}
              onReplayTour={() => {
                setActiveDeviceId('')
                setActiveTab('home')
                setShowTour(true)
              }}
              onOpenTerms={(docType) => setTermsReaderDoc(docType || 'terms')}
              onOpenPlanModal={openPlanModal}
              appConfig={publicAppConfig}
            />
          </div>
        )}

        {isDeviceScope && activeTab === 'live' && (
          <div className="tab-pane-fade">
            <WarningBanner settings={settings} activeDevice={activeDevice} />
            <RealtimeTelemetry
              latest={latestData}
              settings={settings}
              activeDevice={activeDevice}
              isOnline={activeDeviceOnline}
              todaySummary={todaySummary}
              onGoToCharts={() => handleTabChange('charts')}
            />
          </div>
        )}

        {isDeviceScope && activeTab === 'charts' && (
          <div className="tab-pane-fade">
            <EnergyMetrics
              today={todaySummary}
              week={weekSummary}
              month={monthSummary}
              forecast={forecast}
              settings={settings}
              forecastLocked={!forecastEnabled}
              onOpenUpgrade={openPlanModal}
            />
            <div className="charts-desktop-grid">
              <PowerChart
                points={powerPoints}
                range={powerRange}
                onRangeChange={(newRange) => {
                  setPowerRange(newRange)
                  loadPowerChart(newRange)
                }}
                theme={theme}
                historyDaysLimit={historyDaysLimit}
                onOpenUpgrade={openPlanModal}
              />
              <DailyChart
                points={dailyPoints}
                theme={theme}
                tariff={tariffNum}
                historyDays={Math.min(historyDaysLimit, 14)}
                exportEnabled={exportEnabled}
                exporting={exportingCsv}
                onExportCsv={handleExportDeviceCsv}
                onOpenUpgrade={openPlanModal}
              />
            </div>
          </div>
        )}

        {isDeviceScope && activeTab === 'anomalies' && (
          <div className="tab-pane-fade">
            <AnomaliesList anomalies={deviceAnomalies} />
          </div>
        )}

        {isDeviceScope && activeTab === 'device_settings' && (
          <div className="tab-pane-fade">
            <SettingsView
              mode="device"
              settings={settings}
              activeDevice={activeDevice}
              token={userToken}
              isAuthenticated={isAuthenticated}
              currentUser={currentUser}
              onDeviceUpdated={() => loadDevicesAndAlerts()}
              onDeviceDeleted={async () => {
                await loadDevicesAndAlerts()
                await refreshCurrentUser()
                setActiveDeviceId('')
                setActiveTab('home')
              }}
              onOpenLogin={() => {
                setLoginError(null)
                setShowLoginModal(true)
              }}
              onLogout={handleLogout}
              appConfig={publicAppConfig}
            />
          </div>
        )}
      </main>

      <BottomNav
        activeTab={activeTab}
        onTabChange={handleTabChange}
        isDeviceScope={isDeviceScope}
        deviceAnomalyCount={deviceAnomalies.length}
        globalAnomalyCount={globalAnomalies.length}
      />

      {isAuthenticated && (
        <AddDeviceModal
          isOpen={isAddDeviceOpen}
          onClose={() => setIsAddDeviceOpen(false)}
          token={userToken}
          existingDevices={devices}
          onLogout={handleLogout}
          onPlanLimitReached={(msg) => openPlanModal(msg)}
          onDeviceAdded={async (newId) => {
            await loadDevicesAndAlerts()
            await refreshCurrentUser()
            if (newId) {
              setActiveDeviceId(newId)
              setActiveTab('live')
            }
          }}
        />
      )}

      {isAuthenticated && (
        <PlanUpgradeModal
          isOpen={isPlanModalOpen}
          onClose={() => {
            setIsPlanModalOpen(false)
            setPlanModalReason('')
          }}
          currentUser={currentUser}
          appConfig={publicAppConfig}
          token={userToken}
          onLogout={handleLogout}
          onUpgradeSubmitted={refreshCurrentUser}
          lockedReason={planModalReason}
        />
      )}

      {isAuthenticated && (
        <ProfileModal
          isOpen={isProfileModalOpen}
          onClose={() => setIsProfileModalOpen(false)}
          currentUser={currentUser}
          token={userToken}
          onLogout={handleLogout}
          onUserUpdated={(updatedUser) => setCurrentUser(updatedUser)}
          theme={theme}
          onToggleTheme={toggleTheme}
          onReplayTour={() => {
            setActiveDeviceId('')
            setActiveTab('home')
            setShowTour(true)
          }}
          onOpenUsageGuide={() => setShowUsageGuide(true)}
          onOpenTerms={(docType) => setTermsReaderDoc(docType || 'terms')}
          onOpenPlanModal={openPlanModal}
          onOpenSettings={() => handleTabChange('settings')}
          onOpenAddDevice={handleRequestAddDevice}
          onSelectDevice={handleOpenDeviceDetail}
          devices={devices}
          settings={settings}
          onSaveSettings={handleSaveSettings}
          isDeviceOnlineFn={(d) => isDeviceOnlineHelper(d)}
          onTriggerAppLock={() => setIsAppLocked(true)}
          appConfig={publicAppConfig}
        />
      )}

      {showLoginModal && !userToken && (
        <LoginModal
          onLogin={handleUserLogin}
          onRegister={handleUserRegister}
          onGoogleLogin={handleGoogleLogin}
          onForgotPassword={handleForgotPassword}
          googleEnabled={publicAppConfig.google_enabled}
          googleClientId={publicAppConfig.google_client_id || publicAppConfig.google_android_client_id}
          registrationEnabled={publicAppConfig.registration_enabled !== false}
          termsAccepted={!needsTermsAgreement}
          onOpenTerms={(docType) => setTermsReaderDoc(docType || 'terms')}
          error={loginError}
          subtitle={effectiveLoginSubtitle}
          canClose
          theme={theme}
          appName={appName}
          brandDisplay={publicAppConfig.navbar_brand_display}
          onClose={() => {
            setShowLoginModal(false)
            setPendingAddDevice(false)
            setLoginModalSubtitle('')
          }}
        />
      )}

      <TermsAgreementModal
        isOpen={Boolean(termsReaderDoc)}
        readOnly
        initialDoc={termsReaderDoc}
        termsVersion={activeTermsVersion}
        legalUpdatedAt={publicAppConfig.legal_updated_at}
        appName={appName}
        termsTitle={publicAppConfig.terms_title}
        termsContent={publicAppConfig.terms_content}
        privacyTitle={publicAppConfig.privacy_title}
        privacyContent={publicAppConfig.privacy_content}
        onClose={() => setTermsReaderDoc(null)}
      />

      <OnboardingTour
        isOpen={showTour && !isDeviceScope && activeTab === 'home'}
        steps={publicAppConfig.onboarding_steps}
        onComplete={finishTour}
        onSkip={finishTour}
      />

      <UsageGuideModal
        isOpen={showUsageGuide}
        onClose={() => setShowUsageGuide(false)}
        onStartAddDevice={handleRequestAddDevice}
      />

      {isAuthenticated && (
        <AiChatWidget
          token={userToken}
          onUnauthorized={handleUnauthorized}
          hidden={hasForegroundOverlay}
        />
      )}

      <PwaInstallPrompt hasBottomNav appName={appName} hidden={hasForegroundOverlay} />

      <AppLockOverlay
        isOpen={Boolean(isAuthenticated && isAppLocked)}
        userName={currentUser?.name || `Pengguna ${appName}`}
        userEmail={currentUser?.email || ''}
        appName={appName}
        theme={theme}
        BrandLogoComponent={BrandLogo}
        verifyPatternFn={verifyPatternLock}
        onUnlock={() => setIsAppLocked(false)}
        onResetAndLogout={() => {
          clearPatternLock()
          setIsAppLocked(false)
          handleLogout()
        }}
      />
    </div>
  )
}

function ResetPasswordPortalRoot() {
  const [appCfg, setAppCfg] = useState(DEFAULT_APP_CONFIG)
  const { theme } = useThemePreference(appCfg.default_theme)

  useEffect(() => {
    apiRequest('/api/public/app-config')
      .then((cfg) => {
        if (cfg) setAppCfg((prev) => ({ ...prev, ...cfg }))
      })
      .catch(() => {})
  }, [])

  const urlParams = new URLSearchParams(window.location.search)
  const token = (urlParams.get('token') || urlParams.get('reset_token') || '').trim()

  return (
    <ResetPasswordScreen
      initialToken={token}
      theme={theme}
      appName={appCfg.app_name || 'VoltKu'}
      brandDisplay={appCfg.navbar_brand_display}
    />
  )
}

export default function App() {
  const pathname = window.location.pathname
  const urlParams = new URLSearchParams(window.location.search)
  if (pathname.startsWith('/reset-password') || urlParams.has('reset_token')) {
    return <ResetPasswordPortalRoot />
  }
  const isAdminRoute = pathname.startsWith('/admin')
  return isAdminRoute ? <AdminPortalRoot /> : <CustomerPortalRoot />
}
