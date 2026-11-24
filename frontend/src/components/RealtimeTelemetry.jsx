import React from 'react'
import { Zap, Gauge, Activity, Wifi, ShieldAlert } from 'lucide-react'
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

  let meterClass = 'meter-normal'
  if (pct >= 90) {
    meterClass = 'meter-danger'
  } else if (pct >= 75) {
    meterClass = 'meter-warning'
  }

  return (
    <section className="section-block">
      <div className="section-header">
        <h2 className="section-title">
          <Zap size={14} className="text-primary" /> Telemetri Real-Time
        </h2>
        <div className="section-title-line"></div>
      </div>

      <div className="telemetry-cockpit">
        {/* Hero Active Power Card */}
        <div className="card power-hero-card card-hero-glow">
          <div className="card-top-row">
            <span className="card-label">
              <Zap size={15} className="text-primary" /> Daya Aktif (Beban)
            </span>
            <span className="live-indicator">
              <span className="live-dot"></span> Live
            </span>
          </div>

          <div className="power-display-wrap">
            <span className="power-number num-tabular">
              {p !== null ? formatNum(p, 1) : '-'}
            </span>
            <span className="power-unit">Watt</span>
          </div>

          <div className="power-meter-wrap">
            <div className="power-meter-track">
              <div
                className={`power-meter-fill ${meterClass}`}
                style={{ width: `${pct.toFixed(1)}%` }}
              ></div>
            </div>
            <div className="meter-labels num-tabular">
              <span>{pct.toFixed(0)}% Kapasitas</span>
              <span>Batas PLN: {powerLimit ? `${powerLimit} W` : '-'}</span>
            </div>
          </div>
        </div>

        {/* Tegangan Jaringan */}
        <div className="card telemetry-card">
          <div className="card-top-row">
            <span className="card-label">
              <Gauge size={15} /> Tegangan AC
            </span>
          </div>
          <div className="telemetry-val-wrap">
            <span className="telemetry-number num-tabular">
              {v !== null ? formatNum(v, 1) : '-'}
            </span>
            <span className="telemetry-unit">Volt</span>
          </div>
          <div className="card-detail-pill num-tabular">
            <span>Frekuensi: {f !== null ? `${formatNum(f, 1)} Hz` : '-'}</span>
          </div>
        </div>

        {/* Arus Listrik */}
        <div className="card telemetry-card">
          <div className="card-top-row">
            <span className="card-label">
              <Activity size={15} /> Arus Listrik
            </span>
          </div>
          <div className="telemetry-val-wrap">
            <span className="telemetry-number num-tabular">
              {i !== null ? formatNum(i, 2) : '-'}
            </span>
            <span className="telemetry-unit">Ampere</span>
          </div>
          <div className="card-detail-pill num-tabular">
            <span>Power Factor: {pf !== null ? formatNum(pf, 2) : '-'}</span>
          </div>
        </div>

        {/* Koneksi & Waktu */}
        <div className="card telemetry-card">
          <div className="card-top-row">
            <span className="card-label">
              <Wifi size={15} /> Jaringan Sensor
            </span>
          </div>
          <div className="telemetry-val-wrap">
            <span className="telemetry-number num-tabular">
              {rssi !== null ? rssi : '-'}
            </span>
            <span className="telemetry-unit">dBm</span>
          </div>
          <div className="card-detail-pill num-tabular">
            <span>Pukul {ts ? formatTimeWIB(ts) : '-'} WIB</span>
          </div>
        </div>
      </div>
    </section>
  )
}
