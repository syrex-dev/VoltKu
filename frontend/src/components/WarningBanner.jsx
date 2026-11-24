import React from 'react'
import { AlertTriangle } from 'lucide-react'

export function WarningBanner({ settings, activeDevice }) {
  if (!settings || !activeDevice) return null

  const pLimit = parseInt(settings.power_limit_w, 10)
  const mcbWatt = parseInt(activeDevice.mcb_watt, 10)

  if (pLimit <= mcbWatt) return null

  return (
    <div className="alert-banner alert-warning">
      <AlertTriangle className="alert-icon" size={20} />
      <span className="alert-text">
        <strong>Peringatan:</strong> Batas daya PLN ({pLimit} W) melebihi kapasitas MCB perangkat (
        {mcbWatt} W)!
      </span>
    </div>
  )
}
