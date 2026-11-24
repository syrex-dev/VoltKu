import React from 'react'
import { Activity, Gauge, Zap, Wifi } from 'lucide-react'
import { formatNum, formatTimeWIB } from '../utils/formatters'

export function RealtimeTelemetry({ latest, settings }) {
  const p = latest?.p ?? null
  const v = latest?.v ?? null
  const f = latest?.f ?? null
  const i = latest?.i ?? null
  const pf = latest?.pf ?? null
  const rssi = latest?.rssi ?? null
  const ts = latest?.ts ?? null

  // Progress Bar calculation
  const powerLimit = settings?.power_limit_w ? parseFloat(settings.power_limit_w) : null
  const pct = powerLimit && p !== null ? Math.min(100, Math.max(0, (p / powerLimit) * 100)) : 0

  let fillClass = 'bg-primary'
  if (pct >= 90) {
    fillClass = 'bg-danger'
  } else if (pct >= 75) {
    fillClass = 'bg-warning'
  }

  return (
    <section className="section-block">
      <h2 className="section-title">Status Real-time</h2>
      <div className="grid grid-4">
        {/* Daya Aktif Card */}
        <div className="card stat-card highlight-card">
          <div className="card-top">
            <span className="card-label">Daya Aktif</span>
            <Zap size={18} className="text-primary" />
          </div>
          <div className="card-value">{p !== null ? `${formatNum(p, 1)} W` : '- W'}</div>
          <div className="progress-bar-wrap">
            <div className="progress-bar-track">
              <div
                className={`progress-bar-fill ${fillClass}`}
                style={{ width: `${pct.toFixed(1)}%` }}
              ></div>
            </div>
            <div className="progress-label">
              {powerLimit ? `${pct.toFixed(0)}% dari batas ${powerLimit} W` : '-'}
            </div>
          </div>
        </div>

        {/* Tegangan Card */}
        <div className="card stat-card">
          <div className="card-top">
            <span className="card-label">Tegangan Jaringan</span>
            <Gauge size={18} className="text-muted" />
          </div>
          <div className="card-value">{v !== null ? `${formatNum(v, 1)} V` : '- V'}</div>
          <div className="card-sub">
            Frekuensi: {f !== null ? `${formatNum(f, 1)} Hz` : '- Hz'}
          </div>
        </div>

        {/* Arus Card */}
        <div className="card stat-card">
          <div className="card-top">
            <span className="card-label">Arus Listrik</span>
            <Activity size={18} className="text-muted" />
          </div>
          <div className="card-value">{i !== null ? `${formatNum(i, 2)} A` : '- A'}</div>
          <div className="card-sub">
            Power Factor: {pf !== null ? formatNum(pf, 2) : '-'}
          </div>
        </div>

        {/* Koneksi & Waktu Card */}
        <div className="card stat-card">
          <div className="card-top">
            <span className="card-label">Koneksi & Sinyal</span>
            <Wifi size={18} className="text-muted" />
          </div>
          <div className="card-value">{rssi !== null ? `${rssi} dBm` : '- dBm'}</div>
          <div className="card-sub">
            Update: {ts ? formatTimeWIB(ts) : '-'}
          </div>
        </div>
      </div>
    </section>
  )
}
