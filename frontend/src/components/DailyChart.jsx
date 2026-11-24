import React from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'
import { formatDateWIB } from '../utils/formatters'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

export function DailyChart({ points }) {
  const labels = points.map((p) => formatDateWIB(p.ts))
  // Estimasi kWh harian = (rata-rata watt * 24) / 1000
  const dataKwh = points.map((p) => parseFloat(((p.p * 24.0) / 1000.0).toFixed(2)))

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Konsumsi Harian (kWh)',
        data: dataKwh,
        backgroundColor: 'rgba(56, 189, 248, 0.8)',
        borderRadius: 4,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: {
        ticks: { color: '#94a3b8' },
        grid: { display: false },
      },
      y: {
        ticks: { color: '#94a3b8' },
        grid: { color: 'rgba(51, 65, 85, 0.4)' },
      },
    },
    plugins: {
      legend: { display: false },
    },
  }

  return (
    <section className="section-block">
      <div className="card chart-card">
        <div className="chart-header">
          <h3 className="chart-title">Histori Konsumsi Harian (kWh)</h3>
        </div>
        <div className="chart-container">
          <Bar data={chartData} options={options} />
        </div>
      </div>
    </section>
  )
}
