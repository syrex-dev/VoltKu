import React from 'react'
import { Zap, BarChart3, ShieldAlert, Sliders } from 'lucide-react'

export function BottomNav({ activeTab, onTabChange, anomalyCount = 0 }) {
  const tabs = [
    { id: 'live', label: 'Live', icon: Zap },
    { id: 'charts', label: 'Grafik', icon: BarChart3 },
    { id: 'anomalies', label: 'Anomali', icon: ShieldAlert, badge: anomalyCount },
    { id: 'settings', label: 'Pengaturan', icon: Sliders },
  ]

  return (
    <nav className="mobile-bottom-nav" aria-label="Mobile Navigation">
      <div className="bottom-nav-inner">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              className={`bottom-nav-item ${isActive ? 'active' : ''}`}
              onClick={() => {
                onTabChange(tab.id)
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
              aria-selected={isActive}
              role="tab"
            >
              <div className="bottom-nav-icon-box">
                <Icon size={20} className="bottom-nav-icon" />
                {tab.badge > 0 && (
                  <span className="bottom-nav-badge">{tab.badge > 9 ? '9+' : tab.badge}</span>
                )}
              </div>
              <span className="bottom-nav-label">{tab.label}</span>
              {isActive && <span className="bottom-nav-active-pill" />}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
