import React, { useState, useMemo } from 'react'
import {
  ShieldCheck,
  AlertCircle,
  WifiOff,
  Zap,
  Gauge,
  TrendingUp,
  Moon,
} from 'lucide-react'
import { formatDateTimeWIB } from '../utils/formatters'

function getAnomalyMeta(item) {
  const type = item?.type || ''
  let title = 'Peringatan Listrik'
  let Icon = AlertCircle

  if (type === 'offline') {
    title = 'Perangkat Terputus'
    Icon = WifiOff
  } else if (type === 'power_limit') {
    title = 'Daya Melebihi Batas'
    Icon = Zap
  } else if (type === 'voltage' || type === 'voltage_low' || type === 'voltage_high') {
    title = 'Tegangan Tidak Stabil'
    Icon = Gauge
  } else if (type === 'spike_vs_baseline') {
    title = 'Lonjakan Daya Tidak Wajar'
    Icon = TrendingUp
  } else if (type === 'night_baseload') {
    title = 'Pemakaian Malam Tinggi'
    Icon = Moon
  }

  let desc = (item?.message || '').trim()
  desc = desc.replace(/^\[(PERINGATAN|BAHAYA|KRITIS|INFO|WARNING|CRITICAL)\]\s*/i, '')
  if (item?.device_id) {
    const escapedId = item.device_id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    desc = desc.replace(new RegExp(`^${escapedId}\\s*[-:]\\s*`, 'i'), '')
  }

  return { title, desc, Icon }
}

export function AnomaliesList({
  anomalies,
  showDeviceLabel = false,
  deviceNamesById = {},
}) {
  const [sevFilter, setSevFilter] = useState('all')
  const list = useMemo(() => anomalies || [], [anomalies])
  const critCount = useMemo(
    () => list.filter((a) => (a.severity || '').toLowerCase() === 'critical').length,
    [list]
  )
  const warnCount = list.length - critCount
  const visibleList = useMemo(() => {
    if (sevFilter === 'critical') {
      return list.filter((a) => (a.severity || '').toLowerCase() === 'critical')
    }
    if (sevFilter === 'warning') {
      return list.filter((a) => (a.severity || '').toLowerCase() !== 'critical')
    }
    return list
  }, [list, sevFilter])

  return (
    <section className="clean-sheet anomaly-feed-sheet">
      <div className="anomaly-feed-header">
        <div>
          <h2 className="anomaly-feed-title">
            {showDeviceLabel ? 'Semua Peringatan' : 'Catatan Peringatan'}
          </h2>
          <div className="anomaly-feed-sub">Riwayat 7 hari terakhir</div>
        </div>
        {list.length > 0 && (
          <span className="anomaly-count-pill num-tabular">{list.length} Catatan</span>
        )}
      </div>

      {list.length > 0 && (
        <div className="anomaly-filter-bar">
          {[
            { id: 'all', label: `Semua (${list.length})` },
            { id: 'critical', label: `Kritis (${critCount})` },
            { id: 'warning', label: `Peringatan (${warnCount})` },
          ].map((f) => (
            <button
              key={f.id}
              type="button"
              className={`admin-filter-pill ${sevFilter === f.id ? 'active' : ''}`}
              onClick={() => setSevFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {visibleList.length === 0 ? (
        <div className="empty-healthy-card">
          <div className="healthy-icon-wrap">
            <ShieldCheck size={26} />
          </div>
          <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-main)' }}>
            {list.length === 0 ? 'Semua Berjalan Normal' : 'Tidak Ada Catatan pada Filter Ini'}
          </div>
          <div style={{ fontSize: 13 }}>
            {list.length === 0
              ? 'Belum ada catatan gangguan atau lonjakan listrik dalam 7 hari terakhir.'
              : 'Coba pilih filter "Semua" untuk melihat catatan peringatan lainnya.'}
          </div>
        </div>
      ) : (
        <div className="anomaly-feed-list">
          {visibleList.map((item) => {
            const isCrit = item.severity === 'critical'
            const { title, desc, Icon } = getAnomalyMeta(item)
            const devName = showDeviceLabel && item.device_id
              ? deviceNamesById[item.device_id] || item.device_id
              : null

            return (
              <div
                key={item.id || `${item.ts}-${item.type}`}
                className="anomaly-feed-item"
              >
                <div className={`anomaly-glyph-circle ${isCrit ? 'critical' : 'warning'}`}>
                  <Icon size={18} />
                </div>

                <div className="anomaly-item-body">
                  <div className="anomaly-item-top">
                    <span className="anomaly-item-title">
                      {devName ? `${title} · ${devName}` : title}
                    </span>
                    <span className={`severity-tag ${isCrit ? 'critical' : 'warning'}`}>
                      {isCrit ? 'Kritis' : 'Peringatan'}
                    </span>
                  </div>

                  {desc && <p className="anomaly-item-desc">{desc}</p>}

                  <div className="anomaly-item-time num-tabular">
                    {formatDateTimeWIB(item.ts)} WIB
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
