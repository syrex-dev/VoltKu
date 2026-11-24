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
import { BarChart3 } from 'lucide-react'
import { formatDateWIB } from '../utils/formatters'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

export function DailyChart({ points, theme = 'dark' }) {
  const isLight = theme === 'light'
  const labels = points.map((p) => formatDateWIB(p.ts))
  // Estimasi kWh harian = (rata-rata watt * 24) / 1000
  const dataKwh = points.map((p) => parseFloat(((p.p * 24.0) / 1000.0).toFixed(2)))

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Konsumsi Harian (kWh)',
        data: dataKwh,
        backgroundColor: isLight ? 'rgba(2, 132, 199, 0.7)' : 'rgba(56, 189, 248, 0.75)',
        hoverBackgroundColor: isLight ? '#0284c7' : '#38bdf8',
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  }

  const gridColor = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.05)'
  const tickColor = isLight ? '#64748b' : '#94a3b8'

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: {
        ticks: { color: tickColor, font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 } },
        grid: { display: false },
        border: { display: false },
      },
      y: {
        ticks: {
          color: tickColor,
          font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
          callback: (val) => `${val} kWh`,
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
          label: (context) => `${context.parsed.y.toLocaleString('id-ID')} kWh`,
        },
      },
    },
  }

  return (
    <section className="section-block">
      <div className="card">
        <div className="section-header" style={{ marginBottom: 4 }}>
          <div className="section-title">
            <BarChart3 size={15} className="text-primary" /> Histori Konsumsi 14 Hari Terakhir
          </div>
        </div>

        <div className="chart-container-modern">
          <Bar data={chartData} options={options} />
        </div>
      </div>
    </section>
  )
}
