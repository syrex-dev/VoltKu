import React from 'react'
import { Zap, Wifi, WifiOff, ChevronRight } from 'lucide-react'
import { formatNum, formatRp, formatTimeWIB, formatDateTimeWIB } from '../utils/formatters'

export function RealtimeTelemetry({
  latest,
  settings,
  activeDevice,
  isOnline,
  todaySummary,
  onGoToCharts,
}) {
  const p = latest?.p ?? null
  const v = latest?.v ?? null
  const f = latest?.f ?? null
  const i = latest?.i ?? null
  const pf = latest?.pf ?? null
  const e = latest?.e ?? null
  const rssi = latest?.rssi ?? null
  const ts = latest?.ts ?? null

  const powerLimit = activeDevice?.mcb_watt
    ? parseFloat(activeDevice.mcb_watt)
    : settings?.power_limit_w
    ? parseFloat(settings.power_limit_w)
    : 2200

  const pct = p !== null ? Math.min(100, Math.max(0, (p / powerLimit) * 100)) : 0
  const isPowerActive = isOnline && p !== null && p > 5

  let ringColor = '#1677ff'
  let barClass = 'meter-normal'
  if (!isOnline) {
    ringColor = '#94a3b8'
  } else if (pct >= 90) {
    ringColor = '#ef4444'
    barClass = 'meter-danger'
  } else if (pct >= 75) {
    ringColor = '#f59e0b'
    barClass = 'meter-warning'
  }

  const radius = 68
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (pct / 100) * circumference

  return (
    <div className="detail-live-stack">
      {/* Main Hero Sheet (Satu bidang putih bersih seperti app smart-home asli) */}
      <div className="clean-sheet hero-live-sheet">
        <div className="hero-status-bar">
          <span className={`hero-status-text ${isOnline ? 'online' : 'offline'}`}>
            <span className="clean-dot" />
            {isOnline
              ? 'Terhubung'
              : ts
              ? `Offline · Terakhir ${formatDateTimeWIB(ts)}`
              : 'Offline'}
          </span>
          <span className="hero-wifi-chip">
            {isOnline ? <Wifi size={14} /> : <WifiOff size={14} />}
            <span>{rssi !== null ? `${rssi} dBm` : 'Wi-Fi 2.4G'}</span>
          </span>
        </div>

        {/* Circular Power Gauge */}
        <div className="clean-gauge-wrap">
          <div className="clean-gauge-box">
            <svg className="gauge-svg" viewBox="0 0 168 168" aria-hidden="true">
              <circle
                className="gauge-track-circle"
                cx="84"
                cy="84"
                r={radius}
                strokeWidth="10"
                fill="none"
              />
              <circle
                className="gauge-progress-circle"
                cx="84"
                cy="84"
                r={radius}
                strokeWidth="10"
                fill="none"
                stroke={ringColor}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                transform="rotate(-90 84 84)"
              />
            </svg>
            <div className="gauge-center-content">
              <Zap
                size={24}
                className={isPowerActive ? 'brand-blue-text' : 'muted-glyph'}
              />
              <div className="clean-gauge-watts num-tabular">
                {p !== null ? `${formatNum(p, 0)} W` : '-- W'}
              </div>
              <div className="clean-gauge-sub num-tabular">
                {p !== null ? `${pct.toFixed(0)}% dari ${formatNum(powerLimit, 0)} W` : 'Menunggu data'}
              </div>
            </div>
          </div>

          {/* Capacity Thin Line */}
          <div className="clean-capacity-row">
            <div className="capacity-track">
              <div
                className={`capacity-fill ${barClass}`}
                style={{ width: `${pct.toFixed(1)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Trio Power / Current / Voltage on ONE Hairline Row (tanpa 3 kotak terpisah) */}
        <div className="hero-metrics-divider-row">
          <div className="hero-metric-col">
            <div className="hero-metric-val num-tabular">
              {p !== null ? formatNum(p, 1) : '--'}
              <span className="hero-metric-unit">W</span>
            </div>
            <div className="hero-metric-label">Daya</div>
          </div>

          <div className="hero-metric-col bordered-sides">
            <div className="hero-metric-val num-tabular">
              {i !== null ? formatNum(i, 2) : '--'}
              <span className="hero-metric-unit">A</span>
            </div>
            <div className="hero-metric-label">Arus</div>
          </div>

          <div className="hero-metric-col">
            <div className="hero-metric-val num-tabular">
              {v !== null ? formatNum(v, 1) : '--'}
              <span className="hero-metric-unit">V</span>
            </div>
            <div className="hero-metric-label">Tegangan</div>
          </div>
        </div>
      </div>

      {/* Clean Grouped Specs List + Shortcut (Right Column on Desktop) */}
      <div className="live-side-stack">
        <div className="clean-sheet grouped-list-sheet">
          <div className="grouped-row">
            <span className="grouped-row-label">Frekuensi Listrik</span>
            <span className="grouped-row-val num-tabular">
              {f !== null ? `${formatNum(f, 1)} Hz` : '-'}
            </span>
          </div>
          <div className="grouped-row">
            <span className="grouped-row-label">Faktor Daya</span>
            <span className="grouped-row-val num-tabular">
              {pf !== null ? formatNum(pf, 2) : '-'}
            </span>
          </div>
          <div className="grouped-row">
            <span className="grouped-row-label">Total Meter kWh</span>
            <span className="grouped-row-val num-tabular">
              {e !== null ? `${formatNum(e, 2)} kWh` : '-'}
            </span>
          </div>
          <div className="grouped-row">
            <span className="grouped-row-label">Pembaruan Data</span>
            <span className="grouped-row-val num-tabular">
              {ts ? `${formatTimeWIB(ts)} WIB` : '-'}
            </span>
          </div>
        </div>

        <button type="button" className="clean-sheet grouped-action-sheet" onClick={onGoToCharts}>
          <div className="grouped-action-left">
            <span className="grouped-action-title">Pemakaian Hari Ini</span>
            <span className="grouped-action-sub num-tabular">
              {todaySummary
                ? `${formatNum(todaySummary.kwh, 3)} kWh · ${formatRp(todaySummary.cost_rp)}`
                : 'Lihat grafik dan rincian biaya'}
            </span>
          </div>
          <ChevronRight size={19} className="muted-glyph" />
        </button>
      </div>
    </div>
  )
}
