import React from 'react'
import { Home, Zap, BarChart3, ShieldAlert, Sliders, Bell, Settings2 } from 'lucide-react'
import { getUiText, useUserPrefs } from '../utils/userPrefs'

export function BottomNav({
  activeTab,
  onTabChange,
  isDeviceScope = false,
  deviceAnomalyCount = 0,
  globalAnomalyCount = 0,
}) {
  const { prefs } = useUserPrefs()
  const loc = prefs.locale

  const homeTabs = [
    { id: 'alerts', label: getUiText(loc, 'navAlerts'), icon: Bell, badge: globalAnomalyCount },
    { id: 'home', label: getUiText(loc, 'navHome'), icon: Home, isCenterHome: true },
    { id: 'settings', label: getUiText(loc, 'navSettings'), icon: Sliders },
  ]

  const deviceTabs = [
    { id: 'live', label: getUiText(loc, 'navLive'), icon: Zap },
    { id: 'charts', label: getUiText(loc, 'navCharts'), icon: BarChart3 },
    { id: 'home', label: getUiText(loc, 'navHome'), icon: Home, isCenterHome: true },
    { id: 'anomalies', label: getUiText(loc, 'navAnomalies'), icon: ShieldAlert, badge: deviceAnomalyCount },
    { id: 'device_settings', label: getUiText(loc, 'navDeviceSettings'), icon: Settings2 },
  ]

  const tabs = isDeviceScope ? deviceTabs : homeTabs

  return (
    <nav className="mobile-bottom-nav" aria-label="Navigasi Utama">
      <div className="bottom-nav-inner">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              data-tour-target={`nav-${tab.id}`}
              className={`bottom-nav-item ${tab.isCenterHome ? 'is-home-center' : ''} ${
                isActive ? 'active' : ''
              }`}
              onClick={() => {
                onTabChange(tab.id)
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
              aria-selected={isActive}
              role="tab"
            >
              <div className="bottom-nav-icon-box">
                <Icon size={tab.isCenterHome ? 21 : 20} className="bottom-nav-icon" />
                {tab.badge > 0 && (
                  <span className="bottom-nav-badge">{tab.badge > 9 ? '9+' : tab.badge}</span>
                )}
              </div>
              <span className="bottom-nav-label">{tab.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
