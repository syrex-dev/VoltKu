import React, { useMemo } from 'react'
import { Zap, Wifi, WifiOff, Plus, LogIn, Activity, ShieldCheck, AlertTriangle } from 'lucide-react'
import { RoomFilterBar } from './RoomFilterBar'
import { formatNum } from '../utils/formatters'

export function HomeDevicesView({
  devices,
  rooms,
  activeRoom,
  onSelectRoom,
  onSelectDevice,
  onOpenAddDevice,
  isDeviceOnlineFn,
  isAuthenticated = false,
  onOpenLogin,
}) {
  const filteredDevices = devices.filter((dev) => {
    if (activeRoom === 'Semua') return true
    if (activeRoom === 'Lainnya') return !dev.location || !dev.location.trim()
    return (dev.location || '').trim() === activeRoom
  })

  const homeSummary = useMemo(() => {
    let onlineCount = 0
    let totalWatts = 0
    let highLoadCount = 0

    for (const dev of devices) {
      const online = isDeviceOnlineFn(dev)
      if (online) {
        onlineCount += 1
        const w = dev.latest?.p
        if (typeof w === 'number') {
          totalWatts += w
          const mcb = Number(dev.mcb_watt) || 2200
          if (w / mcb >= 0.75) {
            highLoadCount += 1
          }
        }
      }
    }

    return {
      total: devices.length,
      onlineCount,
      totalWatts,
      highLoadCount,
    }
  }, [devices, isDeviceOnlineFn])

  return (
    <div className="home-view-clean tab-pane-fade">
      {/* Bar Dropdown Ruangan & Satu Tombol Tambah di Main Content */}
      <RoomFilterBar
        rooms={rooms}
        activeRoom={activeRoom}
        onSelectRoom={onSelectRoom}
        onOpenAddDevice={onOpenAddDevice}
        devices={devices}
      />

      {/* Ringkasan Cepat Beban Rumah */}
      {homeSummary.total > 0 && (
        <div className="clean-sheet home-summary-strip num-tabular">
          <div className="home-summary-item">
            <Activity size={15} className="brand-blue-text" />
            <span className="home-summary-label">Total Beban</span>
            <strong className="home-summary-val">{formatNum(homeSummary.totalWatts, 0)} W</strong>
          </div>
          <div className="home-summary-divider" aria-hidden="true" />
          <div className="home-summary-item">
            <Wifi size={15} className={homeSummary.onlineCount > 0 ? 'brand-emerald-text' : ''} />
            <span className="home-summary-label">Aktif</span>
            <strong className="home-summary-val">
              {homeSummary.onlineCount}/{homeSummary.total} unit
            </strong>
          </div>
          <div className="home-summary-divider" aria-hidden="true" />
          <div className="home-summary-item">
            {homeSummary.highLoadCount > 0 ? (
              <AlertTriangle size={15} className="brand-amber-text" />
            ) : (
              <ShieldCheck size={15} className="brand-emerald-text" />
            )}
            <span className="home-summary-label">Beban MCB</span>
            <strong
              className={`home-summary-val ${
                homeSummary.highLoadCount > 0 ? 'brand-amber-text' : 'brand-emerald-text'
              }`}
            >
              {homeSummary.highLoadCount > 0 ? `${homeSummary.highLoadCount} tinggi` : 'Aman'}
            </strong>
          </div>
        </div>
      )}

      {/* Grid Kartu Perangkat */}
      {filteredDevices.length === 0 ? (
        <div className="clean-sheet empty-home-sheet" data-tour-target="device-grid">
          <div className="empty-home-circle">
            <Zap size={28} />
          </div>
          <h3>
            {!isAuthenticated && devices.length === 0
              ? 'Belum Ada Perangkat Publik'
              : devices.length === 0
                ? 'Belum Ada Perangkat Anda'
                : `Belum Ada Alat di ${activeRoom}`}
          </h3>
          <p>
            {!isAuthenticated && devices.length === 0
              ? 'Masuk atau daftar akun untuk memasang serta mengelola meteran listrik Anda.'
              : devices.length === 0
                ? 'Tambahkan perangkat VoltKu pertama Anda dan sambungkan ke Wi-Fi rumah.'
                : 'Pilih "Semua Ruangan" atau tekan + Tambah Panel di atas untuk memasang alat baru.'}
          </p>
          {!isAuthenticated && devices.length === 0 && onOpenLogin && (
            <button type="button" className="btn btn-primary" onClick={onOpenLogin}>
              <LogIn size={16} />
              <span>Masuk / Daftar Akun</span>
            </button>
          )}
          {isAuthenticated && devices.length === 0 && (
            <button type="button" className="btn btn-primary" onClick={onOpenAddDevice}>
              <Plus size={16} />
              <span>Tambah Perangkat</span>
            </button>
          )}
        </div>
      ) : (
        <div className="clean-device-grid">
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
                className={`clean-device-card ${online ? 'is-online' : 'is-offline'}`}
                onClick={() => onSelectDevice(device.id)}
              >
                <div className="clean-card-top">
                  <div className={`clean-device-glyph ${online ? 'online' : 'offline'}`}>
                    <Zap size={20} />
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
                  <div className="clean-card-room">
                    {device.location || 'Panel Listrik'} · MCB {mcbCap} W
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
