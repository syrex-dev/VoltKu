import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Capacitor } from '@capacitor/core'
import { App as CapApp } from '@capacitor/app'
import { StatusBar, Style } from '@capacitor/status-bar'
import {
  apiRequest,
  getStoredUserToken,
  setStoredUserToken,
  isNativeApp,
} from './api/client'
import {
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
import { ServerConfigModal } from './components/ServerConfigModal'

const DEFAULT_LOGIN_SUBTITLE = 'Pantau dan kelola pemakaian listrik rumah secara real-time'
const DEFAULT_TERMS_VERSION = '2026-11-v1'
const TERMS_STORAGE_KEY = 'voltku_terms_accepted_version'
const WELCOME_SEEN_KEY = 'voltku_welcome_seen'
const TOUR_COMPLETED_KEY = 'voltku_tour_completed_v1'

const isDeviceOnlineHelper = (dev, overrideLastTs = null) => {
  if (!dev) return false
  const nowSec = Math.floor(Date.now() / 1000)
  const ts = overrideLastTs || dev.last_seen_at || dev.last_data_ts
  const isRecent = ts ? nowSec - ts <= 120 : false
  return dev.status === 'online' && isRecent
}

function useThemePreference() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
    const themeMeta = document.getElementById('app-theme-color')
    if (themeMeta) {
      themeMeta.setAttribute('content', theme === 'dark' ? '#161b22' : '#ffffff')
    }
    if (Capacitor.isNativePlatform()) {
      StatusBar.setStyle({ style: theme === 'dark' ? Style.Dark : Style.Light }).catch(() => {})
      StatusBar.setBackgroundColor({
        color: theme === 'dark' ? '#161b22' : '#ffffff',
      }).catch(() => {})
    }
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggleTheme }
}

/**
 * Portal Khusus Operator Admin (/admin) — terpisah penuh dari UI Customer / Publik.
 */
function AdminPortalRoot() {
  const { theme, toggleTheme } = useThemePreference()
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
        <AdminLoginScreen onAdminLogin={handleAdminLogin} error={adminLoginError} />
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

      <PwaInstallPrompt hasBottomNav />
    </>
  )
}

/**
 * Portal Pelanggan & Publik (/) — Multi-tenant & Mode Demo Tanpa Login (tanpa kontrol Admin).
 */
function CustomerPortalRoot() {
  const { theme, toggleTheme } = useThemePreference()
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
  const [currentUser, setCurrentUser] = useState(null)
  const [loginError, setLoginError] = useState(null)
  const [publicReadEnabled, setPublicReadEnabled] = useState(true)
  const [accessChecked, setAccessChecked] = useState(false)
  const [oauthConfig, setOauthConfig] = useState({
    google_enabled: false,
    google_client_id: null,
    google_android_client_id: null,
    terms_version: DEFAULT_TERMS_VERSION,
  })
  const [acceptedTermsVersion, setAcceptedTermsVersion] = useState(
    () => localStorage.getItem(TERMS_STORAGE_KEY) || ''
  )
  const [termsDeclined, setTermsDeclined] = useState(false)
  const [termsReaderDoc, setTermsReaderDoc] = useState(null)
  const [welcomeSeen, setWelcomeSeen] = useState(
    () => localStorage.getItem(WELCOME_SEEN_KEY) === '1'
  )
  const [showTour, setShowTour] = useState(false)
  const [isServerModalOpen, setIsServerModalOpen] = useState(false)
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [loginModalSubtitle, setLoginModalSubtitle] = useState(DEFAULT_LOGIN_SUBTITLE)
  const [pendingAddDevice, setPendingAddDevice] = useState(false)

  // Two-tier Navigation:
  // Home Scope (activeDeviceId === ''): 'home' | 'alerts' | 'settings'
  // Device Scope (activeDeviceId !== ''): 'live' | 'charts' | 'anomalies' | 'device_settings'
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

  const [isAddDeviceOpen, setIsAddDeviceOpen] = useState(false)

  const homePollRef = useRef(null)
  const pollTimerRef = useRef(null)
  const chartTimerRef = useRef(null)

  const activeTermsVersion = oauthConfig.terms_version || DEFAULT_TERMS_VERSION
  const needsTermsAgreement = acceptedTermsVersion !== activeTermsVersion
  const isTermsUpdate = Boolean(acceptedTermsVersion) && needsTermsAgreement
  const isAuthenticated = Boolean(userToken)
  const showWelcomeGate = !needsTermsAgreement && !termsDeclined && !userToken && !welcomeSeen
  const canReadDashboard = isAuthenticated || (accessChecked && publicReadEnabled)

  const checkPublicAccess = useCallback(async () => {
    try {
      const [accessRes, oauthRes] = await Promise.all([
        apiRequest('/api/public/access').catch(() => null),
        apiRequest('/api/users/oauth-config').catch(() => null),
      ])
      if (accessRes && typeof accessRes.public_read_enabled === 'boolean') {
        setPublicReadEnabled(accessRes.public_read_enabled)
      } else {
        setPublicReadEnabled(true)
      }
      if (oauthRes) {
        setOauthConfig((prev) => ({ ...prev, ...oauthRes }))
      }
    } finally {
      setAccessChecked(true)
    }
  }, [])

  useEffect(() => {
    checkPublicAccess()
  }, [checkPublicAccess])

  const completeOnboardingSession = useCallback((tokenVal, userObj) => {
    setUserToken(tokenVal)
    setStoredUserToken(tokenVal)
    setCurrentUser(userObj || null)
    localStorage.setItem(WELCOME_SEEN_KEY, '1')
    setWelcomeSeen(true)
    setShowLoginModal(false)
    setLoginModalSubtitle(DEFAULT_LOGIN_SUBTITLE)
    setActiveDeviceId('')
    setActiveTab('home')
  }, [])

  const handleLogout = useCallback(() => {
    setUserToken('')
    setCurrentUser(null)
    setStoredUserToken('')
    signOutGoogleIfInitialized()
    setShowLoginModal(false)
    setActiveDeviceId('')
    setLatestData(null)
    setTodaySummary(null)
    setActiveTab('home')
    checkPublicAccess()
  }, [checkPublicAccess])

  const handleUnauthorized = useCallback(() => {
    if (userToken) {
      handleLogout()
    } else {
      setPublicReadEnabled(false)
    }
  }, [userToken, handleLogout])

  useEffect(() => {
    if (!userToken) {
      setCurrentUser(null)
      return
    }
    apiRequest('/api/users/me', {}, userToken, handleUnauthorized)
      .then((profile) => {
        // Pastikan portal pelanggan tidak memakai token admin
        if (profile?.role === 'admin') {
          handleLogout()
          return
        }
        setCurrentUser(profile)
      })
      .catch(() => setCurrentUser(null))
  }, [userToken, handleUnauthorized, handleLogout])

  const handleUserLogin = async (email, password) => {
    setLoginError(null)
    try {
      const data = await apiRequest('/api/users/login', {
        method: 'POST',
        body: { email, password },
      })
      completeOnboardingSession(data.token, data.user)
      if (pendingAddDevice) {
        setPendingAddDevice(false)
        setIsAddDeviceOpen(true)
      } else if (localStorage.getItem(TOUR_COMPLETED_KEY) !== '1') {
        setShowTour(true)
      }
    } catch (err) {
      setLoginError(err.message || 'Email atau kata sandi salah.')
    }
  }

  const handleUserRegister = async (name, email, password) => {
    setLoginError(null)
    try {
      const data = await apiRequest('/api/users/register', {
        method: 'POST',
        body: { name, email, password },
      })
      completeOnboardingSession(data.token, data.user)
      if (pendingAddDevice) {
        setPendingAddDevice(false)
        setIsAddDeviceOpen(true)
      } else if (localStorage.getItem(TOUR_COMPLETED_KEY) !== '1') {
        setShowTour(true)
      }
    } catch (err) {
      setLoginError(err.message || 'Pendaftaran akun gagal.')
    }
  }

  const handleGoogleLogin = async () => {
    setLoginError(null)
    const cid = oauthConfig.google_client_id || oauthConfig.google_android_client_id
    if (!cid || !oauthConfig.google_enabled) {
      throw new Error(
        'Login Google belum dikonfigurasi pada server (.env GOOGLE_CLIENT_ID kosong).'
      )
    }
    const idToken = await signInWithGoogleForIdToken(cid)
    const data = await apiRequest('/api/users/google', {
      method: 'POST',
      body: { id_token: idToken },
    })
    completeOnboardingSession(data.token, data.user)
    if (pendingAddDevice) {
      setPendingAddDevice(false)
      setIsAddDeviceOpen(true)
    } else if (localStorage.getItem(TOUR_COMPLETED_KEY) !== '1') {
      setShowTour(true)
    }
  }

  const handleAgreeTerms = () => {
    localStorage.setItem(TERMS_STORAGE_KEY, activeTermsVersion)
    setAcceptedTermsVersion(activeTermsVersion)
    setTermsDeclined(false)
    setTermsReaderDoc(null)
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
    if (localStorage.getItem(TOUR_COMPLETED_KEY) !== '1') {
      setShowTour(true)
    }
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
      if (today) setTodaySummary(today)
    } catch {
      setTodaySummary(null)
    }
  }, [canReadDashboard, readBase, activeDeviceId, userToken, handleUnauthorized])

  const loadPowerChart = useCallback(async (range) => {
    if (!canReadDashboard || !activeDeviceId) return

    const nowSec = Math.floor(Date.now() / 1000)
    let fromSec = nowSec - 5 * 3600
    let resParam = 'raw'

    if (range === '24h') {
      fromSec = nowSec - 24 * 3600
      resParam = '5m'
    } else if (range === '3d') {
      fromSec = nowSec - 3 * 86400
      resParam = '5m'
    } else if (range === '30d') {
      fromSec = nowSec - 30 * 86400
      resParam = '1h'
    }

    try {
      const data = await apiRequest(
        `${readBase}/devices/${activeDeviceId}/series?from=${fromSec}&to=${nowSec}&resolution=${resParam}`,
        {},
        userToken,
        handleUnauthorized
      )
      setPowerPoints(data.points || [])
    } catch {
      setPowerPoints([])
    }
  }, [canReadDashboard, readBase, activeDeviceId, userToken, handleUnauthorized])

  const loadDailyChart = useCallback(async () => {
    if (!canReadDashboard || !activeDeviceId) return
    const nowSec = Math.floor(Date.now() / 1000)
    const fromSec = nowSec - 14 * 86400

    try {
      const data = await apiRequest(
        `${readBase}/devices/${activeDeviceId}/series?from=${fromSec}&to=${nowSec}&resolution=1d`,
        {},
        userToken,
        handleUnauthorized
      )
      setDailyPoints(data.points || [])
    } catch {
      setDailyPoints([])
    }
  }, [canReadDashboard, readBase, activeDeviceId, userToken, handleUnauthorized])

  const loadPeriodicData = useCallback(async () => {
    if (!canReadDashboard || !activeDeviceId) return
    try {
      const [week, month, fc, anom] = await Promise.all([
        apiRequest(`${readBase}/devices/${activeDeviceId}/summary?range=week`, {}, userToken, handleUnauthorized).catch(() => null),
        apiRequest(`${readBase}/devices/${activeDeviceId}/summary?range=month`, {}, userToken, handleUnauthorized).catch(() => null),
        apiRequest(`${readBase}/devices/${activeDeviceId}/forecast`, {}, userToken, handleUnauthorized).catch(() => null),
        apiRequest(`${readBase}/anomalies?device_id=${activeDeviceId}`, {}, userToken, handleUnauthorized).catch(() => []),
      ])
      setWeekSummary(week)
      setMonthSummary(month)
      setForecast(fc)
      setDeviceAnomalies(anom || [])
    } catch (err) {
      console.error('Gagal memuat periodic data:', err)
    }
  }, [canReadDashboard, readBase, activeDeviceId, userToken, handleUnauthorized])

  useEffect(() => {
    if (canReadDashboard) {
      loadSettings()
      loadDevicesAndAlerts()
    }
  }, [canReadDashboard, loadSettings, loadDevicesAndAlerts])

  useEffect(() => {
    if (!canReadDashboard) return
    clearInterval(homePollRef.current)
    homePollRef.current = setInterval(() => {
      if (document.visibilityState !== 'hidden') {
        loadDevicesAndAlerts()
      }
    }, 8000)
    return () => clearInterval(homePollRef.current)
  }, [canReadDashboard, loadDevicesAndAlerts])

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
  }, [canReadDashboard, activeDeviceId, powerRange, pollLatest, loadPeriodicData, loadPowerChart, loadDailyChart])

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
      setLoginModalSubtitle('Masuk atau daftar akun terlebih dahulu untuk menambahkan panel listrik baru.')
      setShowLoginModal(true)
      return
    }
    setIsAddDeviceOpen(true)
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

  // Dukungan tombol Back Android pada aplikasi Capacitor (.apk)
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return undefined
    let handleRef = null
    CapApp.addListener('backButton', () => {
      if (termsReaderDoc) {
        setTermsReaderDoc(null)
      } else if (isServerModalOpen) {
        setIsServerModalOpen(false)
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
    isServerModalOpen,
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
            Syarat Penggunaan &amp; Kebijakan Privasi VoltKu.
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
          termsVersion={activeTermsVersion}
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
          googleEnabled={oauthConfig.google_enabled}
          termsAccepted={!needsTermsAgreement}
          onOpenTerms={(docType) => setTermsReaderDoc(docType || 'terms')}
          onOpenServerConfig={() => setIsServerModalOpen(true)}
          onTryGuest={publicReadEnabled ? handleEnterGuestMode : undefined}
          error={loginError}
          canClose={false}
        />
        <TermsAgreementModal
          isOpen={Boolean(termsReaderDoc)}
          readOnly
          initialDoc={termsReaderDoc}
          termsVersion={activeTermsVersion}
          onClose={() => setTermsReaderDoc(null)}
        />
        <ServerConfigModal
          isOpen={isServerModalOpen}
          onClose={() => setIsServerModalOpen(false)}
          onSaved={() => checkPublicAccess()}
        />
        <PwaInstallPrompt hasBottomNav={false} />
      </>
    )
  }

  return (
    <div className="app-layout">
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
        onToggleTheme={toggleTheme}
        isAuthenticated={isAuthenticated}
        currentUser={currentUser}
        onOpenLogin={() => {
          setPendingAddDevice(false)
          setLoginError(null)
          setLoginModalSubtitle(DEFAULT_LOGIN_SUBTITLE)
          setShowLoginModal(true)
        }}
      />

      <main className="container main-content-wrap has-bottom-nav">
        {/* HOME SCOPE (Belum memilih perangkat) */}
        {!isDeviceScope && activeTab === 'home' && (
          <HomeDevicesView
            devices={devices}
            rooms={rooms}
            activeRoom={activeRoom}
            onSelectRoom={setActiveRoom}
            onSelectDevice={handleOpenDeviceDetail}
            onOpenAddDevice={handleRequestAddDevice}
            isDeviceOnlineFn={(d) => isDeviceOnlineHelper(d)}
            isAuthenticated={isAuthenticated}
            onReplayTour={() => setShowTour(true)}
            onOpenLogin={() => {
              setPendingAddDevice(false)
              setLoginError(null)
              setLoginModalSubtitle(DEFAULT_LOGIN_SUBTITLE)
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
                setLoginModalSubtitle(DEFAULT_LOGIN_SUBTITLE)
                setShowLoginModal(true)
              }}
              onLogout={handleLogout}
              onReplayTour={() => {
                setActiveDeviceId('')
                setActiveTab('home')
                setShowTour(true)
              }}
              onOpenTerms={(docType) => setTermsReaderDoc(docType || 'terms')}
              onOpenServerConfig={() => setIsServerModalOpen(true)}
            />
          </div>
        )}

        {/* DEVICE SCOPE (Sudah memilih & masuk ke salah satu perangkat) */}
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
              />
              <DailyChart points={dailyPoints} theme={theme} tariff={tariffNum} />
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
                setActiveDeviceId('')
                setActiveTab('home')
              }}
              onOpenLogin={() => {
                setLoginError(null)
                setShowLoginModal(true)
              }}
              onLogout={handleLogout}
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
          onDeviceAdded={async (newId) => {
            await loadDevicesAndAlerts()
            if (newId) {
              setActiveDeviceId(newId)
              setActiveTab('live')
            }
          }}
        />
      )}

      {showLoginModal && !userToken && (
        <LoginModal
          onLogin={handleUserLogin}
          onRegister={handleUserRegister}
          onGoogleLogin={handleGoogleLogin}
          googleEnabled={oauthConfig.google_enabled}
          termsAccepted={!needsTermsAgreement}
          onOpenTerms={(docType) => setTermsReaderDoc(docType || 'terms')}
          onOpenServerConfig={() => setIsServerModalOpen(true)}
          error={loginError}
          subtitle={loginModalSubtitle}
          canClose
          onClose={() => {
            setShowLoginModal(false)
            setPendingAddDevice(false)
            setLoginModalSubtitle(DEFAULT_LOGIN_SUBTITLE)
          }}
        />
      )}

      <TermsAgreementModal
        isOpen={Boolean(termsReaderDoc)}
        readOnly
        initialDoc={termsReaderDoc}
        termsVersion={activeTermsVersion}
        onClose={() => setTermsReaderDoc(null)}
      />

      <ServerConfigModal
        isOpen={isServerModalOpen}
        onClose={() => setIsServerModalOpen(false)}
        onSaved={() => {
          checkPublicAccess()
          if (canReadDashboard) {
            loadSettings()
            loadDevicesAndAlerts()
          }
        }}
      />

      <OnboardingTour
        isOpen={showTour && !isDeviceScope && activeTab === 'home'}
        onComplete={finishTour}
        onSkip={finishTour}
      />

      <PwaInstallPrompt hasBottomNav />
    </div>
  )
}

export default function App() {
  const isAdminRoute = window.location.pathname.startsWith('/admin')
  return isAdminRoute ? <AdminPortalRoot /> : <CustomerPortalRoot />
}
