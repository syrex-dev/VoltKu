import React from 'react'
import { Home, Zap, BarChart3, ShieldAlert, Sliders } from 'lucide-react'

export function DesktopTabBar({ activeTab, onTabChange, anomalyCount = 0, hasDevice = true }) {
  const tabs = [
    { id: 'home', label: 'Beranda', icon: Home },
    { id: 'live', label: 'Live', icon: Zap, needsDevice: true },
    { id: 'charts', label: 'Konsumsi & Grafik', icon: BarChart3, needsDevice: true },
    { id: 'anomalies', label: 'Anomali', icon: ShieldAlert, badge: anomalyCount, needsDevice: true },
    { id: 'settings', label: 'Setelan', icon: Sliders },
  ]

  return (
    <div className="desktop-tab-bar-wrap">
      <div className="desktop-tab-bar" role="tablist">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          const disabled = tab.needsDevice && !hasDevice
          return (
            <button
              key={tab.id}
              type="button"
              className={`desktop-tab-btn ${isActive ? 'active' : ''}`}
              disabled={disabled}
              style={disabled ? { opacity: 0.45 } : undefined}
              onClick={() => onTabChange(tab.id)}
              role="tab"
              aria-selected={isActive}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
              {tab.badge > 0 && (
                <span className="desktop-tab-badge">{tab.badge}</span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
