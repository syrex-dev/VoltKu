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

export function PowerChart({ points, range, onRangeChange, loading }) {
  const labels = points.map((p) => {
    if (range === '5h') return formatTimeWIB(p.ts)
    return formatDateTimeWIB(p.ts)
  })
  const dataValues = points.map((p) => p.p)

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Daya Aktif (Watt)',
        data: dataValues,
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.12)',
        borderWidth: 2,
        tension: 0.2,
        pointRadius: points.length > 100 ? 0 : 2,
        fill: true,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: {
        ticks: { color: '#94a3b8', maxTicksLimit: 8 },
        grid: { color: 'rgba(51, 65, 85, 0.4)' },
      },
      y: {
        ticks: { color: '#94a3b8' },
        grid: { color: 'rgba(51, 65, 85, 0.4)' },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index',
        intersect: false,
      },
    },
  }

  return (
    <section className="section-block">
      <div className="card chart-card">
        <div className="chart-header">
          <h3 className="chart-title">Grafik Profil Daya (Watt)</h3>
          <div className="btn-group">
            {[
              { id: '5h', label: '5 Jam' },
              { id: '24h', label: '24 Jam' },
              { id: '3d', label: '3 Hari' },
              { id: '30d', label: '30 Hari' },
            ].map((r) => (
              <button
                key={r.id}
                className={`btn btn-sm btn-toggle ${range === r.id ? 'active' : ''}`}
                onClick={() => onRangeChange(r.id)}
                disabled={loading}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <div className="chart-container">
          <Line data={chartData} options={options} />
        </div>
      </div>
    </section>
  )
}
