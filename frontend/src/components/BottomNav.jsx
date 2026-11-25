import React from 'react'
import { Home, Zap, BarChart3, ShieldAlert, Sliders, Bell, Settings2 } from 'lucide-react'

export function BottomNav({
  activeTab,
  onTabChange,
  isDeviceScope = false,
  deviceAnomalyCount = 0,
  globalAnomalyCount = 0,
}) {
  const homeTabs = [
    { id: 'alerts', label: 'Peringatan', icon: Bell, badge: globalAnomalyCount },
    { id: 'home', label: 'Beranda', icon: Home, isCenterHome: true },
    { id: 'settings', label: 'Setelan', icon: Sliders },
  ]

  const deviceTabs = [
    { id: 'live', label: 'Live', icon: Zap },
    { id: 'charts', label: 'Konsumsi', icon: BarChart3 },
    { id: 'home', label: 'Beranda', icon: Home, isCenterHome: true },
    { id: 'anomalies', label: 'Anomali', icon: ShieldAlert, badge: deviceAnomalyCount },
    { id: 'device_settings', label: 'Atur Alat', icon: Settings2 },
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
