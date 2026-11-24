import React from 'react'
import { Zap, BarChart3, ShieldAlert, Sliders } from 'lucide-react'

export function DesktopTabBar({ activeTab, onTabChange, anomalyCount = 0 }) {
  const tabs = [
    { id: 'live', label: 'Live Telemetri', icon: Zap },
    { id: 'charts', label: 'Grafik & Riwayat', icon: BarChart3 },
    { id: 'anomalies', label: 'Anomali & Peringatan', icon: ShieldAlert, badge: anomalyCount },
    { id: 'settings', label: 'Pengaturan', icon: Sliders },
  ]

  return (
    <div className="desktop-tab-bar-wrap">
      <div className="desktop-tab-bar" role="tablist">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              className={`desktop-tab-btn ${isActive ? 'active' : ''}`}
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
