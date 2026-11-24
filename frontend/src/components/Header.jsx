import React from 'react'
import { Zap, Settings, LogOut, Radio } from 'lucide-react'
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
    <header className="app-header">
      <div className="header-left">
        <div className="brand-wrap">
          <Zap className="brand-icon" size={24} />
          <h1 className="logo-title">Monitor Listrik</h1>
        </div>

        <div className="device-selector-wrap">
          <select
            className="form-select"
            value={activeDeviceId}
            onChange={(e) => onSelectDevice(e.target.value)}
            aria-label="Pilih Perangkat"
          >
            {devices.length === 0 ? (
              <option value="">Tidak ada perangkat terdaftar</option>
            ) : (
              devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name || d.id} ({d.mcb_watt} W)
                </option>
              ))
            )}
          </select>

          <span className={`badge ${isOnline ? 'badge-online' : 'badge-offline'}`}>
            <span className="badge-dot"></span>
            {isOnline
              ? 'Online'
              : ts
              ? `Offline, data terakhir ${formatDateTimeWIB(ts)} WIB`
              : 'Offline (belum ada data)'}
          </span>
        </div>
      </div>

      <div className="header-right">
        <button
          className="btn btn-secondary btn-icon-text"
          onClick={onOpenSettings}
          title="Pengaturan Sistem"
        >
          <Settings size={16} />
          <span>Pengaturan</span>
        </button>
        <button
          className="btn btn-outline btn-icon-text"
          onClick={onLogout}
          title="Keluar dari Dashboard"
        >
          <LogOut size={16} />
          <span>Keluar</span>
        </button>
      </div>
    </header>
  )
}
