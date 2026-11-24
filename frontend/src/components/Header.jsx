import React from 'react'
import { Zap, Sliders, LogOut, Sun, Moon } from 'lucide-react'
import { CustomDeviceSelector } from './CustomDeviceSelector'
import { formatDateTimeWIB } from '../utils/formatters'

export function Header({
  devices,
  activeDeviceId,
  onSelectDevice,
  onOpenSettings,
  onLogout,
  lastDataTs,
  theme,
  onToggleTheme,
}) {
  const activeDevice = devices.find((d) => d.id === activeDeviceId)

  // Status calculation
  const nowSec = Math.floor(Date.now() / 1000)
  const ts = lastDataTs || activeDevice?.last_data_ts
  const isStale = ts ? nowSec - ts > 30 : true
  const isOnline = activeDevice?.status === 'online' && !isStale

  return (
    <div className="app-header-wrap">
      <div className="container">
        <header className="app-header">
          {/* Top Row / Main Nav Bar */}
          <div className="header-main-row">
            {/* Brand */}
            <div className="header-brand">
              <div className="brand-icon-box">
                <Zap size={18} />
              </div>
              <div className="brand-title-wrap">
                <div className="brand-title">
                  Monitor Listrik
                  <span className="brand-badge">IoT + AI</span>
                </div>
              </div>
            </div>

            {/* Desktop Center: Device Selector & Status Pill */}
            <div className="header-center-desktop">
              <CustomDeviceSelector
                devices={devices}
                activeDeviceId={activeDeviceId}
                onSelectDevice={onSelectDevice}
              />

              <div className={`status-pill ${isOnline ? 'online' : 'offline'}`}>
                <span className="pulse-beacon"></span>
                <span>
                  {isOnline
                    ? 'Online'
                    : ts
                    ? `Offline (${formatDateTimeWIB(ts)})`
                    : 'Offline'}
                </span>
              </div>
            </div>

            {/* Actions (Always visible on mobile & desktop) */}
            <div className="header-actions">
              <button
                className="btn btn-secondary btn-icon-only"
                onClick={onToggleTheme}
                title={theme === 'dark' ? 'Ganti ke Mode Terang' : 'Ganti ke Mode Gelap'}
                aria-label="Toggle Theme"
              >
                {theme === 'dark' ? (
                  <Sun size={16} className="text-amber" />
                ) : (
                  <Moon size={16} className="text-purple" />
                )}
              </button>

              <button
                className="btn btn-secondary btn-icon-only-mobile"
                onClick={onOpenSettings}
                title="Pengaturan Sistem"
                aria-label="Pengaturan"
              >
                <Sliders size={16} />
                <span className="btn-text-desktop">Pengaturan</span>
              </button>

              <button
                className="btn btn-danger-ghost btn-icon-only-mobile"
                onClick={onLogout}
                title="Keluar dari Dashboard"
                aria-label="Keluar"
              >
                <LogOut size={16} />
                <span className="btn-text-desktop">Keluar</span>
              </button>
            </div>
          </div>

          {/* Mobile Sub-row: Device Selector & Status Pill (Only on mobile < 768px) */}
          <div className="header-mobile-subrow">
            <div className="mobile-selector-col">
              <CustomDeviceSelector
                devices={devices}
                activeDeviceId={activeDeviceId}
                onSelectDevice={onSelectDevice}
              />
            </div>
            <div className={`status-pill ${isOnline ? 'online' : 'offline'}`}>
              <span className="pulse-beacon"></span>
              <span>{isOnline ? 'Online' : 'Offline'}</span>
            </div>
          </div>
        </header>
      </div>
    </div>
  )
}
