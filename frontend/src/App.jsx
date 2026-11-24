import React, { useState, useEffect, useRef, useCallback } from 'react'
import { apiRequest } from './api/client'
import { Header } from './components/Header'
import { LoginModal } from './components/LoginModal'
import { WarningBanner } from './components/WarningBanner'
import { RealtimeTelemetry } from './components/RealtimeTelemetry'
import { EnergyMetrics } from './components/EnergyMetrics'
import { PowerChart } from './components/PowerChart'
import { DailyChart } from './components/DailyChart'
import { AnomaliesList } from './components/AnomaliesList'
import { SettingsModal } from './components/SettingsModal'
import { SettingsView } from './components/SettingsView'
import { BottomNav } from './components/BottomNav'
import { DesktopTabBar } from './components/DesktopTabBar'

export default function App() {
  // Auth State
  const [token, setToken] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const tokenFromUrl = urlParams.get('token')
    if (tokenFromUrl) {
      sessionStorage.setItem('token', tokenFromUrl)
      window.history.replaceState({}, document.title, window.location.pathname)
      return tokenFromUrl
    }
    return sessionStorage.getItem('token') || localStorage.getItem('token') || ''
  })
  const [loginError, setLoginError] = useState(null)

  // Theme State ('dark' | 'light')
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'dark'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  // App Data State
  const [devices, setDevices] = useState([])
  const [activeDeviceId, setActiveDeviceId] = useState('')
  const [settings, setSettings] = useState(null)
  const [latestData, setLatestData] = useState(null)
  const [todaySummary, setTodaySummary] = useState(null)
  const [weekSummary, setWeekSummary] = useState(null)
  const [monthSummary, setMonthSummary] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [anomalies, setAnomalies] = useState([])
  const [powerPoints, setPowerPoints] = useState([])
  const [powerRange, setPowerRange] = useState('5h')
  const [dailyPoints, setDailyPoints] = useState([])

  // Active Tab State ('live' | 'charts' | 'anomalies' | 'settings')
  const [activeTab, setActiveTab] = useState('live')

  // Modal State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  // Polling Refs
  const pollTimerRef = useRef(null)
  const chartTimerRef = useRef(null)

  // Logout Handler
  const handleLogout = useCallback(() => {
    setToken('')
    sessionStorage.removeItem('token')
    localStorage.removeItem('token')
    setDevices([])
    setActiveDeviceId('')
    setLatestData(null)
    setTodaySummary(null)
  }, [])

  // Login Handler
  const handleLogin = async (password) => {
    setLoginError(null)
    try {
      const data = await apiRequest('/api/login', {
        method: 'POST',
        body: { password },
      })
      const newToken = data.token
      setToken(newToken)
      sessionStorage.setItem('token', newToken)
    } catch (err) {
      setLoginError(err.message || 'Login gagal.')
    }
  }

  // Load Settings
  const loadSettings = useCallback(async (authToken) => {
    if (!authToken) return
    try {
      const data = await apiRequest('/api/settings', {}, authToken, handleLogout)
      setSettings(data)
    } catch (err) {
      console.error('Gagal memuat pengaturan:', err)
    }
  }, [handleLogout])

  // Load Devices
  const loadDevices = useCallback(async (authToken) => {
    if (!authToken) return
    try {
      const devs = await apiRequest('/api/devices', {}, authToken, handleLogout)
      setDevices(devs || [])
      setActiveDeviceId((prev) => {
        if (!prev || !devs.some((d) => d.id === prev)) {
          const def = devs.find((d) => d.id === 'sim-warung') || devs[0]
          return def ? def.id : ''
        }
        return prev
      })
    } catch (err) {
      console.error('Gagal memuat daftar perangkat:', err)
    }
  }, [handleLogout])

  // Poll Latest & Today Summary (Every 5 seconds)
  const pollLatest = useCallback(async () => {
    if (!token || !activeDeviceId) return

    try {
      const latest = await apiRequest(`/api/devices/${activeDeviceId}/latest`, {}, token, handleLogout)
      if (latest) {
        setLatestData(latest)
      }
    } catch (err) {
      console.error('Gagal polling data terbaru:', err)
    }

    try {
      const today = await apiRequest(
        `/api/devices/${activeDeviceId}/summary?range=today`,
        {},
        token,
        handleLogout
      )
      if (today) {
        setTodaySummary(today)
      }
    } catch (err) {
      console.error('Gagal polling summary hari ini:', err)
    }
  }, [token, activeDeviceId, handleLogout])

  // Load Power Series Chart
  const loadPowerChart = useCallback(async (range) => {
    if (!token || !activeDeviceId) return

    const nowSec = Math.floor(Date.now() / 1000)
    let fromSec = nowSec - 5 * 3600
    let resParam = 'raw'

    if (range === '5h') {
      fromSec = nowSec - 5 * 3600
      resParam = 'raw'
    } else if (range === '24h') {
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
        `/api/devices/${activeDeviceId}/series?from=${fromSec}&to=${nowSec}&resolution=${resParam}`,
        {},
        token,
        handleLogout
      )
      setPowerPoints(data.points || [])
    } catch (err) {
      console.error('Gagal memuat grafik daya:', err)
    }
  }, [token, activeDeviceId, handleLogout])

  // Load Daily Series Chart
  const loadDailyChart = useCallback(async () => {
    if (!token || !activeDeviceId) return
    const nowSec = Math.floor(Date.now() / 1000)
    const fromSec = nowSec - 14 * 86400

    try {
      const data = await apiRequest(
        `/api/devices/${activeDeviceId}/series?from=${fromSec}&to=${nowSec}&resolution=1d`,
        {},
        token,
        handleLogout
      )
      setDailyPoints(data.points || [])
    } catch (err) {
      console.error('Gagal memuat grafik harian:', err)
    }
  }, [token, activeDeviceId, handleLogout])

  // Load Other Periodic Data (Week, Month, Forecast, Anomalies)
  const loadPeriodicData = useCallback(async () => {
    if (!token || !activeDeviceId) return

    try {
      const [week, month, fc, anom] = await Promise.all([
        apiRequest(`/api/devices/${activeDeviceId}/summary?range=week`, {}, token, handleLogout).catch(() => null),
        apiRequest(`/api/devices/${activeDeviceId}/summary?range=month`, {}, token, handleLogout).catch(() => null),
        apiRequest(`/api/devices/${activeDeviceId}/forecast`, {}, token, handleLogout).catch(() => null),
        apiRequest(`/api/anomalies?device_id=${activeDeviceId}`, {}, token, handleLogout).catch(() => []),
      ])

      if (week) setWeekSummary(week)
      if (month) setMonthSummary(month)
      if (fc) setForecast(fc)
      if (anom) setAnomalies(anom)
    } catch (err) {
      console.error('Gagal memuat periodic data:', err)
    }
  }, [token, activeDeviceId, handleLogout])

  // Initial load when token is present
  useEffect(() => {
    if (token) {
      loadSettings(token)
      loadDevices(token)
    }
  }, [token, loadSettings, loadDevices])

  // When active device changes, refresh all device data
  useEffect(() => {
    if (token && activeDeviceId) {
      pollLatest()
      loadPeriodicData()
      loadPowerChart(powerRange)
      loadDailyChart()
    }
  }, [token, activeDeviceId, powerRange, pollLatest, loadPeriodicData, loadPowerChart, loadDailyChart])

  // Polling intervals & Visibility listener
  useEffect(() => {
    if (!token || !activeDeviceId) return

    const startIntervals = () => {
      clearInterval(pollTimerRef.current)
      clearInterval(chartTimerRef.current)

      pollLatest()
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
      if (document.visibilityState === 'hidden') {
        stopIntervals()
      } else {
        startIntervals()
      }
    }

    startIntervals()
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      stopIntervals()
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [token, activeDeviceId, powerRange, pollLatest, loadPeriodicData, loadPowerChart, loadDailyChart])

  // Save Settings Handler
  const handleSaveSettings = async (payload) => {
    const updated = await apiRequest(
      '/api/settings',
      {
        method: 'PATCH',
        body: payload,
      },
      token,
      handleLogout
    )
    setSettings(updated)
    loadPeriodicData()
  }

  // Active Device Object
  const activeDevice = devices.find((d) => d.id === activeDeviceId)

  // If not logged in, show Login Modal
  if (!token) {
    return <LoginModal onLogin={handleLogin} error={loginError} />
  }

  return (
    <div className="app-layout">
      <Header
        devices={devices}
        activeDeviceId={activeDeviceId}
        onSelectDevice={setActiveDeviceId}
        onOpenSettings={() => {
          setActiveTab('settings')
          window.scrollTo({ top: 0, behavior: 'smooth' })
        }}
        onLogout={handleLogout}
        lastDataTs={latestData?.ts}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <main className="container main-content-wrap">
        <DesktopTabBar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          anomalyCount={anomalies.length}
        />

        {activeTab === 'live' && (
          <div className="tab-pane-fade">
            <WarningBanner settings={settings} activeDevice={activeDevice} />
            <RealtimeTelemetry latest={latestData} settings={settings} />
            <EnergyMetrics
              today={todaySummary}
              week={weekSummary}
              month={monthSummary}
              forecast={forecast}
            />
          </div>
        )}

        {activeTab === 'charts' && (
          <div className="tab-pane-fade">
            <PowerChart
              points={powerPoints}
              range={powerRange}
              onRangeChange={(newRange) => {
                setPowerRange(newRange)
                loadPowerChart(newRange)
              }}
              theme={theme}
            />
            <DailyChart points={dailyPoints} theme={theme} />
            <EnergyMetrics
              today={todaySummary}
              week={weekSummary}
              month={monthSummary}
              forecast={forecast}
            />
          </div>
        )}

        {activeTab === 'anomalies' && (
          <div className="tab-pane-fade">
            <AnomaliesList anomalies={anomalies} />
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="tab-pane-fade">
            <SettingsView
              settings={settings}
              activeDevice={activeDevice}
              onSave={handleSaveSettings}
            />
          </div>
        )}
      </main>

      {/* Floating / Fixed Bottom Navigation Bar (Mobile) */}
      <BottomNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        anomalyCount={anomalies.length}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        activeDevice={activeDevice}
        onSave={handleSaveSettings}
      />
    </div>
  )
}
