import React from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { Activity, Lock } from 'lucide-react'
import { formatTimeWIB, formatDateTimeWIB } from '../utils/formatters'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

export function PowerChart({
  points,
  range,
  onRangeChange,
  loading,
  theme = 'dark',
  historyDaysLimit = 366,
  onOpenUpgrade,
}) {
  const isLight = theme === 'light'
  const labels = points.map((p) => {
    if (range === '5h') return formatTimeWIB(p.ts)
    return formatDateTimeWIB(p.ts)
  })
  const dataValues = points.map((p) => p.p)

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Daya',
        data: dataValues,
        borderColor: '#1677ff',
        borderWidth: 2,
        tension: 0.3,
        pointRadius: points.length > 80 ? 0 : 2.5,
        pointHoverRadius: 5,
        pointBackgroundColor: '#1677ff',
        fill: true,
        backgroundColor: (context) => {
          const ctx = context.chart.ctx
          const gradient = ctx.createLinearGradient(0, 0, 0, 240)
          if (isLight) {
            gradient.addColorStop(0, 'rgba(22, 119, 255, 0.14)')
            gradient.addColorStop(1, 'rgba(22, 119, 255, 0)')
          } else {
            gradient.addColorStop(0, 'rgba(59, 130, 246, 0.22)')
            gradient.addColorStop(1, 'rgba(59, 130, 246, 0)')
          }
          return gradient
        },
      },
    ],
  }

  const gridColor = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)'
  const tickColor = isLight ? '#64748b' : '#94a3b8'

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    scales: {
      x: {
        ticks: {
          color: tickColor,
          maxTicksLimit: 5,
          maxRotation: 0,
          autoSkip: true,
          font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
        },
        grid: { display: false },
        border: { display: false },
      },
      y: {
        ticks: {
          color: tickColor,
          font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
          callback: (val) => `${val} W`,
        },
        grid: { color: gridColor, drawTicks: false },
        border: { display: false },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: isLight ? '#ffffff' : '#161b22',
        titleColor: isLight ? '#525b66' : '#a1aab8',
        bodyColor: '#1677ff',
        borderColor: isLight ? '#e6e9ef' : '#262c36',
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        displayColors: false,
        titleFont: { size: 11, family: "'Plus Jakarta Sans', sans-serif" },
        bodyFont: { size: 13.5, weight: '700', family: "'Plus Jakarta Sans', sans-serif" },
        callbacks: {
          label: (context) => `${context.parsed.y.toLocaleString('id-ID')} W`,
        },
      },
    },
  }

  return (
    <section className="clean-sheet chart-panel-sheet">
      <div className="chart-panel-top">
        <div className="chart-panel-title">
          <Activity size={17} className="brand-blue-text" />
          <span>Grafik Daya</span>
        </div>

        <div className="clean-range-tabs" role="tablist" aria-label="Rentang Grafik">
          {[
            { id: '5h', label: '5 Jam', days: 1 },
            { id: '24h', label: '24 Jam', days: 1 },
            { id: '3d', label: '3 Hari', days: 3 },
            { id: '30d', label: '30 Hari', days: 30 },
          ].map((r) => {
            const locked = r.days > historyDaysLimit
            return (
              <button
                key={r.id}
                type="button"
                className={`clean-range-btn ${range === r.id ? 'active' : ''} ${locked ? 'is-locked' : ''}`}
                onClick={() => {
                  if (locked && onOpenUpgrade) {
                    onOpenUpgrade(
                      `Grafik rentang ${r.label} tersedia pada paket VoltKu Pro (paket saat ini maks. ${historyDaysLimit} hari).`
                    )
                    return
                  }
                  onRangeChange(r.id)
                }}
                disabled={loading}
              >
                {locked && <Lock size={11} />}
                <span>{r.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {points.length === 0 ? (
        <div className="chart-empty-placeholder">
          Belum ada data grafik untuk rentang waktu ini.
        </div>
      ) : (
        <div className="chart-canvas-wrap">
          <Line data={chartData} options={options} />
        </div>
      )}
    </section>
  )
}
