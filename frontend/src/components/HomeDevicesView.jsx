import React from 'react'
import { Zap, Wifi, WifiOff, Plus, LogIn, CheckCircle2, ShieldCheck, Compass } from 'lucide-react'
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
  onReplayTour,
  appConfig = {},
}) {
  const showOnboardingCard = Boolean(onReplayTour && appConfig.onboarding_enabled !== false)
  const appName = appConfig.app_name || 'VoltKu'
  const filteredDevices = devices.filter((dev) => {
    if (activeRoom === 'Semua') return true
    if (activeRoom === 'Lainnya') return !dev.location || !dev.location.trim()
    return (dev.location || '').trim() === activeRoom
  })

  return (
    <div className="home-view-clean tab-pane-fade">
      {/* Banner Tips Geser Horizontal ala Native App */}
      <div className="home-tips-strip" aria-label="Pintasan & Panduan Cepat">
        <button type="button" className="home-tip-card is-blue" onClick={onOpenAddDevice}>
          <span className="home-tip-icon">
            <Plus size={16} />
          </span>
          <span className="home-tip-copy">
            <strong>Pasang Panel Wi-Fi 2.4 GHz</strong>
            <span>Sambungkan sensor {appName} baru dalam 3 langkah</span>
          </span>
        </button>

        {showOnboardingCard && (
          <button type="button" className="home-tip-card is-teal" onClick={onReplayTour}>
            <span className="home-tip-icon">
              <Compass size={16} />
            </span>
            <span className="home-tip-copy">
              <strong>Panduan Aplikasi</strong>
              <span>Lihat pengenalan singkat cara memantau daya &amp; biaya</span>
            </span>
          </button>
        )}

        {!isAuthenticated && onOpenLogin && (
          <button type="button" className="home-tip-card is-amber" onClick={onOpenLogin}>
            <span className="home-tip-icon">
              <ShieldCheck size={16} />
            </span>
            <span className="home-tip-copy">
              <strong>Masuk dengan Google / Email</strong>
              <span>Sinkronkan data panel yang sama di Web &amp; Aplikasi</span>
            </span>
          </button>
        )}

        {isAuthenticated && (
          <div className="home-tip-card is-amber is-static">
            <span className="home-tip-icon">
              <CheckCircle2 size={16} />
            </span>
            <span className="home-tip-copy">
              <strong>Sinkronisasi Cloud Aktif</strong>
              <span>Web &amp; Aplikasi terhubung langsung ke panel Anda</span>
            </span>
          </div>
        )}
      </div>

      {/* Bar Ruangan & Satu Tombol Tambah di Main Content */}
      <RoomFilterBar
        rooms={rooms}
        activeRoom={activeRoom}
        onSelectRoom={onSelectRoom}
        onOpenAddDevice={onOpenAddDevice}
      />

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
                : 'Pilih tab "Semua" atau tekan Tambah di atas untuk memasang alat baru.'}
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
                  <div className="clean-card-watt num-tabular">
                    {watts !== null ? `${formatNum(watts, 0)} W` : '-- W'}
                  </div>
                </div>

                <div className="clean-card-middle">
                  <div className="clean-card-title">{device.name || device.id}</div>
                  <div className="clean-card-room">
                    {device.location || 'Panel Listrik'}
                  </div>
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
