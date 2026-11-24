import React from 'react'
import { AlertTriangle } from 'lucide-react'

export function WarningBanner({ settings, activeDevice }) {
  if (!settings || !activeDevice) return null

  const pLimit = parseInt(settings.power_limit_w, 10)
  const mcbWatt = parseInt(activeDevice.mcb_watt, 10)

  if (pLimit <= mcbWatt) return null

  return (
    <div className="alert-banner-modern">
      <AlertTriangle className="alert-banner-icon" size={22} />
      <div>
        <strong style={{ color: '#ffffff' }}>Peringatan Kapasitas:</strong> Batas daya PLN konfigurasi ({pLimit} W) melebihi batas MCB fisik perangkat ({mcbWatt} W). Mohon sesuaikan pengaturan agar MCB tidak anjlok mendadak.
      </div>
    </div>
  )
}
