import React from 'react'
import { TrendingUp, Calendar, Clock, Sparkles } from 'lucide-react'
import { formatRp, formatNum, formatTimeWIB } from '../utils/formatters'

export function EnergyMetrics({ today, week, month, forecast }) {
  return (
    <section className="section-block">
      <div className="section-header">
        <h2 className="section-title">
          <TrendingUp size={14} className="text-primary" /> Akumulasi Energi & Estimasi Biaya
        </h2>
        <div className="section-title-line"></div>
      </div>

      <div className="energy-grid">
        {/* Hari Ini */}
        <div className="card cost-card">
          <div className="card-top-row">
            <span className="card-label">
              <Clock size={14} /> Hari Ini
            </span>
            {today?.cost_estimated && (
              <span className="badge-forecast badge-warning-soft">Estimasi</span>
            )}
          </div>
          <div className="cost-primary num-tabular">{formatRp(today?.cost_rp)}</div>
          <div className="cost-kwh num-tabular">
            {today ? `${formatNum(today.kwh, 3)} kWh` : '- kWh'}
          </div>
          <div className="cost-meta num-tabular">
            {today?.peak_w > 0 && today?.peak_ts
              ? `Beban Puncak: ${formatNum(today.peak_w, 1)} W (${formatTimeWIB(today.peak_ts)})`
              : 'Beban Puncak: - W'}
          </div>
        </div>

        {/* Minggu Ini */}
        <div className="card cost-card">
          <div className="card-top-row">
            <span className="card-label">
              <Calendar size={14} /> Minggu Ini
            </span>
          </div>
          <div className="cost-primary num-tabular">{formatRp(week?.cost_rp)}</div>
          <div className="cost-kwh num-tabular">
            {week ? `${formatNum(week.kwh, 3)} kWh` : '- kWh'}
          </div>
          <div className="cost-meta num-tabular">
            Rata-rata: {week ? `${formatNum(week.avg_power_w, 1)} W` : '- W'}
          </div>
        </div>

        {/* Bulan Ini */}
        <div className="card cost-card">
          <div className="card-top-row">
            <span className="card-label">
              <Calendar size={14} /> Bulan Ini (Berjalan)
            </span>
          </div>
          <div className="cost-primary num-tabular">{formatRp(month?.cost_rp)}</div>
          <div className="cost-kwh num-tabular">
            {month ? `${formatNum(month.kwh, 3)} kWh` : '- kWh'}
          </div>
          <div className="cost-meta num-tabular">
            Puncak Bulanan: {month ? `${formatNum(month.peak_w, 1)} W` : '- W'}
          </div>
        </div>

        {/* Proyeksi Akhir Bulan */}
        <div className="card cost-card forecast-card-modern">
          <div className="card-top-row">
            <span className="card-label" style={{ color: '#c084fc' }}>
              <Sparkles size={14} /> Proyeksi Akhir Bulan
            </span>
            {forecast?.available ? (
              <span
                className={`badge-forecast ${
                  forecast.low_confidence ? 'badge-warning-soft' : ''
                }`}
              >
                {forecast.low_confidence ? 'Kasar' : `Basis ${forecast.basis_days} Hari`}
              </span>
            ) : (
              <span className="badge-forecast" style={{ opacity: 0.6 }}>
                Belum Siap
              </span>
            )}
          </div>
          <div className="cost-primary num-tabular" style={{ color: '#f3e8ff' }}>
            {forecast?.available ? formatRp(forecast.projected_cost_rp) : 'Belum Tersedia'}
          </div>
          <div className="cost-kwh num-tabular" style={{ color: '#c084fc' }}>
            {forecast?.available ? `${formatNum(forecast.projected_kwh, 2)} kWh` : '-'}
          </div>
          <div className="cost-meta num-tabular" style={{ borderColor: 'rgba(168, 85, 247, 0.2)' }}>
            {!forecast || !forecast.available
              ? 'Butuh data minimal 24 jam penuh'
              : forecast.low_confidence
              ? `Akurasi kasar (${forecast.basis_days} hari data)`
              : `Rata-rata: ${formatNum(forecast.avg_daily_kwh, 2)} kWh/hari`}
          </div>
        </div>
      </div>
    </section>
  )
}
