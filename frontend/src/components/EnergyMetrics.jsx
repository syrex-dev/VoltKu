import React from 'react'
import { Calendar, TrendingUp, DollarSign, Clock } from 'lucide-react'
import { formatRp, formatNum, formatTimeWIB } from '../utils/formatters'

export function EnergyMetrics({ today, week, month, forecast }) {
  return (
    <section className="section-block">
      <h2 className="section-title">Konsumsi Energi & Biaya</h2>
      <div className="grid grid-4">
        {/* Hari Ini */}
        <div className="card stat-card">
          <div className="card-header-flex">
            <span className="card-label">Hari Ini</span>
            {today?.cost_estimated && (
              <span className="badge-mini badge-est">Estimasi</span>
            )}
          </div>
          <div className="card-value-lg">{formatRp(today?.cost_rp)}</div>
          <div className="card-sub">{today ? `${formatNum(today.kwh, 3)} kWh` : '- kWh'}</div>
          <div className="card-footnote">
            {today?.peak_w > 0 && today?.peak_ts
              ? `Puncak: ${formatNum(today.peak_w, 1)} W (${formatTimeWIB(today.peak_ts)})`
              : 'Puncak: - W'}
          </div>
        </div>

        {/* Minggu Ini */}
        <div className="card stat-card">
          <div className="card-header-flex">
            <span className="card-label">Minggu Ini</span>
          </div>
          <div className="card-value-lg">{formatRp(week?.cost_rp)}</div>
          <div className="card-sub">{week ? `${formatNum(week.kwh, 3)} kWh` : '- kWh'}</div>
          <div className="card-footnote">
            Rata-rata: {week ? `${formatNum(week.avg_power_w, 1)} W` : '- W'}
          </div>
        </div>

        {/* Bulan Ini */}
        <div className="card stat-card">
          <div className="card-header-flex">
            <span className="card-label">Bulan Ini (Berjalan)</span>
          </div>
          <div className="card-value-lg">{formatRp(month?.cost_rp)}</div>
          <div className="card-sub">{month ? `${formatNum(month.kwh, 3)} kWh` : '- kWh'}</div>
          <div className="card-footnote">
            Puncak: {month ? `${formatNum(month.peak_w, 1)} W` : '- W'}
          </div>
        </div>

        {/* Proyeksi Akhir Bulan */}
        <div className="card stat-card forecast-card">
          <div className="card-header-flex">
            <span className="card-label">Proyeksi Akhir Bulan</span>
            {forecast?.available ? (
              <span className={`badge-mini ${forecast.low_confidence ? 'badge-est' : ''}`}>
                {forecast.low_confidence ? 'Perkiraan Kasar' : `Basis ${forecast.basis_days} Hari`}
              </span>
            ) : (
              <span className="badge-mini">Belum Tersedia</span>
            )}
          </div>
          <div className="card-value-lg">
            {forecast?.available ? formatRp(forecast.projected_cost_rp) : 'Belum Tersedia'}
          </div>
          <div className="card-sub">
            {forecast?.available ? `${formatNum(forecast.projected_kwh, 2)} kWh` : '-'}
          </div>
          <div className="card-footnote">
            {!forecast || !forecast.available
              ? 'Data hari penuh belum mencukupi (< 1 hari)'
              : forecast.low_confidence
              ? `Basis data terbatas (${forecast.basis_days} hari)`
              : `Rata-rata: ${formatNum(forecast.avg_daily_kwh, 2)} kWh/hari`}
          </div>
        </div>
      </div>
    </section>
  )
}
