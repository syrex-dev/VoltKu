import React from 'react'
import { Zap, Sliders, LogOut, ChevronDown, Radio } from 'lucide-react'
import { formatDateTimeWIB } from '../utils/formatters'

export function Header({
  devices,
  activeDeviceId,
  onSelectDevice,
  onOpenSettings,
  onLogout,
  lastDataTs,
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
          {/* Brand */}
          <div className="header-brand">
            <div className="brand-icon-box">
              <Zap size={20} />
            </div>
            <div className="brand-title-wrap">
              <div className="brand-title">
                Monitor Listrik
                <span className="brand-badge">IoT + AI</span>
              </div>
            </div>
          </div>

          {/* Device Switcher & Live Status */}
          <div className="header-center">
            <div className="device-picker">
              <span className="device-label">
                <Radio size={13} /> Perangkat:
              </span>
              <select
                className="device-select-custom"
                value={activeDeviceId}
                onChange={(e) => onSelectDevice(e.target.value)}
                aria-label="Pilih Perangkat"
              >
                {devices.length === 0 ? (
                  <option value="">Tidak ada perangkat</option>
                ) : (
                  devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name || d.id} • {d.mcb_watt} W
                    </option>
                  ))
                )}
              </select>
            </div>

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

          {/* Action Buttons */}
          <div className="header-right">
            <button
              className="btn btn-secondary"
              onClick={onOpenSettings}
              title="Pengaturan Sistem"
            >
              <Sliders size={15} />
              <span>Pengaturan</span>
            </button>
            <button
              className="btn btn-danger-ghost"
              onClick={onLogout}
              title="Keluar dari Dashboard"
            >
              <LogOut size={15} />
              <span>Keluar</span>
            </button>
          </div>
        </header>
      </div>
    </div>
  )
}
