import React, { useState, useRef, useEffect } from 'react'
import {
  Home,
  Zap,
  BarChart3,
  ShieldAlert,
  Sliders,
  Bell,
  Settings2,
  User,
  ChevronDown,
  Check,
  Plus,
  Megaphone,
} from 'lucide-react'
import { formatNum } from '../utils/formatters'
import { getUiText, useUserPrefs } from '../utils/userPrefs'
import { BrandLogo } from './BrandLogo'
import { NotificationBell } from './NotificationBell'

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
  const activeOnline = isDeviceOnlineFn
    ? isDeviceOnlineFn(activeDevice)
    : activeDevice.status === 'online'

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

      {variant === 'mobile' && subLabel && <div className="header-page-sub">{subLabel}</div>}

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

function AccountAvatarButton({
  isAuthenticated,
  currentUser,
  onOpenLogin,
  onOpenProfile,
}) {
  const [imgBroken, setImgBroken] = useState(false)

  useEffect(() => {
    setImgBroken(false)
  }, [currentUser?.avatar_url])

  if (!isAuthenticated) {
    return (
      <button
        type="button"
        className="header-avatar-btn is-guest"
        onClick={onOpenLogin}
        aria-label="Masuk atau Daftar Akun"
        title="Masuk / Daftar Akun"
        data-testid="header-account-btn"
      >
        <User size={19} strokeWidth={1.9} />
      </button>
    )
  }

  const hasPhoto = Boolean(currentUser?.avatar_url && !imgBroken)

  return (
    <div className="header-account-wrap">
      <button
        type="button"
        className="header-avatar-btn is-authenticated"
        onClick={onOpenProfile}
        aria-label={`Profil Akun ${currentUser?.name || ''}`}
        title={currentUser?.name || currentUser?.email || 'Profil Saya'}
        data-testid="header-account-btn"
      >
        {hasPhoto ? (
          <img
            src={currentUser.avatar_url}
            alt={currentUser.name || 'Profil'}
            className="header-avatar-img"
            referrerPolicy="no-referrer"
            onError={() => setImgBroken(true)}
          />
        ) : (
          <User size={19} strokeWidth={2} />
        )}
        <span className="header-avatar-dot" aria-hidden="true" />
      </button>
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
  isAuthenticated = false,
  currentUser = null,
  onOpenLogin,
  onOpenProfile,
  appConfig = {},
  notifications = [],
  unreadNotificationCount = 0,
  onMarkNotificationRead,
  onSelectNotification,
}) {
  const { prefs } = useUserPrefs()
  const loc = prefs.locale
  const appName = appConfig.app_name || 'VoltKu'
  const brandDisplay = appConfig.navbar_brand_display || 'logo_only'
  const mobileTitle =
    isDeviceScope && activeDevice
      ? activeDevice.name || activeDevice.id
      : activeTab === 'alerts'
      ? getUiText(loc, 'navAlerts')
      : activeTab === 'settings'
      ? getUiText(loc, 'navSettings')
      : ''

  const mobileSub = isDeviceScope && activeDevice ? activeDevice.location || '' : ''

  const homeNav = [
    { id: 'alerts', label: getUiText(loc, 'navAlerts'), icon: Bell, badge: globalAnomalyCount },
    { id: 'home', label: getUiText(loc, 'navHome'), icon: Home, isCenterHome: true },
    { id: 'settings', label: getUiText(loc, 'navSettings'), icon: Sliders },
  ]

  const deviceNav = [
    { id: 'live', label: getUiText(loc, 'navLive'), icon: Zap },
    { id: 'charts', label: getUiText(loc, 'navCharts'), icon: BarChart3 },
    { id: 'home', label: getUiText(loc, 'navHome'), icon: Home, isCenterHome: true },
    { id: 'anomalies', label: getUiText(loc, 'navAnomalies'), icon: ShieldAlert, badge: deviceAnomalyCount },
    { id: 'device_settings', label: getUiText(loc, 'navDeviceSettings'), icon: Settings2 },
  ]

  const desktopTabs = isDeviceScope ? deviceNav : homeNav
  const showAnnouncement = Boolean(appConfig.announcement_active && appConfig.announcement_text)

  return (
    <div className="app-header-wrap clean-header-bar">
      {showAnnouncement && (
        <div className="header-announcement-strip">
          <div className="container header-announcement-inner">
            <Megaphone size={13} className="header-announcement-ico" />
            {appConfig.announcement_url ? (
              <a
                href={appConfig.announcement_url}
                target="_blank"
                rel="noreferrer"
                className="header-announcement-link"
              >
                {appConfig.announcement_text}
              </a>
            ) : (
              <span>{appConfig.announcement_text}</span>
            )}
          </div>
        </div>
      )}

      <div className="container">
        <header className="app-header clean-header-inner">
          <div className="header-main-row">
            {/* Brand / Context Left */}
            <div className="header-home-title-wrap">
              <div className="desktop-brand-row">
                <BrandLogo
                  theme={theme}
                  displayMode={brandDisplay}
                  appName={appName}
                  variant="navbar"
                />
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
                ) : activeTab === 'home' ? (
                  <BrandLogo
                    theme={theme}
                    displayMode={brandDisplay}
                    appName={appName}
                    variant="compact"
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

            {/* Desktop Contextual Navigation */}
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
                    {tab.badge > 0 && <span className="desktop-nav-badge">{tab.badge}</span>}
                  </button>
                )
              })}
            </nav>

            {/* Kanan Navbar: Notifikasi & Ikon Akun di PALING KANAN (Tema ada di Setelan/Profil) */}
            <div className="header-actions">
              {isAuthenticated && (
                <NotificationBell
                  notifications={notifications}
                  unreadCount={unreadNotificationCount}
                  onMarkRead={onMarkNotificationRead}
                  onSelectNotification={onSelectNotification}
                />
              )}

              <AccountAvatarButton
                isAuthenticated={isAuthenticated}
                currentUser={currentUser}
                onOpenLogin={onOpenLogin}
                onOpenProfile={onOpenProfile}
              />
            </div>
          </div>
        </header>
      </div>
    </div>
  )
}
