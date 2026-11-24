import React from 'react'
import { Zap, Gauge, Activity, Wifi, ShieldAlert, Cpu } from 'lucide-react'
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

      <div className="telemetry-cockpit-layout">
        {/* Hero Active Power Card (Full width on top) */}
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

        {/* Secondary Telemetry Grid (2x2 on mobile, 3 columns on desktop) */}
        <div className="telemetry-subgrid">
          {/* Tegangan AC */}
          <div className="card telemetry-mini-card">
            <div className="card-top-row">
              <span className="card-label">
                <Gauge size={14} className="text-secondary" /> Tegangan AC
              </span>
            </div>
            <div className="telemetry-val-wrap">
              <span className="telemetry-number num-tabular">
                {v !== null ? formatNum(v, 1) : '-'}
              </span>
              <span className="telemetry-unit">Volt</span>
            </div>
            <div className="card-detail-pill num-tabular">
              <span>{f !== null ? `${formatNum(f, 1)} Hz` : '- Hz'}</span>
            </div>
          </div>

          {/* Arus Listrik */}
          <div className="card telemetry-mini-card">
            <div className="card-top-row">
              <span className="card-label">
                <Activity size={14} className="text-secondary" /> Arus Listrik
              </span>
            </div>
            <div className="telemetry-val-wrap">
              <span className="telemetry-number num-tabular">
                {i !== null ? formatNum(i, 2) : '-'}
              </span>
              <span className="telemetry-unit">Ampere</span>
            </div>
            <div className="card-detail-pill num-tabular">
              <span>PF: {pf !== null ? formatNum(pf, 2) : '-'}</span>
            </div>
          </div>

          {/* Sinyal Wi-Fi / Jaringan */}
          <div className="card telemetry-mini-card">
            <div className="card-top-row">
              <span className="card-label">
                <Wifi size={14} className="text-secondary" /> Sinyal Wi-Fi
              </span>
            </div>
            <div className="telemetry-val-wrap">
              <span className="telemetry-number num-tabular">
                {rssi !== null ? rssi : '-'}
              </span>
              <span className="telemetry-unit">dBm</span>
            </div>
            <div className="card-detail-pill num-tabular">
              <span>{rssi && rssi > -70 ? 'Sinyal Baik' : 'Sinyal Cukup'}</span>
            </div>
          </div>

          {/* Pembaruan Terakhir */}
          <div className="card telemetry-mini-card">
            <div className="card-top-row">
              <span className="card-label">
                <Cpu size={14} className="text-secondary" /> Pembacaan
              </span>
            </div>
            <div className="telemetry-val-wrap">
              <span className="telemetry-number num-tabular" style={{ fontSize: '1.25rem' }}>
                {ts ? formatTimeWIB(ts) : '-'}
              </span>
              <span className="telemetry-unit">WIB</span>
            </div>
            <div className="card-detail-pill num-tabular">
              <span>Sensor Aktif</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
