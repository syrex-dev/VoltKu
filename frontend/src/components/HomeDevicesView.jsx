import React, { useMemo, useState, useEffect } from 'react'
import { Zap, Wifi, WifiOff, Plus, LogIn, ShieldCheck, AlertTriangle, RotateCcw } from 'lucide-react'
import { HeroBannerCarousel } from './HeroBannerCarousel'
import { RoomFilterBar } from './RoomFilterBar'
import { formatNum } from '../utils/formatters'
import { resolveVisualAsset } from '../utils/mascotAssets'

function EmptySmartBoxIllustration({ src }) {
  if (!src) {
    return (
      <div className="healthy-icon-wrap" style={{ marginBottom: 4 }} aria-hidden="true">
        <Zap size={24} />
      </div>
    )
  }
  return (
    <div className="ewl-empty-mascot-wrap" aria-hidden="true">
      <img src={src} alt="" className="ewl-empty-mascot-img" />
    </div>
  )
}

export function HomeDevicesView({
  devices,
  rooms,
  activeRoom,
  onSelectRoom,
  onSelectDevice,
  onOpenAddDevice,
  onOpenUsageGuide,
  isDeviceOnlineFn,
  isAuthenticated = false,
  onOpenLogin,
  currentUser = null,
  appConfig = {},
  onOpenPlanModal,
  onOpenSettings,
  onOpenAlerts,
}) {
  const [viewMode, setViewMode] = useState(() => {
    try {
      return localStorage.getItem('voltku_home_view_mode') === 'list' ? 'list' : 'grid'
    } catch {
      return 'grid'
    }
  })
  const [hideOffline, setHideOffline] = useState(() => {
    try {
      return localStorage.getItem('voltku_home_hide_offline') === 'true'
    } catch {
      return false
    }
  })
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    try {
      localStorage.setItem('voltku_home_view_mode', viewMode)
    } catch {
      // ignore storage failure
    }
  }, [viewMode])

  useEffect(() => {
    try {
      localStorage.setItem('voltku_home_hide_offline', String(hideOffline))
    } catch {
      // ignore storage failure
    }
  }, [hideOffline])

  const normalizedSearch = searchQuery.trim().toLowerCase()

  const filteredDevices = useMemo(
    () =>
      devices.filter((dev) => {
        if (activeRoom === 'Lainnya') {
          if (dev.location && dev.location.trim()) return false
        } else if (activeRoom !== 'Semua') {
          if ((dev.location || '').trim() !== activeRoom) return false
        }

        if (hideOffline && !isDeviceOnlineFn(dev)) {
          return false
        }

        if (normalizedSearch) {
          const haystack = `${dev.name || ''} ${dev.id || ''} ${dev.location || ''}`.toLowerCase()
          if (!haystack.includes(normalizedSearch)) return false
        }

        return true
      }),
    [devices, activeRoom, hideOffline, isDeviceOnlineFn, normalizedSearch]
  )

  const homeSummary = useMemo(() => {
    let onlineCount = 0
    let totalWatts = 0
    let totalMcb = 0
    let highLoadCount = 0

    for (const dev of devices) {
      const mcb = Number(dev.mcb_watt) || 2200
      totalMcb += mcb
      const online = isDeviceOnlineFn(dev)
      if (online) {
        onlineCount += 1
        const w = dev.latest?.p
        if (typeof w === 'number') {
          totalWatts += w
          if (w / mcb >= 0.75) {
            highLoadCount += 1
          }
        }
      }
    }

    const loadRatio = totalMcb > 0 ? Math.min(100, Math.round((totalWatts / totalMcb) * 100)) : 0

    return {
      total: devices.length,
      onlineCount,
      totalWatts,
      highLoadCount,
      loadRatio,
    }
  }, [devices, isDeviceOnlineFn])

  const hasActiveFilter = hideOffline || Boolean(normalizedSearch)

  return (
    <div className="home-view-clean tab-pane-fade">
      {/* eWeLink-Style Auto-Scroll Hero Banner Carousel right below navbar */}
      <HeroBannerCarousel
        currentUser={currentUser}
        isAuthenticated={isAuthenticated}
        appConfig={appConfig}
        onOpenAddDevice={onOpenAddDevice}
        onOpenUsageGuide={onOpenUsageGuide}
        onOpenPlanModal={onOpenPlanModal}
        onOpenSettings={onOpenSettings}
        onOpenAlerts={onOpenAlerts}
        onOpenLogin={onOpenLogin}
      />

      {/* eWeLink-Style Room Tabs + Utility Controls */}
      <RoomFilterBar
        rooms={rooms}
        activeRoom={activeRoom}
        onSelectRoom={onSelectRoom}
        onOpenAddDevice={onOpenAddDevice}
        devices={devices}
        viewMode={viewMode}
        onToggleViewMode={() => setViewMode((prev) => (prev === 'grid' ? 'list' : 'grid'))}
        hideOffline={hideOffline}
        onToggleHideOffline={() => setHideOffline((prev) => !prev)}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchOpen={searchOpen}
        onToggleSearch={(forceVal) =>
          setSearchOpen((prev) => (typeof forceVal === 'boolean' ? forceVal : !prev))
        }
      />

      {/* eWeLink Insight-Inspired Quick Metric Cards */}
      {homeSummary.total > 0 && (
        <div className="insight-quick-grid num-tabular">
          <div className="insight-mini-card">
            <div className="insight-dual-icon is-blue" aria-hidden="true">
              <Zap size={16} />
            </div>
            <div className="insight-mini-copy">
              <span className="insight-mini-label">Beban Saat Ini</span>
              <strong className="insight-mini-val">{formatNum(homeSummary.totalWatts, 0)} W</strong>
            </div>
          </div>

          <div className="insight-mini-card">
            <div className="insight-dual-icon is-emerald" aria-hidden="true">
              <Wifi size={16} />
            </div>
            <div className="insight-mini-copy">
              <span className="insight-mini-label">Panel Aktif</span>
              <strong className="insight-mini-val">
                {homeSummary.onlineCount}/{homeSummary.total} Online
              </strong>
            </div>
          </div>

          <div className="insight-mini-card">
            <div
              className={`insight-dual-icon ${
                homeSummary.highLoadCount > 0 ? 'is-amber' : 'is-emerald'
              }`}
              aria-hidden="true"
            >
              {homeSummary.highLoadCount > 0 ? <AlertTriangle size={16} /> : <ShieldCheck size={16} />}
            </div>
            <div className="insight-mini-copy">
              <span className="insight-mini-label">Kapasitas MCB</span>
              <strong
                className={`insight-mini-val ${
                  homeSummary.highLoadCount > 0 ? 'brand-amber-text' : 'brand-emerald-text'
                }`}
              >
                {homeSummary.highLoadCount > 0
                  ? `${homeSummary.highLoadCount} Tinggi`
                  : `Aman · ${homeSummary.loadRatio}%`}
              </strong>
            </div>
          </div>
        </div>
      )}

      {/* Grid / List Kartu Perangkat */}
      {filteredDevices.length === 0 ? (
        <div className="empty-home-canvas" data-tour-target="device-grid">
          <EmptySmartBoxIllustration src={resolveVisualAsset(appConfig, 'home_empty')} />
          <h3>
            {hasActiveFilter && devices.length > 0
              ? 'Tidak Ada Panel yang Cocok'
              : !isAuthenticated && devices.length === 0
                ? 'Belum Ada Perangkat Publik'
                : devices.length === 0
                  ? 'Belum Ada Panel Listrik'
                  : `Belum Ada Alat di ${activeRoom}`}
          </h3>
          <p>
            {hasActiveFilter && devices.length > 0
              ? 'Coba ubah kata kunci pencarian atau tampilkan perangkat offline.'
              : !isAuthenticated && devices.length === 0
                ? 'Masuk atau daftar akun untuk menautkan serta memantau meteran listrik Anda.'
                : devices.length === 0
                  ? 'Ketuk tombol di bawah atau ikon + di atas untuk menautkan panel VoltKu Anda.'
                  : 'Belum ada panel yang terpasang di ruangan ini.'}
          </p>

          {hasActiveFilter && devices.length > 0 ? (
            <button
              type="button"
              className="btn btn-secondary ewl-reset-filter-btn"
              onClick={() => {
                setHideOffline(false)
                setSearchQuery('')
                setSearchOpen(false)
              }}
            >
              <RotateCcw size={15} />
              <span>Tampilkan Semua Panel</span>
            </button>
          ) : !isAuthenticated && devices.length === 0 && onOpenLogin ? (
            <button type="button" className="ewl-primary-pill-btn" onClick={onOpenLogin}>
              <LogIn size={16} />
              <span>Masuk / Daftar Akun</span>
            </button>
          ) : (
            isAuthenticated &&
            onOpenAddDevice && (
              <button type="button" className="ewl-primary-pill-btn" onClick={onOpenAddDevice}>
                <Plus size={17} strokeWidth={2.5} />
                <span>Tambah Sekarang</span>
              </button>
            )
          )}
        </div>
      ) : (
        <div
          className={`clean-device-grid ${viewMode === 'list' ? 'is-list-view' : ''}`}
          data-tour-target="device-grid"
        >
          {filteredDevices.map((device) => {
            const online = isDeviceOnlineFn(device)
            const latest = device.latest
            const watts = latest && typeof latest.p === 'number' ? latest.p : null
            const volts = latest && typeof latest.v === 'number' ? latest.v : null
            const mcbCap = Number(device.mcb_watt) || 2200
            const loadPct =
              watts !== null ? Math.min(100, Math.max(0, Math.round((watts / mcbCap) * 100))) : 0
            const loadTone = loadPct >= 90 ? 'danger' : loadPct >= 75 ? 'warn' : 'ok'

            return (
              <button
                key={device.id}
                type="button"
                className={`clean-device-card ${online ? 'is-online' : 'is-offline'} ${
                  viewMode === 'list' ? 'is-list-card' : ''
                }`}
                onClick={() => onSelectDevice(device.id)}
              >
                <div className="clean-card-top">
                  <div className={`clean-device-glyph ${online ? 'online' : 'offline'}`}>
                    <Zap size={19} />
                  </div>
                  <div className="clean-card-power-col num-tabular">
                    <div className="clean-card-watt">
                      {watts !== null ? `${formatNum(watts, 0)} W` : '-- W'}
                    </div>
                    {volts !== null && (
                      <div className="clean-card-volt">{formatNum(volts, 0)} V</div>
                    )}
                  </div>
                </div>

                <div className="clean-card-middle">
                  <div className="clean-card-title">{device.name || device.id}</div>
                  <div className="clean-card-meta-row">
                    <span className="clean-card-room-loc">{device.location || 'Panel Utama'}</span>
                    <span className="clean-card-mcb-pill num-tabular">MCB {mcbCap} W</span>
                  </div>
                  {watts !== null && (
                    <div className="clean-card-mcb-track" aria-hidden="true">
                      <div
                        className={`admin-mcb-bar-fill ${loadTone}`}
                        style={{ width: `${loadPct}%` }}
                      />
                    </div>
                  )}
                </div>

                <div className="clean-card-bottom">
                  <span className={`clean-card-state ${online ? 'on' : 'off'}`}>
                    <span className="clean-dot" />
                    {online ? 'Online' : 'Offline'}
                  </span>
                  <span className="clean-card-wifi">
                    {online ? <Wifi size={14} /> : <WifiOff size={14} />}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
