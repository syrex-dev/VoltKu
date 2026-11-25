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
import { CalendarDays, Download, Lock } from 'lucide-react'
import { formatDateWIB, formatNum, formatRp } from '../utils/formatters'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

export function DailyChart({
  points,
  theme = 'dark',
  tariff = 1444.7,
  historyDays = 14,
  exportEnabled = true,
  onExportCsv,
  onOpenUpgrade,
}) {
  const isLight = theme === 'light'
  const labels = points.map((p) => formatDateWIB(p.ts))
  const dataKwh = points.map((p) => parseFloat(((p.p * 24.0) / 1000.0).toFixed(2)))

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Pemakaian Harian (kWh)',
        data: dataKwh,
        backgroundColor: isLight ? 'rgba(22, 119, 255, 0.85)' : 'rgba(59, 130, 246, 0.85)',
        hoverBackgroundColor: '#1677ff',
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  }

  const gridColor = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)'
  const tickColor = isLight ? '#64748b' : '#94a3b8'

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: {
        ticks: {
          color: tickColor,
          maxTicksLimit: 5,
          maxRotation: 0,
          autoSkip: true,
          font: { family: "'Plus Jakarta Sans', system-ui, sans-serif", size: 11 },
        },
        grid: { display: false },
        border: { display: false },
      },
      y: {
        ticks: {
          color: tickColor,
          font: { family: "'Plus Jakarta Sans', system-ui, sans-serif", size: 11 },
          callback: (val) => `${val} kWh`,
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
        titleFont: { size: 11, family: "'Plus Jakarta Sans', system-ui, sans-serif" },
        bodyFont: { size: 13.5, weight: '700', family: "'Plus Jakarta Sans', system-ui, sans-serif" },
        callbacks: {
          label: (context) => {
            const kwh = context.parsed.y
            const rp = Math.round(kwh * tariff)
            return `${formatNum(kwh, 2)} kWh (≈ ${formatRp(rp)})`
          },
        },
      },
    },
  }

  return (
    <section className="clean-sheet chart-panel-sheet">
      <div className="chart-panel-top">
        <div className="chart-panel-title">
          <CalendarDays size={17} className="brand-blue-text" />
          <span>Pemakaian Harian</span>
        </div>
        <div className="chart-head-actions">
          <span className="chart-period-label">{historyDays} Hari Terakhir</span>
          {(onExportCsv || !exportEnabled) && (
            <button
              type="button"
              className={`chart-export-btn ${!exportEnabled ? 'is-locked' : ''}`}
              onClick={() => {
                if (!exportEnabled) {
                  if (onOpenUpgrade) {
                    onOpenUpgrade('Ekspor laporan harian CSV tersedia pada paket VoltKu Pro.')
                  }
                  return
                }
                if (onExportCsv) onExportCsv()
              }}
              title={exportEnabled ? 'Unduh Laporan CSV' : 'Fitur VoltKu Pro'}
            >
              {exportEnabled ? <Download size={13} /> : <Lock size={12} />}
              <span>CSV</span>
            </button>
          )}
        </div>
      </div>

      {points.length === 0 ? (
        <div className="chart-empty-placeholder">
          Belum ada catatan pemakaian harian dalam {historyDays} hari terakhir.
        </div>
      ) : (
        <div className="chart-canvas-wrap">
          <Bar data={chartData} options={options} />
        </div>
      )}
    </section>
  )
}
