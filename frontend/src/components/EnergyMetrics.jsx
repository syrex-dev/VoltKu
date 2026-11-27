import React, { useState } from 'react'
import { Calendar, TrendingUp, Clock, Lock } from 'lucide-react'
import { formatRp, formatNum } from '../utils/formatters'

export function EnergyMetrics({
  today,
  week,
  month,
  forecast,
  settings,
  forecastLocked = false,
  onOpenUpgrade,
}) {
  const [currentMonthYear] = useState(() =>
    new Date().toLocaleDateString('id-ID', {
      month: 'long',
      year: 'numeric',
    })
  )

  const tariffRp = settings?.tariff_sen_per_kwh
    ? parseInt(settings.tariff_sen_per_kwh, 10) / 100
    : settings?.tariff_sen
    ? parseInt(settings.tariff_sen, 10) / 100
    : 1444.7

  return (
    <div className="consumption-clean-stack">
      {/* Ringkasan Bulan Berjalan */}
      <section className="clean-sheet consumption-hero-sheet">
        <div className="consumption-top-row">
          <div>
            <div className="consumption-sub-kicker">Ringkasan Bulan Ini</div>
            <div className="consumption-month-label">{currentMonthYear}</div>
          </div>
          <span className="consumption-tariff-pill num-tabular">
            Tarif {formatRp(tariffRp)}/kWh
          </span>
        </div>

        <div className="consumption-split-pair">
          <div className="split-pair-col">
            <div className="split-pair-label">Total Terpakai</div>
            <div className="split-pair-val num-tabular">
              {month ? formatNum(month.kwh, 2) : '0,00'}
              <span className="split-pair-unit"> kWh</span>
            </div>
            <div className="split-pair-foot num-tabular">
              Hari ini {today ? `${formatNum(today.kwh, 2)} kWh` : '0 kWh'}
            </div>
          </div>

          <div className="split-pair-divider" />

          <div className="split-pair-col">
            <div className="split-pair-label">Estimasi Tagihan</div>
            <div className="split-pair-val accent-blue num-tabular">
              {month ? formatRp(month.cost_rp) : 'Rp 0'}
            </div>
            <div className="split-pair-foot num-tabular">
              Hari ini {today ? formatRp(today.cost_rp) : 'Rp 0'}
            </div>
          </div>
        </div>
      </section>

      {/* Rincian per Periode */}
      <section className="clean-sheet grouped-list-sheet">
        <div className="grouped-row">
          <div className="period-row-left">
            <div className="period-icon-chip">
              <Clock size={16} />
            </div>
            <div>
              <div className="grouped-row-title">Hari Ini</div>
              <div className="grouped-row-sub num-tabular">
                {today ? `${formatNum(today.kwh, 3)} kWh` : '0 kWh'}
                {today?.peak_w > 0 ? ` · Puncak ${formatNum(today.peak_w, 0)} W` : ''}
              </div>
            </div>
          </div>
          <span className="grouped-row-val num-tabular">{formatRp(today?.cost_rp)}</span>
        </div>

        <div className="grouped-row">
          <div className="period-row-left">
            <div className="period-icon-chip">
              <Calendar size={16} />
            </div>
            <div>
              <div className="grouped-row-title">Minggu Ini</div>
              <div className="grouped-row-sub num-tabular">
                {week ? `${formatNum(week.kwh, 3)} kWh` : '0 kWh'}
                {week ? ` · Rata-rata ${formatNum(week.avg_power_w, 0)} W` : ''}
              </div>
            </div>
          </div>
          <span className="grouped-row-val num-tabular">{formatRp(week?.cost_rp)}</span>
        </div>

        <div
          className={`grouped-row ${forecastLocked && onOpenUpgrade ? 'is-clickable' : ''}`}
          onClick={
            forecastLocked && onOpenUpgrade
              ? () =>
                  onOpenUpgrade(
                    'Proyeksi tagihan akhir bulan tersedia eksklusif untuk pelanggan VoltKu Pro.'
                  )
              : undefined
          }
        >
          <div className="period-row-left">
            <div className="period-icon-chip">
              {forecastLocked ? <Lock size={16} /> : <TrendingUp size={16} />}
            </div>
            <div>
              <div className="grouped-row-title">Perkiraan Akhir Bulan</div>
              <div className="grouped-row-sub num-tabular">
                {forecastLocked
                  ? 'Tersedia pada paket VoltKu Pro (ketuk untuk lihat paket)'
                  : forecast?.available
                    ? `${formatNum(forecast.projected_kwh, 1)} kWh (${formatNum(forecast.avg_daily_kwh, 1)} kWh/hari)`
                    : 'Butuh data minimal 1 hari penuh'}
              </div>
            </div>
          </div>
          <span className="grouped-row-val accent-blue num-tabular">
            {forecastLocked
              ? 'Pro'
              : forecast?.available
                ? formatRp(forecast.projected_cost_rp)
                : '-'}
          </span>
        </div>
      </section>
    </div>
  )
}
