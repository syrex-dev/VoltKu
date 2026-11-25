import React, { useState, useRef, useEffect } from 'react'
import {
  Home,
  Zap,
  BarChart3,
  ShieldAlert,
  Sliders,
  Bell,
  Settings2,
  Sun,
  Moon,
  LogIn,
  User,
  ChevronDown,
  Check,
  Plus,
} from 'lucide-react'
import { formatNum } from '../utils/formatters'

function PanelSwitcherDropdown({
  variant = 'mobile',
  devices = [],
  activeDevice,
  subLabel = '',
  isDeviceOnlineFn,
  onSelectDevice,
  onOpenAddDevice,
}) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return undefined
    const handlePointerDown = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    const handleEscape = (e) => {
      if (e.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  if (!activeDevice) return null

  const activeName = activeDevice.name || activeDevice.id
  const activeOnline = isDeviceOnlineFn ? isDeviceOnlineFn(activeDevice) : activeDevice.status === 'online'

  return (
    <div className={`header-panel-switcher is-${variant}`} ref={containerRef}>
      <button
        type="button"
        className={`header-panel-trigger is-${variant} ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        title="Beralih ke panel listrik lain"
      >
        {variant === 'desktop' && (
          <span className={`panel-status-dot ${activeOnline ? 'online' : 'offline'}`} />
        )}
        <span className="header-panel-name">{activeName}</span>
        <span className="header-panel-caret">
          <ChevronDown size={variant === 'mobile' ? 16 : 14} />
        </span>
      </button>

      {variant === 'mobile' && subLabel && (
        <div className="header-page-sub">{subLabel}</div>
      )}

      {isOpen && (
        <div className="header-panel-popover" role="listbox" aria-label="Pilih Panel Listrik">
          <div className="header-panel-popover-head">
            <span>Panel Listrik</span>
            <span className="header-panel-count">{devices.length}</span>
          </div>

          <div className="header-panel-list">
            {devices.map((dev) => {
              const isSelected = dev.id === activeDevice.id
              const online = isDeviceOnlineFn ? isDeviceOnlineFn(dev) : dev.status === 'online'
              const watts = dev.latest && typeof dev.latest.p === 'number' ? dev.latest.p : null
              return (
                <button
                  key={dev.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`header-panel-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    setIsOpen(false)
                    if (onSelectDevice) onSelectDevice(dev.id)
                  }}
                >
                  <span className={`panel-status-dot ${online ? 'online' : 'offline'}`} />
                  <span className="header-panel-item-copy">
                    <span className="header-panel-item-title">{dev.name || dev.id}</span>
                    <span className="header-panel-item-sub">
                      {dev.location || 'Panel Listrik'} · {online ? 'Online' : 'Offline'}
                    </span>
                  </span>
                  <span className="header-panel-item-right">
                    <span className="header-panel-item-watt num-tabular">
                      {watts !== null ? `${formatNum(watts, 0)} W` : `${dev.mcb_watt} W`}
                    </span>
                    {isSelected && <Check size={15} className="header-panel-check" />}
                  </span>
                </button>
              )
            })}
          </div>

          {onOpenAddDevice && (
            <button
              type="button"
              className="header-panel-add-btn"
              onClick={() => {
                setIsOpen(false)
                onOpenAddDevice()
              }}
            >
              <Plus size={15} strokeWidth={2.4} />
              <span>Tambah Panel Baru</span>
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export function Header({
  activeTab,
  onTabChange,
  isDeviceScope = false,
  activeDevice,
  devices = [],
  onSelectDevice,
  onOpenAddDevice,
  isDeviceOnlineFn,
  deviceAnomalyCount = 0,
  globalAnomalyCount = 0,
  theme,
  onToggleTheme,
  isAuthenticated = false,
  currentUser = null,
  onOpenLogin,
}) {
  const mobileTitle = isDeviceScope && activeDevice
    ? activeDevice.name || activeDevice.id
    : activeTab === 'alerts'
    ? 'Peringatan'
    : activeTab === 'settings'
    ? 'Setelan'
    : isAuthenticated
    ? 'Rumah Saya'
    : 'VoltKu'

  const mobileSub = isDeviceScope && activeDevice ? activeDevice.location || '' : ''

  const homeNav = [
    { id: 'alerts', label: 'Peringatan', icon: Bell, badge: globalAnomalyCount },
    { id: 'home', label: 'Beranda', icon: Home, isCenterHome: true },
    { id: 'settings', label: 'Setelan', icon: Sliders },
  ]

  const deviceNav = [
    { id: 'live', label: 'Live', icon: Zap },
    { id: 'charts', label: 'Konsumsi', icon: BarChart3 },
    { id: 'home', label: 'Beranda', icon: Home, isCenterHome: true },
    { id: 'anomalies', label: 'Anomali', icon: ShieldAlert, badge: deviceAnomalyCount },
    { id: 'device_settings', label: 'Atur Alat', icon: Settings2 },
  ]

  const desktopTabs = isDeviceScope ? deviceNav : homeNav
  const shortUserName = currentUser?.name ? currentUser.name.split(' ')[0] : 'Akun'

  return (
    <div className="app-header-wrap clean-header-bar">
      <div className="container">
        <header className="app-header clean-header-inner">
          <div className="header-main-row">
            {/* Brand / Context Left */}
            <div className="header-home-title-wrap">
              <div className="desktop-brand-row">
                <span className="desktop-brand-mark">
                  <Zap size={17} />
                </span>
                <span className="desktop-brand-name">VoltKu</span>
                {isDeviceScope && activeDevice && (
                  <PanelSwitcherDropdown
                    variant="desktop"
                    devices={devices}
                    activeDevice={activeDevice}
                    isDeviceOnlineFn={isDeviceOnlineFn}
                    onSelectDevice={onSelectDevice}
                    onOpenAddDevice={onOpenAddDevice}
                  />
                )}
              </div>

              <div className="mobile-title-block">
                {isDeviceScope && activeDevice ? (
                  <PanelSwitcherDropdown
                    variant="mobile"
                    devices={devices}
                    activeDevice={activeDevice}
                    subLabel={mobileSub}
                    isDeviceOnlineFn={isDeviceOnlineFn}
                    onSelectDevice={onSelectDevice}
                    onOpenAddDevice={onOpenAddDevice}
                  />
                ) : (
                  <>
                    <h1 className="header-home-title" title={mobileTitle}>
                      {mobileTitle}
                    </h1>
                    {mobileSub && <div className="header-page-sub">{mobileSub}</div>}
                  </>
                )}
              </div>
            </div>

            {/* Desktop Contextual Navigation (Beranda di tengah) */}
            <nav className="desktop-header-nav" aria-label="Navigasi Desktop">
              {desktopTabs.map((tab) => {
                const Icon = tab.icon
                const isActive = activeTab === tab.id
                return (
                  <button
                    key={tab.id}
                    type="button"
                    className={`desktop-nav-pill ${tab.isCenterHome ? 'is-home-center' : ''} ${
                      isActive ? 'active' : ''
                    }`}
                    onClick={() => onTabChange(tab.id)}
                  >
                    <Icon size={15} />
                    <span>{tab.label}</span>
                    {tab.badge > 0 && (
                      <span className="desktop-nav-badge">{tab.badge}</span>
                    )}
                  </button>
                )
              })}
            </nav>

            {/* Auth User Action + Theme Switch (Zero Admin Controls) */}
            <div className="header-actions">
              {isAuthenticated ? (
                <button
                  type="button"
                  className="header-role-pill is-user"
                  onClick={() => onTabChange('settings')}
                  title={currentUser?.email || 'Akun Saya'}
                >
                  <User size={14} />
                  <span>{shortUserName}</span>
                </button>
              ) : (
                onOpenLogin && (
                  <button
                    type="button"
                    className="header-role-pill"
                    onClick={onOpenLogin}
                    title="Masuk atau Daftar Akun"
                  >
                    <LogIn size={14} />
                    <span>Masuk</span>
                  </button>
                )
              )}

              <button
                type="button"
                className="header-icon-btn"
                onClick={onToggleTheme}
                aria-label="Ganti Tema"
                title={theme === 'dark' ? 'Mode Terang' : 'Mode Gelap'}
              >
                {theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}
              </button>
            </div>
          </div>
        </header>
      </div>
    </div>
  )
}
