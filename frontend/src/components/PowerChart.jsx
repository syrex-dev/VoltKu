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
import { Activity } from 'lucide-react'
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

export function PowerChart({ points, range, onRangeChange, loading, theme = 'dark' }) {
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
        label: 'Daya Aktif',
        data: dataValues,
        borderColor: '#0284c7',
        borderWidth: 2,
        tension: 0.3,
        pointRadius: points.length > 80 ? 0 : 2.5,
        pointHoverRadius: 5,
        pointBackgroundColor: '#0284c7',
        fill: true,
        backgroundColor: (context) => {
          const ctx = context.chart.ctx
          const gradient = ctx.createLinearGradient(0, 0, 0, 260)
          if (isLight) {
            gradient.addColorStop(0, 'rgba(2, 132, 199, 0.22)')
            gradient.addColorStop(0.7, 'rgba(2, 132, 199, 0.03)')
            gradient.addColorStop(1, 'rgba(2, 132, 199, 0)')
          } else {
            gradient.addColorStop(0, 'rgba(14, 165, 233, 0.32)')
            gradient.addColorStop(0.7, 'rgba(14, 165, 233, 0.04)')
            gradient.addColorStop(1, 'rgba(14, 165, 233, 0)')
          }
          return gradient
        },
      },
    ],
  }

  const gridColor = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.05)'
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
        ticks: { color: tickColor, maxTicksLimit: 8, font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 } },
        grid: { color: gridColor, drawTicks: false },
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
        backgroundColor: isLight ? '#ffffff' : '#0c1220',
        titleColor: isLight ? '#64748b' : '#94a3b8',
        bodyColor: isLight ? '#0284c7' : '#38bdf8',
        borderColor: isLight ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.12)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
        displayColors: false,
        titleFont: { size: 11, family: "'Plus Jakarta Sans', sans-serif" },
        bodyFont: { size: 14, weight: '700', family: "'Plus Jakarta Sans', sans-serif" },
        callbacks: {
          label: (context) => `${context.parsed.y.toLocaleString('id-ID')} Watt`,
        },
      },
    },
  }

  return (
    <section className="section-block">
      <div className="card">
        <div className="section-header" style={{ marginBottom: 4 }}>
          <div className="section-title">
            <Activity size={15} className="text-primary" /> Profil Beban Daya
          </div>

          <div className="segmented-control">
            {[
              { id: '5h', label: '5 Jam' },
              { id: '24h', label: '24 Jam' },
              { id: '3d', label: '3 Hari' },
              { id: '30d', label: '30 Hari' },
            ].map((r) => (
              <button
                key={r.id}
                className={`segment-btn ${range === r.id ? 'active' : ''}`}
                onClick={() => onRangeChange(r.id)}
                disabled={loading}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="chart-container-modern">
          <Line data={chartData} options={options} />
        </div>
      </div>
    </section>
  )
}
